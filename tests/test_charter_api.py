"""HTTP coverage of charter drafts, explicit approval, and replacement attempts."""

import hashlib
import sqlite3
from pathlib import Path

import httpx
import pytest
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ReadinessGateway, ScopeGateway, completed_scope

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.jobs import JobError
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.settings import LLMSettingsService


@pytest.mark.asyncio
async def test_charter_api_draft_approval_edit_and_explicit_regeneration(tmp_path: Path) -> None:
    service, database_path, repository, project_id, _ = completed_scope(tmp_path)
    readiness = repository.enqueue_scope_readiness(project_id, "openai", "gpt-example")
    credentials = MemoryCredentialStore()
    JobWorker(service, credentials, ReadinessGateway({
        "schema_version": 2,
        "ready_for_charter": True,
        "assessment": "The purpose of the evidence investigation is clear.",
        "remaining_uncertainties": ["The evidence will inform the next choice."],
        "follow_up_questions": [],
    })).run_once()
    assert repository.get_job(readiness.id).status == "completed"
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-5.6-sol"])
    settings.select("openai", "gpt-5.6-sol")
    original_markdown = "## Current purpose\n\nMap evidence before choosing a direction."
    app = create_app(
        static_directory=None,
        workspace_service=service,
        llm_settings_service=settings,
        credential_store=credentials,
        generation_gateway=ScopeGateway(original_markdown),
        start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        project_url = f"/api/projects/{project_id}"
        denied = await client.post(f"{project_url}/research-charter/jobs", json={})
        assert denied.status_code == 403
        custom_prompt = "Create a concise charter from the confirmed decisions."
        changed_prompt = await client.patch(
            f"{project_url}/research-charter-prompt", json={"prompt": custom_prompt},
            headers=headers,
        )
        assert changed_prompt.status_code == 200
        assert changed_prompt.json()["research_charter_prompt"] == custom_prompt
        assert changed_prompt.json()["research_charter_prompt_version"] == "custom:4"
        queued = await client.post(
            f"{project_url}/research-charter/jobs", json={}, headers=headers,
        )
        assert queued.status_code == 201
        job_id = queued.json()["id"]
        job_url = f"/api/jobs/{job_id}"
        assert queued.json()["prompt_snapshot"] == custom_prompt
        assert queued.json()["charter_approved_at"] is None
        locked_prompt = await client.patch(
            f"{project_url}/research-charter-prompt",
            json={"prompt": "This must not alter a started charter stage."},
            headers=headers,
        )
        assert locked_prompt.status_code == 409
        assert "locked" in locked_prompt.json()["detail"]
        premature_approval = await client.post(
            f"{job_url}/research-charter-approval", json={"base_version": 1}, headers=headers,
        )
        assert premature_approval.status_code == 409
        assert app.state.job_worker.run_once() is True
        jobs = (await client.get("/api/jobs")).json()
        charter = next(job for job in jobs if job["id"] == job_id)
        assert charter["effective_output_markdown"] == original_markdown
        assert charter["charter_is_editable"] is True
        assert charter["charter_approved_at"] is None
        duplicate = await client.post(
            f"{project_url}/research-charter/jobs", json={}, headers=headers,
        )
        assert duplicate.status_code == 422
        denied_approval = await client.post(
            f"{job_url}/research-charter-approval", json={"base_version": 1},
        )
        assert denied_approval.status_code == 403
        approved = await client.post(
            f"{job_url}/research-charter-approval", json={"base_version": 1}, headers=headers,
        )
        assert approved.status_code == 200
        assert approved.json()["charter_approved_at"] is not None
        approved_input = repository.get_approved_research_charter_input(project_id)
        assert approved_input["charter_job_id"] == job_id
        assert approved_input["charter_version"] == 1
        assert approved_input["charter_markdown"] == original_markdown
        edited = await client.patch(
            f"{job_url}/research-charter-output",
            json={"markdown": original_markdown + "\n\nRetain accepted uncertainty.", "base_version": 1},
            headers=headers,
        )
        assert edited.status_code == 200
        assert edited.json()["effective_output_version"] == 2
        assert edited.json()["original_output_markdown"] == original_markdown
        assert edited.json()["charter_approved_at"] is None
        with pytest.raises(JobError, match="Approve the current research charter"):
            repository.get_approved_research_charter_input(project_id)
        stale_approval = await client.post(
            f"{job_url}/research-charter-approval", json={"base_version": 1}, headers=headers,
        )
        assert stale_approval.status_code == 409
        reapproved = await client.post(
            f"{job_url}/research-charter-approval", json={"base_version": 2}, headers=headers,
        )
        assert reapproved.status_code == 200
        approved_edit = repository.get_approved_research_charter_input(project_id)
        assert approved_edit["charter_version"] == 2
        assert str(approved_edit["charter_markdown"]).endswith("Retain accepted uncertainty.")
        regenerated = await client.post(
            f"{project_url}/research-charter/jobs",
            json={"previous_job_id": job_id, "base_version": 2}, headers=headers,
        )
        assert regenerated.status_code == 201
        replacement_id = regenerated.json()["id"]
        assert replacement_id != job_id
        obsolete_approval = await client.post(
            f"{job_url}/research-charter-approval", json={"base_version": 2}, headers=headers,
        )
        assert obsolete_approval.status_code == 409
        cancelled = await client.post(f"/api/jobs/{replacement_id}/cancel", headers=headers)
        assert cancelled.status_code == 200
        restored_jobs = (await client.get("/api/jobs")).json()
        restored = next(job for job in restored_jobs if job["id"] == job_id)
        assert restored["charter_is_editable"] is True
        assert restored["charter_approved_at"] is not None
        retry = await client.post(
            f"{project_url}/research-charter/jobs", json={}, headers=headers,
        )
        assert retry.status_code == 201
        assert app.state.job_worker.run_once() is True
        final_jobs = (await client.get("/api/jobs")).json()
        final_charters = [job for job in final_jobs if job["kind"] == "research_charter"]
        assert len(final_charters) == 3
        assert final_charters[0]["charter_approved_at"] is None
        assert final_charters[0]["original_output_markdown"] == original_markdown
        assert "test-secret-key" not in str(final_charters)
        with sqlite3.connect(database_path) as connection:
            artifacts = connection.execute(
                "SELECT content_json, content_sha256, byte_size FROM artifact_versions "
                "WHERE kind = 'research_charter_output'"
            ).fetchall()
        assert len(artifacts) == 3
        for content_json, digest, byte_size in artifacts:
            encoded = content_json.encode("utf-8")
            assert digest == hashlib.sha256(encoded).hexdigest()
            assert byte_size == len(encoded)


@pytest.mark.asyncio
async def test_charter_api_rejects_missing_readiness_and_missing_provider(tmp_path: Path) -> None:
    service, _, _, project_id, _ = completed_scope(tmp_path)
    settings = LLMSettingsService(tmp_path / "llm-config")
    credentials = MemoryCredentialStore()
    app = create_app(
        static_directory=None, workspace_service=service,
        llm_settings_service=settings, credential_store=credentials, start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        url = f"/api/projects/{project_id}/research-charter/jobs"
        unconfigured = await client.post(url, json={}, headers=headers)
        assert unconfigured.status_code == 422
        assert "provider and model" in unconfigured.json()["detail"]
        settings.cache_models("openai", ["gpt-5.6-sol"])
        settings.select("openai", "gpt-5.6-sol")
        unready = await client.post(url, json={}, headers=headers)
        assert unready.status_code == 422
        credentials.delete_api_key("openai")
        missing_key = await client.post(url, json={}, headers=headers)
        assert missing_key.status_code == 422
        assert "API key" in missing_key.json()["detail"]
        assert len((await client.get("/api/jobs")).json()) == 2
