"""Strategy generation uses approved inputs and preserves review decisions."""

import hashlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from test_evidence_scope import EVIDENCE_SCOPE_OUTPUT, approved_charter
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ScopeGateway

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.jobs import JobError, JobRepository, provider_input_for_job
from jeromes_laboratory.database.projects import ProjectError, ProjectRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.settings import LLMSettingsService
from jeromes_laboratory.storage.workspace import WorkspaceService
from jeromes_laboratory.workflow.evidence_strategy import (
    DEFAULT_EVIDENCE_STRATEGY_PROMPT,
    EVIDENCE_STRATEGY_PROMPT_VERSION,
)
from jeromes_laboratory.workflow.scope_clarification import ScopeAnswer


def confirmed_evidence_scope(
    tmp_path: Path,
) -> tuple[WorkspaceService, Path, JobRepository, str, str]:
    service, database_path, repository, project_id = approved_charter(tmp_path)
    questionnaire = repository.enqueue_evidence_scope_questionnaire(
        project_id, "openai", "gpt-example"
    )
    JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(EVIDENCE_SCOPE_OUTPUT))
    ).run_once()
    repository.submit_evidence_scope_answers(
        questionnaire.id,
        [
            ScopeAnswer(
                question_id="related_peptide_breadth",
                selected_option_ids=["peptide_and_analogues"],
            ),
            ScopeAnswer(
                question_id="evidence_stages",
                selected_option_ids=["mechanistic", "animal", "human"],
            ),
        ],
    )
    return service, database_path, repository, project_id, questionnaire.id


def test_strategy_requires_confirmed_scope_and_snapshots_effective_version(tmp_path: Path) -> None:
    service, database_path, repository, project_id = approved_charter(tmp_path)
    assert EVIDENCE_STRATEGY_PROMPT_VERSION == "1"
    assert "every mandatory evidence theme" in DEFAULT_EVIDENCE_STRATEGY_PROMPT
    with pytest.raises(JobError, match="Confirm the evidence-scope answers"):
        repository.enqueue_evidence_strategy(project_id, "openai", "gpt-example")
    questionnaire = repository.enqueue_evidence_scope_questionnaire(
        project_id, "openai", "gpt-example"
    )
    JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(EVIDENCE_SCOPE_OUTPUT))
    ).run_once()
    with pytest.raises(JobError, match="Confirm the evidence-scope answers"):
        repository.enqueue_evidence_strategy(project_id, "openai", "gpt-example")
    repository.submit_evidence_scope_answers(
        questionnaire.id,
        [
            ScopeAnswer(question_id="related_peptide_breadth", is_unsure=True),
            ScopeAnswer(question_id="evidence_stages", note="Include all available stages."),
        ],
    )
    repository.edit_evidence_scope_answers(
        questionnaire.id,
        [
            ScopeAnswer(question_id="related_peptide_breadth", note="Use direct evidence first."),
            ScopeAnswer(question_id="evidence_stages", note="Include all available stages."),
        ],
        1,
    )
    queued = repository.enqueue_evidence_strategy(project_id, "openai", "gpt-example")
    snapshot = json.loads(queued.workflow_input_snapshot_json or "{}")
    assert snapshot["evidence_scope_job_id"] == questionnaire.id
    assert snapshot["evidence_scope_answers_version"] == 2
    assert snapshot["evidence_scope_answers"]["answers"][0]["note"] == "Use direct evidence first."
    assert snapshot["approved_research_charter"]["charter_artifact_id"]
    assert {theme["id"] for theme in snapshot["evidence_scope_questions"]["charter_evidence_themes"]} == {
        "peptide_identity", "mechanism_and_translation"
    }
    assert "evidence_scope_answers_artifact_id" in provider_input_for_job(queued)
    assert queued.prompt_snapshot == DEFAULT_EVIDENCE_STRATEGY_PROMPT
    with pytest.raises(JobError, match="locked"):
        repository.edit_evidence_scope_answers(questionnaire.id, [], 2)
    with pytest.raises(ProjectError, match="locked"):
        ProjectRepository(database_path).update_evidence_strategy_prompt(project_id, "Change it")
    with pytest.raises(JobError, match="already been started"):
        repository.enqueue_evidence_strategy(project_id, "openai", "gpt-example")


@pytest.mark.asyncio
async def test_strategy_api_preserves_original_edits_and_exact_approval(tmp_path: Path) -> None:
    service, database_path, repository, project_id, _ = confirmed_evidence_scope(tmp_path)
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-5.6-sol"])
    settings.select("openai", "gpt-5.6-sol")
    original = "## Workstreams\n\nMap peptide activity, mechanisms, and negative findings."
    app = create_app(
        static_directory=None,
        workspace_service=service,
        llm_settings_service=settings,
        credential_store=MemoryCredentialStore(),
        generation_gateway=ScopeGateway(original),
        start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        project_url = f"/api/projects/{project_id}"
        custom_prompt = "Write the evidence strategy as a concise Markdown plan."
        prompt_response = await client.patch(
            f"{project_url}/evidence-strategy-prompt",
            json={"prompt": custom_prompt}, headers=headers,
        )
        assert prompt_response.status_code == 200
        assert prompt_response.json()["evidence_strategy_prompt_version"] == "custom:1"
        denied = await client.post(f"{project_url}/evidence-strategy/jobs")
        assert denied.status_code == 403
        queued = await client.post(f"{project_url}/evidence-strategy/jobs", headers=headers)
        assert queued.status_code == 201
        job_id = queued.json()["id"]
        assert queued.json()["prompt_snapshot"] == custom_prompt
        premature = await client.post(
            f"/api/jobs/{job_id}/evidence-strategy-approval",
            json={"base_version": 1}, headers=headers,
        )
        assert premature.status_code == 409
        assert app.state.job_worker.run_once() is True
        completed = next(job for job in (await client.get("/api/jobs")).json() if job["id"] == job_id)
        assert completed["original_output_markdown"] == original
        assert completed["effective_output_markdown"] == original
        assert completed["evidence_strategy_approved_at"] is None
        approved = await client.post(
            f"/api/jobs/{job_id}/evidence-strategy-approval",
            json={"base_version": 1}, headers=headers,
        )
        assert approved.status_code == 200
        assert approved.json()["evidence_strategy_approved_at"] is not None
        assert repository.get_approved_evidence_strategy_input(project_id)["strategy_version"] == 1
        revision = original + "\n\nKeep indirect evidence in a separate stratum."
        edited = await client.patch(
            f"/api/jobs/{job_id}/evidence-strategy-output",
            json={"markdown": revision, "base_version": 1}, headers=headers,
        )
        assert edited.status_code == 200
        assert edited.json()["original_output_markdown"] == original
        assert edited.json()["effective_output_markdown"] == revision
        assert edited.json()["evidence_strategy_approved_at"] is None
        with pytest.raises(JobError, match="Approve the current evidence strategy"):
            repository.get_approved_evidence_strategy_input(project_id)
        stale = await client.post(
            f"/api/jobs/{job_id}/evidence-strategy-approval",
            json={"base_version": 1}, headers=headers,
        )
        assert stale.status_code == 409
        reapproved = await client.post(
            f"/api/jobs/{job_id}/evidence-strategy-approval",
            json={"base_version": 2}, headers=headers,
        )
        assert reapproved.status_code == 200
        exact = repository.get_approved_evidence_strategy_input(project_id)
        assert exact["strategy_version"] == 2
        assert exact["strategy_markdown"] == revision
        strategy_input = exact["strategy_input"]
        assert isinstance(strategy_input, dict)
        assert strategy_input["evidence_scope_answers_version"] == 1
    with sqlite3.connect(database_path) as connection:
        artifacts = connection.execute(
            "SELECT content_json, content_sha256, byte_size, creator_type "
            "FROM artifact_versions WHERE job_id = ? ORDER BY version_number",
            (job_id,),
        ).fetchall()
    assert [artifact[3] for artifact in artifacts] == ["llm", "user"]
    for content_json, digest, byte_size, _ in artifacts:
        encoded = content_json.encode("utf-8")
        assert digest == hashlib.sha256(encoded).hexdigest()
        assert byte_size == len(encoded)


def test_cancelled_strategy_retry_retains_its_original_scope_snapshot(tmp_path: Path) -> None:
    _, _, repository, project_id, _ = confirmed_evidence_scope(tmp_path)
    first = repository.enqueue_evidence_strategy(project_id, "openai", "gpt-example")
    repository.cancel(first.id)
    retry = repository.enqueue_evidence_strategy(project_id, "openai", "gpt-other")
    first_input = json.loads(first.workflow_input_snapshot_json or "{}")
    retry_input = json.loads(retry.workflow_input_snapshot_json or "{}")
    retry_input.pop("retry_of_job_id")
    assert retry_input == first_input
    assert retry.model == "gpt-other"
