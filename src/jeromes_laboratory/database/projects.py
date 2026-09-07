"""Small SQLite repository for the first project shell."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


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


class ProjectRepository:
    """Persist project roots while workflow entities are still forthcoming."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_projects(self) -> list[ProjectRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, tag, scientific_question, created_at, updated_at "
                "FROM projects ORDER BY created_at"
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> ProjectRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, tag, scientific_question, created_at, updated_at "
                "FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise ProjectError("The selected project no longer exists.")
        return self._record_from_row(row)

    def create_project(self, scientific_question: str) -> ProjectRecord:
        question = self._required_text(scientific_question, "Enter a scientific question before starting.")
        now = self._timestamp()
        project_id = str(uuid4())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            next_tag_number = self._next_tag_number(connection)
            tag = f"PROJ{next_tag_number:03d}"
            connection.execute(
                "INSERT INTO projects (id, tag, scientific_question, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, tag, question, now, now),
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
        if not self._question_is_editable(project_id):
            raise ProjectError(
                "The scientific question is locked because a workflow job already uses it."
            )
        now = self._timestamp()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET scientific_question = ?, updated_at = ? WHERE id = ?",
                (question, now, project_id),
            )
        if cursor.rowcount == 0:
            raise ProjectError("The selected project no longer exists.")
        return self.get_project(project_id)

    def _question_is_editable(self, project_id: str) -> bool:
        """Centralize the future job-input lock rule; no jobs exist in this slice."""
        del project_id
        return True

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
            question_is_editable=True,
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
