"""Small SQLite repository for the first project shell."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from jeromes_laboratory.workflow.intent_clarification import (
    DEFAULT_INTENT_CLARIFICATION_PROMPT,
    INTENT_CLARIFICATION_PROMPT_VERSION,
)
from jeromes_laboratory.workflow.question_detailing import (
    DEFAULT_QUESTION_DETAILING_PROMPT,
    QUESTION_DETAILING_PROMPT_VERSION,
)
from jeromes_laboratory.workflow.scope_clarification import (
    DEFAULT_SCOPE_CLARIFICATION_PROMPT,
    SCOPE_CLARIFICATION_PROMPT_VERSION,
)
from jeromes_laboratory.workflow.scope_readiness import (
    DEFAULT_SCOPE_READINESS_PROMPT,
    SCOPE_READINESS_PROMPT_VERSION,
)


class ProjectError(ValueError):
    """Raised when a requested project operation is not valid."""


@dataclass(frozen=True)
class ProjectRecord:
    """Safe project data for the local API and interface."""

    id: str
    tag: str
    scientific_question: str
    created_at: str
    updated_at: str
    question_is_editable: bool
    question_detailing_prompt: str
    question_detailing_prompt_version: str
    question_detailing_prompt_is_editable: bool
    intent_clarification_prompt: str
    intent_clarification_prompt_version: str
    intent_clarification_prompt_is_editable: bool
    scope_clarification_prompt: str
    scope_clarification_prompt_version: str
    scope_clarification_prompt_is_editable: bool
    scope_readiness_prompt: str
    scope_readiness_prompt_version: str
    scope_readiness_prompt_is_editable: bool


class ProjectRepository:
    """Persist project roots while workflow entities are still forthcoming."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_projects(self) -> list[ProjectRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, tag, scientific_question, created_at, updated_at, "
                "question_detailing_prompt, question_detailing_prompt_version, "
                "intent_clarification_prompt, intent_clarification_prompt_version, "
                "scope_clarification_prompt, scope_clarification_prompt_version, "
                "scope_readiness_prompt, scope_readiness_prompt_version, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id) "
                "AS question_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'question_detailing') AS detailing_prompt_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'intent_clarification') AS intent_prompt_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'scope_clarification_round_1') AS scope_prompt_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'scope_readiness') AS readiness_prompt_is_editable "
                "FROM projects ORDER BY created_at"
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> ProjectRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, tag, scientific_question, created_at, updated_at, "
                "question_detailing_prompt, question_detailing_prompt_version, "
                "intent_clarification_prompt, intent_clarification_prompt_version, "
                "scope_clarification_prompt, scope_clarification_prompt_version, "
                "scope_readiness_prompt, scope_readiness_prompt_version, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id) "
                "AS question_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'question_detailing') AS detailing_prompt_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'intent_clarification') AS intent_prompt_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'scope_clarification_round_1') AS scope_prompt_is_editable, "
                "NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.project_id = projects.id "
                "AND jobs.kind = 'scope_readiness') AS readiness_prompt_is_editable "
                "FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise ProjectError("The selected project no longer exists.")
        return self._record_from_row(row)

    def create_project(self, scientific_question: str) -> ProjectRecord:
        question = self._required_text(
            scientific_question, "Enter a scientific question before starting."
        )
        now = self._timestamp()
        project_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            next_tag_number = self._next_tag_number(connection)
            tag = f"PROJ{next_tag_number:03d}"
            connection.execute(
                "INSERT INTO projects (id, tag, scientific_question, created_at, updated_at, "
                "question_detailing_prompt, question_detailing_prompt_version, "
                "intent_clarification_prompt, intent_clarification_prompt_version, "
                "scope_clarification_prompt, scope_clarification_prompt_version, "
                "scope_readiness_prompt, scope_readiness_prompt_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    tag,
                    question,
                    now,
                    now,
                    DEFAULT_QUESTION_DETAILING_PROMPT,
                    QUESTION_DETAILING_PROMPT_VERSION,
                    DEFAULT_INTENT_CLARIFICATION_PROMPT,
                    INTENT_CLARIFICATION_PROMPT_VERSION,
                    DEFAULT_SCOPE_CLARIFICATION_PROMPT,
                    SCOPE_CLARIFICATION_PROMPT_VERSION,
                    DEFAULT_SCOPE_READINESS_PROMPT,
                    SCOPE_READINESS_PROMPT_VERSION,
                ),
            )
            connection.execute(
                "INSERT INTO application_metadata (key, value) VALUES ('next_project_tag_number', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(next_tag_number + 1),),
            )
        return ProjectRecord(
            id=project_id,
            tag=tag,
            scientific_question=question,
            created_at=now,
            updated_at=now,
            question_is_editable=True,
            question_detailing_prompt=DEFAULT_QUESTION_DETAILING_PROMPT,
            question_detailing_prompt_version=QUESTION_DETAILING_PROMPT_VERSION,
            question_detailing_prompt_is_editable=True,
            intent_clarification_prompt=DEFAULT_INTENT_CLARIFICATION_PROMPT,
            intent_clarification_prompt_version=INTENT_CLARIFICATION_PROMPT_VERSION,
            intent_clarification_prompt_is_editable=True,
            scope_clarification_prompt=DEFAULT_SCOPE_CLARIFICATION_PROMPT,
            scope_clarification_prompt_version=SCOPE_CLARIFICATION_PROMPT_VERSION,
            scope_clarification_prompt_is_editable=True,
            scope_readiness_prompt=DEFAULT_SCOPE_READINESS_PROMPT,
            scope_readiness_prompt_version=SCOPE_READINESS_PROMPT_VERSION,
            scope_readiness_prompt_is_editable=True,
        )

    def rename_project(self, project_id: str, tag_value: str) -> ProjectRecord:
        tag = self._required_text(tag_value, "Enter a project tag.", maximum_length=64)
        now = self._timestamp()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE projects SET tag = ?, updated_at = ? WHERE id = ?",
                    (tag, now, project_id),
                )
        except sqlite3.IntegrityError as error:
            raise ProjectError("That project tag is already in use.") from error
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    def update_scientific_question(self, project_id: str, question_value: str) -> ProjectRecord:
        """Allow an edit only until a future workflow input has begun or completed."""
        question = self._required_text(
            question_value,
            "Enter a scientific question before saving.",
        )
        now = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not self._question_is_editable(connection, project_id):
                raise ProjectError(
                    "The scientific question is locked because a workflow job already uses it."
                )
            cursor = connection.execute(
                "UPDATE projects SET scientific_question = ?, updated_at = ? WHERE id = ?",
                (question, now, project_id),
            )
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    def update_question_detailing_prompt(self, project_id: str, prompt_value: str) -> ProjectRecord:
        """Save the exact project-specific prompt that a later LLM call will use."""
        prompt = self._required_text(prompt_value, "Enter a prompt before saving.")
        now = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not self._question_is_editable(connection, project_id):
                raise ProjectError(
                    "The question-detailing prompt is locked because a workflow job already uses it."
                )
            cursor = connection.execute(
                "UPDATE projects SET question_detailing_prompt = ?, "
                "question_detailing_prompt_version = 'custom', updated_at = ? WHERE id = ?",
                (prompt, now, project_id),
            )
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    def update_intent_clarification_prompt(
        self, project_id: str, prompt_value: str
    ) -> ProjectRecord:
        """Save the exact project prompt used to generate research-intent choices."""
        prompt = self._required_text(prompt_value, "Enter a prompt before saving.")
        now = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'intent_clarification'",
                (project_id,),
            ).fetchone()
            if row is not None:
                raise ProjectError(
                    "The intent-clarification prompt is locked because a workflow job already uses it."
                )
            cursor = connection.execute(
                "UPDATE projects SET intent_clarification_prompt = ?, "
                "intent_clarification_prompt_version = 'custom', updated_at = ? WHERE id = ?",
                (prompt, now, project_id),
            )
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    def update_scope_clarification_prompt(
        self, project_id: str, prompt_value: str
    ) -> ProjectRecord:
        """Save the exact project prompt used to generate first-round scope questions."""
        prompt = self._required_text(prompt_value, "Enter a prompt before saving.")
        now = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'scope_clarification_round_1'",
                (project_id,),
            ).fetchone()
            if row is not None:
                raise ProjectError(
                    "The scope-clarification prompt is locked because a workflow job already uses it."
                )
            cursor = connection.execute(
                "UPDATE projects SET scope_clarification_prompt = ?, "
                "scope_clarification_prompt_version = 'custom', updated_at = ? WHERE id = ?",
                (prompt, now, project_id),
            )
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    def update_scope_readiness_prompt(self, project_id: str, prompt_value: str) -> ProjectRecord:
        """Save the exact prompt used to review the confirmed first scope round."""
        prompt = self._required_text(prompt_value, "Enter a prompt before saving.")
        now = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT 1 FROM jobs WHERE project_id = ? AND kind = 'scope_readiness'",
                (project_id,),
            ).fetchone()
            if row is not None:
                raise ProjectError(
                    "The scope-readiness prompt is locked because a workflow job already uses it."
                )
            cursor = connection.execute(
                "UPDATE projects SET scope_readiness_prompt = ?, "
                "scope_readiness_prompt_version = 'custom', updated_at = ? WHERE id = ?",
                (prompt, now, project_id),
            )
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    @staticmethod
    def _question_is_editable(connection: sqlite3.Connection, project_id: str) -> bool:
        """Lock exact scientific inputs from the moment a job is enqueued."""
        row = connection.execute(
            "SELECT 1 FROM jobs WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return row is None

    def _next_tag_number(self, connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT value FROM application_metadata WHERE key = 'next_project_tag_number'"
        ).fetchone()
        if row is None:
            return 1
        try:
            return max(1, int(row[0]))
        except ValueError:
            return 1

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            id=row["id"],
            tag=row["tag"],
            scientific_question=row["scientific_question"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            question_is_editable=bool(row["question_is_editable"]),
            question_detailing_prompt=row["question_detailing_prompt"],
            question_detailing_prompt_version=row["question_detailing_prompt_version"],
            question_detailing_prompt_is_editable=bool(row["detailing_prompt_is_editable"]),
            intent_clarification_prompt=row["intent_clarification_prompt"],
            intent_clarification_prompt_version=row["intent_clarification_prompt_version"],
            intent_clarification_prompt_is_editable=bool(row["intent_prompt_is_editable"]),
            scope_clarification_prompt=row["scope_clarification_prompt"],
            scope_clarification_prompt_version=row["scope_clarification_prompt_version"],
            scope_clarification_prompt_is_editable=bool(row["scope_prompt_is_editable"]),
            scope_readiness_prompt=row["scope_readiness_prompt"],
            scope_readiness_prompt_version=row["scope_readiness_prompt_version"],
            scope_readiness_prompt_is_editable=bool(row["readiness_prompt_is_editable"]),
        )

    @staticmethod
    def _required_text(value: str, empty_message: str, maximum_length: int = 20_000) -> str:
        normalized = value.strip()
        if not normalized:
            raise ProjectError(empty_message)
        if len(normalized) > maximum_length:
            raise ProjectError(f"Text must be at most {maximum_length} characters.")
        return normalized

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()
