"""Intent-clarification prompt, parsing, provenance, and selection tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.database.initialize import MIGRATIONS_DIRECTORY, database_url
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
from jeromes_laboratory.workflow.intent_clarification import (
    IntentClarificationError,
    parse_intent_clarification_output,
)

INTENT_OUTPUT = {
    "schema_version": 1,
    "question": "Which primary purpose best matches this project?",
    "explanation": "The original question could support several different research goals.",
    "options": [
        {
            "id": "evidence_landscape",
            "label": "Map the evidence",
            "description": "Identify and characterize the available literature.",
        },
        {
            "id": "intervention_effect",
            "label": "Evaluate effects",
            "description": "Assess whether the intervention changes the outcome.",
        },
        {
            "id": "mechanism",
            "label": "Explain the mechanism",
            "description": "Investigate how the intervention could produce the outcome.",
        },
    ],
}


class MemoryCredentialStore:
    def get_api_key(self, provider: str) -> str | None:
        return "test-secret" if provider == "openai" else None

    def set_api_key(self, provider: str, api_key: str) -> None:
        raise AssertionError("The worker must not replace credentials.")

    def delete_api_key(self, provider: str) -> None:
        raise AssertionError("The worker must not delete credentials.")


class IntentGateway:
    def __init__(self, output_text: str = json.dumps(INTENT_OUTPUT)) -> None:
        self._output_text = output_text
        self._gateway = ProviderGenerationGateway()

    def prepare(
        self, provider: ProviderName, model: str, instructions: str, input_content: str
    ) -> PreparedGeneration:
        return self._gateway.prepare(provider, model, instructions, input_content)

    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        return GenerationResult(
            raw_response=json.dumps({"id": "intent-response", "output": self._output_text}),
            output_text=self._output_text,
            provider_request_id="intent-response",
            reported_model=str(prepared.request_body["model"]),
            usage={"input_tokens": 30, "output_tokens": 60, "total_tokens": 90},
            input_tokens=30,
            output_tokens=60,
            total_tokens=90,
            cached_input_tokens=None,
            reasoning_tokens=None,
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


def test_intent_output_parser_rejects_unstructured_or_duplicate_options() -> None:
    parsed = parse_intent_clarification_output(json.dumps(INTENT_OUTPUT))
    assert parsed.options[0].id == "evidence_landscape"

    with pytest.raises(IntentClarificationError):
        parse_intent_clarification_output("Here are several possible intents...")

    duplicated = parsed.model_copy(update={"options": [parsed.options[0]] * 3})
    with pytest.raises(IntentClarificationError):
        parse_intent_clarification_output(duplicated.model_dump_json())


def test_worker_preserves_validated_intent_questions_and_user_selection(
    tmp_path: Path,
) -> None:
    workspace_service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project(
        "Can intervention X improve outcome Y?"
    )
    repository = JobRepository(database_path)
    queued = repository.enqueue_intent_clarification(project.id, "openai", "gpt-example")

    assert JobWorker(
        workspace_service, MemoryCredentialStore(), IntentGateway()
    ).run_once() is True

    completed = repository.get_job(queued.id)
    assert completed.status == "completed"
    assert completed.intent_questions == INTENT_OUTPUT
    assert completed.intent_selection is None

    selected = repository.submit_intent_selection(
        queued.id,
        "intervention_effect",
        ["mechanism"],
        "Prioritize effects, but retain mechanistic context.",
    )
    assert selected.intent_selection is not None
    assert selected.intent_selection["primary_intent_id"] == "intervention_effect"
    assert selected.intent_selection["secondary_intent_ids"] == ["mechanism"]

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        artifacts = connection.execute(
            "SELECT kind, content_json, content_sha256, byte_size, creator_type "
            "FROM artifact_versions WHERE job_id = ? ORDER BY created_at",
            (queued.id,),
        ).fetchall()
    assert [artifact["kind"] for artifact in artifacts] == [
        "intent_clarification_questions",
        "intent_clarification_selection",
    ]
    assert [artifact["creator_type"] for artifact in artifacts] == ["llm", "user"]
    for artifact in artifacts:
        content = artifact["content_json"].encode("utf-8")
        assert artifact["content_sha256"] == hashlib.sha256(content).hexdigest()
        assert artifact["byte_size"] == len(content)

    with pytest.raises(ValueError, match="already been confirmed"):
        repository.submit_intent_selection(queued.id, "mechanism", [], "")


def test_invalid_intent_response_fails_without_creating_an_output_artifact(
    tmp_path: Path,
) -> None:
    workspace_service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("A broad question")
    repository = JobRepository(database_path)
    queued = repository.enqueue_intent_clarification(project.id, "openai", "gpt-example")

    JobWorker(
        workspace_service,
        MemoryCredentialStore(),
        IntentGateway("not valid JSON"),
    ).run_once()

    failed = repository.get_job(queued.id)
    assert failed.status == "failed"
    assert failed.error is not None and "valid intent-clarification" in failed.error
    with sqlite3.connect(database_path) as connection:
        artifact_count = connection.execute(
            "SELECT COUNT(*) FROM artifact_versions WHERE job_id = ?", (queued.id,)
        ).fetchone()
    assert artifact_count == (0,)


@pytest.mark.asyncio
async def test_intent_api_queues_and_confirms_a_selection(tmp_path: Path) -> None:
    workspace_service, _ = configured_workspace(tmp_path)
    settings = LLMSettingsService(tmp_path / "llm-config")
    settings.cache_models("openai", ["gpt-5.6-sol"])
    settings.select("openai", "gpt-5.6-sol")
    app = create_app(
        static_directory=None,
        workspace_service=workspace_service,
        llm_settings_service=settings,
        credential_store=MemoryCredentialStore(),
        generation_gateway=IntentGateway(),
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
                json={"scientific_question": "What should this project accomplish?"},
                headers=headers,
            )
        ).json()
        queued = await client.post(
            f"/api/projects/{project['id']}/intent-clarification/jobs", headers=headers
        )
        assert app.state.job_worker.run_once() is True
        completed = (await client.get("/api/jobs")).json()[0]
        selected = await client.post(
            f"/api/jobs/{completed['id']}/intent-selection",
            json={
                "primary_intent_id": "evidence_landscape",
                "secondary_intent_ids": ["mechanism"],
                "note": "Keep efficacy as a later option.",
            },
            headers=headers,
        )
        edited = await client.patch(
            f"/api/jobs/{completed['id']}/intent-selection",
            json={
                "primary_intent_id": "mechanism",
                "secondary_intent_ids": [],
                "note": "Focus the next stage on mechanism.",
                "base_version": 1,
            },
            headers=headers,
        )

    assert queued.status_code == 201
    assert completed["intent_questions"]["options"][0]["id"] == "evidence_landscape"
    assert selected.status_code == 200
    assert selected.json()["intent_selection"]["primary_intent_id"] == "evidence_landscape"
    assert selected.json()["intent_selection_version"] == 1
    assert edited.status_code == 200
    assert edited.json()["intent_selection"]["primary_intent_id"] == "mechanism"
    assert edited.json()["intent_selection_version"] == 2


def test_confirmed_intent_edits_create_versions_until_downstream_is_queued(
    tmp_path: Path,
) -> None:
    workspace_service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("A broad scientific question")
    repository = JobRepository(database_path)
    job = repository.enqueue_intent_clarification(project.id, "openai", "gpt-example")
    JobWorker(workspace_service, MemoryCredentialStore(), IntentGateway()).run_once()
    confirmed = repository.submit_intent_selection(
        job.id, "evidence_landscape", ["mechanism"], "Initial note"
    )

    edited = repository.edit_intent_selection(
        job.id,
        "intervention_effect",
        [],
        "Narrowed to effectiveness.",
        base_version=1,
    )

    assert confirmed.intent_selection_version == 1
    assert confirmed.intent_selection_is_editable is True
    assert edited.intent_selection_version == 2
    assert edited.intent_selection is not None
    assert edited.intent_selection["primary_intent_id"] == "intervention_effect"
    with sqlite3.connect(database_path) as connection:
        versions = connection.execute(
            "SELECT version_number, content_json FROM artifact_versions "
            "WHERE job_id = ? AND kind = 'intent_clarification_selection' "
            "ORDER BY version_number",
            (job.id,),
        ).fetchall()
    assert [version[0] for version in versions] == [1, 2]
    assert json.loads(versions[0][1])["primary_intent_id"] == "evidence_landscape"

    with pytest.raises(ValueError, match="edited elsewhere"):
        repository.edit_intent_selection(
            job.id, "mechanism", [], "Stale edit", base_version=1
        )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "downstream-job",
                project.id,
                "scope_clarification",
                "pending",
                "9999-01-01T00:00:00+00:00",
                "openai",
                "gpt-example",
                project.scientific_question,
                "Future scope prompt",
                "scope-clarification",
                "1",
            ),
        )
    locked = repository.get_job(job.id)
    assert locked.intent_selection_is_editable is False
    with pytest.raises(ValueError, match="downstream job"):
        repository.edit_intent_selection(
            job.id, "mechanism", [], "Too late", base_version=2
        )


def test_effective_intent_migration_selects_an_existing_confirmation(tmp_path: Path) -> None:
    workspace_service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("Question")
    repository = JobRepository(database_path)
    job = repository.enqueue_intent_clarification(project.id, "openai", "gpt-example")
    JobWorker(workspace_service, MemoryCredentialStore(), IntentGateway()).run_once()
    repository.submit_intent_selection(job.id, "mechanism", [], "")
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))

    command.downgrade(configuration, "0010")
    assert repository.get_job(job.id).intent_selection is None

    command.upgrade(configuration, "head")
    migrated = repository.get_job(job.id)
    assert migrated.intent_selection is not None
    assert migrated.intent_selection["primary_intent_id"] == "mechanism"
    assert migrated.intent_selection_version == 1
