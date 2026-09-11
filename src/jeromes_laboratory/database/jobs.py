"""Persistent single-worker queue and LLM provenance repository."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from jeromes_laboratory.llm.catalog import ProviderName
from jeromes_laboratory.llm.generation import GenerationResult, PreparedGeneration
from jeromes_laboratory.workflow.intent_clarification import (
    IntentClarificationError,
    IntentClarificationOutput,
    IntentSelection,
    parse_intent_clarification_output,
)
from jeromes_laboratory.workflow.scope_clarification import (
    ScopeAnswer,
    ScopeAnswers,
    ScopeClarificationError,
    ScopeClarificationOutput,
    parse_scope_clarification_output,
    validate_scope_answers,
)
from jeromes_laboratory.workflow.scope_readiness import (
    ScopeReadinessError,
    ScopeReadinessOutput,
    parse_scope_readiness_output,
    validate_scope_readiness_against_input,
)

JobStatus = Literal["pending", "awaiting_response", "completed", "failed", "cancelled"]


class JobError(ValueError):
    """Raised when a queue operation cannot be performed."""


@dataclass(frozen=True)
class JobRecord:
    """Durable question-detailing job state safe for the local UI."""

    id: str
    project_id: str
    project_tag: str
    kind: str
    status: JobStatus
    created_at: str
    started_at: str | None
    completed_at: str | None
    provider: ProviderName
    model: str
    scientific_question_snapshot: str
    prompt_snapshot: str
    prompt_template_version: str
    workflow_input_snapshot_json: str | None
    error: str | None
    output_markdown: str | None
    original_output_markdown: str | None
    effective_output_markdown: str | None
    effective_output_version: int | None
    output_was_edited: bool
    llm_call_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: int | None
    cost_status: str | None
    intent_questions: dict[str, object] | None
    intent_selection: dict[str, object] | None
    intent_selection_version: int | None
    intent_selection_is_editable: bool
    scope_questions: dict[str, object] | None
    scope_answers: dict[str, object] | None
    scope_answers_version: int | None
    scope_answers_is_editable: bool
    scope_readiness_review: dict[str, object] | None
    scope_follow_up_answers: dict[str, object] | None
    scope_follow_up_answers_version: int | None
    scope_follow_up_answers_is_editable: bool


class JobRepository:
    """Use short SQLite transactions for queue ordering and state transitions."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @property
    def database_path(self) -> Path:
        return self._database_path

    def enqueue_question_detailing(
        self, project_id: str, provider: ProviderName, model: str
    ) -> JobRecord:
        now = _timestamp()
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute(
                "SELECT scientific_question, question_detailing_prompt, "
                "question_detailing_prompt_version FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise JobError("The selected project no longer exists.")
            existing = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'question_detailing' "
                "AND status IN ('pending', 'awaiting_response', 'completed')",
                (project_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("Question detailing has already been started for this project.")
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version) VALUES (?, ?, 'question_detailing', 'pending', ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    project_id,
                    now,
                    provider,
                    model,
                    project["scientific_question"],
                    project["question_detailing_prompt"],
                    "question-detailing",
                    project["question_detailing_prompt_version"],
                ),
            )
        return self.get_job(job_id)

    def enqueue_intent_clarification(
        self, project_id: str, provider: ProviderName, model: str
    ) -> JobRecord:
        """Snapshot the inputs for one intent-clarification attempt."""
        now = _timestamp()
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute(
                "SELECT scientific_question, intent_clarification_prompt, "
                "intent_clarification_prompt_version FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise JobError("The selected project no longer exists.")
            legacy = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'question_detailing'",
                (project_id,),
            ).fetchone()
            if legacy is not None:
                raise JobError("This project already uses the legacy question-detailing workflow.")
            existing = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'intent_clarification' "
                "AND status IN ('pending', 'awaiting_response', 'completed')",
                (project_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("Intent clarification has already been started for this project.")
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version) VALUES (?, ?, 'intent_clarification', 'pending', "
                "?, ?, ?, ?, ?, 'intent-clarification', ?)",
                (
                    job_id,
                    project_id,
                    now,
                    provider,
                    model,
                    project["scientific_question"],
                    project["intent_clarification_prompt"],
                    project["intent_clarification_prompt_version"],
                ),
            )
        return self.get_job(job_id)

    def enqueue_scope_clarification(
        self, project_id: str, provider: ProviderName, model: str
    ) -> JobRecord:
        """Snapshot the exact effective intent and queue first-round scope questions."""
        now = _timestamp()
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute(
                "SELECT scientific_question, scope_clarification_prompt, "
                "scope_clarification_prompt_version FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise JobError("The selected project no longer exists.")
            existing = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? "
                "AND kind = 'scope_clarification_round_1' "
                "AND status IN ('pending', 'awaiting_response', 'completed')",
                (project_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("Scope clarification has already been started for this project.")
            intent = connection.execute(
                "SELECT questions.id AS questions_artifact_id, "
                "questions.content_json AS questions_json, "
                "selection.id AS selection_artifact_id, "
                "selection.version_number AS selection_version, "
                "selection.content_json AS selection_json "
                "FROM jobs intent_job "
                "JOIN artifact_versions questions ON questions.job_id = intent_job.id "
                "AND questions.kind = 'intent_clarification_questions' "
                "JOIN artifact_effective_versions effective ON effective.job_id = intent_job.id "
                "JOIN artifact_versions selection ON selection.id = effective.artifact_version_id "
                "AND selection.kind = 'intent_clarification_selection' "
                "WHERE intent_job.project_id = ? AND intent_job.kind = 'intent_clarification' "
                "AND intent_job.status = 'completed' ORDER BY intent_job.created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if intent is None:
                raise JobError("Confirm the research intent before clarifying the scope.")
            workflow_input = _scope_input_snapshot(
                project["scientific_question"],
                intent["questions_artifact_id"],
                intent["questions_json"],
                intent["selection_artifact_id"],
                intent["selection_version"],
                intent["selection_json"],
            )
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version, workflow_input_snapshot_json) "
                "VALUES (?, ?, 'scope_clarification_round_1', 'pending', ?, ?, ?, ?, ?, "
                "'scope-clarification-round-1', ?, ?)",
                (
                    job_id,
                    project_id,
                    now,
                    provider,
                    model,
                    project["scientific_question"],
                    project["scope_clarification_prompt"],
                    project["scope_clarification_prompt_version"],
                    workflow_input,
                ),
            )
        return self.get_job(job_id)

    def enqueue_scope_readiness(
        self, project_id: str, provider: ProviderName, model: str
    ) -> JobRecord:
        """Queue a bounded readiness review from the exact effective first-round answers."""
        now = _timestamp()
        job_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute(
                "SELECT scientific_question, scope_readiness_prompt, "
                "scope_readiness_prompt_version FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise JobError("The selected project no longer exists.")
            existing = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'scope_readiness' "
                "AND status IN ('pending', 'awaiting_response', 'completed')",
                (project_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("Scope readiness has already been started for this project.")
            scope = connection.execute(
                "SELECT scope_job.workflow_input_snapshot_json, "
                "questions.id AS questions_artifact_id, questions.content_json AS questions_json, "
                "answers.id AS answers_artifact_id, answers.version_number AS answers_version, "
                "answers.content_json AS answers_json "
                "FROM jobs scope_job "
                "JOIN artifact_versions questions ON questions.job_id = scope_job.id "
                "AND questions.kind = 'scope_clarification_questions' "
                "JOIN artifact_effective_versions effective ON effective.job_id = scope_job.id "
                "JOIN artifact_versions answers ON answers.id = effective.artifact_version_id "
                "AND answers.kind = 'scope_clarification_answers' "
                "WHERE scope_job.project_id = ? "
                "AND scope_job.kind = 'scope_clarification_round_1' "
                "AND scope_job.status = 'completed' ORDER BY scope_job.created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if scope is None:
                raise JobError("Confirm the first scope answers before reviewing readiness.")
            workflow_input = _readiness_input_snapshot(
                scope["workflow_input_snapshot_json"],
                scope["questions_artifact_id"],
                scope["questions_json"],
                scope["answers_artifact_id"],
                scope["answers_version"],
                scope["answers_json"],
            )
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version, workflow_input_snapshot_json) "
                "VALUES (?, ?, 'scope_readiness', 'pending', ?, ?, ?, ?, ?, "
                "'scope-readiness', ?, ?)",
                (
                    job_id,
                    project_id,
                    now,
                    provider,
                    model,
                    project["scientific_question"],
                    project["scope_readiness_prompt"],
                    project["scope_readiness_prompt_version"],
                    workflow_input,
                ),
            )
        return self.get_job(job_id)

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                self._select_sql() + " ORDER BY jobs.created_at DESC"
            ).fetchall()
        return [self._record(row) for row in rows]

    def get_job(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute(
                self._select_sql() + " WHERE jobs.id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise JobError("The selected job no longer exists.")
        return self._record(row)

    def cancel(self, job_id: str) -> JobRecord:
        now = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE jobs SET status = 'cancelled', completed_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (now, job_id),
            )
            if cursor.rowcount == 0:
                row = connection.execute(
                    "SELECT status FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    raise JobError("The selected job no longer exists.")
                raise JobError(
                    "This job can no longer be cancelled because provider dispatch began."
                )
        return self.get_job(job_id)

    def claim_next(self) -> JobRecord | None:
        """Atomically close cancellation immediately before provider preparation."""
        now = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM jobs WHERE status = 'pending' ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            cursor = connection.execute(
                "UPDATE jobs SET status = 'awaiting_response', started_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (now, row["id"]),
            )
            if cursor.rowcount != 1:
                return None
        return self.get_job(row["id"])

    def begin_llm_call(self, job: JobRecord, prepared: PreparedGeneration) -> str:
        call_id = str(uuid4())
        input_content = provider_input_for_job(job)
        if job.kind == "intent_clarification":
            prompt_template_id = "intent-clarification"
            purpose = "Generate research-intent choices for user clarification"
        elif job.kind == "question_detailing":
            prompt_template_id = "question-detailing"
            purpose = "Develop the scientific question for literature-search planning"
        elif job.kind == "scope_clarification_round_1":
            prompt_template_id = "scope-clarification-round-1"
            purpose = "Generate material scope decisions from the confirmed research intent"
        elif job.kind == "scope_readiness":
            prompt_template_id = "scope-readiness"
            purpose = "Evaluate scope readiness and generate the only follow-up round if needed"
        else:
            raise JobError(f"Unsupported LLM job kind: {job.kind}")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO llm_calls (id, project_id, job_id, provider, model, operation, "
                "purpose, prompt_template_id, prompt_template_version, instructions, input_content, "
                "request_json, started_at, status, retry_count, generation_settings_json, cost_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'started', 0, ?, 'unavailable')",
                (
                    call_id,
                    job.project_id,
                    job.id,
                    job.provider,
                    job.model,
                    prepared.operation,
                    purpose,
                    prompt_template_id,
                    job.prompt_template_version,
                    job.prompt_snapshot,
                    input_content,
                    _json(prepared.request_body),
                    _timestamp(),
                    _json(prepared.generation_settings),
                ),
            )
        return call_id

    def complete(self, job_id: str, call_id: str, result: GenerationResult) -> JobRecord:
        now = _timestamp()
        job = self.get_job(job_id)
        if job.kind == "intent_clarification":
            try:
                parsed_intents = parse_intent_clarification_output(result.output_text)
            except IntentClarificationError as error:
                raise JobError(str(error)) from error
            artifact_payload = parsed_intents.model_dump(mode="json")
            artifact_kind = "intent_clarification_questions"
        elif job.kind == "scope_clarification_round_1":
            try:
                parsed_scope = parse_scope_clarification_output(result.output_text)
            except ScopeClarificationError as error:
                raise JobError(str(error)) from error
            artifact_payload = parsed_scope.model_dump(mode="json")
            artifact_kind = "scope_clarification_questions"
        elif job.kind == "scope_readiness":
            try:
                parsed_readiness = parse_scope_readiness_output(result.output_text)
                parsed_readiness = validate_scope_readiness_against_input(
                    parsed_readiness, job.workflow_input_snapshot_json
                )
            except ScopeReadinessError as error:
                raise JobError(str(error)) from error
            artifact_payload = parsed_readiness.model_dump(mode="json")
            artifact_kind = "scope_readiness_review"
        elif job.kind == "question_detailing":
            artifact_payload = {
                "schema_version": 1,
                "content_type": "text/markdown",
                "detailed_question": result.output_text,
            }
            artifact_kind = "question_detailing_output"
        else:
            raise JobError(f"Unsupported LLM job kind: {job.kind}")
        content_json = _json(artifact_payload)
        content_bytes = content_json.encode("utf-8")
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            started = connection.execute(
                "SELECT started_at FROM llm_calls WHERE id = ? AND job_id = ?",
                (call_id, job_id),
            ).fetchone()
            if started is None:
                raise JobError("The LLM call record no longer exists.")
            duration_ms = _duration_ms(started["started_at"], now)
            connection.execute(
                "UPDATE llm_calls SET reported_model = ?, raw_response = ?, parsed_output_json = ?, "
                "provider_request_id = ?, completed_at = ?, duration_ms = ?, status = 'completed', "
                "usage_json = ?, input_tokens = ?, output_tokens = ?, total_tokens = ?, "
                "cached_input_tokens = ?, reasoning_tokens = ?, provider_metadata_json = ? "
                "WHERE id = ?",
                (
                    result.reported_model,
                    result.raw_response,
                    content_json,
                    result.provider_request_id,
                    now,
                    duration_ms,
                    _json(result.usage) if result.usage is not None else None,
                    result.input_tokens,
                    result.output_tokens,
                    result.total_tokens,
                    result.cached_input_tokens,
                    result.reasoning_tokens,
                    _json(result.provider_metadata),
                    call_id,
                ),
            )
            connection.execute(
                "INSERT INTO artifact_versions (id, project_id, job_id, llm_call_id, kind, "
                "content_type, content_json, content_sha256, byte_size, creator_type, "
                "version_number, created_at) SELECT ?, project_id, id, ?, ?, ?, ?, ?, ?, 'llm', 1, ? "
                "FROM jobs WHERE id = ?",
                (
                    artifact_id,
                    call_id,
                    artifact_kind,
                    "application/json",
                    content_json,
                    hashlib.sha256(content_bytes).hexdigest(),
                    len(content_bytes),
                    now,
                    job_id,
                ),
            )
            if job.kind == "question_detailing":
                connection.execute(
                    "INSERT INTO artifact_effective_versions "
                    "(job_id, artifact_version_id, selected_at, selection_reason) "
                    "VALUES (?, ?, ?, 'original_output')",
                    (job_id, artifact_id, now),
                )
            connection.execute(
                "UPDATE jobs SET status = 'completed', completed_at = ? WHERE id = ?",
                (now, job_id),
            )
        return self.get_job(job_id)

    def submit_intent_selection(
        self,
        job_id: str,
        primary_intent_id: str,
        secondary_intent_ids: list[str],
        note: str,
    ) -> JobRecord:
        """Persist one immutable user decision over the generated intent choices."""
        now = _timestamp()
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT jobs.project_id, llm_calls.id AS llm_call_id, "
                "questions.id AS questions_artifact_id, questions.content_json "
                "FROM jobs JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_versions questions ON questions.job_id = jobs.id "
                "AND questions.kind = 'intent_clarification_questions' "
                "WHERE jobs.id = ? AND jobs.kind = 'intent_clarification' "
                "AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("Intent choices are not ready for this job.")
            existing = connection.execute(
                "SELECT 1 FROM artifact_versions WHERE job_id = ? "
                "AND kind = 'intent_clarification_selection'",
                (job_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("The research intent has already been confirmed.")

            questions = IntentClarificationOutput.model_validate_json(row["content_json"])
            selection = _validated_intent_selection(
                questions,
                row["questions_artifact_id"],
                primary_intent_id,
                secondary_intent_ids,
                note,
            )
            content_json = _json(selection.model_dump(mode="json"))
            content_bytes = content_json.encode("utf-8")
            connection.execute(
                "INSERT INTO artifact_versions (id, project_id, job_id, llm_call_id, kind, "
                "content_type, content_json, content_sha256, byte_size, creator_type, "
                "version_number, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 1, ?)",
                (
                    artifact_id,
                    row["project_id"],
                    job_id,
                    row["llm_call_id"],
                    "intent_clarification_selection",
                    "application/json",
                    content_json,
                    hashlib.sha256(content_bytes).hexdigest(),
                    len(content_bytes),
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO artifact_effective_versions "
                "(job_id, artifact_version_id, selected_at, selection_reason) "
                "VALUES (?, ?, ?, 'confirmed_intent')",
                (job_id, artifact_id, now),
            )
        return self.get_job(job_id)

    def edit_intent_selection(
        self,
        job_id: str,
        primary_intent_id: str,
        secondary_intent_ids: list[str],
        note: str,
        base_version: int,
    ) -> JobRecord:
        """Create a new effective intent version before downstream work is queued."""
        now = _timestamp()
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT jobs.project_id, jobs.created_at AS job_created_at, "
                "llm_calls.id AS llm_call_id, questions.id AS questions_artifact_id, "
                "questions.content_json AS questions_json, current.version_number "
                "FROM jobs JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_versions questions ON questions.job_id = jobs.id "
                "AND questions.kind = 'intent_clarification_questions' "
                "JOIN artifact_effective_versions effective ON effective.job_id = jobs.id "
                "JOIN artifact_versions current ON current.id = effective.artifact_version_id "
                "AND current.kind = 'intent_clarification_selection' "
                "WHERE jobs.id = ? AND jobs.kind = 'intent_clarification' "
                "AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("Only a confirmed research intent can be edited.")
            downstream = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND id != ? AND created_at > ? LIMIT 1",
                (row["project_id"], job_id, row["job_created_at"]),
            ).fetchone()
            if downstream is not None:
                raise JobError(
                    "The research intent is locked because a downstream job has been queued."
                )
            if row["version_number"] != base_version:
                raise JobError(
                    "This research intent was edited elsewhere. Reload it before saving."
                )
            questions = IntentClarificationOutput.model_validate_json(row["questions_json"])
            selection = _validated_intent_selection(
                questions,
                row["questions_artifact_id"],
                primary_intent_id,
                secondary_intent_ids,
                note,
            )
            next_version = base_version + 1
            content_json = _json(selection.model_dump(mode="json"))
            content_bytes = content_json.encode("utf-8")
            connection.execute(
                "INSERT INTO artifact_versions (id, project_id, job_id, llm_call_id, kind, "
                "content_type, content_json, content_sha256, byte_size, creator_type, "
                "version_number, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', ?, ?)",
                (
                    artifact_id,
                    row["project_id"],
                    job_id,
                    row["llm_call_id"],
                    "intent_clarification_selection",
                    "application/json",
                    content_json,
                    hashlib.sha256(content_bytes).hexdigest(),
                    len(content_bytes),
                    next_version,
                    now,
                ),
            )
            connection.execute(
                "UPDATE artifact_effective_versions SET artifact_version_id = ?, "
                "selected_at = ?, selection_reason = 'user_edit' WHERE job_id = ?",
                (artifact_id, now, job_id),
            )
        return self.get_job(job_id)

    def submit_scope_answers(self, job_id: str, answers: list[ScopeAnswer]) -> JobRecord:
        """Persist the first complete, immutable answer set for a scope round."""
        now = _timestamp()
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT jobs.project_id, llm_calls.id AS llm_call_id, "
                "questions.id AS questions_artifact_id, questions.content_json "
                "FROM jobs JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_versions questions ON questions.job_id = jobs.id "
                "AND questions.kind = 'scope_clarification_questions' "
                "WHERE jobs.id = ? AND jobs.kind = 'scope_clarification_round_1' "
                "AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("Scope questions are not ready for this job.")
            existing = connection.execute(
                "SELECT 1 FROM artifact_versions WHERE job_id = ? "
                "AND kind = 'scope_clarification_answers'",
                (job_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("The scope answers have already been confirmed.")
            questions = ScopeClarificationOutput.model_validate_json(row["content_json"])
            try:
                validated = validate_scope_answers(questions, row["questions_artifact_id"], answers)
            except (ScopeClarificationError, ValueError) as error:
                raise JobError(str(error)) from error
            content_json = _json(validated.model_dump(mode="json"))
            self._insert_user_artifact(
                connection,
                artifact_id=artifact_id,
                project_id=row["project_id"],
                job_id=job_id,
                llm_call_id=row["llm_call_id"],
                kind="scope_clarification_answers",
                content_json=content_json,
                version=1,
                created_at=now,
            )
            connection.execute(
                "INSERT INTO artifact_effective_versions "
                "(job_id, artifact_version_id, selected_at, selection_reason) "
                "VALUES (?, ?, ?, 'confirmed_scope_answers')",
                (job_id, artifact_id, now),
            )
        return self.get_job(job_id)

    def edit_scope_answers(
        self, job_id: str, answers: list[ScopeAnswer], base_version: int
    ) -> JobRecord:
        """Select a new immutable answer version before downstream work is queued."""
        now = _timestamp()
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT jobs.project_id, jobs.created_at AS job_created_at, "
                "llm_calls.id AS llm_call_id, questions.id AS questions_artifact_id, "
                "questions.content_json AS questions_json, current.version_number "
                "FROM jobs JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_versions questions ON questions.job_id = jobs.id "
                "AND questions.kind = 'scope_clarification_questions' "
                "JOIN artifact_effective_versions effective ON effective.job_id = jobs.id "
                "JOIN artifact_versions current ON current.id = effective.artifact_version_id "
                "AND current.kind = 'scope_clarification_answers' "
                "WHERE jobs.id = ? AND jobs.kind = 'scope_clarification_round_1' "
                "AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("Only confirmed scope answers can be edited.")
            downstream = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND id != ? AND created_at > ? LIMIT 1",
                (row["project_id"], job_id, row["job_created_at"]),
            ).fetchone()
            if downstream is not None:
                raise JobError("The scope answers are locked because a downstream job was queued.")
            if row["version_number"] != base_version:
                raise JobError("These scope answers were edited elsewhere. Reload before saving.")
            questions = ScopeClarificationOutput.model_validate_json(row["questions_json"])
            try:
                validated = validate_scope_answers(questions, row["questions_artifact_id"], answers)
            except (ScopeClarificationError, ValueError) as error:
                raise JobError(str(error)) from error
            content_json = _json(validated.model_dump(mode="json"))
            self._insert_user_artifact(
                connection,
                artifact_id=artifact_id,
                project_id=row["project_id"],
                job_id=job_id,
                llm_call_id=row["llm_call_id"],
                kind="scope_clarification_answers",
                content_json=content_json,
                version=base_version + 1,
                created_at=now,
            )
            connection.execute(
                "UPDATE artifact_effective_versions SET artifact_version_id = ?, "
                "selected_at = ?, selection_reason = 'user_edit' WHERE job_id = ?",
                (artifact_id, now, job_id),
            )
        return self.get_job(job_id)

    def submit_scope_follow_up_answers(self, job_id: str, answers: list[ScopeAnswer]) -> JobRecord:
        """Persist the only follow-up round after a not-ready review."""
        now = _timestamp()
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT jobs.project_id, llm_calls.id AS llm_call_id, "
                "review.id AS review_artifact_id, review.content_json "
                "FROM jobs JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_versions review ON review.job_id = jobs.id "
                "AND review.kind = 'scope_readiness_review' "
                "WHERE jobs.id = ? AND jobs.kind = 'scope_readiness' "
                "AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("The scope-readiness review is not available.")
            existing = connection.execute(
                "SELECT 1 FROM artifact_versions WHERE job_id = ? "
                "AND kind = 'scope_follow_up_answers'",
                (job_id,),
            ).fetchone()
            if existing is not None:
                raise JobError("The follow-up answers have already been confirmed.")
            validated = _validated_follow_up_answers(
                row["content_json"], row["review_artifact_id"], answers
            )
            content_json = _json(validated.model_dump(mode="json"))
            self._insert_user_artifact(
                connection,
                artifact_id=artifact_id,
                project_id=row["project_id"],
                job_id=job_id,
                llm_call_id=row["llm_call_id"],
                kind="scope_follow_up_answers",
                content_json=content_json,
                version=1,
                created_at=now,
            )
            connection.execute(
                "INSERT INTO artifact_effective_versions "
                "(job_id, artifact_version_id, selected_at, selection_reason) "
                "VALUES (?, ?, ?, 'confirmed_scope_follow_up')",
                (job_id, artifact_id, now),
            )
        return self.get_job(job_id)

    def edit_scope_follow_up_answers(
        self, job_id: str, answers: list[ScopeAnswer], base_version: int
    ) -> JobRecord:
        """Create a new effective follow-up answer version before charter enqueueing."""
        now = _timestamp()
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT jobs.project_id, jobs.created_at AS job_created_at, "
                "llm_calls.id AS llm_call_id, review.id AS review_artifact_id, "
                "review.content_json AS review_json, current.version_number "
                "FROM jobs JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_versions review ON review.job_id = jobs.id "
                "AND review.kind = 'scope_readiness_review' "
                "JOIN artifact_effective_versions effective ON effective.job_id = jobs.id "
                "JOIN artifact_versions current ON current.id = effective.artifact_version_id "
                "AND current.kind = 'scope_follow_up_answers' "
                "WHERE jobs.id = ? AND jobs.kind = 'scope_readiness' "
                "AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if row is None:
                raise JobError("Only confirmed follow-up answers can be edited.")
            downstream = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND id != ? AND created_at > ? LIMIT 1",
                (row["project_id"], job_id, row["job_created_at"]),
            ).fetchone()
            if downstream is not None:
                raise JobError(
                    "The follow-up answers are locked because a downstream job was queued."
                )
            if row["version_number"] != base_version:
                raise JobError(
                    "These follow-up answers were edited elsewhere. Reload before saving."
                )
            validated = _validated_follow_up_answers(
                row["review_json"], row["review_artifact_id"], answers
            )
            content_json = _json(validated.model_dump(mode="json"))
            self._insert_user_artifact(
                connection,
                artifact_id=artifact_id,
                project_id=row["project_id"],
                job_id=job_id,
                llm_call_id=row["llm_call_id"],
                kind="scope_follow_up_answers",
                content_json=content_json,
                version=base_version + 1,
                created_at=now,
            )
            connection.execute(
                "UPDATE artifact_effective_versions SET artifact_version_id = ?, "
                "selected_at = ?, selection_reason = 'user_edit' WHERE job_id = ?",
                (artifact_id, now, job_id),
            )
        return self.get_job(job_id)

    @staticmethod
    def _insert_user_artifact(
        connection: sqlite3.Connection,
        *,
        artifact_id: str,
        project_id: str,
        job_id: str,
        llm_call_id: str,
        kind: str,
        content_json: str,
        version: int,
        created_at: str,
    ) -> None:
        content_bytes = content_json.encode("utf-8")
        connection.execute(
            "INSERT INTO artifact_versions (id, project_id, job_id, llm_call_id, kind, "
            "content_type, content_json, content_sha256, byte_size, creator_type, "
            "version_number, created_at) VALUES (?, ?, ?, ?, ?, 'application/json', ?, ?, ?, "
            "'user', ?, ?)",
            (
                artifact_id,
                project_id,
                job_id,
                llm_call_id,
                kind,
                content_json,
                hashlib.sha256(content_bytes).hexdigest(),
                len(content_bytes),
                version,
                created_at,
            ),
        )

    def edit_question_detailing_output(
        self, job_id: str, markdown_value: str, base_version: int
    ) -> JobRecord:
        """Create a user version and select it without modifying prior content."""
        markdown = markdown_value.strip()
        if not markdown:
            raise JobError("The detailed scientific question cannot be empty.")
        if len(markdown) > 100_000:
            raise JobError("The detailed scientific question is too long.")
        now = _timestamp()
        artifact_payload = {
            "schema_version": 1,
            "content_type": "text/markdown",
            "detailed_question": markdown,
        }
        content_json = _json(artifact_payload)
        content_bytes = content_json.encode("utf-8")
        artifact_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT effective.version_number, jobs.project_id, llm_calls.id AS llm_call_id "
                "FROM jobs "
                "JOIN llm_calls ON llm_calls.job_id = jobs.id "
                "JOIN artifact_effective_versions selection ON selection.job_id = jobs.id "
                "JOIN artifact_versions effective ON effective.id = selection.artifact_version_id "
                "WHERE jobs.id = ? AND jobs.status = 'completed'",
                (job_id,),
            ).fetchone()
            if current is None:
                raise JobError("Only a completed question-detailing output can be edited.")
            if current["version_number"] != base_version:
                raise JobError(
                    "This output was edited elsewhere. Reload it before making another change."
                )
            next_version = base_version + 1
            connection.execute(
                "INSERT INTO artifact_versions (id, project_id, job_id, llm_call_id, kind, "
                "content_type, content_json, content_sha256, byte_size, creator_type, "
                "version_number, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', ?, ?)",
                (
                    artifact_id,
                    current["project_id"],
                    job_id,
                    current["llm_call_id"],
                    "question_detailing_output",
                    "application/json",
                    content_json,
                    hashlib.sha256(content_bytes).hexdigest(),
                    len(content_bytes),
                    next_version,
                    now,
                ),
            )
            connection.execute(
                "UPDATE artifact_effective_versions SET artifact_version_id = ?, "
                "selected_at = ?, selection_reason = 'user_edit' WHERE job_id = ?",
                (artifact_id, now, job_id),
            )
        return self.get_job(job_id)

    def fail(
        self, job_id: str, call_id: str | None, error: str, raw_response: str | None = None
    ) -> JobRecord:
        now = _timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if call_id is not None:
                started = connection.execute(
                    "SELECT started_at FROM llm_calls WHERE id = ?", (call_id,)
                ).fetchone()
                duration_ms = _duration_ms(started["started_at"], now) if started else None
                connection.execute(
                    "UPDATE llm_calls SET raw_response = ?, completed_at = ?, duration_ms = ?, "
                    "status = 'failed', error = ? WHERE id = ?",
                    (raw_response, now, duration_ms, error, call_id),
                )
            connection.execute(
                "UPDATE jobs SET status = 'failed', completed_at = ?, error = ? WHERE id = ?",
                (now, error, job_id),
            )
        return self.get_job(job_id)

    def fail_interrupted_jobs(self) -> int:
        """Never replay an ambiguous request that may already have been billed."""
        now = _timestamp()
        message = "The application stopped while awaiting the provider response; this job was not retried."
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE jobs SET status = 'failed', completed_at = ?, error = ? "
                "WHERE status = 'awaiting_response'",
                (now, message),
            )
            connection.execute(
                "UPDATE llm_calls SET status = 'failed', completed_at = ?, error = ? "
                "WHERE status = 'started'",
                (now, message),
            )
        return cursor.rowcount

    @staticmethod
    def _select_sql() -> str:
        return (
            "SELECT jobs.*, projects.tag AS project_tag, llm_calls.id AS llm_call_id, "
            "llm_calls.input_tokens, llm_calls.output_tokens, llm_calls.total_tokens, "
            "llm_calls.duration_ms, llm_calls.cost_status, "
            "original.content_json AS original_content_json, "
            "effective.content_json AS effective_content_json, "
            "effective.version_number AS effective_version_number, "
            "intent_questions.content_json AS intent_questions_json, "
            "intent_selection.content_json AS intent_selection_json, "
            "intent_selection.version_number AS intent_selection_version, "
            "scope_questions.content_json AS scope_questions_json, "
            "scope_answers.content_json AS scope_answers_json, "
            "scope_answers.version_number AS scope_answers_version, "
            "readiness_review.content_json AS readiness_review_json, "
            "follow_up_answers.content_json AS follow_up_answers_json, "
            "follow_up_answers.version_number AS follow_up_answers_version, "
            "NOT EXISTS (SELECT 1 FROM jobs downstream WHERE "
            "downstream.project_id = jobs.project_id AND downstream.id != jobs.id "
            "AND downstream.created_at > jobs.created_at) AS no_downstream_job "
            "FROM jobs JOIN projects ON projects.id = jobs.project_id "
            "LEFT JOIN llm_calls ON llm_calls.job_id = jobs.id "
            "LEFT JOIN artifact_versions original ON original.job_id = jobs.id "
            "AND original.kind = 'question_detailing_output' AND original.version_number = 1 "
            "LEFT JOIN artifact_effective_versions selection ON selection.job_id = jobs.id "
            "LEFT JOIN artifact_versions effective ON effective.id = selection.artifact_version_id "
            "LEFT JOIN artifact_versions intent_questions ON intent_questions.job_id = jobs.id "
            "AND intent_questions.kind = 'intent_clarification_questions' "
            "AND intent_questions.version_number = 1 "
            "LEFT JOIN artifact_versions intent_selection "
            "ON intent_selection.id = selection.artifact_version_id "
            "AND intent_selection.kind = 'intent_clarification_selection' "
            "LEFT JOIN artifact_versions scope_questions ON scope_questions.job_id = jobs.id "
            "AND scope_questions.kind = 'scope_clarification_questions' "
            "AND scope_questions.version_number = 1 "
            "LEFT JOIN artifact_versions scope_answers "
            "ON scope_answers.id = selection.artifact_version_id "
            "AND scope_answers.kind = 'scope_clarification_answers' "
            "LEFT JOIN artifact_versions readiness_review ON readiness_review.job_id = jobs.id "
            "AND readiness_review.kind = 'scope_readiness_review' "
            "AND readiness_review.version_number = 1 "
            "LEFT JOIN artifact_versions follow_up_answers "
            "ON follow_up_answers.id = selection.artifact_version_id "
            "AND follow_up_answers.kind = 'scope_follow_up_answers' "
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> JobRecord:
        original_output = _markdown_from_json(row["original_content_json"])
        effective_output = _markdown_from_json(row["effective_content_json"])
        output_markdown = effective_output or original_output
        effective_version = row["effective_version_number"]
        return JobRecord(
            id=row["id"],
            project_id=row["project_id"],
            project_tag=row["project_tag"],
            kind=row["kind"],
            status=row["status"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            provider=row["provider"],
            model=row["model"],
            scientific_question_snapshot=row["scientific_question_snapshot"],
            prompt_snapshot=row["prompt_snapshot"],
            prompt_template_version=row["prompt_template_version"],
            workflow_input_snapshot_json=_optional_row_value(row, "workflow_input_snapshot_json"),
            error=row["error"],
            output_markdown=output_markdown,
            original_output_markdown=original_output,
            effective_output_markdown=effective_output or original_output,
            effective_output_version=effective_version,
            output_was_edited=isinstance(effective_version, int) and effective_version > 1,
            llm_call_id=row["llm_call_id"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            total_tokens=row["total_tokens"],
            duration_ms=row["duration_ms"],
            cost_status=row["cost_status"],
            intent_questions=_object_from_json(row["intent_questions_json"]),
            intent_selection=_object_from_json(row["intent_selection_json"]),
            intent_selection_version=row["intent_selection_version"],
            intent_selection_is_editable=(
                row["kind"] == "intent_clarification"
                and row["intent_selection_version"] is not None
                and bool(row["no_downstream_job"])
            ),
            scope_questions=_object_from_json(row["scope_questions_json"]),
            scope_answers=_object_from_json(row["scope_answers_json"]),
            scope_answers_version=row["scope_answers_version"],
            scope_answers_is_editable=(
                row["kind"] == "scope_clarification_round_1"
                and row["scope_answers_version"] is not None
                and bool(row["no_downstream_job"])
            ),
            scope_readiness_review=_object_from_json(row["readiness_review_json"]),
            scope_follow_up_answers=_object_from_json(row["follow_up_answers_json"]),
            scope_follow_up_answers_version=row["follow_up_answers_version"],
            scope_follow_up_answers_is_editable=(
                row["kind"] == "scope_readiness"
                and row["follow_up_answers_version"] is not None
                and bool(row["no_downstream_job"])
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection


def provider_input(scientific_question: str) -> str:
    """Return the exact user content sent independently of provider transport."""
    return _provider_input(scientific_question)


def provider_input_for_job(job: JobRecord) -> str:
    """Return the immutable input prepared for this exact job kind."""
    if job.kind in {"scope_clarification_round_1", "scope_readiness"}:
        if job.workflow_input_snapshot_json is None:
            raise JobError("The structured workflow input snapshot is missing.")
        return f"Scientific workflow input (JSON):\n\n{job.workflow_input_snapshot_json}"
    return _provider_input(job.scientific_question_snapshot)


def _provider_input(scientific_question: str) -> str:
    return f"Scientific question:\n\n{scientific_question}"


def _scope_input_snapshot(
    scientific_question: str,
    questions_artifact_id: str,
    questions_json: str,
    selection_artifact_id: str,
    selection_version: int,
    selection_json: str,
) -> str:
    questions = IntentClarificationOutput.model_validate_json(questions_json)
    selection = IntentSelection.model_validate_json(selection_json)
    options = {option.id: option for option in questions.options}
    primary = options.get(selection.primary_intent_id)
    secondaries = [options.get(option_id) for option_id in selection.secondary_intent_ids]
    if primary is None or any(option is None for option in secondaries):
        raise JobError("The effective research-intent artifact is inconsistent.")
    payload = {
        "schema_version": 1,
        "scientific_question": scientific_question,
        "intent_questions_artifact_id": questions_artifact_id,
        "intent_selection_artifact_id": selection_artifact_id,
        "intent_selection_version": selection_version,
        "primary_intent": primary.model_dump(mode="json"),
        "secondary_intents": [
            option.model_dump(mode="json") for option in secondaries if option is not None
        ],
        "user_note": selection.note,
    }
    return _json(payload)


def _readiness_input_snapshot(
    scope_input_json: str | None,
    questions_artifact_id: str,
    questions_json: str,
    answers_artifact_id: str,
    answers_version: int,
    answers_json: str,
) -> str:
    """Build a canonical, self-contained snapshot for the readiness call."""
    if scope_input_json is None:
        raise JobError("The first scope round is missing its input snapshot.")
    try:
        upstream = json.loads(scope_input_json)
        questions = json.loads(questions_json)
        answers = json.loads(answers_json)
    except json.JSONDecodeError as error:
        raise JobError("The stored scope input is not valid JSON.") from error
    return _json(
        {
            "schema_version": 1,
            "upstream_question_and_intent": upstream,
            "scope_questions_artifact_id": questions_artifact_id,
            "scope_questions": questions,
            "scope_answers_artifact_id": answers_artifact_id,
            "scope_answers_version": answers_version,
            "scope_answers": answers,
        }
    )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validated_intent_selection(
    questions: IntentClarificationOutput,
    questions_artifact_id: str,
    primary_intent_id: str,
    secondary_intent_ids: list[str],
    note: str,
) -> IntentSelection:
    valid_ids = {option.id for option in questions.options}
    if primary_intent_id not in valid_ids:
        raise JobError("Select one of the available primary research intents.")
    if primary_intent_id in secondary_intent_ids:
        raise JobError("The primary intent cannot also be a secondary intent.")
    if any(intent_id not in valid_ids for intent_id in secondary_intent_ids):
        raise JobError("One or more selected secondary intents are not available.")
    try:
        return IntentSelection(
            questions_artifact_id=questions_artifact_id,
            primary_intent_id=primary_intent_id,
            secondary_intent_ids=secondary_intent_ids,
            note=note,
        )
    except ValueError as error:
        raise JobError("The research-intent selection is not valid.") from error


def _validated_follow_up_answers(
    review_json: str,
    review_artifact_id: str,
    answers: list[ScopeAnswer],
) -> ScopeAnswers:
    try:
        review = ScopeReadinessOutput.model_validate_json(review_json)
    except ValueError as error:
        raise JobError("The preserved readiness review is not valid.") from error
    if review.ready_for_charter:
        raise JobError("This scope was already declared ready and has no follow-up questions.")
    try:
        return validate_scope_answers(review.follow_up_questions, review_artifact_id, answers)
    except (ScopeClarificationError, ValueError) as error:
        raise JobError(str(error)) from error


def _markdown_from_json(content_json: str | None) -> str | None:
    if content_json is None:
        return None
    try:
        value = json.loads(content_json).get("detailed_question")
    except (AttributeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, str) else None


def _object_from_json(content_json: str | None) -> dict[str, object] | None:
    if content_json is None:
        return None
    try:
        value = json.loads(content_json)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _optional_row_value(row: sqlite3.Row, key: str) -> str | None:
    """Read a newly added column while migration downgrade tests inspect older schemas."""
    if key not in set(row.keys()):
        return None
    value = row[key]
    return value if isinstance(value, str) else None


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started_at: str, completed_at: str) -> int:
    started = datetime.fromisoformat(started_at)
    completed = datetime.fromisoformat(completed_at)
    return max(0, round((completed - started).total_seconds() * 1000))
