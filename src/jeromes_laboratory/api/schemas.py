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


LLMProviderName = Literal["openai", "anthropic"]


class LLMProviderStatus(BaseModel):
    """Non-secret configuration and cached models for one provider."""

    id: LLMProviderName
    display_name: str
    api_key_configured: bool
    models: list[str]


class LLMSettingsResponse(BaseModel):
    """Global device-level LLM defaults without credential values."""

    configured: bool
    onboarding_complete: bool
    selected_provider: LLMProviderName | None
    selected_model: str | None
    providers: list[LLMProviderStatus]
    credential_store_error: str | None = None


class FetchLLMModelsRequest(BaseModel):
    """An optional replacement secret used only at the credential boundary."""

    api_key: str | None = None


class FetchLLMModelsResponse(BaseModel):
    """Compatible account-visible models returned by a provider."""

    provider: LLMProviderName
    models: list[str]


class UpdateLLMSettingsRequest(BaseModel):
    """Select the global provider and compatible model default."""

    provider: LLMProviderName
    model: str


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
    question_detailing_prompt_is_editable: bool


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


JobStatus = Literal["pending", "awaiting_response", "completed", "failed", "cancelled"]


class JobResponse(BaseModel):
    """Safe queue, result, and concise call-provenance state for the UI."""

    id: str
    project_id: str
    project_tag: str
    kind: str
    status: JobStatus
    created_at: str
    started_at: str | None
    completed_at: str | None
    provider: LLMProviderName
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


class ClientStateResponse(BaseModel):
    """Device-local navigation state, not research data."""

    selected_project_id: str | None = None
    scroll_top: int = Field(default=0, ge=0)


class UpdateClientStateRequest(ClientStateResponse):
    """The project and scroll location to restore on the next local launch."""
