"""Versioned prompt and validated artifacts for first-round scope clarification."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCOPE_CLARIFICATION_PROMPT_VERSION = "4"


class ScopeClarificationError(ValueError):
    """Raised when a scope questionnaire or answer set is invalid."""


class ScopeOption(BaseModel):
    """One concise answer offered for a material scope decision."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=700)

    @field_validator("label", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ScopeQuestion(BaseModel):
    """One single- or multiple-choice scope decision."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    question: str = Field(min_length=1, max_length=400)
    why_it_matters: str = Field(min_length=1, max_length=900)
    selection_mode: Literal["single_choice", "multiple_choice"]
    option_structure: Literal["independent", "cumulative"] | None = None
    options: list[ScopeOption] = Field(min_length=2, max_length=7)

    @field_validator("question", "why_it_matters")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("options")
    @classmethod
    def unique_option_ids(cls, value: list[ScopeOption]) -> list[ScopeOption]:
        ids = [option.id for option in value]
        if len(ids) != len(set(ids)):
            raise ValueError("scope option IDs must be unique within a question")
        return value

    @model_validator(mode="after")
    def cumulative_options_require_one_boundary(self) -> ScopeQuestion:
        if self.option_structure == "cumulative" and self.selection_mode != "single_choice":
            raise ValueError("cumulative scope options must use single_choice")
        return self

    def uses_explicit_cumulative_wording(self) -> bool:
        """Detect wording that directly says an option silently includes another tier."""
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


class ScopeClarificationOutput(BaseModel):
    """Strict provider output rendered as the first scope-question round."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1, 2]
    introduction: str = Field(min_length=1, max_length=1_200)
    # Version 3 and later permit a small questionnaire rather than forcing
    # the model to fill a quota with decisions that belong to search planning.
    # The upper bound remains compatible with preserved version 1/2 responses.
    questions: list[ScopeQuestion] = Field(min_length=1, max_length=7)

    @field_validator("introduction")
    @classmethod
    def strip_introduction(cls, value: str) -> str:
        return value.strip()

    @field_validator("questions")
    @classmethod
    def unique_question_ids(cls, value: list[ScopeQuestion]) -> list[ScopeQuestion]:
        ids = [question.id for question in value]
        if len(ids) != len(set(ids)):
            raise ValueError("scope question IDs must be unique")
        return value

    @model_validator(mode="after")
    def version_two_declares_option_structure(self) -> ScopeClarificationOutput:
        if self.schema_version == 2 and any(
            question.option_structure is None for question in self.questions
        ):
            raise ValueError("schema version 2 questions must declare option_structure")
        if self.schema_version == 2 and any(
            question.selection_mode == "multiple_choice"
            and question.uses_explicit_cumulative_wording()
            for question in self.questions
        ):
            raise ValueError("multiple-choice scope options cannot use cumulative wording")
        return self


class ScopeAnswer(BaseModel):
    """The user's response to one generated scope question."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    selected_option_ids: list[str] = Field(default_factory=list, max_length=7)
    note: str = Field(default="", max_length=5_000)
    is_unsure: bool = False

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        return value.strip()

    @field_validator("selected_option_ids")
    @classmethod
    def unique_option_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("selected option IDs must be unique")
        return value


class ScopeAnswers(BaseModel):
    """One immutable, complete answer version for a generated question round."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    questions_artifact_id: str
    # The first questionnaire contains 3–7 questions, while the one permitted
    # readiness follow-up contains 1–5. The validator below still requires an
    # answer for every question in the specific questionnaire.
    answers: list[ScopeAnswer] = Field(min_length=1, max_length=7)


def load_scope_clarification_prompt(version: str) -> str:
    """Load one immutable bundled scope prompt version."""
    prompt_file = files("jeromes_laboratory.workflow.prompts").joinpath(
        f"scope_clarification_v{version}.txt"
    )
    return prompt_file.read_text(encoding="utf-8").strip()


DEFAULT_SCOPE_CLARIFICATION_PROMPT = load_scope_clarification_prompt(
    SCOPE_CLARIFICATION_PROMPT_VERSION
)


def parse_scope_clarification_output(value: str) -> ScopeClarificationOutput:
    """Validate exact JSON, tolerating only an otherwise empty Markdown fence."""
    candidate = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL)
    if fenced is not None:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
        return ScopeClarificationOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ScopeClarificationError(
            "The provider did not return a valid scope-clarification questionnaire. "
            "The raw response was preserved in the call record."
        ) from error


def validate_scope_answers(
    questions: ScopeClarificationOutput | list[ScopeQuestion],
    questions_artifact_id: str,
    answers: list[ScopeAnswer],
) -> ScopeAnswers:
    """Require one valid response per question without forcing a suggested option."""
    question_list = (
        questions.questions if isinstance(questions, ScopeClarificationOutput) else questions
    )
    by_id = {answer.question_id: answer for answer in answers}
    if len(by_id) != len(answers) or set(by_id) != {question.id for question in question_list}:
        raise ScopeClarificationError("Answer every scope question exactly once.")
    for question in question_list:
        answer = by_id[question.id]
        option_ids = {option.id for option in question.options}
        if any(option_id not in option_ids for option_id in answer.selected_option_ids):
            raise ScopeClarificationError("A selected scope option is not available.")
        if answer.is_unsure and answer.selected_option_ids:
            raise ScopeClarificationError("Not sure cannot be combined with a suggested answer.")
        if not answer.is_unsure and not answer.selected_option_ids and not answer.note:
            raise ScopeClarificationError(
                "Select an answer, add a manual note, or choose Not sure for every question."
            )
        if question.selection_mode == "single_choice" and len(answer.selected_option_ids) > 1:
            raise ScopeClarificationError("A single-choice scope question has multiple answers.")
    return ScopeAnswers(questions_artifact_id=questions_artifact_id, answers=answers)
