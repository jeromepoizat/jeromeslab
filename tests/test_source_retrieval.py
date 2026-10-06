"""Retrieval preserves raw pages and every query-to-record discovery link."""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ScopeGateway
from test_source_queries import PROPOSAL, approved_strategy

from jeromes_laboratory.api.schemas import RetrievalSummaryResponse
from jeromes_laboratory.database import retrieval as retrieval_module
from jeromes_laboratory.database.jobs import JobRepository
from jeromes_laboratory.database.retrieval import RetrievalRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.sources.europe_pmc import SearchPage, SourceSearchError
from jeromes_laboratory.storage.workspace import WorkspaceService


class FakeEuropePMCClient:
    def __init__(self, fail_on: str | None = None, total_hits: int = 1) -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on
        self.total_hits = total_hits

    def fetch(self, query: str, cursor_mark: str, page_size: int = 1000) -> SearchPage:
        assert cursor_mark == "*"
        assert page_size > 0
        self.calls.append(query)
        if self.fail_on is not None and self.fail_on in query:
            raise SourceSearchError("Europe PMC returned HTTP 503.")
        record = {
            "source": "MED", "id": "123", "title": "Myostatin peptide study",
            "pmid": "123", "doi": "10.1234/example", "abstractText": "An abstract.",
        }
        raw = json.dumps({"hitCount": self.total_hits, "resultList": {"result": [record]}}).encode()
        return SearchPage("https://www.ebi.ac.uk/europepmc/webservices/rest/search?test=1", raw, self.total_hits, None, [record])


def _approved_query_job(tmp_path: Path) -> tuple[Path, JobRepository, str, WorkspaceService]:
    service, database_path, repository, project_id = approved_strategy(tmp_path)
    query_job = repository.enqueue_source_queries(project_id, "openai", "gpt-example")
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(PROPOSAL))
    ).run_once()
    repository.approve_source_queries(query_job.id, 1)
    retrieval = next(job for job in repository.list_jobs() if job.kind == "source_retrieval")
    return database_path, repository, retrieval.id, service


def test_approved_queries_retrieve_and_preserve_duplicate_discoveries(tmp_path: Path) -> None:
    database_path, repository, job_id, service = _approved_query_job(tmp_path)
    empty_summary = RetrievalRepository(database_path).summary_for_job(job_id)
    assert empty_summary["runs"] == []
    assert empty_summary["distinct_source_records"] == 0
    assert empty_summary["provisional_record_groups"] is None
    assert empty_summary["sources"] == []
    client = FakeEuropePMCClient()
    worker = JobWorker(service, MemoryCredentialStore(), ScopeGateway("unused"), europe_pmc_client=client)
    assert worker.run_once()
    assert repository.get_job(job_id).status == "completed"
    assert len(client.calls) == 2
    runs = RetrievalRepository(database_path).runs_for_job(job_id)
    assert len(runs) == 2
    assert all(run["retrieved_count"] == 1 and run["total_hits"] == 1 for run in runs)
    with sqlite3.connect(database_path) as connection:
        records = connection.execute(
            "SELECT run_id, source, source_record_id FROM publication_source_records"
        ).fetchall()
        pages = connection.execute(
            "SELECT raw_path, raw_sha256, raw_byte_size FROM search_pages"
        ).fetchall()
    assert len(records) == 2
    assert records[0][0] != records[1][0]
    assert [(record[1], record[2]) for record in records] == [("MED", "123"), ("MED", "123")]
    summary = RetrievalRepository(database_path).summary_for_job(job_id)
    assert summary["reported_hits"] == 2
    assert summary["raw_saved_records"] == 2
    assert summary["distinct_source_records"] == 1
    assert summary["provisional_record_groups"] == 1
    assert summary["additional_source_ids_grouped"] == 0
    assert summary["repeat_discoveries"] == 1
    assert summary["records_in_multiple_queries"] == 1
    assert [run["unique_to_query"] for run in cast(list[dict[str, object]], summary["runs"])] == [0, 0]
    assert summary["distinct_records_with_abstract"] == 1
    assert summary["sources"] == [{"source": "MED", "unique_records": 1, "raw_records": 2}]
    for relative, digest, size in pages:
        raw = (database_path.parent / "artifacts" / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert len(raw) == size


def test_query_unique_counts_use_distinct_source_ids_within_retrieval(tmp_path: Path) -> None:
    database_path, _, job_id, service = _approved_query_job(tmp_path)

    class OverlappingClient:
        def fetch(self, query: str, cursor_mark: str, page_size: int = 1000) -> SearchPage:
            assert cursor_mark == "*"
            shared = {"source": "MED", "id": "shared", "title": "Shared report"}
            if "peptidomimetic" in query:
                own = {"source": "MED", "id": "peptide-only", "title": "Peptide-only report"}
                records = [shared, own, own]
            else:
                own = {"source": "MED", "id": "mechanism-only", "title": "Mechanism-only report"}
                records = [shared, own]
            raw = json.dumps({
                "hitCount": len(records), "resultList": {"result": records},
            }).encode()
            return SearchPage("https://example.test/search", raw, len(records), None, records)

    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=OverlappingClient(),
    ).run_once()
    summary = RetrievalRepository(database_path).summary_for_job(job_id)
    assert summary["raw_saved_records"] == 5
    assert summary["distinct_source_records"] == 3
    assert summary["records_in_multiple_queries"] == 1
    assert [(run["query_id"], run["unique_to_query"])
            for run in cast(list[dict[str, object]], summary["runs"])] == [
        ("peptide_precedents", 1), ("mechanism_outcomes", 1),
    ]
    assert RetrievalSummaryResponse.model_validate(summary).runs[0].unique_to_query == 1


def test_failed_retrieval_keeps_prior_pages_and_can_retry(tmp_path: Path) -> None:
    database_path, repository, job_id, service = _approved_query_job(tmp_path)
    failing = FakeEuropePMCClient(fail_on="inhibition")
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"), europe_pmc_client=failing
    ).run_once()
    assert repository.get_job(job_id).status == "failed"
    first_runs = RetrievalRepository(database_path).runs_for_job(job_id)
    assert [run["status"] for run in first_runs] == ["completed", "failed"]
    retry = repository.retry_source_retrieval(job_id)
    assert retry.status == "pending"
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(),
    ).run_once()
    assert repository.get_job(retry.id).status == "completed"
    assert len(RetrievalRepository(database_path).runs_for_job(job_id)) == 2
    assert len(RetrievalRepository(database_path).runs_for_job(retry.id)) == 2
    assert RetrievalRepository(database_path).summary_for_job(job_id)["raw_saved_records"] == 1
    assert RetrievalRepository(database_path).summary_for_job(retry.id)["raw_saved_records"] == 2


def test_safety_limit_is_reported_as_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path, repository, job_id, service = _approved_query_job(tmp_path)
    monkeypatch.setattr(retrieval_module, "MAX_RECORDS_PER_QUERY", 1)
    assert JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("unused"),
        europe_pmc_client=FakeEuropePMCClient(total_hits=20),
    ).run_once()
    assert repository.get_job(job_id).status == "completed"
    runs = RetrievalRepository(database_path).runs_for_job(job_id)
    assert all(run["truncated"] and run["retrieved_count"] == 1 and run["total_hits"] == 20 for run in runs)
    summary = RetrievalRepository(database_path).summary_for_job(job_id)
    assert summary["reported_hits"] == 40
    assert summary["raw_saved_records"] == 2
