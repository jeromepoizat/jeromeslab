"""Acquisition is bounded, resumable, source-linked, and never invokes an LLM."""

import hashlib
import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, ClassVar, cast
from urllib.error import HTTPError
from urllib.request import Request

import httpx
import pytest
from test_jobs import MemoryCredentialStore
from test_relevance_score_filter import _pool
from test_scope_clarification import ScopeGateway

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database import materials as material_database
from jeromes_laboratory.database.jobs import JobRepository
from jeromes_laboratory.database.materials import MaterialError, MaterialRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.sources import materials
from jeromes_laboratory.sources.fallback import FullTextResolver
from jeromes_laboratory.sources.materials import MaterialResponse, parse_material
from jeromes_laboratory.storage.workspace import WorkspaceService

XML = b'<article><front><article-meta><permissions><license>CC BY 4.0</license></permissions></article-meta></front><body><p>Study text</p><supplementary-material/></body></article>'


@pytest.fixture(autouse=True)
def offline_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(FullTextResolver, "resolve", lambda *_: MaterialResponse("unavailable", "", error="Fixture unavailable"))


def _zip(names: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, b"sequence,measurement\nTEST,1\n")
    return buffer.getvalue()


class FakeMaterials:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str]] = []
        self.fail_full_text = False
        self.pause: Any = None

    def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
        self.requests.append((kind, source, source_id))
        if self.pause is not None:
            self.pause()
            self.pause = None
        if kind == "full_text" and self.fail_full_text:
            self.fail_full_text = False
            return MaterialResponse("failed", "https://example.test/fullTextXML", error="Fixture network failure")
        raw = {
            "metadata": json.dumps({"version": "6.9", "hitCount": 1, "result": {"id": source_id, "source": source, "pmcid": "PMC123", "license": "CC BY"}}).encode(),
            "full_text": XML, "supplements": _zip(["sequences.csv"]),
            "data_links": json.dumps({"hitCount": 1, "dataLinkList": {"Category": [{"Section": [{"Linklist": {"Link": [{
                "Source": {"Identifier": {"ID": source_id}}, "Target": {"Title": "Linked protein", "Identifier": {"ID": "P12345"}},
            }]}}]}]}}).encode(),
        }[kind]
        return MaterialResponse("saved", f"https://example.test/{kind}", 200, raw,
                                "application/octet-stream", parse_material(kind, raw))


def _ready(tmp_path: Path, count: int = 1) -> tuple[MaterialRepository, str, str, WorkspaceService]:
    scoring, project_id, run_id, service = _pool(tmp_path, count)
    state = scoring.filter_state(run_id, project_id)
    scoring.validate_filter(run_id, project_id, 0, True, cast(str, state["confirmation_sha256"]))
    return MaterialRepository(scoring.database_path), project_id, run_id, service


def _start(repository: MaterialRepository, project_id: str, filter_id: str) -> dict[str, Any]:
    state = repository.state(project_id, filter_id)
    return repository.start(project_id, filter_id, state["selection_sha256"])


def test_collection_freezes_selection_and_preserves_original_bytes(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    state = _start(repository, project_id, filter_id)
    assert state["run"]["total"] == 1
    client = FakeMaterials()
    worker = JobWorker(service, MemoryCredentialStore(), ScopeGateway("must not be called"), material_client=client)
    assert worker.run_once()
    state = repository.state(project_id, filter_id)
    assert state["run"]["status"] == "completed"
    assert state["run"]["counts"] == {**dict.fromkeys([f"{kind}:saved" for kind in materials.LIMITS], 1), "full_text_fallback:not_applicable": 1}
    assert state["run"]["records"][0]["resources"][1]["details"]["license_statements"] == ["CC BY 4.0"]
    with sqlite3.connect(repository.database_path) as connection:
        rows = connection.execute("SELECT raw_path, raw_sha256, raw_byte_size FROM source_material_attempts WHERE raw_path IS NOT NULL").fetchall()
        assert len(rows) == 4
        for path, digest, size in rows:
            content = (repository.database_path.parent / "artifacts" / path).read_bytes()
            assert hashlib.sha256(content).hexdigest() == digest
            assert len(content) == size
        assert connection.execute("SELECT COUNT(*) FROM llm_calls WHERE job_id = ?", (state["run"]["jobs"][0]["id"],)).fetchone()[0] == 0
        retained = json.loads(connection.execute("SELECT content_json FROM relevance_score_filters WHERE run_id = ?", (filter_id,)).fetchone()[0])["included_records"]
        material_ids = connection.execute("SELECT source, source_record_id FROM source_material_records").fetchall()
        assert material_ids == [(item["source"], item["source_record_id"]) for item in retained]
    assert _start(repository, project_id, filter_id)["run"]["id"] == state["run"]["id"]
    assert not worker.run_once()


def test_pause_resume_and_retry_skip_successful_resources(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]
    client = FakeMaterials()
    client.pause = lambda: repository.control(project_id, run_id, "pause")
    worker = JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=client)
    assert worker.run_once()
    state = repository.state(project_id, filter_id)
    assert state["run"]["status"] == "paused"
    assert client.requests[0][0] == "metadata"
    assert len(client.requests) == 1
    repository.control(project_id, run_id, "resume")
    client.fail_full_text = True
    assert worker.run_once()
    assert repository.state(project_id, filter_id)["run"]["counts"]["full_text:failed"] == 1
    assert repository.state(project_id, filter_id)["run"]["processed"] == 1
    repository.control(project_id, run_id, "resume")
    retry = repository.state(project_id, filter_id)["run"]
    assert retry["processed"] == 0
    assert retry["retrying"]
    assert retry["counts"]["full_text:failed"] == 1  # Earlier failure remains visible.
    during_retry: list[int] = []
    client.pause = lambda: during_retry.append(repository.state(project_id, filter_id)["run"]["processed"])
    assert worker.run_once()
    assert during_retry == [0]
    assert repository.state(project_id, filter_id)["run"]["processed"] == 1
    assert repository.state(project_id, filter_id)["run"]["counts"]["full_text:saved"] == 1
    assert sum(kind == "metadata" for kind, _, _ in client.requests) == 1
    assert sum(kind == "data_links" for kind, _, _ in client.requests) == 1
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_material_attempts WHERE status = 'failed'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM source_material_attempts WHERE status = 'blocked'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM source_material_attempts WHERE status = 'saved'").fetchone()[0] == 4


def test_restart_and_pending_cancellation_leave_resumable_run(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    initial = _start(repository, project_id, filter_id)
    jobs = JobRepository(repository.database_path)
    jobs.cancel(initial["run"]["jobs"][0]["id"])
    assert repository.state(project_id, filter_id)["run"]["status"] == "paused"
    repository.control(project_id, initial["run"]["id"], "resume")
    job = jobs.claim_next()
    assert job is not None
    jobs.fail_interrupted_jobs()
    assert repository.state(project_id, filter_id)["run"]["status"] == "paused"
    repository.control(project_id, initial["run"]["id"], "resume")
    assert JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=FakeMaterials()).run_once()
    assert jobs.get_job(job.id).status == "failed"


def test_retry_progress_counts_records_not_failed_resources(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path, 7)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]

    class TwoFailures(FakeMaterials):
        remaining_failures = 2

        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            if kind == "full_text" and self.remaining_failures:
                self.remaining_failures -= 1
                return MaterialResponse("failed", "https://example.test/fullTextXML", error="Fixture failure")
            return super().fetch(kind, source, source_id)

    worker = JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=TwoFailures())
    assert worker.run_once()
    initial = repository.state(project_id, filter_id)["run"]
    assert initial["processed"] == 7
    assert initial["counts"]["full_text:failed"] == 2
    assert initial["counts"]["supplements:blocked"] == 2
    repository.control(project_id, run_id, "resume")
    assert repository.state(project_id, filter_id)["run"]["processed"] == 5
    assert repository.state(project_id, filter_id)["run"]["remaining_resources"] == 4

    class ObserveRetry(FakeMaterials):
        observed: list[int]
        remaining: list[int]

        def __init__(self) -> None:
            super().__init__()
            self.observed = []
            self.remaining = []

        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            self.observed.append(repository.state(project_id, filter_id)["run"]["processed"])
            self.remaining.append(repository.state(project_id, filter_id)["run"]["remaining_resources"])
            return super().fetch(kind, source, source_id)

    client = ObserveRetry()
    assert JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=client).run_once()
    assert client.observed == [5, 5, 5, 6]  # Both texts are tried before either supplement.
    assert client.remaining == [4, 3, 2, 1]
    assert repository.state(project_id, filter_id)["run"]["processed"] == 7
    assert repository.state(project_id, filter_id)["run"]["remaining_resources"] == 0


def test_unavailable_text_is_not_an_exclusion(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    _start(repository, project_id, filter_id)

    class Unavailable(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            if kind == "full_text":
                self.requests.append((kind, source, source_id))
                return MaterialResponse("unavailable", "https://example.test/fullTextXML", 404)
            return super().fetch(kind, source, source_id)

    client = Unavailable()
    assert JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=client).run_once()
    state = repository.state(project_id, filter_id)
    assert state["run"]["total"] == 1
    assert state["run"]["counts"]["full_text:unavailable"] == 1
    assert state["run"]["counts"]["supplements:unavailable"] == 1
    assert not any(kind == "supplements" for kind, _, _ in client.requests)
    with sqlite3.connect(repository.database_path) as connection:
        assert json.loads(connection.execute("SELECT content_json FROM relevance_score_filters WHERE run_id = ?",
                                             (filter_id,)).fetchone()[0])["included_count"] == 1


def test_task_manifest_corruption_pauses_without_network(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    _start(repository, project_id, filter_id)
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("DELETE FROM source_material_job_tasks WHERE ordinal = 0")
    client = FakeMaterials()
    assert JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=client).run_once()
    assert repository.state(project_id, filter_id)["run"]["status"] == "paused"
    assert not client.requests


def test_known_no_access_is_not_requested_or_retried(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]

    class Closed(FakeMaterials):
        fail_links = True

        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            if kind == "metadata":
                self.requests.append((kind, source, source_id))
                raw = json.dumps({"result": {"id": source_id, "source": source, "pmcid": "PMC123",
                                             "isOpenAccess": "N", "inEPMC": "Y"}}).encode()
                return MaterialResponse("saved", "https://example.test/metadata", 200, raw,
                                        "application/json", parse_material(kind, raw))
            if kind == "data_links" and self.fail_links:
                self.fail_links = False
                return MaterialResponse("failed", "https://example.test/links", error="Fixture timeout")
            return super().fetch(kind, source, source_id)

    client = Closed()
    worker = JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=client)
    assert worker.run_once()
    state = repository.state(project_id, filter_id)["run"]
    assert state["counts"]["full_text:unavailable"] == 1
    assert state["counts"]["supplements:unavailable"] == 1
    repository.control(project_id, run_id, "resume")
    assert worker.run_once()
    assert not any(kind in {"full_text", "supplements"} for kind, _, _ in client.requests)
    with pytest.raises(MaterialError, match="No unfinished"):
        repository.control(project_id, run_id, "resume")
    with sqlite3.connect(repository.database_path) as connection:
        decisions = [json.loads(row[0]) for row in connection.execute(
            "SELECT details_json FROM source_material_attempts WHERE status = 'unavailable' "
            "AND details_json LIKE '%access_rule_version%'",
        )]
    assert decisions[0]["metadata_attempt_id"]
    assert decisions[0]["access_scope"] == "Europe PMC XML endpoint only"


def test_access_rules_do_not_assume_paywalls_or_classify_unknown_errors() -> None:
    assert materials.xml_access_limitation({"isOpenAccess": "N"}) is not None
    assert materials.xml_access_limitation({"inEPMC": "N", "isOpenAccess": "Y"}) is not None
    assert materials.xml_access_limitation({"inEPMC": "Y", "isOpenAccess": "Y"}) is None
    assert materials.xml_access_limitation({}) is None


def test_existing_failed_access_appends_local_decision_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]

    class Legacy(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            result = super().fetch(kind, source, source_id)
            if kind == "metadata":
                record = {**result.details["record"], "isOpenAccess": "N", "inEPMC": "Y"}
                raw = json.dumps({"result": record}).encode()
                return MaterialResponse("saved", result.request_url, 200, raw,
                                        "application/json", parse_material(kind, raw))
            return result

    client = Legacy()
    client.fail_full_text = True
    worker = JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=client)
    # Simulate a historical worker that attempted XML despite known access flags.
    with monkeypatch.context() as historical:
        historical.setattr(material_database, "xml_access_limitation", lambda _: None)
        assert worker.run_once()
    with sqlite3.connect(repository.database_path) as connection:
        previous = connection.execute("SELECT id, status, details_json, error FROM source_material_attempts ORDER BY rowid").fetchall()
    request_count = len(client.requests)
    repository.control(project_id, run_id, "resume")
    assert worker.run_once()
    assert len(client.requests) == request_count
    assert repository.state(project_id, filter_id)["run"]["counts"]["full_text:unavailable"] == 1
    with sqlite3.connect(repository.database_path) as connection:
        current = connection.execute("SELECT id, status, details_json, error FROM source_material_attempts ORDER BY rowid").fetchall()
    assert current[:len(previous)] == previous
    assert len(current) == len(previous) + 2


def test_guards_digest_scope_downstream_and_pagination(tmp_path: Path) -> None:
    repository, project_id, filter_id, _ = _ready(tmp_path, 7)
    with pytest.raises(MaterialError, match="Validate"):
        repository.state("wrong-project", filter_id)
    with pytest.raises(MaterialError, match="digest"):
        repository.start(project_id, filter_id, "a" * 64)
    state = _start(repository, project_id, filter_id)
    assert state["run"]["total"] == 7
    assert repository.state(project_id, filter_id, offset=5)["run"]["records"] == state["run"]["records"][5:]
    with pytest.raises(MaterialError, match="belong"):
        repository.control("wrong-project", state["run"]["id"], "pause")
    repository.control(project_id, state["run"]["id"], "pause")
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("UPDATE jobs SET kind = 'future_extraction', created_at = '2099' WHERE kind = 'source_material_collection'")
    with pytest.raises(MaterialError, match="fork"):
        repository.control(project_id, state["run"]["id"], "resume")


@pytest.mark.asyncio
async def test_material_api_token_validation_and_project_scope(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    app = create_app(static_directory=None, workspace_service=service, credential_store=MemoryCredentialStore(), start_job_worker=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        path = f"/api/projects/{project_id}/source-material"
        state = (await client.get(path, params={"filter_run_id": filter_id})).json()
        payload = {"filter_run_id": filter_id, "expected_selection_sha256": state["selection_sha256"]}
        assert (await client.post(path, json=payload)).status_code == 403
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        result = await client.post(path, json=payload, headers=headers)
        assert result.status_code == 201, result.text
        run_id = result.json()["run"]["id"]
        assert (await client.post(f"{path}/{run_id}/pause", headers=headers)).status_code == 200
        assert (await client.post(f"{path}/{run_id}/resume", headers=headers)).status_code == 200
        assert (await client.get(path, params={"filter_run_id": filter_id, "offset": -1})).status_code == 422
        assert (await client.get("/api/projects/wrong/source-material", params={"filter_run_id": filter_id})).status_code == 409
    assert repository.state(project_id, filter_id)["run"]["status"] == "pending"


def test_formats_limits_and_link_inventory() -> None:
    assert parse_material("full_text", XML)["has_supplements"]
    with pytest.raises(ValueError, match="entity"):
        parse_material("full_text", b'<!DOCTYPE article [<!ENTITY x "bad">]><article>&x;</article>')
    with pytest.raises(ValueError, match="article XML"):
        parse_material("full_text", b"<html><body>Error</body></html>")
    with pytest.raises(ValueError, match="unsafe"):
        parse_material("supplements", _zip(["../escape.txt"]))
    with pytest.raises(OverflowError):
        parse_material("supplements", _zip([f"{index}.txt" for index in range(1001)]))
    assert parse_material("data_links", b'{"hitCount":0}')["links"] == []
    with pytest.raises(ValueError, match="usable"):
        parse_material("data_links", b'{"hitCount":1}')


class HTTPResponse(io.BytesIO):
    status = 200
    headers: ClassVar[dict[str, str]] = {"Content-Type": "application/xml"}


def test_http_requests_are_bounded_retryable_and_validate_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []
    responses: list[bytes | Exception] = [HTTPError("fixture", 503, "unavailable", cast(Any, {}), None), XML]

    class Opener:
        def open(self, request: Request, timeout: int) -> HTTPResponse:
            assert timeout == 30
            requests.append(request.full_url)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return HTTPResponse(response)

    monkeypatch.setattr(materials, "build_opener", lambda *_: Opener())
    monkeypatch.setattr(time, "sleep", lambda _: None)
    client = materials.EuropePMCMaterialClient()
    result = client.fetch("full_text", "PMC", "PMC123")
    assert result.status == "saved"
    assert requests == [f"{materials.BASE_URL}/PMC123/fullTextXML"] * 2
    assert len(result.details["http_attempts"]) == 2
    assert result.details["http_attempts"][0]["http_status"] == 503
    responses.append(b"x" * 21)
    monkeypatch.setitem(materials.LIMITS, "full_text", 20)
    assert client.fetch("full_text", "PMC", "PMC123").status == "skipped_limit"
    responses.append(b'{"resultList":{"result":[{"id":"wrong","source":"MED"}]}}')
    assert client.fetch("metadata", "MED", "1").status == "needs_review"
    responses.append(HTTPError("fixture", 404, "missing", cast(Any, {}), None))
    assert client.fetch("full_text", "PMC", "PMC123").status == "unavailable"
    assert client.fetch("full_text", "PMC", "../private").status == "unsupported"
    responses.append(b'<article><front><article-meta><article-id pub-id-type="pmc">999</article-id></article-meta></front></article>')
    monkeypatch.setitem(materials.LIMITS, "full_text", 20000000)
    assert client.fetch("full_text", "PMC", "PMC123").status == "needs_review"
