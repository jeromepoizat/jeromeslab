"""Store LLM API keys in the operating system's native credential store."""

from __future__ import annotations

from typing import Protocol

import keyring
from keyring.errors import KeyringError

SERVICE_NAME = "Jerome's Laboratory"


class CredentialStoreError(RuntimeError):
    """Raised when the native credential store cannot be accessed."""


class CredentialStore(Protocol):
    """Narrow secret-storage boundary used by provider configuration."""

    def get_api_key(self, provider: str) -> str | None: ...

    def set_api_key(self, provider: str, api_key: str) -> None: ...

    def delete_api_key(self, provider: str) -> None: ...


class NativeCredentialStore:
    """Use Python keyring without exposing stored values to callers above this boundary."""

    @staticmethod
    def _username(provider: str) -> str:
        return f"llm-api-key:{provider}"

    def get_api_key(self, provider: str) -> str | None:
        try:
            return keyring.get_password(SERVICE_NAME, self._username(provider))
        except KeyringError as error:
            raise CredentialStoreError(
                "The operating system credential store is unavailable."
            ) from error

    def set_api_key(self, provider: str, api_key: str) -> None:
        try:
            keyring.set_password(SERVICE_NAME, self._username(provider), api_key)
        except KeyringError as error:
            raise CredentialStoreError(
                "The API key could not be saved in the operating system credential store."
            ) from error

    def delete_api_key(self, provider: str) -> None:
        try:
            if keyring.get_password(SERVICE_NAME, self._username(provider)) is not None:
                keyring.delete_password(SERVICE_NAME, self._username(provider))
        except KeyringError as error:
            raise CredentialStoreError(
                "The API key could not be removed from the operating system credential store."
            ) from error
