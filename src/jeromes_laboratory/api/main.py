"""FastAPI application factory."""

from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.staticfiles import StaticFiles

from jeromes_laboratory.api.schemas import (
    FolderPickerResponse,
    HealthResponse,
    WorkspaceConfiguredResponse,
    WorkspaceForgottenResponse,
    WorkspacePathRequest,
    WorkspaceSetupStatus,
)
from jeromes_laboratory.storage.workspace import (
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
        return HealthResponse()

    @application.get("/api/setup", response_model=WorkspaceSetupStatus, tags=["setup"])
    def get_workspace_setup() -> WorkspaceSetupStatus:
        """Return first-run state without creating local research data."""
        workspace_path = application.state.workspace_service.configured_workspace_path()
        return WorkspaceSetupStatus(
            configured=workspace_path is not None,
            recommended_workspace_path=str(
                application.state.workspace_service.recommended_workspace_path
            ),
            setup_token=application.state.setup_token,
            workspace_path=str(workspace_path) if workspace_path is not None else None,
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

    if static_directory is not None and (static_directory / "index.html").is_file():
        application.mount(
            "/",
            StaticFiles(directory=static_directory, html=True),
            name="frontend",
        )

    return application


app = create_app()
