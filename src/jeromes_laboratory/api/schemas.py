"""Schemas exposed by the local HTTP API."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Public health information for the local application."""

    status: Literal["ok"] = "ok"
    application: str = "Jerome's Laboratory"

