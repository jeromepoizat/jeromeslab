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


class ProjectResponse(BaseModel):
    """The initial durable research project state."""

    id: str
    tag: str
    scientific_question: str
    created_at: str
    updated_at: str
    question_is_editable: bool
    question_detailing_prompt: str
    question_detailing_prompt_version: str


class CreateProjectRequest(BaseModel):
    """The exact initial scientific question supplied by the user."""

    scientific_question: str = Field(min_length=1, max_length=20_000)


class RenameProjectRequest(BaseModel):
    """A mutable display tag for a project."""

    tag: str = Field(min_length=1, max_length=64)


class UpdateQuestionRequest(BaseModel):
    """A pre-workflow correction to the project scientific question."""

    scientific_question: str = Field(min_length=1, max_length=20_000)


class UpdateQuestionDetailingPromptRequest(BaseModel):
    """The exact project prompt for the question-detailing LLM operation."""

    prompt: str = Field(min_length=1, max_length=20_000)


class ClientStateResponse(BaseModel):
    """Device-local navigation state, not research data."""

    selected_project_id: str | None = None
    scroll_top: int = Field(default=0, ge=0)


class UpdateClientStateRequest(ClientStateResponse):
    """The project and scroll location to restore on the next local launch."""
