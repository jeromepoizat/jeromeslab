"""First-round scope clarification, provenance, and answer-version tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from test_intent_clarification import IntentGateway, MemoryCredentialStore

from jeromes_laboratory.database.jobs import JobError, JobRepository, provider_input_for_job
from jeromes_laboratory.database.projects import ProjectRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.catalog import ProviderName
from jeromes_laboratory.llm.generation import (
    GenerationResult,
    PreparedGeneration,
    ProviderGenerationGateway,
)
from jeromes_laboratory.storage.workspace import DATABASE_FILE_NAME, WorkspaceService
from jeromes_laboratory.workflow.scope_clarification import (
    DEFAULT_SCOPE_CLARIFICATION_PROMPT,
    SCOPE_CLARIFICATION_PROMPT_VERSION,
    ScopeAnswer,
    ScopeClarificationError,
    parse_scope_clarification_output,
    validate_scope_answers,
)
from jeromes_laboratory.workflow.scope_readiness import (
    DEFAULT_SCOPE_READINESS_PROMPT,
    SCOPE_READINESS_PROMPT_VERSION,
    ScopeReadinessError,
    parse_scope_readiness_output,
    validate_scope_readiness_against_input,
)

SCOPE_OUTPUT: dict[str, Any] = {
    "schema_version": 2,
    "introduction": "The population, evidence boundary, and sequencing remain open.",
    "questions": [
        {
            "id": "target_population",
            "question": "Which population should anchor the research?",
            "why_it_matters": "Population changes search terms and screening criteria.",
            "selection_mode": "single_choice",
            "option_structure": "independent",
            "options": [
                {
                    "id": "healthy_adults",
                    "label": "Healthy adults",
                    "description": "Prioritize muscle growth in otherwise healthy adults.",
                },
                {
                    "id": "muscle_wasting",
                    "label": "Muscle-wasting conditions",
                    "description": "Prioritize therapeutic use in disease-associated wasting.",
                },
            ],
        },
        {
            "id": "evidence_types",
            "question": "Which evidence types should be included?",
            "why_it_matters": "This controls databases, filters, and evidence synthesis.",
            "selection_mode": "multiple_choice",
            "option_structure": "independent",
            "options": [
                {
                    "id": "preclinical",
                    "label": "Preclinical",
                    "description": "Include in vitro and animal evidence.",
                },
                {
                    "id": "clinical",
                    "label": "Clinical",
                    "description": "Include human trials and observational evidence.",
                },
            ],
        },
        {
            "id": "track_order",
            "question": "How should the selected research tracks be sequenced?",
            "why_it_matters": "Sequencing prevents one broad request from becoming one unstructured search.",
            "selection_mode": "single_choice",
            "option_structure": "independent",
            "options": [
                {
                    "id": "evidence_first",
                    "label": "Evidence first",
                    "description": "Map known candidates before design work.",
                },
                {
                    "id": "parallel_tracks",
                    "label": "Parallel tracks",
                    "description": "Treat each selected objective as a coordinated track.",
                },
            ],
        },
    ],
}

READINESS_OUTPUT: dict[str, Any] = {
    "schema_version": 2,
    "ready_for_charter": False,
    "assessment": "One material application boundary remains unresolved.",
    "remaining_uncertainties": ["The intended population or application context is unclear."],
    "follow_up_questions": [
        {
            "id": "evidence_conflict_policy",
            "question": "How should conflicting findings across evidence tiers be organized?",
            "why_it_matters": "The decision determines whether unlike evidence is synthesized together.",
            "selection_mode": "single_choice",
            "option_structure": "independent",
            "options": [
                {
                    "id": "separate_tiers",
                    "label": "Separate evidence tiers",
                    "description": "Analyze computational, preclinical, and clinical findings separately.",
                },
                {
                    "id": "integrated_with_labels",
                    "label": "Integrate with explicit labels",
                    "description": "Synthesize tiers together while preserving their evidence type.",
                },
            ],
        }
    ],
}


class ScopeGateway:
    def __init__(self, output_text: str = json.dumps(SCOPE_OUTPUT)) -> None:
        self._output_text = output_text
        self._gateway = ProviderGenerationGateway()
        self.prepared_input: str | None = None

    def prepare(
        self, provider: ProviderName, model: str, instructions: str, input_content: str
    ) -> PreparedGeneration:
        self.prepared_input = input_content
        return self._gateway.prepare(provider, model, instructions, input_content)

    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        return GenerationResult(
            raw_response=json.dumps({"id": "scope-response", "output": self._output_text}),
            output_text=self._output_text,
            provider_request_id="scope-response",
            reported_model=str(prepared.request_body["model"]),
            usage={"input_tokens": 80, "output_tokens": 160, "total_tokens": 240},
            input_tokens=80,
            output_tokens=160,
            total_tokens=240,
            cached_input_tokens=None,
            reasoning_tokens=None,
            provider_metadata={"status": "completed"},
        )


def test_default_framing_prompts_separate_project_and_literature_scope() -> None:
    assert SCOPE_CLARIFICATION_PROMPT_VERSION == "6"
    assert SCOPE_READINESS_PROMPT_VERSION == "6"
    assert "therapeutic peptide discovery" in DEFAULT_SCOPE_CLARIFICATION_PROMPT
    assert "between 0 and 5" in DEFAULT_SCOPE_CLARIFICATION_PROMPT
    assert "scientific-source investigation and query planning" in (
        DEFAULT_SCOPE_CLARIFICATION_PROMPT
    )
    assert "multiple-choice question must always use independent" in (
        DEFAULT_SCOPE_CLARIFICATION_PROMPT
    )
    assert "Broad exploratory work is ready" in DEFAULT_SCOPE_READINESS_PROMPT
    assert "peptide quality" in DEFAULT_SCOPE_READINESS_PROMPT
    assert "study designs" in DEFAULT_SCOPE_READINESS_PROMPT
    assert "Never repeat or rephrase an answered question" in DEFAULT_SCOPE_READINESS_PROMPT


class ReadinessGateway(ScopeGateway):
    def __init__(self, output: dict[str, object] = READINESS_OUTPUT) -> None:
        super().__init__(json.dumps(output))


def configured_workspace(tmp_path: Path) -> tuple[WorkspaceService, Path]:
    service = WorkspaceService(
        configuration_directory=tmp_path / "config", documents_directory=tmp_path / "Documents"
    )
    workspace = tmp_path / "research"
    service.configure_workspace(str(workspace))
    return service, workspace


def completed_intent(tmp_path: Path) -> tuple[WorkspaceService, Path, JobRepository, str, str]:
    service, workspace = configured_workspace(tmp_path)
    database_path = workspace / DATABASE_FILE_NAME
    project = ProjectRepository(database_path).create_project("Can a peptide inhibit myostatin?")
    repository = JobRepository(database_path)
    intent = repository.enqueue_intent_clarification(project.id, "openai", "gpt-example")
    JobWorker(service, MemoryCredentialStore(), IntentGateway()).run_once()
    repository.submit_intent_selection(
        intent.id, "evidence_landscape", ["mechanism"], "Keep both tracks."
    )
    repository.edit_intent_selection(
        intent.id, "mechanism", ["evidence_landscape"], "Mechanism first.", 1
    )
    return service, database_path, repository, project.id, intent.id


def valid_answers() -> list[ScopeAnswer]:
    return [
        ScopeAnswer(question_id="target_population", selected_option_ids=["muscle_wasting"]),
        ScopeAnswer(
            question_id="evidence_types",
            selected_option_ids=["preclinical", "clinical"],
            note="Separate the evidence tiers.",
        ),
        ScopeAnswer(question_id="track_order", is_unsure=True),
    ]


def completed_scope(
    tmp_path: Path,
) -> tuple[WorkspaceService, Path, JobRepository, str, str]:
    service, database_path, repository, project_id, _ = completed_intent(tmp_path)
    scope = repository.enqueue_scope_clarification(project_id, "openai", "gpt-example")
    JobWorker(service, MemoryCredentialStore(), ScopeGateway()).run_once()
    repository.submit_scope_answers(scope.id, valid_answers())
    edited = valid_answers()
    edited[0] = ScopeAnswer(
        question_id="target_population",
        note="Include both populations and report them separately.",
    )
    repository.edit_scope_answers(scope.id, edited, 1)
    return service, database_path, repository, project_id, scope.id


def test_scope_output_and_answers_are_strictly_validated() -> None:
    questions = parse_scope_clarification_output(json.dumps(SCOPE_OUTPUT))
    validated = validate_scope_answers(questions, "questions-id", valid_answers())
    assert validated.answers[2].is_unsure is True

    with pytest.raises(ScopeClarificationError):
        parse_scope_clarification_output("A useful but unstructured questionnaire")

    missing_structure = json.loads(json.dumps(SCOPE_OUTPUT))
    del missing_structure["questions"][0]["option_structure"]
    with pytest.raises(ScopeClarificationError):
        parse_scope_clarification_output(json.dumps(missing_structure))

    cumulative_multiple = json.loads(json.dumps(SCOPE_OUTPUT))
    cumulative_multiple["questions"][1]["option_structure"] = "cumulative"
    with pytest.raises(ScopeClarificationError):
        parse_scope_clarification_output(json.dumps(cumulative_multiple))

    implicit_cumulative_multiple = json.loads(json.dumps(SCOPE_OUTPUT))
    implicit_cumulative_multiple["questions"][1]["options"][1]["description"] = (
        "Also includes all evidence from the preceding tier."
    )
    with pytest.raises(ScopeClarificationError):
        parse_scope_clarification_output(json.dumps(implicit_cumulative_multiple))

    legacy_output = json.loads(json.dumps(SCOPE_OUTPUT))
    legacy_output["schema_version"] = 1
    for question in legacy_output["questions"]:
        del question["option_structure"]
    assert parse_scope_clarification_output(json.dumps(legacy_output)).schema_version == 1
    empty_output = {
        "schema_version": 3,
        "introduction": "The selected direction is already framed for this cycle.",
        "questions": [],
    }
    assert parse_scope_clarification_output(json.dumps(empty_output)).questions == []
    with pytest.raises(ScopeClarificationError):
        parse_scope_clarification_output(json.dumps({**empty_output, "schema_version": 2}))
    with pytest.raises(ScopeClarificationError, match="single-choice"):
        validate_scope_answers(
            questions,
            "questions-id",
            [
                ScopeAnswer(
                    question_id="target_population",
                    selected_option_ids=["healthy_adults", "muscle_wasting"],
                ),
                *valid_answers()[1:],
            ],
        )
    uncertain_with_note = valid_answers()
    uncertain_with_note[2] = ScopeAnswer(
        question_id="track_order",
        note="I need help comparing these approaches.",
        is_unsure=True,
    )
    assert (
        validate_scope_answers(questions, "questions-id", uncertain_with_note).answers[2].note
        == "I need help comparing these approaches."
    )

    with pytest.raises(ScopeClarificationError, match="Not sure"):
        validate_scope_answers(
            questions,
            "questions-id",
            [
                *valid_answers()[:2],
                ScopeAnswer(
                    question_id="track_order",
                    selected_option_ids=["parallel_tracks"],
                    is_unsure=True,
                ),
            ],
        )


def test_scope_job_snapshots_effective_intent_and_versions_answers(tmp_path: Path) -> None:
    service, database_path, repository, project_id, intent_id = completed_intent(tmp_path)
    queued = repository.enqueue_scope_clarification(project_id, "openai", "gpt-example")
    snapshot = json.loads(queued.workflow_input_snapshot_json or "{}")
    assert snapshot["intent_selection_version"] == 2
    assert snapshot["primary_intent"]["id"] == "mechanism"
    assert snapshot["secondary_intents"][0]["id"] == "evidence_landscape"
    assert snapshot["user_note"] == "Mechanism first."
    assert provider_input_for_job(queued).endswith(queued.workflow_input_snapshot_json or "")
    assert repository.get_job(intent_id).intent_selection_is_editable is False

    gateway = ScopeGateway()
    assert JobWorker(service, MemoryCredentialStore(), gateway).run_once() is True
    completed = repository.get_job(queued.id)
    assert completed.scope_questions == SCOPE_OUTPUT
    assert gateway.prepared_input == provider_input_for_job(completed)

    confirmed = repository.submit_scope_answers(queued.id, valid_answers())
    assert confirmed.scope_answers_version == 1
    assert confirmed.scope_answers_is_editable is True
    edited_answers = valid_answers()
    edited_answers[0] = ScopeAnswer(
        question_id="target_population", note="Include both populations, reported separately."
    )
    edited = repository.edit_scope_answers(queued.id, edited_answers, 1)
    assert edited.scope_answers_version == 2
    assert edited.scope_answers is not None
    edited_payload = cast(dict[str, Any], edited.scope_answers)
    assert (
        edited_payload["answers"][0]["note"]
        == "Include both populations, reported separately."
    )

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        artifacts = connection.execute(
            "SELECT kind, content_json, content_sha256, creator_type, version_number "
            "FROM artifact_versions WHERE job_id = ? ORDER BY created_at",
            (queued.id,),
        ).fetchall()
    assert [row["kind"] for row in artifacts] == [
        "scope_clarification_questions",
        "scope_clarification_answers",
        "scope_clarification_answers",
    ]
    assert [row["version_number"] for row in artifacts] == [1, 1, 2]
    assert [row["creator_type"] for row in artifacts] == ["llm", "user", "user"]
    for row in artifacts:
        assert row["content_sha256"] == hashlib.sha256(row["content_json"].encode()).hexdigest()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "future-job",
                project_id,
                "research_charter",
                "pending",
                "9999-01-01T00:00:00+00:00",
                "openai",
                "gpt-example",
                "Question",
                "Future prompt",
                "research-charter",
                "1",
            ),
        )
    assert repository.get_job(queued.id).scope_answers_is_editable is False
    with pytest.raises(ValueError, match="downstream job"):
        repository.edit_scope_answers(queued.id, valid_answers(), 2)


def test_empty_peptide_framing_is_confirmed_without_fake_user_answers(
    tmp_path: Path,
) -> None:
    service, database_path, repository, project_id, _ = completed_intent(tmp_path)
    queued = repository.enqueue_scope_clarification(project_id, "openai", "gpt-example")
    empty_output = {
        "schema_version": 3,
        "introduction": "No additional user-controlled framing decision is needed.",
        "questions": [],
    }

    assert JobWorker(
        service,
        MemoryCredentialStore(),
        ScopeGateway(json.dumps(empty_output)),
    ).run_once() is True
    completed = repository.get_job(queued.id)

    assert completed.scope_questions == empty_output
    assert completed.scope_answers_version == 1
    assert completed.scope_answers is not None
    assert completed.scope_answers["answers"] == []
    with sqlite3.connect(database_path) as connection:
        artifacts = connection.execute(
            "SELECT kind, creator_type FROM artifact_versions WHERE job_id = ? "
            "ORDER BY rowid",
            (queued.id,),
        ).fetchall()
    assert artifacts == [
        ("scope_clarification_questions", "llm"),
        ("scope_clarification_answers", "application"),
    ]

    with pytest.raises(JobError, match="No framing check is required"):
        repository.enqueue_scope_readiness(project_id, "openai", "gpt-example")

    charter = repository.enqueue_research_charter(project_id, "openai", "gpt-example")
    snapshot = json.loads(charter.workflow_input_snapshot_json or "{}")
    assert snapshot["framing_input"]["scope_answers"]["answers"] == []
    assert snapshot["framing_check_source"] == "application_rule_no_questions"
    assert snapshot["readiness_job_id"] is None
    assert snapshot["readiness_artifact_id"] is None
    assert snapshot["readiness_review"] == {
        "assessment": (
            "No separate framing check was required because project framing identified "
            "no additional user-controlled decisions."
        ),
        "follow_up_questions": [],
        "ready_for_charter": True,
        "remaining_uncertainties": [],
        "schema_version": 2,
    }
    assert repository.get_job(queued.id).scope_answers_is_editable is False


def test_invalid_scope_response_fails_without_trusted_artifact(tmp_path: Path) -> None:
    service, database_path, repository, project_id, _ = completed_intent(tmp_path)
    queued = repository.enqueue_scope_clarification(project_id, "openai", "gpt-example")
    JobWorker(service, MemoryCredentialStore(), ScopeGateway("not json")).run_once()
    failed = repository.get_job(queued.id)
    assert failed.status == "failed"
    assert failed.error is not None and "valid scope-clarification" in failed.error
    with sqlite3.connect(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM artifact_versions WHERE job_id = ?", (queued.id,)
        ).fetchone()
    assert count == (0,)


def test_scope_readiness_output_enforces_bounded_follow_up() -> None:
    parsed = parse_scope_readiness_output(json.dumps(READINESS_OUTPUT))
    assert parsed.ready_for_charter is False
    assert len(parsed.follow_up_questions) == 1

    invalid_ready = {**READINESS_OUTPUT, "ready_for_charter": True}
    with pytest.raises(ScopeReadinessError):
        parse_scope_readiness_output(json.dumps(invalid_ready))

    invalid_not_ready = {**READINESS_OUTPUT, "follow_up_questions": []}
    with pytest.raises(ScopeReadinessError):
        parse_scope_readiness_output(json.dumps(invalid_not_ready))


def test_readiness_rejects_a_repeated_answered_question(tmp_path: Path) -> None:
    service, database_path, repository, project_id, _ = completed_scope(tmp_path)
    queued = repository.enqueue_scope_readiness(project_id, "openai", "gpt-example")
    repeated = {
        **READINESS_OUTPUT,
        "follow_up_questions": [
            {
                **SCOPE_OUTPUT["questions"][2],
                "id": "track_order_followup",
            }
        ],
    }

    assert queued.workflow_input_snapshot_json is not None
    parsed = parse_scope_readiness_output(json.dumps(repeated))
    with pytest.raises(ScopeReadinessError, match="repeated an already answered"):
        validate_scope_readiness_against_input(parsed, queued.workflow_input_snapshot_json)

    JobWorker(service, MemoryCredentialStore(), ReadinessGateway(repeated)).run_once()
    failed = repository.get_job(queued.id)
    assert failed.status == "failed"
    assert failed.error is not None and "repeated an already answered" in failed.error
    with sqlite3.connect(database_path) as connection:
        review_count = connection.execute(
            "SELECT COUNT(*) FROM artifact_versions "
            "WHERE job_id = ? AND kind = 'scope_readiness_review'",
            (queued.id,),
        ).fetchone()
        raw_response = connection.execute(
            "SELECT raw_response FROM llm_calls WHERE job_id = ?", (queued.id,)
        ).fetchone()
    assert review_count == (0,)
    assert raw_response is not None and "track_order_followup" in raw_response[0]


def test_readiness_snapshots_scope_version_and_versions_follow_up(tmp_path: Path) -> None:
    service, database_path, repository, project_id, scope_id = completed_scope(tmp_path)
    queued = repository.enqueue_scope_readiness(project_id, "openai", "gpt-example")
    snapshot = json.loads(queued.workflow_input_snapshot_json or "{}")
    assert snapshot["scope_answers_version"] == 2
    assert snapshot["scope_answers"]["answers"][0]["note"].startswith("Include both")
    assert repository.get_job(scope_id).scope_answers_is_editable is False

    gateway = ReadinessGateway()
    assert JobWorker(service, MemoryCredentialStore(), gateway).run_once() is True
    completed = repository.get_job(queued.id)
    assert completed.scope_readiness_review == READINESS_OUTPUT
    assert completed.scope_follow_up_answers is None
    assert gateway.prepared_input == provider_input_for_job(completed)

    first = [
        ScopeAnswer(
            question_id="evidence_conflict_policy",
            selected_option_ids=["separate_tiers"],
            note="Keep explicit links between tiers.",
        )
    ]
    confirmed = repository.submit_scope_follow_up_answers(queued.id, first)
    assert confirmed.scope_follow_up_answers_version == 1
    assert confirmed.scope_follow_up_answers_is_editable is True

    second = [
        ScopeAnswer(
            question_id="evidence_conflict_policy",
            selected_option_ids=["integrated_with_labels"],
            note="Preserve evidence labels in the integrated view.",
        )
    ]
    edited = repository.edit_scope_follow_up_answers(queued.id, second, 1)
    assert edited.scope_follow_up_answers_version == 2
    assert edited.scope_follow_up_answers is not None
    edited_payload = cast(dict[str, Any], edited.scope_follow_up_answers)
    assert edited_payload["answers"][0]["selected_option_ids"] == [
        "integrated_with_labels",
    ]

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT kind, version_number, creator_type FROM artifact_versions "
            "WHERE job_id = ? ORDER BY created_at",
            (queued.id,),
        ).fetchall()
    assert rows == [
        ("scope_readiness_review", 1, "llm"),
        ("scope_follow_up_answers", 1, "user"),
        ("scope_follow_up_answers", 2, "user"),
    ]


def test_ready_scope_has_no_follow_up_answers(tmp_path: Path) -> None:
    service, _, repository, project_id, _ = completed_scope(tmp_path)
    queued = repository.enqueue_scope_readiness(project_id, "openai", "gpt-example")
    ready_output = {
        "schema_version": 1,
        "ready_for_charter": True,
        "assessment": "The scope is explicit enough to construct the charter.",
        "remaining_uncertainties": ["The user accepted uncertainty about track timing."],
        "follow_up_questions": [],
    }
    JobWorker(service, MemoryCredentialStore(), ReadinessGateway(ready_output)).run_once()
    completed = repository.get_job(queued.id)
    assert completed.scope_readiness_review == ready_output
    with pytest.raises(ValueError, match="already declared ready"):
        repository.submit_scope_follow_up_answers(queued.id, [])
