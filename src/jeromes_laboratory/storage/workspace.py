"""Manage the user-selected local research workspace."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from platformdirs import user_config_path, user_documents_path

from jeromes_laboratory.database.initialize import upgrade_database

APPLICATION_NAME = "Jerome's Laboratory"
CONFIGURATION_FILE_NAME = "workspace.json"
CLIENT_STATE_FILE_NAME = "client-state.json"
WORKSPACE_MARKER_NAME = ".jeromes-laboratory-workspace.json"
DATABASE_FILE_NAME = "jeromes-laboratory.sqlite3"
WORKSPACE_FORMAT_VERSION = 1

WorkspacePathKind = Literal["empty", "existing_workspace", "not_empty", "new"]
WorkspaceAvailabilityKind = Literal["unconfigured", "available", "unavailable"]


class WorkspaceLocationError(ValueError):
    """Raised when a selected or saved workspace location is not usable."""


class FolderPickerUnavailableError(RuntimeError):
    """Raised when the operating-system folder picker cannot be opened."""


@dataclass(frozen=True)
class WorkspaceLocation:
    """A normalized workspace path and its current on-disk state."""

    path: Path
    kind: WorkspacePathKind


@dataclass(frozen=True)
class WorkspaceAvailability:
    """The configured workspace's availability without changing its pointer."""

    kind: WorkspaceAvailabilityKind
    path: Path | None
    error: str | None = None


class WorkspaceService:
    """Persist and initialize the one local research workspace."""

    def __init__(
        self,
        configuration_directory: Path | None = None,
        documents_directory: Path | None = None,
    ) -> None:
        self._configuration_directory = (
            configuration_directory
            if configuration_directory is not None
            else user_config_path(appname=APPLICATION_NAME, appauthor=False)
        )
        self._documents_directory = (
            documents_directory if documents_directory is not None else user_documents_path()
        )

    @property
    def configuration_file(self) -> Path:
        """Return the small config file that points to the selected workspace."""
        return self._configuration_directory / CONFIGURATION_FILE_NAME

    @property
    def client_state_file(self) -> Path:
        """Return the device-local, non-research interface-state file."""
        return self._configuration_directory / CLIENT_STATE_FILE_NAME

    def read_client_state(self) -> dict[str, object]:
        """Read optional device UI state without making it critical to launch."""
        try:
            if not self.client_state_file.is_file():
                return {}
            content = json.loads(self.client_state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return content if isinstance(content, dict) else {}

    def write_client_state(self, selected_project_id: str | None, scroll_top: int) -> None:
        """Persist the last project and its viewport position on this device only."""
        if scroll_top < 0:
            raise WorkspaceLocationError("The saved scroll position is invalid.")
        try:
            self._configuration_directory.mkdir(parents=True, exist_ok=True)
            self._write_json_atomically(
                self.client_state_file,
                {
                    "selected_project_id": selected_project_id,
                    "scroll_top": scroll_top,
                },
            )
        except OSError as error:
            raise WorkspaceLocationError("The local interface state could not be saved.") from error

    @property
    def recommended_workspace_path(self) -> Path:
        """Return the friendly default shown during first-run setup."""
        return self._documents_directory / APPLICATION_NAME

    def configured_workspace_path(self) -> Path | None:
        """Return the saved workspace path, if first-run setup is complete."""
        try:
            configuration_exists = self.configuration_file.is_file()
        except OSError as error:
            raise WorkspaceLocationError(
                "The saved workspace location cannot be accessed. Restore access to the "
                "configuration folder before opening or changing a workspace."
            ) from error

        if not configuration_exists:
            try:
                configuration_entry_exists = self.configuration_file.exists()
            except OSError as error:
                raise WorkspaceLocationError(
                    "The saved workspace location cannot be accessed. Restore access to the "
                    "configuration folder before opening or changing a workspace."
                ) from error
            if not configuration_entry_exists:
                return None
            raise WorkspaceLocationError("The saved workspace pointer is not a valid file.")

        try:
            content = json.loads(self.configuration_file.read_text(encoding="utf-8"))
            path_value = content["workspace_path"]
        except (json.JSONDecodeError, KeyError, OSError, TypeError) as error:
            raise WorkspaceLocationError(
                "The saved workspace location is unreadable. Choose a workspace again "
                "after restoring or locating the existing data."
            ) from error

        if not isinstance(path_value, str):
            raise WorkspaceLocationError("The saved workspace path is invalid.")
        return self._normalize_path(path_value)

    def inspect_path(self, path_value: str) -> WorkspaceLocation:
        """Validate a typed path without creating or modifying it."""
        path = self._normalize_path(path_value)
        if not path.exists():
            return WorkspaceLocation(path=path, kind="new")
        if not path.is_dir():
            raise WorkspaceLocationError("The selected path is a file, not a folder.")

        marker = path / WORKSPACE_MARKER_NAME
        if marker.is_file():
            return WorkspaceLocation(path=path, kind="existing_workspace")
        if any(path.iterdir()):
            return WorkspaceLocation(path=path, kind="not_empty")
        return WorkspaceLocation(path=path, kind="empty")

    def configure_workspace(
        self,
        path_value: str,
        *,
        confirm_nonempty: bool = False,
    ) -> WorkspaceLocation:
        """Initialize a selected workspace and save its location after success."""
        if self.configured_workspace_path() is not None:
            raise WorkspaceLocationError("A workspace is already configured.")

        location = self.inspect_path(path_value)
        if location.kind == "not_empty" and not confirm_nonempty:
            raise WorkspaceLocationError(
                "This folder already contains files. Confirm that you want Jerome's "
                "Laboratory to create its workspace files there."
            )

        try:
            location.path.mkdir(parents=True, exist_ok=True)
            for directory_name in ("artifacts", "exports", "backups"):
                (location.path / directory_name).mkdir(exist_ok=True)
            upgrade_database(location.path / DATABASE_FILE_NAME)
            self._write_workspace_marker(location.path)
            self._write_configuration(location.path)
        except OSError as error:
            raise WorkspaceLocationError(
                f"Jerome's Laboratory could not create or write to '{location.path}'."
            ) from error

        return WorkspaceLocation(path=location.path, kind="existing_workspace")

    def workspace_availability(self) -> WorkspaceAvailability:
        """Describe whether the remembered workspace can safely be opened."""
        workspace_path = self.configured_workspace_path()
        if workspace_path is None:
            return WorkspaceAvailability(kind="unconfigured", path=None)
        try:
            self._validate_existing_workspace(workspace_path)
        except WorkspaceLocationError as error:
            return WorkspaceAvailability(
                kind="unavailable",
                path=workspace_path,
                error=str(error),
            )
        return WorkspaceAvailability(kind="available", path=workspace_path)

    def initialize_configured_workspace(self) -> Path | None:
        """Apply database migrations before serving an already-configured workspace."""
        workspace_path = self.configured_workspace_path()
        if workspace_path is None:
            return None

        self._validate_existing_workspace(workspace_path)

        try:
            upgrade_database(workspace_path / DATABASE_FILE_NAME)
        except OSError as error:
            raise WorkspaceLocationError(
                f"Jerome's Laboratory could not open '{workspace_path}'."
            ) from error
        return workspace_path

    def recover_configured_workspace(self, path_value: str) -> WorkspaceLocation:
        """Point the device at a moved, recognized workspace without copying data."""
        availability = self.workspace_availability()
        if availability.kind != "unavailable":
            raise WorkspaceLocationError("Workspace recovery is only needed when the saved folder is unavailable.")

        location = self.inspect_path(path_value)
        if location.kind != "existing_workspace":
            raise WorkspaceLocationError(
                "Choose the existing Jerome's Laboratory workspace folder containing its database."
            )
        self._validate_existing_workspace(location.path)
        try:
            upgrade_database(location.path / DATABASE_FILE_NAME)
            self._write_configuration(location.path)
        except OSError as error:
            raise WorkspaceLocationError(
                f"Jerome's Laboratory could not open '{location.path}'."
            ) from error
        return location

    def move_configured_workspace(self, destination_value: str) -> tuple[Path, Path]:
        """Copy, byte-verify, then repoint one workspace; never remove its source."""
        availability = self.workspace_availability()
        if availability.kind != "available" or availability.path is None:
            raise WorkspaceLocationError("The current workspace must be available before it can be moved.")
        source_path = availability.path
        destination = self._normalize_path(destination_value)
        if destination == source_path or self._is_within(destination, source_path) or self._is_within(source_path, destination):
            raise WorkspaceLocationError("Choose a separate destination folder outside the current workspace.")

        destination_location = self.inspect_path(str(destination))
        if destination_location.kind not in ("new", "empty"):
            raise WorkspaceLocationError("Choose a new or empty destination folder for the workspace move.")

        try:
            self._checkpoint_database(source_path / DATABASE_FILE_NAME)
            source_manifest = self._file_manifest(source_path)
            required_bytes = sum(size for size, _ in source_manifest.values())
            destination_parent = destination.parent
            destination_parent.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(destination_parent).free < required_bytes:
                raise WorkspaceLocationError("The destination drive does not have enough free space.")

            staging_path = destination_parent / f".{destination.name}.moving-{uuid4().hex}"
            shutil.copytree(source_path, staging_path, copy_function=shutil.copy2)
            if self._file_manifest(staging_path) != source_manifest:
                raise WorkspaceLocationError(
                    "The copied workspace did not match the original. The saved location was not changed."
                )
            staging_path.replace(destination)
            self._write_configuration(destination)
        except WorkspaceLocationError:
            raise
        except OSError as error:
            raise WorkspaceLocationError(
                f"Jerome's Laboratory could not move the workspace to '{destination}'. "
                "The original folder was not changed."
            ) from error
        return source_path, destination

    def forget_configured_workspace(self) -> Path:
        """Remove only this device's workspace pointer, never workspace data."""
        workspace_path = self.configured_workspace_path()
        if workspace_path is None:
            raise WorkspaceLocationError("No workspace is currently configured.")

        try:
            self.configuration_file.unlink()
        except OSError as error:
            raise WorkspaceLocationError(
                "Jerome's Laboratory could not forget the saved workspace location."
            ) from error
        return workspace_path

    def choose_workspace_directory(self) -> str | None:
        """Open the native folder picker, returning no value when the user cancels."""
        try:
            import tkinter
            from tkinter import filedialog
        except ImportError as error:
            raise FolderPickerUnavailableError(
                "The folder picker is unavailable. Enter or paste a folder path instead."
            ) from error

        try:
            root = tkinter.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected_path = filedialog.askdirectory(
                initialdir=str(self.recommended_workspace_path.parent),
                mustexist=False,
                title="Choose Jerome's Laboratory workspace",
            )
            root.destroy()
        except tkinter.TclError as error:
            raise FolderPickerUnavailableError(
                "The folder picker could not be opened. Enter or paste a folder path instead."
            ) from error

        return selected_path or None

    def _normalize_path(self, path_value: str) -> Path:
        if not path_value.strip():
            raise WorkspaceLocationError("Choose a folder before continuing.")

        path = Path(path_value).expanduser()
        if not path.is_absolute():
            raise WorkspaceLocationError("Enter an absolute folder path.")
        normalized_path = path.resolve(strict=False)
        if normalized_path == Path(normalized_path.anchor):
            raise WorkspaceLocationError("Choose a dedicated folder, not a drive root.")
        return normalized_path

    def _validate_existing_workspace(self, workspace_path: Path) -> None:
        try:
            if not workspace_path.is_dir():
                raise WorkspaceLocationError(
                    f"The configured workspace '{workspace_path}' could not be found. Locate its new folder or forget this saved location."
                )
            if not (workspace_path / WORKSPACE_MARKER_NAME).is_file() or not (
                workspace_path / DATABASE_FILE_NAME
            ).is_file():
                raise WorkspaceLocationError(
                    f"The configured workspace '{workspace_path}' is incomplete or cannot be recognized. Locate its intact folder or forget this saved location."
                )
        except OSError as error:
            raise WorkspaceLocationError(
                f"The configured workspace '{workspace_path}' cannot be accessed. Locate it after restoring access."
            ) from error

    @staticmethod
    def _is_within(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True

    @staticmethod
    def _checkpoint_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    @staticmethod
    def _file_manifest(workspace_path: Path) -> dict[str, tuple[int, str]]:
        manifest: dict[str, tuple[int, str]] = {}
        for entry in workspace_path.rglob("*"):
            if entry.is_symlink():
                raise WorkspaceLocationError("A workspace containing symbolic links cannot be moved yet.")
            if entry.is_file():
                digest = hashlib.sha256()
                with entry.open("rb") as artifact:
                    for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                        digest.update(chunk)
                manifest[str(entry.relative_to(workspace_path))] = (entry.stat().st_size, digest.hexdigest())
        return manifest

    def _write_configuration(self, workspace_path: Path) -> None:
        self._configuration_directory.mkdir(parents=True, exist_ok=True)
        self._write_json_atomically(
            self.configuration_file,
            {
                "format_version": WORKSPACE_FORMAT_VERSION,
                "workspace_path": str(workspace_path),
            },
        )

    def _write_workspace_marker(self, workspace_path: Path) -> None:
        self._write_json_atomically(
            workspace_path / WORKSPACE_MARKER_NAME,
            {
                "application": APPLICATION_NAME,
                "database_file": DATABASE_FILE_NAME,
                "format_version": WORKSPACE_FORMAT_VERSION,
            },
        )

    @staticmethod
    def _write_json_atomically(path: Path, content: dict[str, object]) -> None:
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(content, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)
