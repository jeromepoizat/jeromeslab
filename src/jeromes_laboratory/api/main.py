"""FastAPI application factory."""

from fastapi import FastAPI

from jeromes_laboratory.api.schemas import HealthResponse


def create_app() -> FastAPI:
    """Create the local API application."""
    application = FastAPI(
        title="Jerome's Laboratory",
        description="Local API for a provenance-first scientific research workflow.",
        version="0.0.0",
    )

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()

