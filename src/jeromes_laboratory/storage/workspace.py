"""Manage the user-selected local research workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from platformdirs import user_config_path, user_documents_path

from jeromes_laboratory.database.initialize import upgrade_database

APPLICATION_NAME = "Jerome's Laboratory"
CONFIGURATION_FILE_NAME = "workspace.json"
WORKSPACE_MARKER_NAME = ".jeromes-laboratory-workspace.json"
DATABASE_FILE_NAME = "jeromes-laboratory.sqlite3"
WORKSPACE_FORMAT_VERSION = 1

WorkspacePathKind = Literal["empty", "existing_workspace", "not_empty", "new"]


class WorkspaceLocationError(ValueError):
    """Raised when a selected or saved workspace location is not usable."""


class FolderPickerUnavailableError(RuntimeError):
    """Raised when the operating-system folder picker cannot be opened."""


@dataclass(frozen=True)
class WorkspaceLocation:
    """A normalized workspace path and its current on-disk state."""

    path: Path
    kind: WorkspacePathKind


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

    def initialize_configured_workspace(self) -> Path | None:
        """Apply database migrations before serving an already-configured workspace."""
        workspace_path = self.configured_workspace_path()
        if workspace_path is None:
            return None

        marker = workspace_path / WORKSPACE_MARKER_NAME
        if not marker.is_file():
            raise WorkspaceLocationError(
                f"The configured workspace '{workspace_path}' could not be found. "
                "Restore it or update the workspace location."
            )

        try:
            upgrade_database(workspace_path / DATABASE_FILE_NAME)
        except OSError as error:
            raise WorkspaceLocationError(
                f"Jerome's Laboratory could not open '{workspace_path}'."
            ) from error
        return workspace_path

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
