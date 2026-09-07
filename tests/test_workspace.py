"""Tests for first-run workspace selection and initialization."""

import sqlite3
from pathlib import Path

import pytest

from jeromes_laboratory.storage.workspace import (
    DATABASE_FILE_NAME,
    WORKSPACE_MARKER_NAME,
    WorkspaceLocationError,
    WorkspaceService,
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
    assert revision == ("0001",)


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
