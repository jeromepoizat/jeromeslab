"""Schemas exposed by the local HTTP API."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Public health information for the local application."""

    status: Literal["ok"] = "ok"
    application: str = "Jerome's Laboratory"
    instance_id: str | None = None


class WorkspaceSetupStatus(BaseModel):
    """Safe state needed by the first-run workspace setup screen."""

    configured: bool
    recommended_workspace_path: str
    setup_token: str
    workspace_path: str | None = None
    workspace_state: Literal["unconfigured", "available", "unavailable"]
    workspace_error: str | None = None


class WorkspacePathRequest(BaseModel):
    """A workspace path supplied by the local browser client."""

    path: str = Field(min_length=1, max_length=4096)
    confirm_nonempty: bool = False


class WorkspaceConfiguredResponse(BaseModel):
    """The successfully initialized local workspace."""

    workspace_path: str


class FolderPickerResponse(BaseModel):
    """A directory selected by the operating-system folder picker."""

    path: str | None


class WorkspaceForgottenResponse(BaseModel):
    """Confirmation that only this device's workspace pointer was removed."""

    forgotten_workspace_path: str


class WorkspaceMovedResponse(BaseModel):
    """Confirmation that a verified copy is now the remembered workspace."""

    previous_workspace_path: str
    workspace_path: str
