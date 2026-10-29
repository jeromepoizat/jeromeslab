from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ScopeGateway
from test_source_materials import FakeMaterials, _ready, _start

from jeromes_laboratory.database.jobs import JobRepository
from jeromes_laboratory.database.materials import MaterialError
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.sources.fallback import (
    FullTextResolver,
    interpret_bioc,
    preprint_server,
    safe_url,
)
from jeromes_laboratory.sources.materials import MaterialResponse

BIOC = b'<collection><document><id>PMC123</id><infon key="license">CC BY</infon><passage><infon key="section_type">RESULTS</infon><text>Study body.</text></passage></document></collection>'
DOI = "10.1101/2025.10.01.679778"
JATS_URL = "https://www.biorxiv.org/content/early/2025/10/03/2025.10.01.679778.source.xml"
JATS = f'<article><front><article-meta><article-id pub-id-type="doi">{DOI}</article-id></article-meta></front><body><p>Body text.</p></body></article>'.encode()
NO_RESULT = b'[Error] : No result can be found. <BR><HR>API documentation'


def test_article_supplement_declaration_precedes_summary_flag(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    _start(repository, project_id, filter_id)
    class SummaryFlag(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            response = super().fetch(kind, source, source_id)
            if kind == "metadata":
                record = {**response.details["record"], "hasSuppl": "N"}
                return MaterialResponse("saved", response.request_url, 200, json.dumps({"result": record}).encode(),
                                        "application/json", {"record": record})
            return response
    assert JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=SummaryFlag()).run_once()
    assert repository.state(project_id, filter_id)["run"]["counts"]["supplements:saved"] == 1


@pytest.mark.parametrize(('has_suppl', 'supplement_status'), [('N', 'not_applicable'), ('Y', 'unsupported'), (None, 'unsupported')])
def test_fallback_resolves_primary_failure_without_losing_history(
    tmp_path: Path, has_suppl: str | None, supplement_status: str,
) -> None:
    repository, project_id, filter_id, _ = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]
    class PrimaryFailure(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            if kind == "full_text":
                return MaterialResponse("failed", "fixture-primary", 500, error="Fixture primary service failure")
            response = super().fetch(kind, source, source_id)
            if kind == "metadata":
                record = {**response.details["record"], "hasSuppl": has_suppl}
                return MaterialResponse("saved", response.request_url, 200, json.dumps({"result": record}).encode(),
                                        "application/json", {"record": record})
            return response
    job = JobRepository(repository.database_path).claim_next()
    assert job is not None
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(200, content=BIOC)))
    repository.run_job(job.id, PrimaryFailure(), resolver=resolver)
    state = repository.state(project_id, filter_id)["run"]
    assert state["counts"]["full_text:recovered"] == 1
    assert state["counts"][f"supplements:{supplement_status}"] == 1
    assert state["full_text_saved"] == 1
    with sqlite3.connect(repository.database_path) as connection:
        primary = connection.execute("SELECT a.id,a.status FROM source_material_attempts a JOIN source_material_resources r "
            "ON r.id=a.resource_id WHERE r.kind='full_text'").fetchone()
        fallback = json.loads(connection.execute("SELECT a.details_json FROM source_material_attempts a JOIN source_material_resources r "
            "ON r.id=a.resource_id WHERE r.kind='full_text_fallback'").fetchone()[0])
        assert primary is not None and primary[1] == 'failed'
        assert fallback['prior_primary_attempt_id'] == primary[0]
        # Simulate an older completed run with unresolved mutable cursors.
        before = connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()
        connection.execute("UPDATE source_material_resources SET status='failed' WHERE kind='full_text'")
        connection.execute("UPDATE source_material_resources SET status='blocked' WHERE kind='supplements'")
    recovery = repository.reconcile_saved(project_id, run_id)
    class NoNetwork(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            raise AssertionError("Coverage reconciliation must not request a failed primary again")
    repository.run_job(recovery, NoNetwork())
    state = repository.state(project_id, filter_id)["run"]
    assert state["counts"]["full_text:recovered"] == 1
    assert state["counts"][f"supplements:{supplement_status}"] == 1
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()[:len(before)] == before
    with pytest.raises(MaterialError, match="No unfinished"):
        repository.control(project_id, run_id, "resume")


def test_preprint_route_uses_publisher_not_a_hardcoded_doi_prefix() -> None:
    assert preprint_server({"doi": "10.64898/2026.04.06.716693", "bookOrReportDetails": {"publisher": "bioRxiv"}}) == "biorxiv"
    assert preprint_server({"doi": DOI, "bookOrReportDetails": {"publisher": "medRxiv"}}) == "medrxiv"
    assert preprint_server({"doi": DOI, "bookOrReportDetails": {"publisher": "Other publisher"}}) is None
    assert preprint_server({"doi": "10.64898/../../private", "bookOrReportDetails": {"publisher": "bioRxiv"}}) is None


def test_newly_supported_preprint_becomes_pending_without_network(tmp_path: Path) -> None:
    repository, project_id, filter_id, _ = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]
    class Metadata(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            if kind == "metadata":
                return MaterialResponse("saved", "fixture", details={"record": {"doi": "10.64898/2026.04.06.716693",
                    "bookOrReportDetails": {"publisher": "bioRxiv"}, "firstPublicationDate": "2026-04-08"}})
            if kind == "full_text":
                return MaterialResponse("unavailable", "fixture")
            return super().fetch(kind, source, source_id)
    class OldPrefixFilter(FullTextResolver):
        def resolve(self, metadata: dict[str, Any], stopped: Any = None) -> MaterialResponse:
            return MaterialResponse("unavailable", "", details={"routes": [], "resolver_policy": {"version": "legacy"}})
    job = JobRepository(repository.database_path).claim_next()
    assert job is not None
    repository.run_job(job.id, Metadata(), resolver=OldPrefixFilter())
    recovery = repository.reconcile_saved(project_id, run_id)
    class NoNetwork(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            raise AssertionError("Local routing repair must not download")
    repository.run_job(recovery, NoNetwork())
    assert repository.state(project_id, filter_id)["run"]["counts"]["full_text_fallback:pending"] == 1
    repository.control(project_id, run_id, "resume")
    with sqlite3.connect(repository.database_path) as connection:
        tasks = connection.execute("SELECT r.kind FROM source_material_job_tasks t JOIN source_material_resources r "
            "ON r.id=t.resource_id WHERE t.job_id=(SELECT id FROM jobs ORDER BY rowid DESC LIMIT 1)").fetchall()
        assert tasks == [("full_text_fallback",)]


def test_bioc_identity_accepts_numeric_and_explicit_ids_without_accepting_conflicts() -> None:
    for raw in [BIOC, BIOC.replace(b'<id>PMC123</id>', b'<id>123</id>'),
                BIOC.replace(b'<id>PMC123</id>', b'<id>unknown</id><passage><infon key="article-id_pmcid">PMC123</infon></passage>')]:
        assert interpret_bioc(MaterialResponse("saved", "fixture", raw=raw), "PMC123").status == "saved"
    for raw in [BIOC.replace(b'PMC123', b'PMC999'), BIOC.replace(b'<id>PMC123</id>', b'<id>unknown</id>'),
                BIOC.replace(b'<id>PMC123</id>', b'<id>123</id><infon key="article-id_pmcid">PMC999</infon>')]:
        assert interpret_bioc(MaterialResponse("saved", "fixture", raw=raw), "PMC123").status == "needs_review"


def test_offline_reconciliation_recovers_bytes_and_excludes_terminal_outcomes(tmp_path: Path) -> None:
    repository, project_id, filter_id, _ = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]
    class Missing(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            return MaterialResponse("unavailable", "") if kind == "full_text" else super().fetch(kind, source, source_id)
    class Legacy(FullTextResolver):
        def resolve(self, metadata: dict[str, Any], stopped: Any = None) -> MaterialResponse:
            url = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC123/unicode"
            return MaterialResponse("failed", url, raw=BIOC.replace(b'PMC123', b'123'),
                                    details={"routes": [{"url": url, "http_status": 200}]})
    job = JobRepository(repository.database_path).claim_next()
    assert job is not None
    repository.run_job(job.id, Missing(), resolver=Legacy())
    with sqlite3.connect(repository.database_path) as connection:
        before = connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()
    recovery = repository.reconcile_saved(project_id, run_id)
    assert JobRepository(repository.database_path).claim_next() is None
    class NoRequests(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            raise AssertionError("Offline recovery must not download")
    repository.run_job(recovery, NoRequests())
    assert repository.state(project_id, filter_id)["run"]["full_text_saved"] == 1
    with sqlite3.connect(repository.database_path) as connection:
        after = connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()
        assert after[:len(before)] == before
        assert len(after) == len(before) + 1
    with pytest.raises(MaterialError, match="No saved"):
        repository.reconcile_saved(project_id, run_id)
    with pytest.raises(MaterialError, match="No unfinished"):
        repository.control(project_id, run_id, "resume")


def test_server_errors_remain_retryable_and_529_can_recover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _: None)
    responses = [httpx.Response(529), httpx.Response(200, content=BIOC)]
    resolver = FullTextResolver(httpx.MockTransport(lambda _: responses.pop(0)))
    assert resolver.resolve({"pmcid": "PMC123"}).status == "saved"
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(503)))
    assert resolver.resolve({"pmcid": "PMC123"}).status == "failed"


def test_explicit_bioc_absence_is_not_a_retryable_failure() -> None:
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(200, content=NO_RESULT)))
    result = resolver.resolve({"pmcid": "PMC123"})
    assert result.status == "unavailable" and result.raw == NO_RESULT
    assert result.details["routes"][0]["access_rule_version"] == "pmc-bioc-no-result-v1"
    for raw in [b'<html>Server error</html>', b'Unexpected failure: No result can be found.', b'[Error] : Temporarily unavailable.']:
        resolver = FullTextResolver(httpx.MockTransport(lambda _, data=raw: httpx.Response(200, content=data)))
        assert resolver.resolve({"pmcid": "PMC123"}).status == "needs_review"


def test_global_full_text_priority_defers_supplements(tmp_path: Path) -> None:
    repository, project_id, filter_id, _ = _ready(tmp_path, 7)
    state = _start(repository, project_id, filter_id)
    assert state["run"]["phase"] == "Collecting metadata and full text"
    with sqlite3.connect(repository.database_path) as connection:
        kinds = [row[0] for row in connection.execute(
            "SELECT r.kind FROM source_material_job_tasks t JOIN source_material_resources r ON r.id=t.resource_id "
            "WHERE t.job_id=? ORDER BY t.ordinal", (state["run"]["jobs"][0]["id"],))]
    assert kinds[:21] == ["metadata", "full_text", "full_text_fallback"] * 7
    assert kinds[21:28] == ["data_links"] * 7
    assert kinds[28:] == ["supplements"] * 7


def test_saved_absence_is_reclassified_without_network_or_history_changes(tmp_path: Path) -> None:
    repository, project_id, filter_id, _ = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]
    class Missing(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> MaterialResponse:
            return MaterialResponse("unavailable", "") if kind == "full_text" else super().fetch(kind, source, source_id)
    class OldResolver(FullTextResolver):
        def resolve(self, metadata: dict[str, Any], stopped: Any = None) -> MaterialResponse:
            url = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC123/unicode"
            return MaterialResponse("failed", url, raw=NO_RESULT, content_type="text/html",
                                    details={"routes": [{"url": url, "http_status": 200}]})
    job = JobRepository(repository.database_path).claim_next()
    assert job is not None
    repository.run_job(job.id, Missing(), resolver=OldResolver())
    with sqlite3.connect(repository.database_path) as connection:
        before = connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()
    repository.control(project_id, run_id, "resume")
    job = JobRepository(repository.database_path).claim_next()
    assert job is not None
    class NoNetwork(FullTextResolver):
        def resolve(self, metadata: dict[str, Any], stopped: Any = None) -> MaterialResponse:
            raise AssertionError("The saved absence must not be requested again")
    repository.run_job(job.id, Missing(), resolver=NoNetwork())
    assert repository.state(project_id, filter_id)["run"]["counts"]["full_text_fallback:unavailable"] == 1
    with sqlite3.connect(repository.database_path) as connection:
        after = connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()
        assert after[:len(before)] == before and len(after) == len(before) + 1
        details = json.loads(connection.execute("SELECT details_json FROM source_material_attempts ORDER BY rowid DESC LIMIT 1").fetchone()[0])
        assert details["reused_saved_response"] and details["prior_attempt_id"]


def test_pmc_fallback_checks_identity_and_body() -> None:
    requests = []
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, content=BIOC)
    resolver = FullTextResolver(httpx.MockTransport(handler))
    result = resolver.resolve({"pmcid": "PMC123"})
    assert result.status == "saved" and result.raw == BIOC
    assert result.details["provider"] == "PMC BioC"
    assert result.details["license_statements"] == ["CC BY"]
    assert len(requests) == 1
    assert resolver.resolve({"pmcid": "PMC999"}).status == "needs_review"
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(200, content=BIOC.replace(b"RESULTS", b"ABSTRACT"))))
    assert resolver.resolve({"pmcid": "PMC123"}).status == "needs_review"


def test_preprint_pins_retained_date_and_doi() -> None:
    payload = {"collection": [{"doi": DOI, "date": "2025-10-03", "version": "1", "jatsxml": JATS_URL},
                              {"doi": DOI, "date": "2026-01-01", "version": "2", "jatsxml": "https://127.0.0.1/secret"}]}
    requests: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=payload) if request.url.host == "api.biorxiv.org" else httpx.Response(200, content=JATS)
    resolver = FullTextResolver(httpx.MockTransport(handler))
    metadata: dict[str, Any] = {"doi": DOI, "firstPublicationDate": "2025-10-03", "bookOrReportDetails": {"publisher": "bioRxiv"}}
    result = resolver.resolve(metadata)
    assert result.status == "saved" and result.raw == JATS
    assert result.details["discovery"]["response"] == payload
    assert requests[-1] == JATS_URL
    assert resolver.resolve({**metadata, "firstPublicationDate": "2025-10-04"}).status == "needs_review"
    assert len(requests) == 3
    payload["collection"][0]["jatsxml"] = "https://localhost/private"
    assert resolver.resolve(metadata).status == "needs_review"
    assert len(requests) == 4


def test_redirects_limits_failures_and_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _: None)
    for url in ["http://www.biorxiv.org/x", "https://www.biorxiv.org@localhost/x", "https://www.biorxiv.org:8000/x", "https://127.0.0.1/x"]:
        assert not safe_url(url)
    requests: list[str] = []
    def redirect(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://127.0.0.1/private"})
    resolver = FullTextResolver(httpx.MockTransport(redirect))
    assert resolver.resolve({"pmcid": "PMC123"}).status == "needs_review"
    assert len(requests) == 1
    assert resolver.resolve({"pmcid": "PMC123"}, lambda: True).status == "blocked"
    assert len(requests) == 1
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(200, content=b"too large")))
    assert resolver._download("https://www.biorxiv.org/x", 3).status == "skipped_limit"
    assert resolver.resolve({"pmcid": "PMC123"}).status == "needs_review"
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(404)))
    assert resolver.resolve({"pmcid": "PMC123"}).status == "unavailable"
    assert resolver.resolve({}).status == "unsupported"


def test_existing_run_preparation_is_additive_guarded_and_idempotent(tmp_path: Path) -> None:
    repository, project_id, filter_id, service = _ready(tmp_path)
    run_id = _start(repository, project_id, filter_id)["run"]["id"]
    with pytest.raises(MaterialError, match="Pause"):
        repository.prepare_fallback(project_id, run_id)
    # Simulate the resource set of an older run without the newly supported kind.
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute("DELETE FROM source_material_job_tasks WHERE resource_id IN (SELECT id FROM source_material_resources WHERE kind='full_text_fallback')")
        connection.execute("DELETE FROM source_material_resources WHERE kind='full_text_fallback'")
        job = connection.execute("SELECT id, workflow_input_snapshot_json FROM jobs WHERE kind='source_material_collection'").fetchone()
        snapshot = json.loads(job[1])
        import hashlib
        ids = [r[0] for r in connection.execute("SELECT resource_id FROM source_material_job_tasks WHERE job_id=? ORDER BY ordinal", (job[0],))]
        snapshot["resource_manifest_sha256"] = hashlib.sha256(json.dumps(ids, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        connection.execute("UPDATE jobs SET workflow_input_snapshot_json=? WHERE id=?", (json.dumps(snapshot), job[0]))
    class Missing(FakeMaterials):
        def fetch(self, kind: str, source: str, source_id: str) -> Any:
            from jeromes_laboratory.sources.materials import MaterialResponse
            return MaterialResponse("unavailable", "") if kind == "full_text" else super().fetch(kind, source, source_id)
    assert JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), material_client=Missing()).run_once()
    with sqlite3.connect(repository.database_path) as connection:
        before = connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()
    assert repository.prepare_fallback(project_id, run_id) == 1
    assert repository.prepare_fallback(project_id, run_id) == 0
    assert repository.state(project_id, filter_id)["run"]["processed"] == 0
    repository.control(project_id, run_id, "resume")
    job_model = JobRepository(repository.database_path).claim_next()
    assert job_model is not None
    resolver = FullTextResolver(httpx.MockTransport(lambda _: httpx.Response(200, content=BIOC)))
    repository.run_job(job_model.id, Missing(), resolver=resolver)
    state = repository.state(project_id, filter_id)["run"]
    assert state["full_text_saved"] == 1 and state["abstract_only"] == 0
    assert state["counts"]["full_text:unavailable"] == 1
    assert state["counts"]["full_text_fallback:saved"] == 1
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute("SELECT * FROM source_material_attempts ORDER BY rowid").fetchall()[:len(before)] == before
        connection.execute("UPDATE jobs SET created_at='2099', kind='future_extraction' WHERE id=?", (job_model.id,))
    with pytest.raises(MaterialError, match="fork"):
        repository.prepare_fallback(project_id, run_id)
