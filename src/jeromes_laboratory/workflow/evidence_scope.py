"""Versioned prompt and validated artifacts for evidence-search scoping."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from jeromes_laboratory.workflow.scope_clarification import ScopeAnswer

EVIDENCE_SCOPE_PROMPT_VERSION = "1"


class EvidenceScopeError(ValueError):
    """Raised when an evidence-scope questionnaire or answer set is invalid."""


class EvidenceTheme(BaseModel):
    """One charter-derived evidence theme that remains in the investigation."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=900)
    evidence_domains: list[str] = Field(min_length=1, max_length=12)
    negative_evidence_required: bool

    @field_validator("label", "purpose")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("evidence_domains")
    @classmethod
    def validate_domains(cls, value: list[str]) -> list[str]:
        normalized = [domain.strip() for domain in value]
        if any(not domain or len(domain) > 80 for domain in normalized):
            raise ValueError("evidence domains must contain concise non-empty labels")
        if len(normalized) != len(set(normalized)):
            raise ValueError("evidence domains must be unique within a theme")
        return normalized


class EvidenceScopeOption(BaseModel):
    """One answer offered for an evidence-acquisition boundary."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=700)

    @field_validator("label", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class EvidenceScopeQuestion(BaseModel):
    """One user-controlled evidence retrieval or screening decision."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    question: str = Field(min_length=1, max_length=400)
    why_it_matters: str = Field(min_length=1, max_length=900)
    selection_mode: Literal["single_choice", "multiple_choice"]
    option_structure: Literal["independent", "cumulative"]
    options: list[EvidenceScopeOption] = Field(min_length=2, max_length=7)
    recommended_option_ids: list[str] = Field(default_factory=list, max_length=7)
    recommendation_reason: str = Field(default="", max_length=900)

    @field_validator("question", "why_it_matters", "recommendation_reason")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_options_and_recommendation(self) -> EvidenceScopeQuestion:
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("evidence-scope option IDs must be unique within a question")
        if self.option_structure == "cumulative" and self.selection_mode != "single_choice":
            raise ValueError("cumulative evidence-scope options must use single_choice")
        if self.selection_mode == "multiple_choice" and self._uses_cumulative_wording():
            raise ValueError("multiple-choice evidence-scope options cannot use cumulative wording")
        recommended = self.recommended_option_ids
        if len(recommended) != len(set(recommended)) or any(
            option_id not in option_ids for option_id in recommended
        ):
            raise ValueError("recommended evidence-scope options must be unique available options")
        if self.selection_mode == "single_choice" and len(recommended) > 1:
            raise ValueError("a single-choice question can recommend at most one option")
        if bool(recommended) != bool(self.recommendation_reason):
            raise ValueError("recommendations require both option IDs and a reason")
        return self

    def _uses_cumulative_wording(self) -> bool:
        cumulative_wording = re.compile(
            r"\b(?:also includes?|includes? (?:all )?(?:the )?"
            r"(?:prior|previous|preceding)|all (?:prior|previous|preceding) "
            r"(?:levels?|tiers?|options?))\b",
            flags=re.IGNORECASE,
        )
        return any(
            cumulative_wording.search(f"{option.label} {option.description}") is not None
            for option in self.options
        )


class EvidenceScopeOutput(BaseModel):
    """Strict provider output for the evidence-scope questionnaire."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    introduction: str = Field(min_length=1, max_length=1_200)
    charter_evidence_themes: list[EvidenceTheme] = Field(min_length=1, max_length=12)
    questions: list[EvidenceScopeQuestion] = Field(default_factory=list, max_length=6)

    @field_validator("introduction")
    @classmethod
    def strip_introduction(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def unique_ids(self) -> EvidenceScopeOutput:
        theme_ids = [theme.id for theme in self.charter_evidence_themes]
        question_ids = [question.id for question in self.questions]
        if len(theme_ids) != len(set(theme_ids)):
            raise ValueError("evidence-theme IDs must be unique")
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("evidence-scope question IDs must be unique")
        return self


class EvidenceScopeAnswers(BaseModel):
    """One immutable complete answer version for the generated questionnaire."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    questions_artifact_id: str
    answers: list[ScopeAnswer] = Field(default_factory=list, max_length=6)


def load_evidence_scope_prompt(version: str) -> str:
    """Load one immutable bundled evidence-scope prompt version."""
    prompt_file = files("jeromes_laboratory.workflow.prompts").joinpath(
        f"evidence_scope_v{version}.txt"
    )
    return prompt_file.read_text(encoding="utf-8").strip()


DEFAULT_EVIDENCE_SCOPE_PROMPT = load_evidence_scope_prompt(EVIDENCE_SCOPE_PROMPT_VERSION)


def parse_evidence_scope_output(value: str) -> EvidenceScopeOutput:
    """Validate exact JSON, tolerating only an otherwise empty Markdown fence."""
    candidate = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL)
    if fenced is not None:
        candidate = fenced.group(1)
    try:
        return EvidenceScopeOutput.model_validate(json.loads(candidate))
    except (json.JSONDecodeError, ValidationError) as error:
        raise EvidenceScopeError(
            "The provider did not return a valid evidence-scope questionnaire. "
            "The raw response was preserved in the call record."
        ) from error


def validate_evidence_scope_answers(
    questions: EvidenceScopeOutput,
    questions_artifact_id: str,
    answers: list[ScopeAnswer],
) -> EvidenceScopeAnswers:
    """Require one valid response per generated question, while allowing uncertainty."""
    by_id = {answer.question_id: answer for answer in answers}
    if len(by_id) != len(answers) or set(by_id) != {
        question.id for question in questions.questions
    }:
        raise EvidenceScopeError("Answer every evidence-scope question exactly once.")
    for question in questions.questions:
        answer = by_id[question.id]
        option_ids = {option.id for option in question.options}
        if any(option_id not in option_ids for option_id in answer.selected_option_ids):
            raise EvidenceScopeError("A selected evidence-scope option is not available.")
        if answer.is_unsure and answer.selected_option_ids:
            raise EvidenceScopeError("Not sure cannot be combined with a suggested answer.")
        if not answer.is_unsure and not answer.selected_option_ids and not answer.note:
            raise EvidenceScopeError(
                "Select an answer, add a manual note, or choose Not sure for every question."
            )
        if question.selection_mode == "single_choice" and len(answer.selected_option_ids) > 1:
            raise EvidenceScopeError(
                "A single-choice evidence-scope question has multiple answers."
            )
    return EvidenceScopeAnswers(
        questions_artifact_id=questions_artifact_id,
        answers=answers,
    )
