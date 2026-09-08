"""Persistent queue, provider execution, and LLM provenance tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.jobs import JobRepository
from jeromes_laboratory.database.projects import ProjectRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.catalog import ProviderName
from jeromes_laboratory.llm.generation import (
    GenerationResult,
    PreparedGeneration,
    ProviderGenerationGateway,
)
from jeromes_laboratory.llm.settings import LLMSettingsService
from jeromes_laboratory.storage.workspace import DATABASE_FILE_NAME, WorkspaceService


class MemoryCredentialStore:
    def __init__(self, provider: str = "openai", key: str = "test-secret-key") -> None:
        self.keys = {provider: key}

    def get_api_key(self, provider: str) -> str | None:
        return self.keys.get(provider)

    def set_api_key(self, provider: str, api_key: str) -> None:
        self.keys[provider] = api_key

    def delete_api_key(self, provider: str) -> None:
        self.keys.pop(provider, None)


class SuccessfulGateway:
    def __init__(self) -> None:
        self.provider_gateway = ProviderGenerationGateway()
        self.received_key: str | None = None

    def prepare(
        self, provider: ProviderName, model: str, instructions: str, input_content: str
    ) -> PreparedGeneration:
        assert provider in ("openai", "anthropic")
        return self.provider_gateway.prepare(provider, model, instructions, input_content)

    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        self.received_key = api_key
        return GenerationResult(
            raw_response='{"debug":"test-secret-key","id":"response-1","output":[]}',
            output_text="## Developed question\n\nA rigorous research direction.",
            provider_request_id="response-1",
            reported_model=str(prepared.request_body["model"]),
            usage={"input_tokens": 24, "output_tokens": 18, "total_tokens": 42},
            input_tokens=24,
            output_tokens=18,
            total_tokens=42,
            cached_input_tokens=3,
            reasoning_tokens=2,
            provider_metadata={"status": "completed"},
        )


def configured_workspace(tmp_path: Path) -> tuple[WorkspaceService, Path]:
    service = WorkspaceService(
        configuration_directory=tmp_path / "workspace-config",
        documents_directory=tmp_path / "Documents",
    )
    workspace = tmp_path / "research"
    service.configure_workspace(str(workspace))
    return service, workspace


def test_openai_response_is_parsed_and_authorization_is_not_in_request_body() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            headers={"x-request-id": "header-request-id"},
            json={
                "id": "resp_123",
                "model": "gpt-example-2026-09-01",
                "status": "completed",
                "output": [{"content": [{"type": "output_text", "text": "Developed answer"}]}],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 7,
                    "total_tokens": 17,
                    "input_tokens_details": {"cached_tokens": 4},
                    "output_tokens_details": {"reasoning_tokens": 2},
                },
            },
        )

    gateway = ProviderGenerationGateway(transport=httpx.MockTransport(handler))
    prepared = gateway.prepare("openai", "gpt-example", "instructions", "input")
    result = gateway.execute(prepared, "very-secret")

    assert result.output_text == "Developed answer"
    assert result.total_tokens == 17
    assert result.cached_input_tokens == 4
    assert result.reasoning_tokens == 2
    assert captured_request is not None
    assert captured_request.headers["authorization"] == "Bearer very-secret"
    assert "very-secret" not in json.dumps(prepared.request_body)


def test_anthropic_message_is_parsed_with_provider_specific_usage() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "msg_123",
                "model": "claude-example",
                "content": [{"type": "text", "text": "Developed answer"}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 9,
                    "cache_creation_input_tokens": 3,
                    "cache_read_input_tokens": 5,
                },
            },
        )

    gateway = ProviderGenerationGateway(transport=httpx.MockTransport(handler))
    result = gateway.execute(
        gateway.prepare("anthropic", "claude-example", "instructions", "input"),
        "secret",
    )

    assert result.output_text == "Developed answer"
    assert result.total_tokens == 20
    assert result.cached_input_tokens == 8


def test_worker_preserves_exact_call_and_hashes_the_parsed_artifact(tmp_path: Path) -> None:
    workspace_service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("Can intervention X improve Y?")
    jobs = JobRepository(database_path)
    queued = jobs.enqueue_question_detailing(project.id, "openai", "gpt-example")
    gateway = SuccessfulGateway()
    worker = JobWorker(workspace_service, MemoryCredentialStore(), gateway)

    assert worker.run_once() is True

    completed = jobs.get_job(queued.id)
    assert completed.status == "completed"
    assert completed.output_markdown == "## Developed question\n\nA rigorous research direction."
    assert completed.total_tokens == 42
    assert completed.cost_status == "unavailable"
    assert gateway.received_key == "test-secret-key"
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        call = connection.execute(
            "SELECT * FROM llm_calls WHERE job_id = ?", (queued.id,)
        ).fetchone()
        artifact = connection.execute(
            "SELECT * FROM artifact_versions WHERE job_id = ?", (queued.id,)
        ).fetchone()
    assert call is not None and artifact is not None
    assert call["instructions"] == project.question_detailing_prompt
    assert call["input_content"] == "Scientific question:\n\nCan intervention X improve Y?"
    assert call["raw_response"] == '{"debug":"[REDACTED]","id":"response-1","output":[]}'
    assert call["provider_request_id"] == "response-1"
    assert call["cost_status"] == "unavailable"
    content_bytes = artifact["content_json"].encode("utf-8")
    assert artifact["content_sha256"] == hashlib.sha256(content_bytes).hexdigest()
    assert artifact["byte_size"] == len(content_bytes)
    assert b"test-secret-key" not in database_path.read_bytes()


@pytest.mark.asyncio
async def test_pending_job_can_be_cancelled_and_enqueue_locks_inputs(tmp_path: Path) -> None:
    workspace_service, _ = configured_workspace(tmp_path)
    credentials = MemoryCredentialStore()
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-5.6-sol"])
    settings.select("openai", "gpt-5.6-sol")
    app = create_app(
        static_directory=None,
        workspace_service=workspace_service,
        llm_settings_service=settings,
        credential_store=credentials,
        start_job_worker=False,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": token}
        project = (
            await client.post(
                "/api/projects",
                json={"scientific_question": "What should be investigated?"},
                headers=headers,
            )
        ).json()
        queued = await client.post(
            f"/api/projects/{project['id']}/question-detailing/jobs", headers=headers
        )
        projects_after_enqueue = await client.get("/api/projects")
        locked_edit = await client.patch(
            f"/api/projects/{project['id']}/scientific-question",
            json={"scientific_question": "A changed question"},
            headers=headers,
        )
        cancelled = await client.post(f"/api/jobs/{queued.json()['id']}/cancel", headers=headers)

    assert queued.status_code == 201
    assert queued.json()["status"] == "pending"
    assert projects_after_enqueue.json()[0]["question_is_editable"] is False
    assert projects_after_enqueue.json()[0]["question_detailing_prompt_is_editable"] is False
    assert locked_edit.status_code == 422
    assert cancelled.json()["status"] == "cancelled"


def test_awaiting_response_job_cannot_be_cancelled(tmp_path: Path) -> None:
    _, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("Question")
    repository = JobRepository(database_path)
    queued = repository.enqueue_question_detailing(project.id, "openai", "gpt-example")

    claimed = repository.claim_next()

    assert claimed is not None and claimed.status == "awaiting_response"
    with pytest.raises(ValueError, match="can no longer be cancelled"):
        repository.cancel(queued.id)


def test_interrupted_dispatched_job_is_failed_without_retry(tmp_path: Path) -> None:
    workspace_service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("Question")
    repository = JobRepository(database_path)
    repository.enqueue_question_detailing(project.id, "openai", "gpt-example")
    claimed = repository.claim_next()
    assert claimed is not None
    prepared = ProviderGenerationGateway().prepare(
        "openai",
        claimed.model,
        claimed.prompt_snapshot,
        "Scientific question:\n\nQuestion",
    )
    repository.begin_llm_call(claimed, prepared)
    gateway = SuccessfulGateway()
    worker = JobWorker(workspace_service, MemoryCredentialStore(), gateway)

    assert worker.run_once() is False

    recovered = repository.get_job(claimed.id)
    assert recovered.status == "failed"
    assert recovered.error is not None and "was not retried" in recovered.error
    assert gateway.received_key is None
