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
    intent_clarification_prompt: str
    intent_clarification_prompt_version: str
    intent_clarification_prompt_is_editable: bool
    scope_clarification_prompt: str
    scope_clarification_prompt_version: str
    scope_clarification_prompt_is_editable: bool
    scope_readiness_prompt: str
    scope_readiness_prompt_version: str
    scope_readiness_prompt_is_editable: bool
    research_charter_prompt: str
    research_charter_prompt_version: str
    research_charter_prompt_is_editable: bool
    evidence_scope_prompt: str
    evidence_scope_prompt_version: str
    evidence_scope_prompt_is_editable: bool


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


class UpdateIntentClarificationPromptRequest(BaseModel):
    """The exact project prompt used to generate research-intent choices."""

    prompt: str = Field(min_length=1, max_length=20_000)


class UpdateScopeClarificationPromptRequest(BaseModel):
    """The exact project prompt used to generate first-round scope questions."""

    prompt: str = Field(min_length=1, max_length=20_000)


class UpdateScopeReadinessPromptRequest(BaseModel):
    """The exact project prompt used for the bounded readiness review."""

    prompt: str = Field(min_length=1, max_length=20_000)


class UpdateQuestionDetailingOutputRequest(BaseModel):
    """A manual revision based on the currently effective immutable version."""

    markdown: str = Field(min_length=1, max_length=100_000)
    base_version: int = Field(ge=1)


class UpdateResearchCharterPromptRequest(BaseModel):
    """Instructions saved for the next explicit charter-generation attempt."""

    prompt: str = Field(min_length=1, max_length=20_000)


class UpdateEvidenceScopePromptRequest(BaseModel):
    """Instructions used to generate the evidence-search scope questionnaire."""

    prompt: str = Field(min_length=1, max_length=20_000)


class EnqueueResearchCharterRequest(BaseModel):
    """An initial attempt or an explicit replacement of the visible charter."""

    previous_job_id: str | None = Field(default=None, min_length=1, max_length=64)
    base_version: int | None = Field(default=None, ge=1)


class UpdateResearchCharterOutputRequest(BaseModel):
    """A manual charter revision that will require fresh approval."""

    markdown: str = Field(min_length=1, max_length=100_000)
    base_version: int = Field(ge=1)


class ApproveResearchCharterRequest(BaseModel):
    """Approve precisely the effective charter version reviewed by the user."""

    base_version: int = Field(ge=1)


JobStatus = Literal["pending", "awaiting_response", "completed", "failed", "cancelled"]


class IntentOptionResponse(BaseModel):
    """One provider-generated research-intent option."""

    id: str
    label: str
    description: str


class IntentQuestionsResponse(BaseModel):
    """Validated intent questionnaire stored as an immutable artifact."""

    schema_version: Literal[1]
    question: str
    explanation: str
    options: list[IntentOptionResponse]


class IntentSelectionResponse(BaseModel):
    """The user's immutable confirmed intent selection."""

    schema_version: Literal[1]
    questions_artifact_id: str
    primary_intent_id: str
    secondary_intent_ids: list[str]
    note: str


class SubmitIntentSelectionRequest(BaseModel):
    """One primary intent, optional secondary intents, and a qualifying note."""

    primary_intent_id: str = Field(min_length=1, max_length=64)
    secondary_intent_ids: list[str] = Field(default_factory=list, max_length=7)
    note: str = Field(default="", max_length=5_000)


class UpdateIntentSelectionRequest(SubmitIntentSelectionRequest):
    """A new effective version based on the currently selected confirmation."""

    base_version: int = Field(ge=1)


class ScopeOptionResponse(BaseModel):
    """One provider-generated answer option for a scope decision."""

    id: str
    label: str
    description: str


class ScopeQuestionResponse(BaseModel):
    """One validated decision in a scope-clarification round."""

    id: str
    question: str
    why_it_matters: str
    selection_mode: Literal["single_choice", "multiple_choice"]
    option_structure: Literal["independent", "cumulative"] | None = None
    options: list[ScopeOptionResponse]


class ScopeQuestionsResponse(BaseModel):
    """The immutable provider-generated first scope round."""

    schema_version: Literal[1, 2, 3]
    introduction: str
    questions: list[ScopeQuestionResponse]


class ScopeAnswerRequest(BaseModel):
    """A flexible answer using suggestions, a manual note, or explicit uncertainty."""

    question_id: str = Field(min_length=1, max_length=64)
    selected_option_ids: list[str] = Field(default_factory=list, max_length=7)
    note: str = Field(default="", max_length=5_000)
    is_unsure: bool = False


class ScopeAnswersResponse(BaseModel):
    """The currently effective immutable answer version."""

    schema_version: Literal[1]
    questions_artifact_id: str
    answers: list[ScopeAnswerRequest]


class SubmitScopeAnswersRequest(BaseModel):
    """A complete first-round scope response."""

    answers: list[ScopeAnswerRequest] = Field(min_length=1, max_length=7)


class UpdateScopeAnswersRequest(SubmitScopeAnswersRequest):
    """A new answer version based on the effective version seen by the user."""

    base_version: int = Field(ge=1)


class ScopeReadinessResponse(BaseModel):
    """Validated readiness decision and optional final questionnaire."""

    schema_version: Literal[1, 2]
    ready_for_charter: bool
    assessment: str
    remaining_uncertainties: list[str]
    follow_up_questions: list[ScopeQuestionResponse]


class EvidenceThemeResponse(BaseModel):
    """One mandatory evidence theme derived from the approved charter."""

    id: str
    label: str
    purpose: str
    evidence_domains: list[str]
    negative_evidence_required: bool


class EvidenceScopeQuestionResponse(ScopeQuestionResponse):
    """One evidence-acquisition decision with an optional advisory recommendation."""

    option_structure: Literal["independent", "cumulative"]
    recommended_option_ids: list[str]
    recommendation_reason: str


class EvidenceScopeQuestionsResponse(BaseModel):
    """Validated charter-derived evidence themes and scope questions."""

    schema_version: Literal[1]
    introduction: str
    charter_evidence_themes: list[EvidenceThemeResponse]
    questions: list[EvidenceScopeQuestionResponse]


class SubmitEvidenceScopeAnswersRequest(BaseModel):
    """A complete response to the generated evidence-scope questions."""

    answers: list[ScopeAnswerRequest] = Field(min_length=1, max_length=6)


class UpdateEvidenceScopeAnswersRequest(SubmitEvidenceScopeAnswersRequest):
    """A new answer version based on the effective version shown to the user."""

    base_version: int = Field(ge=1)


class SubmitScopeFollowUpAnswersRequest(BaseModel):
    """A complete response to the optional one-to-five-question follow-up."""

    answers: list[ScopeAnswerRequest] = Field(min_length=1, max_length=5)


class UpdateScopeFollowUpAnswersRequest(SubmitScopeFollowUpAnswersRequest):
    """A new follow-up version based on the effective version shown."""

    base_version: int = Field(ge=1)


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
    workflow_input_snapshot_json: str | None
    error: str | None
    output_markdown: str | None
    original_output_markdown: str | None
    effective_output_markdown: str | None
    effective_output_version: int | None
    output_was_edited: bool
    llm_call_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: int | None
    cost_status: str | None
    intent_questions: IntentQuestionsResponse | None
    intent_selection: IntentSelectionResponse | None
    intent_selection_version: int | None
    intent_selection_is_editable: bool
    scope_questions: ScopeQuestionsResponse | None
    scope_answers: ScopeAnswersResponse | None
    scope_answers_version: int | None
    scope_answers_is_editable: bool
    scope_readiness_review: ScopeReadinessResponse | None
    scope_follow_up_answers: ScopeAnswersResponse | None
    scope_follow_up_answers_version: int | None
    scope_follow_up_answers_is_editable: bool
    charter_approved_at: str | None
    charter_is_editable: bool
    charter_can_regenerate: bool
    evidence_scope_questions: EvidenceScopeQuestionsResponse | None
    evidence_scope_answers: ScopeAnswersResponse | None
    evidence_scope_answers_version: int | None
    evidence_scope_answers_is_editable: bool


class ClientStateResponse(BaseModel):
    """Device-local navigation state, not research data."""

    selected_project_id: str | None = None
    scroll_top: int = Field(default=0, ge=0)


class UpdateClientStateRequest(ClientStateResponse):
    """The project and scroll location to restore on the next local launch."""
