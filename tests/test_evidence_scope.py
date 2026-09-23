"""Evidence-search scope questionnaire, provenance, and answer tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_jobs import MemoryCredentialStore
from test_scope_clarification import ReadinessGateway, ScopeGateway, completed_scope

from jeromes_laboratory.database.jobs import JobRepository, provider_input_for_job
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.storage.workspace import WorkspaceService
from jeromes_laboratory.workflow.evidence_scope import (
    DEFAULT_EVIDENCE_SCOPE_PROMPT,
    EVIDENCE_SCOPE_PROMPT_VERSION,
    EvidenceScopeError,
    parse_evidence_scope_output,
)
from jeromes_laboratory.workflow.scope_clarification import ScopeAnswer

EVIDENCE_SCOPE_OUTPUT: dict[str, Any] = {
    "schema_version": 1,
    "introduction": "The charter requires identity, mechanism, and liability evidence.",
    "charter_evidence_themes": [
        {
            "id": "peptide_identity",
            "label": "Peptide identity and reported activity",
            "purpose": "Disambiguate the fixed peptide and map its reported biological activity.",
            "evidence_domains": ["peptide identity", "sequence", "bioactivity"],
            "negative_evidence_required": False,
        },
        {
            "id": "mechanism_and_translation",
            "label": "Mechanism and translational coherence",
            "purpose": "Test whether reported activity has a reproducible mechanistic basis.",
            "evidence_domains": ["target", "pathway", "cellular", "animal", "human"],
            "negative_evidence_required": True,
        },
    ],
    "questions": [
        {
            "id": "related_peptide_breadth",
            "question": "How broadly should related peptide evidence be retrieved?",
            "why_it_matters": "Related analogues may clarify activity while broad families add noise.",
            "selection_mode": "single_choice",
            "option_structure": "cumulative",
            "options": [
                {
                    "id": "exact_peptide",
                    "label": "Exact peptide only",
                    "description": "Retrieve records explicitly concerning the fixed peptide and aliases.",
                },
                {
                    "id": "peptide_and_analogues",
                    "label": "Peptide and direct analogues",
                    "description": "Include the exact peptide plus explicitly derived or close analogues.",
                },
            ],
            "recommended_option_ids": ["peptide_and_analogues"],
            "recommendation_reason": "Direct analogues can help distinguish retained activity.",
        },
        {
            "id": "evidence_stages",
            "question": "Which evidence stages should be retrieved?",
            "why_it_matters": "Separate evidence stages answer different parts of the charter.",
            "selection_mode": "multiple_choice",
            "option_structure": "independent",
            "options": [
                {
                    "id": "mechanistic",
                    "label": "Mechanistic and cellular",
                    "description": "Retrieve biochemical and cellular observations.",
                },
                {
                    "id": "animal",
                    "label": "Animal",
                    "description": "Retrieve in-vivo animal observations as a separate stratum.",
                },
                {
                    "id": "human",
                    "label": "Human",
                    "description": "Retrieve human observational and interventional evidence.",
                },
            ],
            "recommended_option_ids": ["mechanistic", "animal", "human"],
            "recommendation_reason": "The broad charter requires each available stage, kept separate.",
        },
    ],
}


def approved_charter(
    tmp_path: Path,
) -> tuple[WorkspaceService, Path, JobRepository, str]:
    service, database_path, repository, project_id, _ = completed_scope(tmp_path)
    readiness = repository.enqueue_scope_readiness(project_id, "openai", "gpt-example")
    ready_output = {
        "schema_version": 2,
        "ready_for_charter": True,
        "assessment": "The investigation can be represented faithfully.",
        "remaining_uncertainties": ["The evidence stages remain to be scoped."],
        "follow_up_questions": [],
    }
    JobWorker(service, MemoryCredentialStore(), ReadinessGateway(ready_output)).run_once()
    assert repository.get_job(readiness.id).status == "completed"
    charter = repository.enqueue_research_charter(project_id, "openai", "gpt-example")
    JobWorker(
        service,
        MemoryCredentialStore(),
        ScopeGateway("## Charter\n\nMap peptide identity, mechanism, and liabilities."),
    ).run_once()
    repository.approve_research_charter(charter.id, 1)
    return service, database_path, repository, project_id


def test_prompt_and_output_schema_enforce_scientific_scope_rules() -> None:
    assert EVIDENCE_SCOPE_PROMPT_VERSION == "1"
    assert "Every current evidence objective" in DEFAULT_EVIDENCE_SCOPE_PROMPT
    assert "negative, null, contradictory" in DEFAULT_EVIDENCE_SCOPE_PROMPT
    assert "Do not generate database query syntax" in DEFAULT_EVIDENCE_SCOPE_PROMPT
    parsed = parse_evidence_scope_output(json.dumps(EVIDENCE_SCOPE_OUTPUT))
    assert len(parsed.charter_evidence_themes) == 2
    assert parsed.questions[0].recommended_option_ids == ["peptide_and_analogues"]

    invalid = json.loads(json.dumps(EVIDENCE_SCOPE_OUTPUT))
    invalid["questions"][0]["recommended_option_ids"] = ["missing_option"]
    with pytest.raises(EvidenceScopeError):
        parse_evidence_scope_output(json.dumps(invalid))


def test_questionnaire_consumes_approved_charter_and_versions_answers(tmp_path: Path) -> None:
    service, database_path, repository, project_id = approved_charter(tmp_path)
    queued = repository.enqueue_evidence_scope_questionnaire(
        project_id, "openai", "gpt-example"
    )
    snapshot = json.loads(queued.workflow_input_snapshot_json or "{}")
    approved = snapshot["approved_research_charter"]
    assert approved["charter_markdown"].startswith("## Charter")
    assert approved["charter_artifact_id"]
    assert "approved_research_charter" in provider_input_for_job(queued)

    JobWorker(
        service,
        MemoryCredentialStore(),
        ScopeGateway(json.dumps(EVIDENCE_SCOPE_OUTPUT)),
    ).run_once()
    completed = repository.get_job(queued.id)
    assert completed.status == "completed"
    assert completed.evidence_scope_questions is not None
    answers = [
        ScopeAnswer(
            question_id="related_peptide_breadth",
            selected_option_ids=["peptide_and_analogues"],
        ),
        ScopeAnswer(
            question_id="evidence_stages",
            selected_option_ids=["mechanistic", "animal", "human"],
            note="Keep the stages separate during synthesis.",
        ),
    ]
    repository.submit_evidence_scope_answers(queued.id, answers)
    saved = repository.get_job(queued.id)
    assert saved.evidence_scope_answers_version == 1
    assert saved.evidence_scope_answers_is_editable is True

    edited = list(answers)
    edited[0] = ScopeAnswer(
        question_id="related_peptide_breadth",
        selected_option_ids=["exact_peptide"],
    )
    repository.edit_evidence_scope_answers(queued.id, edited, 1)
    current = repository.get_job(queued.id)
    assert current.evidence_scope_answers_version == 2

    with sqlite3.connect(database_path) as connection:
        artifacts = connection.execute(
            "SELECT kind, content_json, content_sha256, byte_size, creator_type "
            "FROM artifact_versions WHERE job_id = ? ORDER BY version_number, kind",
            (queued.id,),
        ).fetchall()
    assert {artifact[0] for artifact in artifacts} == {
        "evidence_scope_questions",
        "evidence_scope_answers",
    }
    assert [artifact[4] for artifact in artifacts].count("user") == 2
    for _, content_json, digest, byte_size, _ in artifacts:
        encoded = content_json.encode("utf-8")
        assert digest == hashlib.sha256(encoded).hexdigest()
        assert byte_size == len(encoded)


def test_zero_question_scope_is_confirmed_by_application(tmp_path: Path) -> None:
    service, _, repository, project_id = approved_charter(tmp_path)
    output = json.loads(json.dumps(EVIDENCE_SCOPE_OUTPUT))
    output["questions"] = []
    queued = repository.enqueue_evidence_scope_questionnaire(
        project_id, "openai", "gpt-example"
    )
    JobWorker(
        service, MemoryCredentialStore(), ScopeGateway(json.dumps(output))
    ).run_once()
    completed = repository.get_job(queued.id)
    assert completed.evidence_scope_answers is not None
    assert completed.evidence_scope_answers["schema_version"] == 1
    assert completed.evidence_scope_answers["answers"] == []
