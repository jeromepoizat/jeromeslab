"""Smoke tests for the local HTTP API."""

from pathlib import Path

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


@pytest.mark.asyncio
async def test_built_frontend_is_served(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Jerome's Laboratory</h1>", encoding="utf-8")
    transport = httpx.ASGITransport(app=create_app(static_directory=tmp_path))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Jerome's Laboratory" in response.text
