"""Tests for first-run workspace selection and initialization."""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from jeromes_laboratory.database.initialize import MIGRATIONS_DIRECTORY, database_url
from jeromes_laboratory.database.projects import ProjectRepository
from jeromes_laboratory.storage.workspace import (
    DATABASE_FILE_NAME,
    WORKSPACE_MARKER_NAME,
    WorkspaceLocationError,
    WorkspaceService,
)
from jeromes_laboratory.workflow.intent_clarification import (
    DEFAULT_INTENT_CLARIFICATION_PROMPT,
    INTENT_CLARIFICATION_PROMPT_VERSION,
    load_intent_clarification_prompt,
)
from jeromes_laboratory.workflow.research_charter import (
    DEFAULT_RESEARCH_CHARTER_PROMPT,
    RESEARCH_CHARTER_PROMPT_VERSION,
    load_research_charter_prompt,
)
from jeromes_laboratory.workflow.scope_clarification import (
    DEFAULT_SCOPE_CLARIFICATION_PROMPT,
    SCOPE_CLARIFICATION_PROMPT_VERSION,
    load_scope_clarification_prompt,
)
from jeromes_laboratory.workflow.scope_readiness import (
    DEFAULT_SCOPE_READINESS_PROMPT,
    SCOPE_READINESS_PROMPT_VERSION,
    load_scope_readiness_prompt,
)


def create_service(tmp_path: Path) -> WorkspaceService:
    """Create a workspace service isolated from the real user configuration."""
    return WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )


def test_configure_workspace_creates_layout_and_applies_migration(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    workspace_path = tmp_path / "research"

    location = service.configure_workspace(str(workspace_path))

    assert location.path == workspace_path
    assert location.kind == "existing_workspace"
    assert service.configured_workspace_path() == workspace_path
    assert (workspace_path / WORKSPACE_MARKER_NAME).is_file()
    assert (workspace_path / "artifacts").is_dir()
    assert (workspace_path / "exports").is_dir()
    assert (workspace_path / "backups").is_dir()

    with sqlite3.connect(workspace_path / DATABASE_FILE_NAME) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    assert "application_metadata" in tables
    assert revision == ("0022",)


def test_readiness_migration_preserves_consumed_scope_prompt(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0012")

    old_prompt = load_scope_clarification_prompt("1")
    with sqlite3.connect(database_path) as connection:
        project_columns = connection.execute("PRAGMA table_info(projects)").fetchall()

        def insert_project(project_id: str, tag: str) -> None:
            values: dict[str, object] = {
                "id": project_id,
                "tag": tag,
                "scientific_question": "Question",
                "created_at": "2026-09-09T00:00:00+00:00",
                "updated_at": "2026-09-09T00:00:00+00:00",
                "question_detailing_prompt": "Legacy detailing prompt",
                "question_detailing_prompt_version": "4",
                "intent_clarification_prompt": "Legacy intent prompt",
                "intent_clarification_prompt_version": "1",
                "scope_clarification_prompt": old_prompt,
                "scope_clarification_prompt_version": "1",
            }
            required_names = [row[1] for row in project_columns]
            placeholders = ", ".join("?" for _ in required_names)
            connection.execute(
                f"INSERT INTO projects ({', '.join(required_names)}) VALUES ({placeholders})",
                [values[name] for name in required_names],
            )

        insert_project("consumed", "PROJ001")
        insert_project("unused", "PROJ002")
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "intent-job",
                "consumed",
                "intent_clarification",
                "completed",
                "2026-09-09T00:00:00+00:00",
                "openai",
                "gpt-example",
                "Question",
                "Legacy intent prompt",
                "intent-clarification",
                "1",
            ),
        )
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "scope-job",
                "consumed",
                "scope_clarification_round_1",
                "pending",
                "2026-09-09T00:00:00+00:00",
                "openai",
                "gpt-example",
                "Question",
                old_prompt,
                "scope-clarification",
                "1",
            ),
        )

    command.upgrade(configuration, "0013")

    old_readiness_prompt = load_scope_readiness_prompt("1")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE projects SET scope_readiness_prompt = ?, scope_readiness_prompt_version = '1'",
            (old_readiness_prompt,),
        )
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "readiness-job",
                "consumed",
                "scope_readiness",
                "pending",
                "2026-09-10T00:00:00+00:00",
                "openai",
                "gpt-example",
                "Question",
                old_readiness_prompt,
                "scope-readiness",
                "1",
            ),
        )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        consumed = connection.execute(
            "SELECT intent_clarification_prompt, intent_clarification_prompt_version, "
            "scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version FROM projects WHERE id = ?",
            ("consumed",),
        ).fetchone()
        unused = connection.execute(
            "SELECT intent_clarification_prompt, intent_clarification_prompt_version, "
            "scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version FROM projects WHERE id = ?",
            ("unused",),
        ).fetchone()

    assert consumed == (
        "Legacy intent prompt",
        "1",
        old_prompt,
        "1",
        old_readiness_prompt,
        "1",
    )
    assert unused == (
        DEFAULT_INTENT_CLARIFICATION_PROMPT,
        INTENT_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_CLARIFICATION_PROMPT,
        SCOPE_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_READINESS_PROMPT,
        SCOPE_READINESS_PROMPT_VERSION,
    )


def test_structured_option_migration_preserves_consumed_version_three_prompts(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "structured-options.db"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0015")
    repository = ProjectRepository(database_path)
    consumed = repository.create_project("Consumed framing")
    unused = repository.create_project("Unused framing")
    old_scope_prompt = load_scope_clarification_prompt("3")
    old_readiness_prompt = load_scope_readiness_prompt("3")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE projects SET scope_clarification_prompt = ?, "
            "scope_clarification_prompt_version = '3', scope_readiness_prompt = ?, "
            "scope_readiness_prompt_version = '3'",
            (old_scope_prompt, old_readiness_prompt),
        )
        for job_id, kind, prompt, template_id in (
            ("scope-v3", "scope_clarification_round_1", old_scope_prompt, "scope-clarification"),
            ("readiness-v3", "scope_readiness", old_readiness_prompt, "scope-readiness"),
        ):
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    consumed.id,
                    kind,
                    "completed",
                    "2026-09-11T00:00:00+00:00",
                    "openai",
                    "gpt-example",
                    consumed.scientific_question,
                    prompt,
                    template_id,
                    "3",
                ),
            )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        consumed_prompts = connection.execute(
            "SELECT scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version FROM projects WHERE id = ?",
            (consumed.id,),
        ).fetchone()
        unused_prompts = connection.execute(
            "SELECT scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version FROM projects WHERE id = ?",
            (unused.id,),
        ).fetchone()

    assert consumed_prompts == (old_scope_prompt, "3", old_readiness_prompt, "3")
    assert unused_prompts == (
        DEFAULT_SCOPE_CLARIFICATION_PROMPT,
        SCOPE_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_READINESS_PROMPT,
        SCOPE_READINESS_PROMPT_VERSION,
    )


def test_peptide_prompt_migration_updates_only_unconsumed_defaults(tmp_path: Path) -> None:
    database_path = tmp_path / "peptide-prompts.db"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0017")
    repository = ProjectRepository(database_path)
    consumed = repository.create_project("Consumed peptide workflow")
    unused = repository.create_project("Unused peptide workflow")
    old_prompts = (
        load_intent_clarification_prompt("2"),
        load_scope_clarification_prompt("4"),
        load_scope_readiness_prompt("4"),
        load_research_charter_prompt("1"),
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE projects SET intent_clarification_prompt = ?, "
            "intent_clarification_prompt_version = '2', scope_clarification_prompt = ?, "
            "scope_clarification_prompt_version = '4', scope_readiness_prompt = ?, "
            "scope_readiness_prompt_version = '4', research_charter_prompt = ?, "
            "research_charter_prompt_version = '1'",
            old_prompts,
        )
        for index, (kind, prompt, template_id, version) in enumerate((
            ("intent_clarification", old_prompts[0], "intent-clarification", "2"),
            ("scope_clarification_round_1", old_prompts[1], "scope-clarification-round-1", "4"),
            ("scope_readiness", old_prompts[2], "scope-readiness", "4"),
            ("research_charter", old_prompts[3], "research-charter", "1"),
        )):
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"consumed-stage-{index}",
                    consumed.id,
                    kind,
                    "completed",
                    f"2026-09-21T00:00:0{index}+00:00",
                    "openai",
                    "gpt-example",
                    consumed.scientific_question,
                    prompt,
                    template_id,
                    version,
                ),
            )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        consumed_prompts = connection.execute(
            "SELECT intent_clarification_prompt, intent_clarification_prompt_version, "
            "scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version, "
            "research_charter_prompt, research_charter_prompt_version "
            "FROM projects WHERE id = ?",
            (consumed.id,),
        ).fetchone()
        unused_prompts = connection.execute(
            "SELECT intent_clarification_prompt, intent_clarification_prompt_version, "
            "scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version, "
            "research_charter_prompt, research_charter_prompt_version "
            "FROM projects WHERE id = ?",
            (unused.id,),
        ).fetchone()

    assert consumed_prompts == (
        old_prompts[0], "2", old_prompts[1], "4", old_prompts[2], "4", old_prompts[3], "1"
    )
    assert unused_prompts == (
        DEFAULT_INTENT_CLARIFICATION_PROMPT,
        INTENT_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_CLARIFICATION_PROMPT,
        SCOPE_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_READINESS_PROMPT,
        SCOPE_READINESS_PROMPT_VERSION,
        DEFAULT_RESEARCH_CHARTER_PROMPT,
        RESEARCH_CHARTER_PROMPT_VERSION,
    )


def test_investigation_prompt_migration_preserves_consumed_stage_prompts(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "investigation-prompts.db"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0018")
    repository = ProjectRepository(database_path)
    consumed = repository.create_project("Consumed investigation terminology")
    unused = repository.create_project("Unused investigation terminology")
    old_prompts = (
        load_intent_clarification_prompt("3"),
        load_scope_clarification_prompt("5"),
        load_scope_readiness_prompt("5"),
        load_research_charter_prompt("2"),
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE projects SET intent_clarification_prompt = ?, "
            "intent_clarification_prompt_version = '3', scope_clarification_prompt = ?, "
            "scope_clarification_prompt_version = '5', scope_readiness_prompt = ?, "
            "scope_readiness_prompt_version = '5', research_charter_prompt = ?, "
            "research_charter_prompt_version = '2'",
            old_prompts,
        )
        for index, (kind, prompt, template_id, version) in enumerate((
            ("intent_clarification", old_prompts[0], "intent-clarification", "3"),
            ("scope_clarification_round_1", old_prompts[1], "scope-clarification-round-1", "5"),
            ("scope_readiness", old_prompts[2], "scope-readiness", "5"),
            ("research_charter", old_prompts[3], "research-charter", "2"),
        )):
            connection.execute(
                "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
                "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
                "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"consumed-investigation-stage-{index}",
                    consumed.id,
                    kind,
                    "completed",
                    f"2026-09-21T01:00:0{index}+00:00",
                    "openai",
                    "gpt-example",
                    consumed.scientific_question,
                    prompt,
                    template_id,
                    version,
                ),
            )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        consumed_prompts = connection.execute(
            "SELECT intent_clarification_prompt, intent_clarification_prompt_version, "
            "scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version, "
            "research_charter_prompt, research_charter_prompt_version "
            "FROM projects WHERE id = ?",
            (consumed.id,),
        ).fetchone()
        unused_prompts = connection.execute(
            "SELECT intent_clarification_prompt, intent_clarification_prompt_version, "
            "scope_clarification_prompt, scope_clarification_prompt_version, "
            "scope_readiness_prompt, scope_readiness_prompt_version, "
            "research_charter_prompt, research_charter_prompt_version "
            "FROM projects WHERE id = ?",
            (unused.id,),
        ).fetchone()

    assert consumed_prompts == (
        old_prompts[0], "3", old_prompts[1], "5", old_prompts[2], "5", old_prompts[3], "2"
    )
    assert unused_prompts == (
        DEFAULT_INTENT_CLARIFICATION_PROMPT,
        INTENT_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_CLARIFICATION_PROMPT,
        SCOPE_CLARIFICATION_PROMPT_VERSION,
        DEFAULT_SCOPE_READINESS_PROMPT,
        SCOPE_READINESS_PROMPT_VERSION,
        DEFAULT_RESEARCH_CHARTER_PROMPT,
        RESEARCH_CHARTER_PROMPT_VERSION,
    )


def test_concise_charter_prompt_migration_preserves_consumed_prompt(tmp_path: Path) -> None:
    database_path = tmp_path / "concise-charter.db"
    configuration = Config()
    configuration.set_main_option("script_location", str(MIGRATIONS_DIRECTORY))
    configuration.set_main_option("sqlalchemy.url", database_url(database_path))
    command.upgrade(configuration, "0019")
    repository = ProjectRepository(database_path)
    consumed = repository.create_project("Consumed charter prompt")
    unused = repository.create_project("Unused charter prompt")
    old_prompt = load_research_charter_prompt("3")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE projects SET research_charter_prompt = ?, "
            "research_charter_prompt_version = '3'",
            (old_prompt,),
        )
        connection.execute(
            "INSERT INTO jobs (id, project_id, kind, status, created_at, provider, model, "
            "scientific_question_snapshot, prompt_snapshot, prompt_template_id, "
            "prompt_template_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "consumed-charter-v3",
                consumed.id,
                "research_charter",
                "completed",
                "2026-09-21T02:00:00+00:00",
                "openai",
                "gpt-example",
                consumed.scientific_question,
                old_prompt,
                "research-charter",
                "3",
            ),
        )

    command.upgrade(configuration, "head")

    with sqlite3.connect(database_path) as connection:
        consumed_prompt = connection.execute(
            "SELECT research_charter_prompt, research_charter_prompt_version "
            "FROM projects WHERE id = ?",
            (consumed.id,),
        ).fetchone()
        unused_prompt = connection.execute(
            "SELECT research_charter_prompt, research_charter_prompt_version "
            "FROM projects WHERE id = ?",
            (unused.id,),
        ).fetchone()

    assert consumed_prompt == (old_prompt, "3")
    assert unused_prompt == (
        DEFAULT_RESEARCH_CHARTER_PROMPT,
        RESEARCH_CHARTER_PROMPT_VERSION,
    )


def test_nonempty_folder_requires_explicit_confirmation(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    workspace_path = tmp_path / "existing-folder"
    workspace_path.mkdir()
    (workspace_path / "unrelated.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(WorkspaceLocationError, match="already contains files"):
        service.configure_workspace(str(workspace_path))

    assert not service.configuration_file.exists()
    service.configure_workspace(str(workspace_path), confirm_nonempty=True)

    assert (workspace_path / "unrelated.txt").read_text(encoding="utf-8") == "keep"
    assert service.configured_workspace_path() == workspace_path


def test_configured_workspace_is_initialized_on_a_later_launch(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    workspace_path = tmp_path / "research"
    service.configure_workspace(str(workspace_path))

    reopened_service = create_service(tmp_path)

    assert reopened_service.initialize_configured_workspace() == workspace_path


def test_concurrent_requests_run_workspace_migrations_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = create_service(tmp_path)
    workspace_path = tmp_path / "research"
    service.configure_workspace(str(workspace_path))
    reopened_service = create_service(tmp_path)
    upgrade_calls: list[Path] = []

    def slow_upgrade(database_path: Path) -> None:
        upgrade_calls.append(database_path)
        time.sleep(0.05)

    monkeypatch.setattr("jeromes_laboratory.storage.workspace.upgrade_database", slow_upgrade)
    with ThreadPoolExecutor(max_workers=8) as executor:
        initialized_paths = list(
            executor.map(lambda _: reopened_service.initialize_configured_workspace(), range(8))
        )

    assert initialized_paths == [workspace_path] * 8
    assert upgrade_calls == [workspace_path / DATABASE_FILE_NAME]


def test_forget_workspace_removes_only_the_saved_pointer(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    workspace_path = tmp_path / "research"
    service.configure_workspace(str(workspace_path))
    artifact_path = workspace_path / "artifacts" / "preserved.txt"
    artifact_path.write_text("research data", encoding="utf-8")

    forgotten_path = service.forget_configured_workspace()

    assert forgotten_path == workspace_path
    assert service.configured_workspace_path() is None
    assert (workspace_path / DATABASE_FILE_NAME).is_file()
    assert artifact_path.read_text(encoding="utf-8") == "research data"


def test_moved_workspace_can_be_reconnected_without_copying(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    original_path = tmp_path / "research"
    moved_path = tmp_path / "moved-research"
    service.configure_workspace(str(original_path))
    original_path.rename(moved_path)

    availability = service.workspace_availability()
    recovered = service.recover_configured_workspace(str(moved_path))

    assert availability.kind == "unavailable"
    assert recovered.path == moved_path
    assert service.configured_workspace_path() == moved_path


def test_workspace_move_copies_verifies_and_keeps_the_source(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    source_path = tmp_path / "research"
    destination_path = tmp_path / "relocated-research"
    service.configure_workspace(str(source_path))
    artifact_path = source_path / "artifacts" / "result.txt"
    artifact_path.write_text("verified research data", encoding="utf-8")

    previous_path, moved_path = service.move_configured_workspace(str(destination_path))

    assert previous_path == source_path
    assert moved_path == destination_path
    assert service.configured_workspace_path() == destination_path
    assert artifact_path.read_text(encoding="utf-8") == "verified research data"
    assert (destination_path / "artifacts" / "result.txt").read_text(encoding="utf-8") == (
        "verified research data"
    )


def test_workspace_move_rejects_a_nonempty_destination(tmp_path: Path) -> None:
    service = create_service(tmp_path)
    source_path = tmp_path / "research"
    destination_path = tmp_path / "occupied"
    service.configure_workspace(str(source_path))
    destination_path.mkdir()
    (destination_path / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(WorkspaceLocationError, match="new or empty"):
        service.move_configured_workspace(str(destination_path))

    assert service.configured_workspace_path() == source_path
