"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from jeromes_laboratory.api.schemas import HealthResponse

DEFAULT_FRONTEND_DIRECTORY = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(static_directory: Path | None = DEFAULT_FRONTEND_DIRECTORY) -> FastAPI:
    """Create the local API application."""
    application = FastAPI(
        title="Jerome's Laboratory",
        description="Local API for a provenance-first scientific research workflow.",
        version="0.0.0",
    )

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    if static_directory is not None and (static_directory / "index.html").is_file():
        application.mount(
            "/",
            StaticFiles(directory=static_directory, html=True),
            name="frontend",
        )

    return application


app = create_app()
