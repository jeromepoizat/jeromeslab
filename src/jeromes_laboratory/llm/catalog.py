"""Fetch and filter models available through supported LLM providers."""

from __future__ import annotations

from typing import Literal, cast

import httpx

ProviderName = Literal["openai", "anthropic"]
SUPPORTED_PROVIDERS: tuple[ProviderName, ...] = ("openai", "anthropic")
PROVIDER_DISPLAY_NAMES: dict[ProviderName, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
}

_OPENAI_TEXT_PREFIXES = ("gpt-6", "gpt-5", "gpt-4.1", "gpt-4o", "o1", "o3", "o4")
_OPENAI_EXCLUDED_MARKERS = (
    "audio",
    "codex",
    "computer-use",
    "deep-research",
    "image",
    "realtime",
    "search",
    "transcribe",
    "tts",
)


class ModelCatalogError(RuntimeError):
    """A sanitized provider model-discovery failure safe to return to the UI."""


def is_compatible_model(provider: ProviderName, model_id: str) -> bool:
    """Return whether a fetched model is supported for scientific text generation."""
    normalized = model_id.lower()
    if provider == "anthropic":
        return normalized.startswith("claude-")
    return normalized.startswith(_OPENAI_TEXT_PREFIXES) and not any(
        marker in normalized for marker in _OPENAI_EXCLUDED_MARKERS
    )


class ProviderModelCatalog:
    """Retrieve account-visible models through provider HTTP APIs."""

    def __init__(
        self, *, timeout_seconds: float = 15.0, transport: httpx.BaseTransport | None = None
    ):
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def fetch_models(self, provider: ProviderName, api_key: str) -> list[str]:
        """Fetch and return only compatible model identifiers, preserving provider order."""
        if provider == "openai":
            models = self._fetch_openai_models(api_key)
        else:
            models = self._fetch_anthropic_models(api_key)
        return list(
            dict.fromkeys(model for model in models if is_compatible_model(provider, model))
        )

    def _fetch_openai_models(self, api_key: str) -> list[str]:
        response = self._get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            provider="OpenAI",
        )
        return self._model_ids(response, provider="OpenAI")

    def _fetch_anthropic_models(self, api_key: str) -> list[str]:
        model_ids: list[str] = []
        after_id: str | None = None
        while True:
            parameters = {"limit": "1000"}
            if after_id is not None:
                parameters["after_id"] = after_id
            response = self._get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                params=parameters,
                provider="Anthropic",
            )
            model_ids.extend(self._model_ids(response, provider="Anthropic"))
            payload = self._json_object(response, provider="Anthropic")
            if payload.get("has_more") is not True:
                return model_ids
            last_id = payload.get("last_id")
            if not isinstance(last_id, str) or not last_id or last_id == after_id:
                raise ModelCatalogError("Anthropic returned an invalid paginated model list.")
            after_id = last_id

    def _get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        provider: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            with httpx.Client(timeout=self._timeout_seconds, transport=self._transport) as client:
                response = client.get(url, headers=headers, params=params)
        except httpx.RequestError as error:
            raise ModelCatalogError(
                f"{provider} could not be reached. Check the internet connection and try again."
            ) from error
        if response.status_code in (401, 403):
            raise ModelCatalogError(f"The API key was not accepted by {provider}.")
        if response.status_code == 429:
            raise ModelCatalogError(
                f"{provider} temporarily limited the request. Wait briefly and try again."
            )
        if response.status_code >= 500:
            raise ModelCatalogError(f"{provider} is temporarily unavailable. Try again later.")
        if not response.is_success:
            raise ModelCatalogError(f"{provider} could not list models available to this account.")
        return response

    @staticmethod
    def _json_object(response: httpx.Response, *, provider: str) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError as error:
            raise ModelCatalogError(f"{provider} returned an invalid model list.") from error
        if not isinstance(payload, dict):
            raise ModelCatalogError(f"{provider} returned an invalid model list.")
        return cast(dict[str, object], payload)

    @classmethod
    def _model_ids(cls, response: httpx.Response, *, provider: str) -> list[str]:
        payload = cls._json_object(response, provider=provider)
        data = payload.get("data")
        if not isinstance(data, list):
            raise ModelCatalogError(f"{provider} returned an invalid model list.")
        model_ids: list[str] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                model_ids.append(item["id"])
        return model_ids
