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
    evidence_strategy_prompt: str
    evidence_strategy_prompt_version: str
    evidence_strategy_prompt_is_editable: bool
    source_queries_prompt: str
    source_queries_prompt_version: str
    source_queries_prompt_is_editable: bool


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


class UpdateEvidenceStrategyPromptRequest(BaseModel):
    """Instructions used to generate a reviewable evidence-investigation strategy."""

    prompt: str = Field(min_length=1, max_length=20_000)


class UpdateEvidenceStrategyOutputRequest(BaseModel):
    """A manual strategy revision that needs approval of its exact version."""

    markdown: str = Field(min_length=1, max_length=100_000)
    base_version: int = Field(ge=1)


class ApproveEvidenceStrategyRequest(BaseModel):
    """Approve the effective strategy version reviewed by the user."""

    base_version: int = Field(ge=1)


class UpdateSourceQueriesPromptRequest(BaseModel):
    """Instructions for the Europe PMC query-drafting job."""

    prompt: str = Field(min_length=1, max_length=20_000)


class EnqueueSourceQueriesRequest(BaseModel):
    """Optional user guidance captured exactly in the immutable job input."""

    note: str = Field(default="", max_length=10_000)


class UpdateSourceQueriesRequest(BaseModel):
    """One reviewed query-set version with inclusion decisions."""

    queries: list[dict[str, object]] = Field(min_length=1, max_length=16)
    base_version: int = Field(ge=1)


class ApproveSourceQueriesRequest(BaseModel):
    """Approve only the current effective query-set version."""

    base_version: int = Field(ge=1)


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
    provider: LLMProviderName | Literal["europe_pmc"]
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
    estimated_cost: str | None
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
    evidence_strategy_approved_at: str | None
    evidence_strategy_is_editable: bool
    source_queries: dict[str, object] | None
    original_source_queries: dict[str, object] | None
    source_queries_approved_at: str | None
    source_queries_is_editable: bool


class SearchRunResponse(BaseModel):
    """Progress and completeness of one included Europe PMC query."""

    query_id: str
    query_title: str
    status: str
    total_hits: int | None
    retrieved_count: int
    truncated: bool
    started_at: str | None
    completed_at: str | None
    error: str | None


class RetrievalQuerySummaryResponse(SearchRunResponse):
    """One query's saved source IDs not found by another query in this job."""

    unique_to_query: int


class RetrievalSourceCountResponse(BaseModel):
    source: str
    unique_records: int
    raw_records: int


class RetrievalSummaryResponse(BaseModel):
    """Saved discoveries and provisional, read-only same-article matching."""

    runs: list[RetrievalQuerySummaryResponse]
    reported_hits: int
    raw_saved_records: int
    distinct_source_records: int
    repeat_discoveries: int
    records_in_multiple_queries: int
    distinct_records_with_abstract: int
    provisional_record_groups: int | None
    additional_source_ids_grouped: int | None
    groups_with_metadata_differences: int | None
    sources: list[RetrievalSourceCountResponse]


class RelevancePreviewRequest(BaseModel):
    retrieval_job_id: str
    scoring_limit: int | None = Field(default=None, ge=1, le=100_000)
    calibration_count: int = Field(ge=1, le=30)
    seed: int = Field(ge=0, le=2_147_483_647)
    instructions: str = Field(min_length=40, max_length=20_000)


class StartRelevanceCalibrationRequest(RelevancePreviewRequest):
    expected_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_provider: LLMProviderName
    expected_model: str
    prompt_generation_job_id: str | None = None


class UpdateRelevancePromptRequest(BaseModel):
    scoring_prompt: str = Field(min_length=100, max_length=12_000)
    base_version: int = Field(ge=1)


class RelevancePreviewResponse(BaseModel):
    provider: LLMProviderName | None
    model: str | None
    algorithm_version: str
    retrieval_job_id: str
    seed: int
    available_distinct_source_records: int
    scoring_limit: int | None
    calibration_count: int
    selected_manifest_sha256: str
    selected_metadata_sha256: str
    calibration_records: list[dict[str, object]]
    selected_by_collection: list[dict[str, object]]
    selected_by_query: list[dict[str, object]]
    calibration_input_tokens_estimate: int
    compact_calibration_input_tokens_estimate: int
    estimated_calibration_output_tokens: int
    prompt_generation_input_tokens_estimate: int
    estimated_prompt_generation_output_tokens: int
    estimated_scoring_input_tokens: int
    estimated_scoring_output_tokens: int
    calibration_cost: dict[str, object]
    compact_calibration_cost: dict[str, object]
    prompt_generation_cost: dict[str, object]
    scoring_cost: dict[str, object]
    per_1000_input_tokens_estimate: int
    per_1000_output_tokens_estimate: int
    per_1000_cost: dict[str, object]


class RelevanceCalibrationResponse(BaseModel):
    schema_version: Literal[1]
    calibration: list[dict[str, object]]


class RelevancePromptGenerationResponse(BaseModel):
    schema_version: Literal[1]
    scoring_prompt: str
    sample_observations: list[str]


class ClientStateResponse(BaseModel):
    """Device-local navigation state, not research data."""

    selected_project_id: str | None = None
    scroll_top: int = Field(default=0, ge=0)


class UpdateClientStateRequest(ClientStateResponse):
    """The project and scroll location to restore on the next local launch."""
