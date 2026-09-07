"""Smoke tests for the local HTTP API."""

import httpx
import pytest

from jeromes_laboratory.api.main import create_app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "Jerome's Laboratory",
    }
