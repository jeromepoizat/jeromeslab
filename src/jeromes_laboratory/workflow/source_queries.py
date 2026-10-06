"""Versioned Europe PMC query drafts, never executed by this workflow stage."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SOURCE_QUERIES_PROMPT_VERSION = "1"


class SourceQueryError(ValueError):
    """Raised when generated or edited query drafts are invalid."""


class SourceQuery(BaseModel):
    """One purpose-labelled proposed query, with a user-controlled run selection."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=600)
    theme_ids: list[str] = Field(min_length=1, max_length=12)
    query_text: str = Field(min_length=1, max_length=8_000)
    included: bool = True

    @field_validator("title", "description", "query_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query text fields cannot be blank")
        return stripped

    @field_validator("theme_ids")
    @classmethod
    def unique_theme_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("query theme IDs must be unique")
        return value


class SourceQuerySet(BaseModel):
    """An immutable complete draft/review version for one publication source."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source: Literal["europe_pmc"] = "europe_pmc"
    queries: list[SourceQuery] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_ids(self) -> SourceQuerySet:
        ids = [query.id for query in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("query IDs must be unique")
        return self


def parse_source_queries(raw: str, theme_ids: set[str]) -> SourceQuerySet:
    """Validate a proposed set against the exact mandatory themes it consumes."""
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("The output must be a JSON object.")
        # The provider proposes queries, not the user's inclusion choices.
        for query in payload.get("queries", []):
            if isinstance(query, dict):
                query["included"] = True
        result = SourceQuerySet.model_validate(payload)
        for query in result.queries:
            if any(theme not in theme_ids for theme in query.theme_ids):
                raise ValueError("A query references an unknown evidence theme.")
        covered = {theme for query in result.queries for theme in query.theme_ids}
        if covered != theme_ids:
            raise ValueError("The query set must address every mandatory evidence theme.")
    except (ValueError, TypeError, ValidationError) as error:
        raise SourceQueryError(f"Invalid Europe PMC query draft: {error}") from error
    return result


def validate_edited_source_queries(
    payload: SourceQuerySet, original: SourceQuerySet, theme_ids: set[str]
) -> None:
    """Allow text/selection edits while preserving proposal identities and coverage."""
    if [query.id for query in payload.queries] != [query.id for query in original.queries]:
        raise SourceQueryError("The generated query identities cannot be changed.")
    for edited, initial in zip(payload.queries, original.queries, strict=True):
        if edited.theme_ids != initial.theme_ids:
            raise SourceQueryError("Query theme links cannot be changed in this version.")
        if any(theme not in theme_ids for theme in edited.theme_ids):
            raise SourceQueryError("A query references an unknown evidence theme.")


DEFAULT_SOURCE_QUERIES_PROMPT = files("jeromes_laboratory.workflow.prompts").joinpath(
    "source_queries_v1.txt"
).read_text(encoding="utf-8").strip()
