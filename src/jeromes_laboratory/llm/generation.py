"""Provider-neutral preparation and execution of text-generation requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx

from jeromes_laboratory.llm.catalog import ProviderName

MAX_OUTPUT_TOKENS = 8_192


class GenerationError(RuntimeError):
    """A safe provider-call failure with an optional exact provider response."""

    def __init__(self, message: str, *, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response


@dataclass(frozen=True)
class PreparedGeneration:
    """Secret-free request material that can be persisted before dispatch."""

    provider: ProviderName
    operation: str
    endpoint: str
    request_body: dict[str, object]
    generation_settings: dict[str, object]


@dataclass(frozen=True)
class GenerationResult:
    """Exact response plus normalized values needed by workflow code."""

    raw_response: str
    output_text: str
    provider_request_id: str | None
    reported_model: str | None
    usage: dict[str, object] | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    reasoning_tokens: int | None
    provider_metadata: dict[str, object]


class GenerationGateway(Protocol):
    """Narrow injectable boundary used by the durable worker."""

    def prepare(
        self, provider: ProviderName, model: str, instructions: str, input_content: str
    ) -> PreparedGeneration: ...

    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult: ...


class ProviderGenerationGateway:
    """Call OpenAI Responses or Anthropic Messages over their HTTP APIs."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def prepare(
        self, provider: ProviderName, model: str, instructions: str, input_content: str
    ) -> PreparedGeneration:
        if provider == "openai":
            body: dict[str, object] = {
                "model": model,
                "instructions": instructions,
                "input": input_content,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "store": False,
            }
            return PreparedGeneration(
                provider=provider,
                operation="responses.create",
                endpoint="https://api.openai.com/v1/responses",
                request_body=body,
                generation_settings={"max_output_tokens": MAX_OUTPUT_TOKENS, "store": False},
            )
        body = {
            "model": model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": instructions,
            "messages": [{"role": "user", "content": input_content}],
        }
        return PreparedGeneration(
            provider=provider,
            operation="messages.create",
            endpoint="https://api.anthropic.com/v1/messages",
            request_body=body,
            generation_settings={"max_tokens": MAX_OUTPUT_TOKENS},
        )

    def execute(self, prepared: PreparedGeneration, api_key: str) -> GenerationResult:
        headers = {"content-type": "application/json"}
        if prepared.provider == "openai":
            headers["authorization"] = f"Bearer {api_key}"
        else:
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        try:
            with httpx.Client(transport=self._transport, timeout=300.0) as client:
                response = client.post(
                    prepared.endpoint,
                    headers=headers,
                    json=prepared.request_body,
                )
        except httpx.HTTPError as error:
            raise GenerationError(
                f"{self._display_name(prepared.provider)} could not be reached."
            ) from error
        if response.status_code >= 400:
            raise GenerationError(
                self._status_error(prepared.provider, response.status_code),
                raw_response=response.text,
            )
        try:
            payload = cast(dict[str, Any], response.json())
            return (
                self._parse_openai(payload, response.text, response.headers)
                if prepared.provider == "openai"
                else self._parse_anthropic(payload, response.text, response.headers)
            )
        except (KeyError, TypeError, ValueError) as error:
            raise GenerationError(
                f"{self._display_name(prepared.provider)} returned an unreadable response.",
                raw_response=response.text,
            ) from error

    @staticmethod
    def _parse_openai(
        payload: dict[str, Any], raw_response: str, headers: httpx.Headers
    ) -> GenerationResult:
        text_parts = [
            content["text"]
            for output in payload.get("output", [])
            for content in output.get("content", [])
            if content.get("type") == "output_text" and isinstance(content.get("text"), str)
        ]
        output_text = "".join(text_parts).strip()
        if not output_text:
            raise ValueError("missing output text")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
        input_details = usage.get("input_tokens_details", {}) if usage else {}
        output_details = usage.get("output_tokens_details", {}) if usage else {}
        return GenerationResult(
            raw_response=raw_response,
            output_text=output_text,
            provider_request_id=_string(payload.get("id")) or headers.get("x-request-id"),
            reported_model=_string(payload.get("model")),
            usage=usage,
            input_tokens=_integer(usage, "input_tokens"),
            output_tokens=_integer(usage, "output_tokens"),
            total_tokens=_integer(usage, "total_tokens"),
            cached_input_tokens=_integer(input_details, "cached_tokens"),
            reasoning_tokens=_integer(output_details, "reasoning_tokens"),
            provider_metadata={
                "status": payload.get("status"),
                "incomplete_details": payload.get("incomplete_details"),
            },
        )

    @staticmethod
    def _parse_anthropic(
        payload: dict[str, Any], raw_response: str, headers: httpx.Headers
    ) -> GenerationResult:
        text_parts = [
            block["text"]
            for block in payload.get("content", [])
            if block.get("type") == "text" and isinstance(block.get("text"), str)
        ]
        output_text = "".join(text_parts).strip()
        if not output_text:
            raise ValueError("missing output text")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
        input_tokens = _integer(usage, "input_tokens")
        output_tokens = _integer(usage, "output_tokens")
        return GenerationResult(
            raw_response=raw_response,
            output_text=output_text,
            provider_request_id=_string(payload.get("id")) or headers.get("request-id"),
            reported_model=_string(payload.get("model")),
            usage=usage,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens)
            if input_tokens is not None and output_tokens is not None
            else None,
            cached_input_tokens=_sum_integers(
                usage,
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            ),
            reasoning_tokens=None,
            provider_metadata={"stop_reason": payload.get("stop_reason")},
        )

    @staticmethod
    def _display_name(provider: ProviderName) -> str:
        return "OpenAI" if provider == "openai" else "Anthropic"

    def _status_error(self, provider: ProviderName, status_code: int) -> str:
        display_name = self._display_name(provider)
        if status_code in (401, 403):
            return f"The saved {display_name} API key was not accepted."
        if status_code == 429:
            return f"{display_name} rejected the request because of a rate or usage limit."
        return f"{display_name} could not complete the request (HTTP {status_code})."


def _integer(container: dict[str, Any] | None, key: str) -> int | None:
    value = container.get(key) if container else None
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _sum_integers(container: dict[str, Any] | None, *keys: str) -> int | None:
    values = [_integer(container, key) for key in keys]
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
