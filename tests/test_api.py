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
        "instance_id": None,
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
async def test_setup_reports_missing_workspace_and_can_recover_it(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    original_path = tmp_path / "research"
    recovered_path = tmp_path / "moved-research"
    workspace_service.configure_workspace(str(original_path))
    original_path.rename(recovered_path)
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup = (await client.get("/api/setup")).json()
        response = await client.post(
            "/api/recovery/locate-workspace",
            json={"path": str(recovered_path)},
            headers={"X-Jeromes-Lab-Setup-Token": setup["setup_token"]},
        )

    assert setup["workspace_state"] == "unavailable"
    assert response.status_code == 200
    assert response.json() == {"workspace_path": str(recovered_path)}


@pytest.mark.asyncio
async def test_move_workspace_api_keeps_original_data(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    source_path = tmp_path / "research"
    destination_path = tmp_path / "moved-research"
    workspace_service.configure_workspace(str(source_path))
    (source_path / "artifacts" / "data.txt").write_text("data", encoding="utf-8")
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup = (await client.get("/api/setup")).json()
        response = await client.post(
            "/api/settings/move-workspace",
            json={"path": str(destination_path)},
            headers={"X-Jeromes-Lab-Setup-Token": setup["setup_token"]},
        )

    assert response.status_code == 200
    assert response.json() == {
        "previous_workspace_path": str(source_path),
        "workspace_path": str(destination_path),
    }
    assert (source_path / "artifacts" / "data.txt").read_text(encoding="utf-8") == "data"


@pytest.mark.asyncio
async def test_projects_have_sequential_default_tags_and_mutable_display_tags(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    workspace_service.configure_workspace(str(tmp_path / "research"))
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup = (await client.get("/api/setup")).json()
        headers = {"X-Jeromes-Lab-Setup-Token": setup["setup_token"]}
        first = await client.post(
            "/api/projects",
            json={"scientific_question": "What is the evidence for intervention X?"},
            headers=headers,
        )
        second = await client.post(
            "/api/projects",
            json={"scientific_question": "What is the evidence for intervention Y?"},
            headers=headers,
        )
        renamed = await client.patch(
            f"/api/projects/{first.json()['id']}/tag",
            json={"tag": "CARDIO"},
            headers=headers,
        )
        updated_question = await client.patch(
            f"/api/projects/{first.json()['id']}/scientific-question",
            json={"scientific_question": "What is the corrected evidence for intervention X?"},
            headers=headers,
        )
        updated_prompt = await client.patch(
            f"/api/projects/{first.json()['id']}/question-detailing-prompt",
            json={"prompt": "Use this project's saved custom prompt."},
            headers=headers,
        )
        projects = await client.get("/api/projects")

    assert first.status_code == 201
    assert first.json()["tag"] == "PROJ001"
    assert first.json()["scientific_question"] == "What is the evidence for intervention X?"
    assert first.json()["question_is_editable"] is True
    assert second.json()["tag"] == "PROJ002"
    assert renamed.json()["tag"] == "CARDIO"
    assert updated_question.json()["scientific_question"] == (
        "What is the corrected evidence for intervention X?"
    )
    assert updated_prompt.json()["question_detailing_prompt"] == (
        "Use this project's saved custom prompt."
    )
    assert updated_prompt.json()["question_detailing_prompt_version"] == "custom"
    assert [project["tag"] for project in projects.json()] == ["CARDIO", "PROJ002"]


@pytest.mark.asyncio
async def test_client_state_is_saved_outside_the_workspace_database(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup = (await client.get("/api/setup")).json()
        headers = {"X-Jeromes-Lab-Setup-Token": setup["setup_token"]}
        saved = await client.put(
            "/api/client-state",
            json={"selected_project_id": "project-id", "scroll_top": 240},
            headers=headers,
        )
        restored = await client.get("/api/client-state")

    assert saved.status_code == 200
    assert restored.json() == {"selected_project_id": "project-id", "scroll_top": 240}
    assert workspace_service.client_state_file.is_file()


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


@pytest.mark.asyncio
async def test_workspace_setup_reports_an_unreadable_saved_pointer(tmp_path: Path) -> None:
    workspace_service = WorkspaceService(
        configuration_directory=tmp_path / "config",
        documents_directory=tmp_path / "Documents",
    )
    workspace_service.configuration_file.mkdir(parents=True)
    transport = httpx.ASGITransport(
        app=create_app(static_directory=None, workspace_service=workspace_service)
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/setup")

    assert response.status_code == 503
    assert "not a valid file" in response.json()["detail"]
