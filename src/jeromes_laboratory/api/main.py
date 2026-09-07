"""FastAPI application factory."""

from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.staticfiles import StaticFiles

from jeromes_laboratory.api.schemas import (
    ClientStateResponse,
    CreateProjectRequest,
    FolderPickerResponse,
    HealthResponse,
    ProjectResponse,
    RenameProjectRequest,
    UpdateClientStateRequest,
    UpdateQuestionDetailingPromptRequest,
    UpdateQuestionRequest,
    WorkspaceConfiguredResponse,
    WorkspaceForgottenResponse,
    WorkspaceMovedResponse,
    WorkspacePathRequest,
    WorkspaceSetupStatus,
)
from jeromes_laboratory.database.projects import ProjectError, ProjectRecord, ProjectRepository
from jeromes_laboratory.storage.workspace import (
    DATABASE_FILE_NAME,
    FolderPickerUnavailableError,
    WorkspaceLocationError,
    WorkspaceService,
)

DEFAULT_FRONTEND_DIRECTORY = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(
    static_directory: Path | None = DEFAULT_FRONTEND_DIRECTORY,
    workspace_service: WorkspaceService | None = None,
) -> FastAPI:
    """Create the local API application."""
    application = FastAPI(
        title="Jerome's Laboratory",
        description="Local API for a provenance-first scientific research workflow.",
        version="0.0.0",
    )
    application.state.workspace_service = (
        workspace_service if workspace_service is not None else WorkspaceService()
    )
    application.state.setup_token = token_urlsafe(32)
    application.state.instance_id = None

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
        )

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

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(instance_id=application.state.instance_id)

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
            location = application.state.workspace_service.recover_configured_workspace(request.path)
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
            previous_path, workspace_path = application.state.workspace_service.move_configured_workspace(
                request.path
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
            return project_response(project_repository().create_project(request.scientific_question))
        except ProjectError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

    @application.patch("/api/projects/{project_id}/tag", response_model=ProjectResponse, tags=["projects"])
    def rename_project(
        project_id: str,
        request: RenameProjectRequest,
        _: Annotated[None, Depends(require_setup_token)],
    ) -> ProjectResponse:
        """Rename a mutable project display tag."""
        try:
            return project_response(project_repository().rename_project(project_id, request.tag))
        except ProjectError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

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
                project_repository().update_scientific_question(project_id, request.scientific_question)
            )
        except ProjectError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error

    @application.get("/api/client-state", response_model=ClientStateResponse, tags=["client"])
    def get_client_state() -> ClientStateResponse:
        """Return optional device-local navigation state."""
        content = application.state.workspace_service.read_client_state()
        selected_project_id = content.get("selected_project_id")
        scroll_top = content.get("scroll_top")
        return ClientStateResponse(
            selected_project_id=selected_project_id if isinstance(selected_project_id, str) else None,
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
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
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
