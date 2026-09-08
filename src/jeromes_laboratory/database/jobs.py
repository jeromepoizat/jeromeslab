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
    error: str | None
    output_markdown: str | None
    llm_call_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: int | None
    cost_status: str | None


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
        input_content = _provider_input(job.scientific_question_snapshot)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO llm_calls (id, project_id, job_id, provider, model, operation, "
                "purpose, prompt_template_id, prompt_template_version, instructions, input_content, "
                "request_json, started_at, status, retry_count, generation_settings_json, cost_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'question-detailing', ?, ?, ?, ?, ?, 'started', 0, ?, 'unavailable')",
                (
                    call_id,
                    job.project_id,
                    job.id,
                    job.provider,
                    job.model,
                    prepared.operation,
                    "Develop the scientific question for literature-search planning",
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
        artifact_payload = {
            "schema_version": 1,
            "content_type": "text/markdown",
            "detailed_question": result.output_text,
        }
        content_json = _json(artifact_payload)
        content_bytes = content_json.encode("utf-8")
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
                    str(uuid4()),
                    call_id,
                    "question_detailing_output",
                    "application/json",
                    content_json,
                    hashlib.sha256(content_bytes).hexdigest(),
                    len(content_bytes),
                    now,
                    job_id,
                ),
            )
            connection.execute(
                "UPDATE jobs SET status = 'completed', completed_at = ? WHERE id = ?",
                (now, job_id),
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
            "llm_calls.duration_ms, llm_calls.cost_status, artifact_versions.content_json "
            "FROM jobs JOIN projects ON projects.id = jobs.project_id "
            "LEFT JOIN llm_calls ON llm_calls.job_id = jobs.id "
            "LEFT JOIN artifact_versions ON artifact_versions.job_id = jobs.id "
            "AND artifact_versions.kind = 'question_detailing_output' "
        )

    @staticmethod
    def _record(row: sqlite3.Row) -> JobRecord:
        output_markdown: str | None = None
        if row["content_json"] is not None:
            try:
                payload = json.loads(row["content_json"])
                value = payload.get("detailed_question")
                output_markdown = value if isinstance(value, str) else None
            except json.JSONDecodeError:
                output_markdown = None
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
            error=row["error"],
            output_markdown=output_markdown,
            llm_call_id=row["llm_call_id"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            total_tokens=row["total_tokens"],
            duration_ms=row["duration_ms"],
            cost_status=row["cost_status"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection


def provider_input(scientific_question: str) -> str:
    """Return the exact user content sent independently of provider transport."""
    return _provider_input(scientific_question)


def _provider_input(scientific_question: str) -> str:
    return f"Scientific question:\n\n{scientific_question}"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started_at: str, completed_at: str) -> int:
    started = datetime.fromisoformat(started_at)
    completed = datetime.fromisoformat(completed_at)
    return max(0, round((completed - started).total_seconds() * 1000))
