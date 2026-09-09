"""Versioned prompt and validated output for research-intent clarification."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

INTENT_CLARIFICATION_PROMPT_VERSION = "1"


class IntentClarificationError(ValueError):
    """Raised when a provider response is not a valid intent questionnaire."""


class IntentOption(BaseModel):
    """One distinct research direction offered to the user."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)

    @field_validator("label", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class IntentClarificationOutput(BaseModel):
    """Strict provider output rendered as an interactive choice."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    question: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=1_000)
    options: list[IntentOption] = Field(min_length=3, max_length=8)

    @field_validator("question", "explanation")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("options")
    @classmethod
    def unique_option_ids(cls, value: list[IntentOption]) -> list[IntentOption]:
        ids = [option.id for option in value]
        if len(ids) != len(set(ids)):
            raise ValueError("intent option IDs must be unique")
        return value


class IntentSelection(BaseModel):
    """The user's immutable decision over one generated intent questionnaire."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    questions_artifact_id: str
    primary_intent_id: str
    secondary_intent_ids: list[str] = Field(default_factory=list, max_length=7)
    note: str = Field(default="", max_length=5_000)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        return value.strip()

    @field_validator("secondary_intent_ids")
    @classmethod
    def unique_secondary_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("secondary intent IDs must be unique")
        return value


def load_intent_clarification_prompt(version: str) -> str:
    """Load one immutable bundled prompt version."""
    prompt_file = files("jeromes_laboratory.workflow.prompts").joinpath(
        f"intent_clarification_v{version}.txt"
    )
    return prompt_file.read_text(encoding="utf-8").strip()


DEFAULT_INTENT_CLARIFICATION_PROMPT = load_intent_clarification_prompt(
    INTENT_CLARIFICATION_PROMPT_VERSION
)


def parse_intent_clarification_output(value: str) -> IntentClarificationOutput:
    """Validate exact JSON, tolerating only an otherwise empty Markdown fence."""
    candidate = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL)
    if fenced is not None:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
        return IntentClarificationOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise IntentClarificationError(
            "The provider did not return a valid intent-clarification questionnaire. "
            "The raw response was preserved in the call record."
        ) from error
