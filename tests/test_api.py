"""Smoke tests for the local HTTP API."""

from pathlib import Path

import httpx
import pytest

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.storage.workspace import WorkspaceService


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


@pytest.mark.asyncio
async def test_workspace_setup_requires_token_and_initializes_selected_path(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup_response = await client.get("/api/setup")
        setup = setup_response.json()
        unauthorized_response = await client.post(
            "/api/setup/workspace",
            json={"path": str(tmp_path / "research")},
        )
        configured_response = await client.post(
            "/api/setup/workspace",
            json={"path": str(tmp_path / "research")},
            headers={"X-Jeromes-Lab-Setup-Token": setup["setup_token"]},
        )

    assert setup_response.status_code == 200
    assert setup["configured"] is False
    assert setup["recommended_workspace_path"] == str(tmp_path / "Documents" / "Jerome's Laboratory")
    assert unauthorized_response.status_code == 403
    assert configured_response.status_code == 200
    assert configured_response.json() == {"workspace_path": str(tmp_path / "research")}


@pytest.mark.asyncio
async def test_workspace_folder_picker_returns_the_native_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    selected_path = tmp_path / "selected-folder"
    monkeypatch.setattr(workspace_service, "choose_workspace_directory", lambda: str(selected_path))
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup = (await client.get("/api/setup")).json()
        response = await client.post(
            "/api/setup/select-folder",
            headers={"X-Jeromes-Lab-Setup-Token": setup["setup_token"]},
        )

    assert response.status_code == 200
    assert response.json() == {"path": str(selected_path)}


@pytest.mark.asyncio
async def test_forget_workspace_api_removes_only_the_saved_pointer(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    workspace_path = tmp_path / "research"
    workspace_service.configure_workspace(str(workspace_path))
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup = (await client.get("/api/setup")).json()
        response = await client.post(
            "/api/settings/forget-workspace",
            headers={"X-Jeromes-Lab-Setup-Token": setup["setup_token"]},
        )
        updated_setup = await client.get("/api/setup")

    assert response.status_code == 200
    assert response.json() == {"forgotten_workspace_path": str(workspace_path)}
    assert updated_setup.json()["configured"] is False
    assert (workspace_path / "artifacts").is_dir()
