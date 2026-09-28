"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.staticfiles import StaticFiles

from jeromes_laboratory.api.schemas import (
    ApproveEvidenceStrategyRequest,
    ApproveResearchCharterRequest,
    ClientStateResponse,
    CreateProjectRequest,
    EnqueueResearchCharterRequest,
    FetchLLMModelsRequest,
    FetchLLMModelsResponse,
    FolderPickerResponse,
    HealthResponse,
    JobResponse,
    LLMProviderName,
    LLMProviderStatus,
    LLMSettingsResponse,
    ProjectResponse,
    RenameProjectRequest,
    SubmitEvidenceScopeAnswersRequest,
    SubmitIntentSelectionRequest,
    SubmitScopeAnswersRequest,
    SubmitScopeFollowUpAnswersRequest,
    UpdateClientStateRequest,
    UpdateEvidenceScopeAnswersRequest,
    UpdateEvidenceScopePromptRequest,
    UpdateEvidenceStrategyOutputRequest,
    UpdateEvidenceStrategyPromptRequest,
    UpdateIntentClarificationPromptRequest,
    UpdateIntentSelectionRequest,
    UpdateLLMSettingsRequest,
    UpdateQuestionDetailingOutputRequest,
    UpdateQuestionDetailingPromptRequest,
    UpdateQuestionRequest,
    UpdateResearchCharterOutputRequest,
    UpdateResearchCharterPromptRequest,
    UpdateScopeAnswersRequest,
    UpdateScopeClarificationPromptRequest,
    UpdateScopeFollowUpAnswersRequest,
    UpdateScopeReadinessPromptRequest,
    WorkspaceConfiguredResponse,
    WorkspaceForgottenResponse,
    WorkspaceMovedResponse,
    WorkspacePathRequest,
    WorkspaceSetupStatus,
)
from jeromes_laboratory.database.jobs import JobError, JobRecord, JobRepository
from jeromes_laboratory.database.projects import ProjectError, ProjectRecord, ProjectRepository
from jeromes_laboratory.jobs.worker import JobWorker
from jeromes_laboratory.llm.catalog import (
    PROVIDER_DISPLAY_NAMES,
    SUPPORTED_PROVIDERS,
    ModelCatalogError,
    ProviderModelCatalog,
    ProviderName,
)
from jeromes_laboratory.llm.generation import GenerationGateway, ProviderGenerationGateway
from jeromes_laboratory.llm.settings import LLMSettingsError, LLMSettingsService
from jeromes_laboratory.security.credentials import (
    CredentialStore,
    CredentialStoreError,
    NativeCredentialStore,
)
from jeromes_laboratory.storage.workspace import (
    DATABASE_FILE_NAME,
    FolderPickerUnavailableError,
    WorkspaceLocationError,
    WorkspaceService,
)
from jeromes_laboratory.workflow.scope_clarification import ScopeAnswer

DEFAULT_FRONTEND_DIRECTORY = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(
    static_directory: Path | None = DEFAULT_FRONTEND_DIRECTORY,
    workspace_service: WorkspaceService | None = None,
    llm_settings_service: LLMSettingsService | None = None,
    credential_store: CredentialStore | None = None,
    model_catalog: ProviderModelCatalog | None = None,
    generation_gateway: GenerationGateway | None = None,
    start_job_worker: bool = True,
) -> FastAPI:
    """Create the local API application."""
    selected_workspace_service = (
        workspace_service if workspace_service is not None else WorkspaceService()
    )
    selected_credential_store = (
        credential_store if credential_store is not None else NativeCredentialStore()
    )
    selected_generation_gateway = (
        generation_gateway if generation_gateway is not None else ProviderGenerationGateway()
    )
    worker = JobWorker(
        selected_workspace_service,
        selected_credential_store,
        selected_generation_gateway,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if start_job_worker:
            worker.start()
        try:
            yield
        finally:
            if start_job_worker:
                worker.stop()

    application = FastAPI(
        title="Jerome's Laboratory",
        description="Local API for a provenance-first scientific research workflow.",
        version="0.0.0",
        lifespan=lifespan,
    )
    application.state.workspace_service = selected_workspace_service
    application.state.llm_settings_service = (
        llm_settings_service if llm_settings_service is not None else LLMSettingsService()
    )
    application.state.credential_store = selected_credential_store
    application.state.model_catalog = (
        model_catalog if model_catalog is not None else ProviderModelCatalog()
    )
    application.state.setup_token = token_urlsafe(32)
    application.state.instance_id = None
    application.state.job_worker = worker

    def project_repository() -> ProjectRepository:
        """Open project storage only after a valid workspace has been selected."""
        try:
            workspace_path = application.state.workspace_service.initialize_configured_workspace()
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        if workspace_path is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Choose a workspace before creating or opening projects.",
            )
        return ProjectRepository(workspace_path / DATABASE_FILE_NAME)

    def project_response(record: ProjectRecord) -> ProjectResponse:
        return ProjectResponse(
            id=record.id,
            tag=record.tag,
            scientific_question=record.scientific_question,
            created_at=record.created_at,
            updated_at=record.updated_at,
            question_is_editable=record.question_is_editable,
            question_detailing_prompt=record.question_detailing_prompt,
            question_detailing_prompt_version=record.question_detailing_prompt_version,
            question_detailing_prompt_is_editable=record.question_detailing_prompt_is_editable,
            intent_clarification_prompt=record.intent_clarification_prompt,
            intent_clarification_prompt_version=record.intent_clarification_prompt_version,
            intent_clarification_prompt_is_editable=record.intent_clarification_prompt_is_editable,
            scope_clarification_prompt=record.scope_clarification_prompt,
            scope_clarification_prompt_version=record.scope_clarification_prompt_version,
            scope_clarification_prompt_is_editable=record.scope_clarification_prompt_is_editable,
            scope_readiness_prompt=record.scope_readiness_prompt,
            scope_readiness_prompt_version=record.scope_readiness_prompt_version,
            scope_readiness_prompt_is_editable=record.scope_readiness_prompt_is_editable,
            research_charter_prompt=record.research_charter_prompt,
            research_charter_prompt_version=record.research_charter_prompt_version,
            research_charter_prompt_is_editable=record.research_charter_prompt_is_editable,
            evidence_scope_prompt=record.evidence_scope_prompt,
            evidence_scope_prompt_version=record.evidence_scope_prompt_version,
            evidence_scope_prompt_is_editable=record.evidence_scope_prompt_is_editable,
            evidence_strategy_prompt=record.evidence_strategy_prompt,
            evidence_strategy_prompt_version=record.evidence_strategy_prompt_version,
            evidence_strategy_prompt_is_editable=record.evidence_strategy_prompt_is_editable,
        )

    def job_repository() -> JobRepository:
        try:
            workspace_path = application.state.workspace_service.initialize_configured_workspace()
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        if workspace_path is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Choose a workspace before using the research queue.",
            )
        return JobRepository(workspace_path / DATABASE_FILE_NAME)

    def job_response(record: JobRecord) -> JobResponse:
        return JobResponse(**record.__dict__)

    def require_setup_token(
        x_jeromes_lab_setup_token: Annotated[
            str | None,
            Header(alias="X-Jeromes-Lab-Setup-Token"),
        ] = None,
    ) -> None:
        if x_jeromes_lab_setup_token != application.state.setup_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The local setup token is missing or invalid.",
            )

    def llm_settings_response() -> LLMSettingsResponse:
        """Return global LLM defaults and key presence without exposing secrets."""
        try:
            settings = application.state.llm_settings_service.read()
        except LLMSettingsError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        credential_store_error: str | None = None
        providers: list[LLMProviderStatus] = []
        for provider in SUPPORTED_PROVIDERS:
            try:
                has_api_key = application.state.credential_store.get_api_key(provider) is not None
            except CredentialStoreError as error:
                has_api_key = False
                credential_store_error = str(error)
            providers.append(
                LLMProviderStatus(
                    id=provider,
                    display_name=PROVIDER_DISPLAY_NAMES[provider],
                    api_key_configured=has_api_key,
                    models=settings.model_cache[provider],
                )
            )
        selected_has_key = any(
            provider.id == settings.provider and provider.api_key_configured
            for provider in providers
        )
        configured = (
            settings.provider is not None
            and settings.model is not None
            and selected_has_key
            and settings.model in settings.model_cache[settings.provider]
        )
        return LLMSettingsResponse(
            configured=configured,
            onboarding_complete=configured or settings.setup_skipped,
            selected_provider=settings.provider,
            selected_model=settings.model,
            providers=providers,
            credential_store_error=credential_store_error,
        )

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(instance_id=application.state.instance_id)

    @application.get("/api/llm/settings", response_model=LLMSettingsResponse, tags=["llm"])
    def get_llm_settings() -> LLMSettingsResponse:
        """Return the device's non-secret global LLM configuration."""
        return llm_settings_response()

    @application.post(
        "/api/llm/providers/{provider}/models",
        response_model=FetchLLMModelsResponse,
        tags=["llm"],
    )
    def fetch_llm_models(
        provider: LLMProviderName,
        request: FetchLLMModelsRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> FetchLLMModelsResponse:
        """Validate a credential, save it securely, and cache compatible models."""
        typed_provider: ProviderName = provider
        supplied_key = request.api_key.strip() if request.api_key is not None else None
        try:
            api_key = supplied_key or application.state.credential_store.get_api_key(provider)
            if api_key is None:
                raise ModelCatalogError(
                    f"Enter an {PROVIDER_DISPLAY_NAMES[typed_provider]} API key."
                )
            models = application.state.model_catalog.fetch_models(typed_provider, api_key)
            if not models:
                raise ModelCatalogError(
                    f"No compatible text-generation models were found for this "
                    f"{PROVIDER_DISPLAY_NAMES[typed_provider]} account."
                )
            if supplied_key is not None:
                application.state.credential_store.set_api_key(provider, supplied_key)
            application.state.llm_settings_service.cache_models(typed_provider, models)
        except (CredentialStoreError, LLMSettingsError, ModelCatalogError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return FetchLLMModelsResponse(provider=provider, models=models)

    @application.put("/api/llm/settings", response_model=LLMSettingsResponse, tags=["llm"])
    def update_llm_settings(
        request: UpdateLLMSettingsRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> LLMSettingsResponse:
        """Change the global provider and model used by future LLM jobs."""
        try:
            if application.state.credential_store.get_api_key(request.provider) is None:
                raise LLMSettingsError("Fetch models with an API key before saving this provider.")
            application.state.llm_settings_service.select(request.provider, request.model)
        except (CredentialStoreError, LLMSettingsError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return llm_settings_response()

    @application.post("/api/llm/settings/skip", response_model=LLMSettingsResponse, tags=["llm"])
    def skip_llm_setup(
        _: Annotated[None, Depends(require_setup_token)],
    ) -> LLMSettingsResponse:
        """Allow local non-LLM use while leaving live jobs unconfigured."""
        try:
            application.state.llm_settings_service.skip_setup()
        except LLMSettingsError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return llm_settings_response()

    @application.delete(
        "/api/llm/providers/{provider}/api-key",
        response_model=LLMSettingsResponse,
        tags=["llm"],
    )
    def forget_llm_api_key(
        provider: LLMProviderName,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> LLMSettingsResponse:
        """Forget one provider key without exposing or touching workspace research data."""
        try:
            application.state.credential_store.delete_api_key(provider)
            application.state.llm_settings_service.clear_provider(provider)
        except (CredentialStoreError, LLMSettingsError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return llm_settings_response()

    @application.get("/api/setup", response_model=WorkspaceSetupStatus, tags=["setup"])
    def get_workspace_setup() -> WorkspaceSetupStatus:
        """Return first-run state without creating local research data."""
        try:
            availability = application.state.workspace_service.workspace_availability()
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        return WorkspaceSetupStatus(
            configured=availability.kind == "available",
            recommended_workspace_path=str(
                application.state.workspace_service.recommended_workspace_path
            ),
            setup_token=application.state.setup_token,
            workspace_path=str(availability.path) if availability.path is not None else None,
            workspace_state=availability.kind,
            workspace_error=availability.error,
        )

    @application.post(
        "/api/setup/select-folder",
        response_model=FolderPickerResponse,
        tags=["setup"],
    )
    def select_workspace_folder(
        _: Annotated[None, Depends(require_setup_token)],
    ) -> FolderPickerResponse:
        """Open the local operating-system folder picker for first-run setup."""
        try:
            selected_path = application.state.workspace_service.choose_workspace_directory()
        except FolderPickerUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(error),
            ) from error
        return FolderPickerResponse(path=selected_path)

    @application.post(
        "/api/setup/workspace",
        response_model=WorkspaceConfiguredResponse,
        tags=["setup"],
    )
    def configure_workspace(
        request: WorkspacePathRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> WorkspaceConfiguredResponse:
        """Initialize and remember a workspace after user confirmation."""
        try:
            location = application.state.workspace_service.configure_workspace(
                request.path,
                confirm_nonempty=request.confirm_nonempty,
            )
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return WorkspaceConfiguredResponse(workspace_path=str(location.path))

    @application.post(
        "/api/recovery/locate-workspace",
        response_model=WorkspaceConfiguredResponse,
        tags=["setup"],
    )
    def recover_workspace(
        request: WorkspacePathRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> WorkspaceConfiguredResponse:
        """Reconnect a moved workspace without copying or deleting its data."""
        try:
            location = application.state.workspace_service.recover_configured_workspace(
                request.path
            )
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return WorkspaceConfiguredResponse(workspace_path=str(location.path))

    @application.post(
        "/api/settings/forget-workspace",
        response_model=WorkspaceForgottenResponse,
        tags=["settings"],
    )
    def forget_workspace(
        _: Annotated[None, Depends(require_setup_token)],
    ) -> WorkspaceForgottenResponse:
        """Forget the workspace pointer without touching any workspace data."""
        try:
            workspace_path = application.state.workspace_service.forget_configured_workspace()
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return WorkspaceForgottenResponse(forgotten_workspace_path=str(workspace_path))

    @application.post(
        "/api/settings/move-workspace",
        response_model=WorkspaceMovedResponse,
        tags=["settings"],
    )
    def move_workspace(
        request: WorkspacePathRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> WorkspaceMovedResponse:
        """Verify a complete copy before changing the one saved workspace location."""
        try:
            previous_path, workspace_path = (
                application.state.workspace_service.move_configured_workspace(request.path)
            )
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return WorkspaceMovedResponse(
            previous_workspace_path=str(previous_path),
            workspace_path=str(workspace_path),
        )

    @application.get("/api/projects", response_model=list[ProjectResponse], tags=["projects"])
    def list_projects() -> list[ProjectResponse]:
        """List projects solely for the persistent navigation panel."""
        return [project_response(record) for record in project_repository().list_projects()]

    @application.post(
        "/api/projects",
        response_model=ProjectResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["projects"],
    )
    def create_project(
        request: CreateProjectRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Create a project from its exact scientific question."""
        try:
            return project_response(
                project_repository().create_project(request.scientific_question)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.patch(
        "/api/projects/{project_id}/tag", response_model=ProjectResponse, tags=["projects"]
    )
    def rename_project(
        project_id: str,
        request: RenameProjectRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Rename a mutable project display tag."""
        try:
            return project_response(project_repository().rename_project(project_id, request.tag))
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.patch(
        "/api/projects/{project_id}/scientific-question",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_scientific_question(
        project_id: str,
        request: UpdateQuestionRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Correct the question only before a future workflow run consumes it."""
        try:
            return project_response(
                project_repository().update_scientific_question(
                    project_id, request.scientific_question
                )
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.patch(
        "/api/projects/{project_id}/question-detailing-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_question_detailing_prompt(
        project_id: str,
        request: UpdateQuestionDetailingPromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the exact effective prompt before the future LLM operation runs."""
        try:
            return project_response(
                project_repository().update_question_detailing_prompt(project_id, request.prompt)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.get("/api/jobs", response_model=list[JobResponse], tags=["jobs"])
    def list_jobs() -> list[JobResponse]:
        """List the persistent queue and completed history for the local interface."""
        return [job_response(record) for record in job_repository().list_jobs()]

    @application.patch(
        "/api/projects/{project_id}/intent-clarification-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_intent_clarification_prompt(
        project_id: str,
        request: UpdateIntentClarificationPromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the exact prompt before intent clarification is enqueued."""
        try:
            return project_response(
                project_repository().update_intent_clarification_prompt(project_id, request.prompt)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.patch(
        "/api/projects/{project_id}/scope-clarification-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_scope_clarification_prompt(
        project_id: str,
        request: UpdateScopeClarificationPromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the exact prompt before the first scope round is enqueued."""
        try:
            return project_response(
                project_repository().update_scope_clarification_prompt(project_id, request.prompt)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.patch(
        "/api/projects/{project_id}/scope-readiness-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_scope_readiness_prompt(
        project_id: str,
        request: UpdateScopeReadinessPromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the exact prompt before readiness review is enqueued."""
        try:
            return project_response(
                project_repository().update_scope_readiness_prompt(project_id, request.prompt)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.post(
        "/api/projects/{project_id}/intent-clarification/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_intent_clarification(
        project_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Queue generation of dynamic research-intent choices."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_intent_clarification(
                project_id, settings.provider, settings.model
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return job_response(record)

    @application.post(
        "/api/projects/{project_id}/scope-clarification/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_scope_clarification(
        project_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Queue first-round scope questions from the effective research intent."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_scope_clarification(
                project_id, settings.provider, settings.model
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return job_response(record)

    @application.post(
        "/api/projects/{project_id}/scope-readiness/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_scope_readiness(
        project_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Queue the bounded readiness decision and optional follow-up generation."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_scope_readiness(
                project_id, settings.provider, settings.model
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return job_response(record)

    @application.post(
        "/api/projects/{project_id}/question-detailing/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_question_detailing(
        project_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Snapshot inputs and the global provider/model into the sequential queue."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_question_detailing(
                project_id,
                settings.provider,
                settings.model,
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return job_response(record)

    @application.post(
        "/api/jobs/{job_id}/cancel",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def cancel_job(
        job_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Cancel only while the job remains pending and no request may have left."""
        try:
            return job_response(job_repository().cancel(job_id))
        except JobError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

    @application.post(
        "/api/jobs/{job_id}/intent-selection",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def submit_intent_selection(
        job_id: str,
        request: SubmitIntentSelectionRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Confirm and preserve the user's research-intent decision."""
        try:
            return job_response(
                job_repository().submit_intent_selection(
                    job_id,
                    request.primary_intent_id,
                    request.secondary_intent_ids,
                    request.note,
                )
            )
        except JobError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.patch(
        "/api/jobs/{job_id}/intent-selection",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_intent_selection(
        job_id: str,
        request: UpdateIntentSelectionRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Select a new immutable intent version before downstream work exists."""
        try:
            return job_response(
                job_repository().edit_intent_selection(
                    job_id,
                    request.primary_intent_id,
                    request.secondary_intent_ids,
                    request.note,
                    request.base_version,
                )
            )
        except JobError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.post(
        "/api/jobs/{job_id}/scope-answers",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def submit_scope_answers(
        job_id: str,
        request: SubmitScopeAnswersRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Confirm and preserve one complete first-round scope response."""
        try:
            answers = [
                ScopeAnswer.model_validate(answer.model_dump()) for answer in request.answers
            ]
            return job_response(job_repository().submit_scope_answers(job_id, answers))
        except (JobError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.patch(
        "/api/jobs/{job_id}/scope-answers",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_scope_answers(
        job_id: str,
        request: UpdateScopeAnswersRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Select a new immutable answer version before downstream work exists."""
        try:
            answers = [
                ScopeAnswer.model_validate(answer.model_dump()) for answer in request.answers
            ]
            return job_response(
                job_repository().edit_scope_answers(job_id, answers, request.base_version)
            )
        except (JobError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.post(
        "/api/jobs/{job_id}/scope-follow-up-answers",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def submit_scope_follow_up_answers(
        job_id: str,
        request: SubmitScopeFollowUpAnswersRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Confirm and preserve the only automatic scope follow-up round."""
        try:
            answers = [
                ScopeAnswer.model_validate(answer.model_dump()) for answer in request.answers
            ]
            return job_response(job_repository().submit_scope_follow_up_answers(job_id, answers))
        except (JobError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.patch(
        "/api/jobs/{job_id}/scope-follow-up-answers",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_scope_follow_up_answers(
        job_id: str,
        request: UpdateScopeFollowUpAnswersRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Select a new follow-up answer version before charter work is queued."""
        try:
            answers = [
                ScopeAnswer.model_validate(answer.model_dump()) for answer in request.answers
            ]
            return job_response(
                job_repository().edit_scope_follow_up_answers(job_id, answers, request.base_version)
            )
        except (JobError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.patch(
        "/api/jobs/{job_id}/question-detailing-output",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_question_detailing_output(
        job_id: str,
        request: UpdateQuestionDetailingOutputRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Create and select a manual version while preserving the original output."""
        try:
            return job_response(
                job_repository().edit_question_detailing_output(
                    job_id,
                    request.markdown,
                    request.base_version,
                )
            )
        except JobError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error

    @application.patch(
        "/api/projects/{project_id}/research-charter-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_research_charter_prompt(
        project_id: str,
        request: UpdateResearchCharterPromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the prompt for a future charter attempt without changing earlier calls."""
        try:
            return project_response(
                project_repository().update_research_charter_prompt(project_id, request.prompt)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(error)
            ) from error

    @application.post(
        "/api/projects/{project_id}/research-charter/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_research_charter(
        project_id: str,
        request: EnqueueResearchCharterRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Queue a charter draft or an explicitly requested regeneration."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_research_charter(
                project_id,
                settings.provider,
                settings.model,
                previous_job_id=request.previous_job_id,
                base_version=request.base_version,
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return job_response(record)

    @application.patch(
        "/api/jobs/{job_id}/research-charter-output",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_research_charter_output(
        job_id: str,
        request: UpdateResearchCharterOutputRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Create a new draft version while retaining the original charter and approvals."""
        try:
            return job_response(job_repository().edit_research_charter_output(
                job_id, request.markdown, request.base_version
            ))
        except JobError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(error)
            ) from error

    @application.post(
        "/api/jobs/{job_id}/research-charter-approval",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def approve_research_charter(
        job_id: str,
        request: ApproveResearchCharterRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Record explicit approval of the current effective charter version."""
        try:
            return job_response(job_repository().approve_research_charter(
                job_id, request.base_version
            ))
        except JobError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(error)
            ) from error

    @application.patch(
        "/api/projects/{project_id}/evidence-scope-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_evidence_scope_prompt(
        project_id: str,
        request: UpdateEvidenceScopePromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the exact advanced prompt before questionnaire generation."""
        try:
            return project_response(
                project_repository().update_evidence_scope_prompt(project_id, request.prompt)
            )
        except ProjectError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(error)
            ) from error

    @application.post(
        "/api/projects/{project_id}/evidence-scope/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_evidence_scope_questionnaire(
        project_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Queue charter-derived evidence themes and search-scope decisions."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_evidence_scope_questionnaire(
                project_id, settings.provider, settings.model
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return job_response(record)

    @application.post(
        "/api/jobs/{job_id}/evidence-scope-answers",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def submit_evidence_scope_answers(
        job_id: str,
        request: SubmitEvidenceScopeAnswersRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Confirm one complete evidence-search scope answer set."""
        try:
            answers = [
                ScopeAnswer.model_validate(answer.model_dump()) for answer in request.answers
            ]
            return job_response(job_repository().submit_evidence_scope_answers(job_id, answers))
        except (JobError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.patch(
        "/api/jobs/{job_id}/evidence-scope-answers",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_evidence_scope_answers(
        job_id: str,
        request: UpdateEvidenceScopeAnswersRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Select a new evidence-scope answer version before downstream work."""
        try:
            answers = [
                ScopeAnswer.model_validate(answer.model_dump()) for answer in request.answers
            ]
            return job_response(
                job_repository().edit_evidence_scope_answers(
                    job_id, answers, request.base_version
                )
            )
        except (JobError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.patch(
        "/api/projects/{project_id}/evidence-strategy-prompt",
        response_model=ProjectResponse,
        tags=["projects"],
    )
    def update_evidence_strategy_prompt(
        project_id: str,
        request: UpdateEvidenceStrategyPromptRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Save the exact strategy prompt before its first job."""
        try:
            return project_response(
                project_repository().update_evidence_strategy_prompt(
                    project_id, request.prompt
                )
            )
        except ProjectError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.post(
        "/api/projects/{project_id}/evidence-strategy/jobs",
        response_model=JobResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["jobs"],
    )
    def enqueue_evidence_strategy(
        project_id: str,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Queue a strategy draft from the approved charter and exact scope answers."""
        try:
            settings = application.state.llm_settings_service.read()
            if settings.provider is None or settings.model is None:
                raise JobError("Configure an LLM provider and model before starting this job.")
            if application.state.credential_store.get_api_key(settings.provider) is None:
                raise JobError("The selected provider API key is no longer available.")
            record = job_repository().enqueue_evidence_strategy(
                project_id, settings.provider, settings.model
            )
        except (CredentialStoreError, LLMSettingsError, JobError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return job_response(record)

    @application.patch(
        "/api/jobs/{job_id}/evidence-strategy-output",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def edit_evidence_strategy_output(
        job_id: str,
        request: UpdateEvidenceStrategyOutputRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Create an effective strategy version while preserving the original."""
        try:
            return job_response(
                job_repository().edit_evidence_strategy_output(
                    job_id, request.markdown, request.base_version
                )
            )
        except JobError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.post(
        "/api/jobs/{job_id}/evidence-strategy-approval",
        response_model=JobResponse,
        tags=["jobs"],
    )
    def approve_evidence_strategy(
        job_id: str,
        request: ApproveEvidenceStrategyRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> JobResponse:
        """Approve only the current effective strategy artifact version."""
        try:
            return job_response(
                job_repository().approve_evidence_strategy(job_id, request.base_version)
            )
        except JobError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @application.get("/api/client-state", response_model=ClientStateResponse, tags=["client"])
    def get_client_state() -> ClientStateResponse:
        """Return optional device-local navigation state."""
        content = application.state.workspace_service.read_client_state()
        selected_project_id = content.get("selected_project_id")
        scroll_top = content.get("scroll_top")
        return ClientStateResponse(
            selected_project_id=selected_project_id
            if isinstance(selected_project_id, str)
            else None,
            scroll_top=scroll_top if isinstance(scroll_top, int) and scroll_top >= 0 else 0,
        )

    @application.put("/api/client-state", response_model=ClientStateResponse, tags=["client"])
    def update_client_state(
        request: UpdateClientStateRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ClientStateResponse:
        """Save non-research navigation state in per-user application configuration."""
        try:
            application.state.workspace_service.write_client_state(
                request.selected_project_id,
                request.scroll_top,
            )
        except WorkspaceLocationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        return ClientStateResponse(
            selected_project_id=request.selected_project_id,
            scroll_top=request.scroll_top,
        )

    if static_directory is not None and (static_directory / "index.html").is_file():
        application.mount(
            "/",
            StaticFiles(directory=static_directory, html=True),
            name="frontend",
        )

    return application


app = create_app()
