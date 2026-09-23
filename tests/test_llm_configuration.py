"""Tests for provider model discovery and secure global LLM configuration."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from jeromes_laboratory.api.main import create_app
from jeromes_laboratory.llm.catalog import ModelCatalogError, ProviderModelCatalog
from jeromes_laboratory.llm.settings import LLMSettingsError, LLMSettingsService
from jeromes_laboratory.security.credentials import CredentialStoreError
from jeromes_laboratory.storage.workspace import WorkspaceService


class MemoryCredentialStore:
    """Test credential store that never touches the host operating system."""

    def __init__(self) -> None:
        self.keys: dict[str, str] = {}

    def get_api_key(self, provider: str) -> str | None:
        return self.keys.get(provider)

    def set_api_key(self, provider: str, api_key: str) -> None:
        self.keys[provider] = api_key

    def delete_api_key(self, provider: str) -> None:
        self.keys.pop(provider, None)


class UnavailableCredentialStore(MemoryCredentialStore):
    def get_api_key(self, provider: str) -> str | None:
        raise CredentialStoreError("The operating system credential store is unavailable.")


def catalog_with_responses(responses: dict[str, dict[str, object]]) -> ProviderModelCatalog:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = responses[str(request.url)]
        return httpx.Response(200, json=payload)

    return ProviderModelCatalog(transport=httpx.MockTransport(handler))


def test_openai_catalog_returns_only_supported_text_models() -> None:
    catalog = catalog_with_responses(
        {
            "https://api.openai.com/v1/models": {
                "data": [
                    {"id": "gpt-6-astra"},
                    {"id": "gpt-6-sol"},
                    {"id": "gpt-6-luna"},
                    {"id": "gpt-5.6-sol"},
                    {"id": "gpt-4.1-mini"},
                    {"id": "gpt-6-codex"},
                    {"id": "gpt-5.6-codex"},
                    {"id": "gpt-realtime"},
                    {"id": "text-embedding-3-large"},
                ]
            }
        }
    )

    assert catalog.fetch_models("openai", "secret") == [
        "gpt-6-astra",
        "gpt-6-sol",
        "gpt-6-luna",
        "gpt-5.6-sol",
        "gpt-4.1-mini",
    ]


def test_anthropic_catalog_follows_pagination_and_filters_models() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("after_id") is None:
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "claude-sonnet"}, {"id": "not-a-claude-model"}],
                    "has_more": True,
                    "last_id": "claude-sonnet",
                },
            )
        return httpx.Response(
            200,
            json={"data": [{"id": "claude-haiku"}], "has_more": False},
        )

    catalog = ProviderModelCatalog(transport=httpx.MockTransport(handler))

    assert catalog.fetch_models("anthropic", "secret") == ["claude-sonnet", "claude-haiku"]


def test_catalog_errors_do_not_disclose_provider_response_or_api_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "secret-provider-detail"})

    catalog = ProviderModelCatalog(transport=httpx.MockTransport(handler))

    with pytest.raises(ModelCatalogError) as captured:
        catalog.fetch_models("openai", "top-secret-key")

    message = str(captured.value)
    assert message == "The API key was not accepted by OpenAI."
    assert "top-secret-key" not in message
    assert "secret-provider-detail" not in message


def test_settings_reject_an_incompatible_model_even_if_cache_was_edited(tmp_path: Path) -> None:
    settings = LLMSettingsService(tmp_path / "config")
    settings.settings_file.parent.mkdir(parents=True)
    settings.settings_file.write_text(
        json.dumps(
            {
                "model_cache": {"openai": ["gpt-image-2"], "anthropic": []},
                "provider": None,
                "model": None,
                "setup_skipped": False,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(LLMSettingsError, match="Refresh the model list"):
        settings.select("openai", "gpt-image-2")


@pytest.mark.asyncio
async def test_llm_configuration_saves_secret_outside_plaintext_settings(tmp_path: Path) -> None:
    credentials = MemoryCredentialStore()
    settings = LLMSettingsService(tmp_path / "config")
    catalog = catalog_with_responses(
        {
            "https://api.openai.com/v1/models": {
                "data": [{"id": "gpt-5.6-sol"}, {"id": "gpt-image-2"}]
            }
        }
    )
    app = create_app(
        static_directory=None,
        workspace_service=WorkspaceService(
            configuration_directory=tmp_path / "workspace-config",
            documents_directory=tmp_path / "Documents",
        ),
        llm_settings_service=settings,
        credential_store=credentials,
        model_catalog=catalog,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        setup_token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": setup_token}
        initial = await client.get("/api/llm/settings")
        fetched = await client.post(
            "/api/llm/providers/openai/models",
            json={"api_key": "top-secret-key"},
            headers=headers,
        )
        saved = await client.put(
            "/api/llm/settings",
            json={"provider": "openai", "model": "gpt-5.6-sol"},
            headers=headers,
        )

    assert initial.json()["onboarding_complete"] is False
    assert fetched.json() == {"provider": "openai", "models": ["gpt-5.6-sol"]}
    assert credentials.keys == {"openai": "top-secret-key"}
    assert saved.json()["configured"] is True
    assert saved.json()["selected_model"] == "gpt-5.6-sol"
    settings_text = settings.settings_file.read_text(encoding="utf-8")
    assert "top-secret-key" not in settings_text
    assert json.loads(settings_text)["provider"] == "openai"


@pytest.mark.asyncio
async def test_llm_setup_can_be_skipped_and_key_can_be_forgotten(tmp_path: Path) -> None:
    credentials = MemoryCredentialStore()
    credentials.keys["anthropic"] = "anthropic-secret"
    settings = LLMSettingsService(tmp_path / "config")
    settings.cache_models("anthropic", ["claude-sonnet"])
    settings.select("anthropic", "claude-sonnet")
    app = create_app(
        static_directory=None,
        workspace_service=WorkspaceService(
            configuration_directory=tmp_path / "workspace-config",
            documents_directory=tmp_path / "Documents",
        ),
        llm_settings_service=settings,
        credential_store=credentials,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        setup_token = (await client.get("/api/setup")).json()["setup_token"]
        headers = {"X-Jeromes-Lab-Setup-Token": setup_token}
        forgotten = await client.delete("/api/llm/providers/anthropic/api-key", headers=headers)
        skipped = await client.post("/api/llm/settings/skip", headers=headers)

    assert forgotten.json()["configured"] is False
    assert credentials.keys == {}
    assert skipped.json()["onboarding_complete"] is True
    assert skipped.json()["selected_provider"] is None


@pytest.mark.asyncio
async def test_unavailable_credential_store_does_not_block_local_onboarding(
    tmp_path: Path,
) -> None:
    app = create_app(
        static_directory=None,
        workspace_service=WorkspaceService(
            configuration_directory=tmp_path / "workspace-config",
            documents_directory=tmp_path / "Documents",
        ),
        llm_settings_service=LLMSettingsService(tmp_path / "config"),
        credential_store=UnavailableCredentialStore(),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/llm/settings")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["credential_store_error"] == (
        "The operating system credential store is unavailable."
    )
