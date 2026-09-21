"""Versioned prompt and validated output for scope-readiness review."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from jeromes_laboratory.workflow.scope_clarification import ScopeQuestion

SCOPE_READINESS_PROMPT_VERSION = "6"


class ScopeReadinessError(ValueError):
    """Raised when a readiness review is not valid."""


class ScopeReadinessOutput(BaseModel):
    """A bounded readiness decision with at most one follow-up questionnaire."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1, 2]
    ready_for_charter: bool
    assessment: str = Field(min_length=1, max_length=2_000)
    remaining_uncertainties: list[str] = Field(default_factory=list, max_length=7)
    follow_up_questions: list[ScopeQuestion] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def consistent_readiness(self) -> ScopeReadinessOutput:
        self.assessment = self.assessment.strip()
        self.remaining_uncertainties = [value.strip() for value in self.remaining_uncertainties]
        if any(not value for value in self.remaining_uncertainties):
            raise ValueError("remaining uncertainties cannot be empty")
        question_ids = [question.id for question in self.follow_up_questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("follow-up question IDs must be unique")
        if self.ready_for_charter and self.follow_up_questions:
            raise ValueError("a ready scope cannot contain follow-up questions")
        if not self.ready_for_charter and not self.follow_up_questions:
            raise ValueError("a scope that is not ready must contain follow-up questions")
        if self.schema_version == 2 and any(
            question.option_structure is None for question in self.follow_up_questions
        ):
            raise ValueError("schema version 2 follow-up questions must declare option_structure")
        if self.schema_version == 2 and any(
            question.selection_mode == "multiple_choice"
            and question.uses_explicit_cumulative_wording()
            for question in self.follow_up_questions
        ):
            raise ValueError("multiple-choice follow-up options cannot use cumulative wording")
        return self


def load_scope_readiness_prompt(version: str) -> str:
    """Load one immutable bundled readiness prompt version."""
    prompt_file = files("jeromes_laboratory.workflow.prompts").joinpath(
        f"scope_readiness_v{version}.txt"
    )
    return prompt_file.read_text(encoding="utf-8").strip()


DEFAULT_SCOPE_READINESS_PROMPT = load_scope_readiness_prompt(SCOPE_READINESS_PROMPT_VERSION)


def parse_scope_readiness_output(value: str) -> ScopeReadinessOutput:
    """Validate exact JSON, tolerating only an otherwise empty Markdown fence."""
    candidate = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL)
    if fenced is not None:
        candidate = fenced.group(1)
    try:
        return ScopeReadinessOutput.model_validate(json.loads(candidate))
    except (json.JSONDecodeError, ValidationError) as error:
        raise ScopeReadinessError(
            "The provider did not return a valid scope-readiness review. "
            "The raw response was preserved in the call record."
        ) from error


def validate_scope_readiness_against_input(
    output: ScopeReadinessOutput, workflow_input_snapshot_json: str | None
) -> ScopeReadinessOutput:
    """Reject a follow-up that repeats an already answered first-round question."""
    if workflow_input_snapshot_json is None:
        raise ScopeReadinessError("The scope-readiness input snapshot is missing.")
    try:
        snapshot = json.loads(workflow_input_snapshot_json)
        first_questions = snapshot["scope_questions"]["questions"]
        answered_ids = {answer["question_id"] for answer in snapshot["scope_answers"]["answers"]}
        question_texts = {
            _normalized_text(question["question"])
            for question in first_questions
            if question["id"] in answered_ids
        }
        first_ids = {
            question["id"] for question in first_questions if question["id"] in answered_ids
        }
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ScopeReadinessError("The preserved scope-readiness input is not valid.") from error

    for follow_up in output.follow_up_questions:
        repeats_text = _normalized_text(follow_up.question) in question_texts
        if follow_up.id in first_ids or repeats_text:
            raise ScopeReadinessError(
                "The provider repeated an already answered scope question instead of "
                "accepting the recorded answer or uncertainty. The raw response was "
                "preserved in the call record."
            )
    return output


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))
