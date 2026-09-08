"""Tests for bundled question-detailing prompt resources."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from jeromes_laboratory.database.initialize import MIGRATIONS_DIRECTORY, database_url
from jeromes_laboratory.workflow.question_detailing import (
    DEFAULT_QUESTION_DETAILING_PROMPT,
    QUESTION_DETAILING_PROMPT_VERSION,
    load_question_detailing_prompt,
)


def test_default_question_detailing_prompt_is_loaded_from_versioned_resource() -> None:
    assert QUESTION_DETAILING_PROMPT_VERSION == "5"
    assert DEFAULT_QUESTION_DETAILING_PROMPT == load_question_detailing_prompt("5")
    assert "scientific question below" not in DEFAULT_QUESTION_DETAILING_PROMPT
    assert "primary refined scientific question" in DEFAULT_QUESTION_DETAILING_PROMPT
    assert "failed or null results" in DEFAULT_QUESTION_DETAILING_PROMPT
    assert "candidate synonyms" in DEFAULT_QUESTION_DETAILING_PROMPT
    assert "Do not write database-specific Boolean query syntax yet" in (
        DEFAULT_QUESTION_DETAILING_PROMPT
    )
    assert "Do not wrap it in JSON" in DEFAULT_QUESTION_DETAILING_PROMPT


def test_historical_question_detailing_prompt_remains_available() -> None:
    assert "scientific question below" in load_question_detailing_prompt("1")
    assert "structured research plan" in load_question_detailing_prompt("2")
    assert 'exactly one field named "detailed_question"' in load_question_detailing_prompt("3")
    assert "Return only the complete developed question as Markdown text" in (
        load_question_detailing_prompt("4")
    )


def test_v2_migration_updates_only_the_previous_default(tmp_path: Path) -> None:
    database_path = tmp_path / "prompt-migration.sqlite3"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0003")

    project_values = (
        "Question?",
        "2026-09-08T00:00:00Z",
        "2026-09-08T00:00:00Z",
    )
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO projects "
            "(id, tag, scientific_question, created_at, updated_at, "
            "question_detailing_prompt, question_detailing_prompt_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "default-project",
                    "PROJ001",
                    *project_values,
                    load_question_detailing_prompt("1"),
                    "1",
                ),
                (
                    "custom-project",
                    "PROJ002",
                    *project_values,
                    "My custom prompt",
                    "custom",
                ),
            ],
        )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        prompts = dict(
            connection.execute(
                "SELECT id, question_detailing_prompt || '|' || "
                "question_detailing_prompt_version FROM projects"
            )
        )

    assert prompts["default-project"] == f"{load_question_detailing_prompt('5')}|5"
    assert prompts["custom-project"] == "My custom prompt|custom"


def test_v5_migration_does_not_rewrite_a_prompt_used_by_a_job(tmp_path: Path) -> None:
    database_path = tmp_path / "used-prompt-migration.sqlite3"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0007")
    prompt_v4 = load_question_detailing_prompt("4")
    project_values = ("Question?", "2026-09-09T00:00:00Z", "2026-09-09T00:00:00Z")
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO projects (id, tag, scientific_question, created_at, updated_at, "
            "question_detailing_prompt, question_detailing_prompt_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("unused", "PROJ001", *project_values, prompt_v4, "4"),
                ("used", "PROJ002", *project_values, prompt_v4, "4"),
            ],
        )
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "job-id",
                "used",
                "question_detailing",
                "completed",
                "2026-09-09T00:00:01Z",
                "openai",
                "gpt-test",
                "Question?",
                prompt_v4,
                "question-detailing",
                "4",
            ),
        )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        versions = dict(
            connection.execute("SELECT id, question_detailing_prompt_version FROM projects")
        )
    assert versions == {"unused": "5", "used": "4"}
