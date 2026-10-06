"""Europe PMC drafts retain choices and approval atomically queues retrieval."""

import hashlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from test_evidence_strategy import confirmed_evidence_scope
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ScopeGateway

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.jobs import JobError, JobRepository, provider_input_for_job
from jeromes_laboratory.database.projects import ProjectError, ProjectRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.settings import LLMSettingsService
from jeromes_laboratory.storage.workspace import WorkspaceService
from jeromes_laboratory.workflow.source_queries import (
    DEFAULT_SOURCE_QUERIES_PROMPT,
    SourceQueryError,
    parse_source_queries,
    validate_edited_source_queries,
)

PROPOSAL = {
    "schema_version": 1,
    "source": "europe_pmc",
    "queries": [
        {
            "id": "peptide_precedents", "title": "Peptide precedents",
            "description": "Find direct and related peptide approaches, including null findings.",
            "theme_ids": ["peptide_identity"],
            "query_text": '(myostatin OR GDF8) AND (peptide OR peptidomimetic)',
        },
        {
            "id": "mechanism_outcomes", "title": "Mechanisms and outcomes",
            "description": "Find biology and translational outcomes without requiring peptide terms.",
            "theme_ids": ["mechanism_and_translation"],
            "query_text": '(myostatin OR GDF8) AND (inhibition OR muscle mass)',
        },
    ],
}


def approved_strategy(tmp_path: Path) -> tuple[WorkspaceService, Path, JobRepository, str]:
    service, database_path, repository, project_id, _ = confirmed_evidence_scope(tmp_path)
    strategy = repository.enqueue_evidence_strategy(project_id, "openai", "gpt-example")
    JobWorker(
        service, MemoryCredentialStore(), ScopeGateway("Map peptide approaches and biology.")
    ).run_once()
    repository.approve_evidence_strategy(strategy.id, 1)
    return service, database_path, repository, project_id


def test_queries_require_approved_strategy_and_snapshot_note(tmp_path: Path) -> None:
    _, _, repository, project_id, _ = confirmed_evidence_scope(tmp_path)
    with pytest.raises(JobError, match="Approve the current evidence strategy"):
        repository.enqueue_source_queries(project_id, "openai", "gpt-example", "Include failures")
    service, database_path, repository, project_id = approved_strategy(tmp_path / "ready")
    _ = service
    queued = repository.enqueue_source_queries(
        project_id, "openai", "gpt-example", "Include null and adverse findings."
    )
    snapshot = json.loads(queued.workflow_input_snapshot_json or "{}")
    assert snapshot["source"] == "europe_pmc"
    assert snapshot["user_note"] == "Include null and adverse findings."
    strategy_input = snapshot["approved_strategy"]
    assert isinstance(strategy_input, dict)
    assert strategy_input["strategy_artifact_id"]
    assert "Include null and adverse findings" in provider_input_for_job(queued)
    assert queued.prompt_snapshot == DEFAULT_SOURCE_QUERIES_PROMPT
    with pytest.raises(ProjectError, match="locked"):
        ProjectRepository(database_path).update_source_queries_prompt(project_id, "Alter")
    with pytest.raises(JobError, match="already been started"):
        repository.enqueue_source_queries(project_id, "openai", "gpt-example")


def test_query_parser_requires_theme_coverage_and_source() -> None:
    themes = {"peptide_identity", "mechanism_and_translation"}
    parsed = parse_source_queries(json.dumps(PROPOSAL), themes)
    assert all(query.included for query in parsed.queries)
    original_queries = PROPOSAL["queries"]
    assert isinstance(original_queries, list)
    missing = {**PROPOSAL, "queries": [original_queries[0]]}
    with pytest.raises(SourceQueryError, match="every mandatory evidence theme"):
        parse_source_queries(json.dumps(missing), themes)
    wrong_source = {**PROPOSAL, "source": "pubmed"}
    with pytest.raises(SourceQueryError, match="Invalid Europe PMC query draft"):
        parse_source_queries(json.dumps(wrong_source), themes)


@pytest.mark.asyncio
async def test_query_review_edit_selection_and_approval(tmp_path: Path) -> None:
    service, database_path, repository, project_id = approved_strategy(tmp_path)
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-5.6-sol"])
    settings.select("openai", "gpt-5.6-sol")
    app = create_app(
        static_directory=None, workspace_service=service, llm_settings_service=settings,
        credential_store=MemoryCredentialStore(),
        generation_gateway=ScopeGateway(json.dumps(PROPOSAL)), start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        project_url = f"/api/projects/{project_id}"
        prompt_response = await client.patch(
            f"{project_url}/source-queries-prompt",
            json={"prompt": "Draft Europe PMC queries in JSON."}, headers=headers,
        )
        assert prompt_response.status_code == 200
        assert prompt_response.json()["source_queries_prompt_version"] == "custom:1"
        queued = await client.post(
            f"{project_url}/source-queries/jobs",
            json={"note": "Keep the target-biology query broad."}, headers=headers,
        )
        assert queued.status_code == 201
        job_id = queued.json()["id"]
        assert queued.json()["source_queries"] is None
        assert app.state.job_worker.run_once() is True
        completed = next(job for job in (await client.get("/api/jobs")).json() if job["id"] == job_id)
        assert completed["source_queries"]["queries"][0]["included"] is True
        assert completed["source_queries_approved_at"] is None
        assert completed["output_markdown"] is None
        with pytest.raises(JobError, match="Approve the current Europe PMC queries"):
            repository.get_approved_source_queries_input(project_id)
        queries = completed["source_queries"]["queries"]
        queries[0]["included"] = False
        edited = await client.patch(
            f"/api/jobs/{job_id}/source-queries",
            json={"queries": queries, "base_version": 1}, headers=headers,
        )
        assert edited.status_code == 200
        assert edited.json()["source_queries"]["queries"][0]["included"] is False
        assert edited.json()["original_source_queries"]["queries"][0]["included"] is True
        no_coverage = await client.post(
            f"/api/jobs/{job_id}/source-queries-approval",
            json={"base_version": 2}, headers=headers,
        )
        assert no_coverage.status_code == 409
        assert "every mandatory theme" in no_coverage.json()["detail"]
        queries[0]["included"] = True
        queries[0]["query_text"] += " AND NOT REVIEW"
        saved = await client.patch(
            f"/api/jobs/{job_id}/source-queries",
            json={"queries": queries, "base_version": 2}, headers=headers,
        )
        assert saved.status_code == 200
        stale = await client.post(
            f"/api/jobs/{job_id}/source-queries-approval",
            json={"base_version": 2}, headers=headers,
        )
        assert stale.status_code == 409
        approved = await client.post(
            f"/api/jobs/{job_id}/source-queries-approval",
            json={"base_version": 3}, headers=headers,
        )
        assert approved.status_code == 200
        assert approved.json()["source_queries_approved_at"] is not None
        approved_input = repository.get_approved_source_queries_input(project_id)
        assert approved_input["query_version"] == 3
        assert "AND NOT REVIEW" in json.dumps(approved_input["query_set"])
        retrieval_jobs = [job for job in (await client.get("/api/jobs")).json()
                          if job["kind"] == "source_retrieval"]
        assert len(retrieval_jobs) == 1
        assert retrieval_jobs[0]["status"] == "pending"
        retrieval_input = json.loads(retrieval_jobs[0]["workflow_input_snapshot_json"])
        assert retrieval_input["query_artifact_id"] == approved_input["query_artifact_id"]
        assert retrieval_input["query_approval_id"] == approved_input["query_approval_id"]
        queries[0]["description"] = "Revised after approval."
        revised = await client.patch(
            f"/api/jobs/{job_id}/source-queries",
            json={"queries": queries, "base_version": 3}, headers=headers,
        )
        assert revised.status_code == 409
        duplicate = await client.post(
            f"/api/jobs/{job_id}/source-queries-approval",
            json={"base_version": 3}, headers=headers,
        )
        assert duplicate.status_code == 409
        # Queueing does not make a source request before the worker claims it.
        with sqlite3.connect(database_path) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
            assert "search_runs" in tables
            assert connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0] == 0
            artifacts = connection.execute(
                "SELECT content_json, content_sha256, byte_size, creator_type "
                "FROM artifact_versions WHERE job_id = ? ORDER BY version_number", (job_id,)
            ).fetchall()
    assert [row[3] for row in artifacts] == ["llm", "user", "user"]
    for content_json, digest, byte_size, _ in artifacts:
        encoded = content_json.encode("utf-8")
        assert hashlib.sha256(encoded).hexdigest() == digest
        assert len(encoded) == byte_size


def test_cancelled_query_job_retry_preserves_original_note(tmp_path: Path) -> None:
    _, _, repository, project_id = approved_strategy(tmp_path)
    first = repository.enqueue_source_queries(project_id, "openai", "gpt-example", "Include X")
    repository.cancel(first.id)
    retry = repository.enqueue_source_queries(project_id, "openai", "gpt-other", "Ignore Y")
    snapshot = json.loads(retry.workflow_input_snapshot_json or "{}")
    assert snapshot["user_note"] == "Include X"
    assert snapshot["retry_of_job_id"] == first.id
    with pytest.raises(JobError, match="already been started"):
        repository.enqueue_source_queries(project_id, "openai", "gpt-example")


def test_query_set_shape_rejects_mutated_ids() -> None:
    valid = parse_source_queries(json.dumps(PROPOSAL), {"peptide_identity", "mechanism_and_translation"})
    changed = valid.model_copy(deep=True)
    changed.queries[0].id = "different"
    with pytest.raises(SourceQueryError, match="identities"):
        validate_edited_source_queries(changed, valid, {"peptide_identity", "mechanism_and_translation"})
