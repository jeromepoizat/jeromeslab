"""Persist non-secret global LLM preferences in device-local configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_path

from jeromes_laboratory.llm.catalog import (
    SUPPORTED_PROVIDERS,
    ProviderName,
    is_compatible_model,
)
from jeromes_laboratory.storage.workspace import APPLICATION_NAME

LLM_SETTINGS_FILE_NAME = "llm-settings.json"
LLM_SETTINGS_FORMAT_VERSION = 1


class LLMSettingsError(ValueError):
    """Raised when device-local LLM preferences cannot be read or updated."""


@dataclass(frozen=True)
class LLMSettings:
    """Current non-secret provider selection and cached compatible models."""

    provider: ProviderName | None
    model: str | None
    setup_skipped: bool
    model_cache: dict[ProviderName, list[str]]


class LLMSettingsService:
    """Read and atomically update the device-level LLM configuration file."""

    def __init__(self, configuration_directory: Path | None = None) -> None:
        self._configuration_directory = (
            configuration_directory
            if configuration_directory is not None
            else user_config_path(appname=APPLICATION_NAME, appauthor=False)
        )

    @property
    def settings_file(self) -> Path:
        return self._configuration_directory / LLM_SETTINGS_FILE_NAME

    def read(self) -> LLMSettings:
        try:
            if not self.settings_file.is_file():
                return LLMSettings(None, None, False, {provider: [] for provider in SUPPORTED_PROVIDERS})
            payload = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise LLMSettingsError("The saved LLM settings could not be read.") from error
        if not isinstance(payload, dict):
            raise LLMSettingsError("The saved LLM settings are invalid.")

        provider_value = payload.get("provider")
        provider: ProviderName | None = (
            provider_value if provider_value in SUPPORTED_PROVIDERS else None
        )
        model_value = payload.get("model")
        model = model_value if isinstance(model_value, str) and model_value else None
        cache_payload = payload.get("model_cache")
        cache: dict[ProviderName, list[str]] = {}
        for supported_provider in SUPPORTED_PROVIDERS:
            cached_models = (
                cache_payload.get(supported_provider) if isinstance(cache_payload, dict) else None
            )
            cache[supported_provider] = (
                [
                    item
                    for item in cached_models
                    if isinstance(item, str)
                    and is_compatible_model(supported_provider, item)
                ]
                if isinstance(cached_models, list)
                else []
            )
        return LLMSettings(
            provider=provider,
            model=model,
            setup_skipped=payload.get("setup_skipped") is True,
            model_cache=cache,
        )

    def cache_models(self, provider: ProviderName, models: list[str]) -> LLMSettings:
        settings = self.read()
        cache = {name: list(values) for name, values in settings.model_cache.items()}
        cache[provider] = list(models)
        updated = LLMSettings(settings.provider, settings.model, settings.setup_skipped, cache)
        self._write(updated)
        return updated

    def select(self, provider: ProviderName, model: str) -> LLMSettings:
        settings = self.read()
        if not is_compatible_model(provider, model) or model not in settings.model_cache[provider]:
            raise LLMSettingsError("Refresh the model list and select an available model.")
        updated = LLMSettings(provider, model, False, settings.model_cache)
        self._write(updated)
        return updated

    def skip_setup(self) -> LLMSettings:
        settings = self.read()
        updated = LLMSettings(
            settings.provider,
            settings.model,
            True,
            settings.model_cache,
        )
        self._write(updated)
        return updated

    def clear_provider(self, provider: ProviderName) -> LLMSettings:
        settings = self.read()
        selected_provider = settings.provider
        selected_model = settings.model
        if selected_provider == provider:
            selected_provider = None
            selected_model = None
        cache = {name: list(values) for name, values in settings.model_cache.items()}
        cache[provider] = []
        updated = LLMSettings(
            selected_provider,
            selected_model,
            settings.setup_skipped,
            cache,
        )
        self._write(updated)
        return updated

    def _write(self, settings: LLMSettings) -> None:
        try:
            self._configuration_directory.mkdir(parents=True, exist_ok=True)
            temporary_path = self.settings_file.with_suffix(".json.tmp")
            temporary_path.write_text(
                json.dumps(
                    {
                        "format_version": LLM_SETTINGS_FORMAT_VERSION,
                        "model": settings.model,
                        "model_cache": settings.model_cache,
                        "provider": settings.provider,
                        "setup_skipped": settings.setup_skipped,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.settings_file)
        except OSError as error:
            raise LLMSettingsError("The LLM settings could not be saved on this device.") from error
