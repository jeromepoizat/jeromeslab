"""Deterministic distinct-source sampling and relevance-only calibration contracts."""

from __future__ import annotations

import hashlib
import json
import math
import random
from importlib.resources import files
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CALIBRATION_TEMPLATE_VERSION = "1"
PROMPT_GENERATION_TEMPLATE_VERSION = "1"
RELEVANCE_SCORING_PROMPT_VERSION = "1"
SAMPLE_ALGORITHM_VERSION = "stratified-source-id-v1"
DEFAULT_CALIBRATION_INSTRUCTIONS = files("jeromes_laboratory.workflow.prompts").joinpath(
    "relevance_calibration_v1.txt"
).read_text(encoding="utf-8").strip()
DEFAULT_COMPACT_CALIBRATION_INSTRUCTIONS = files("jeromes_laboratory.workflow.prompts").joinpath(
    "relevance_calibration_v2.txt"
).read_text(encoding="utf-8").strip()
DEFAULT_RELEVANCE_SCORING_PROMPT = files("jeromes_laboratory.workflow.prompts").joinpath(
    "relevance_scoring_v1.txt"
).read_text(encoding="utf-8").strip()
DEFAULT_PROMPT_GENERATION_INSTRUCTIONS = files("jeromes_laboratory.workflow.prompts").joinpath(
    "relevance_prompt_generation_v1.txt"
).read_text(encoding="utf-8").strip()


class RelevanceError(ValueError):
    """A preparation or provider result cannot be used safely."""


class CalibrationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_record_id: str
    outcome: int | Literal["not_assessable"]
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("outcome", mode="before")
    @classmethod
    def relevance_only(cls, value: object) -> int | str:
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 5:
            return value
        if value == "not_assessable":
            return value
        raise ValueError("Outcome must be 0–5 or not_assessable.")


class CalibrationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    calibration: list[CalibrationDecision]


class PromptGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    scoring_prompt: str = Field(min_length=100, max_length=12_000)
    sample_observations: list[str] = Field(min_length=1, max_length=12)

    @field_validator("sample_observations")
    @classmethod
    def nonempty_observations(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 500 for item in value):
            raise ValueError("Each sample observation must contain 1–500 characters.")
        return value


def parse_prompt_generation(raw: str) -> dict[str, object]:
    try:
        result = PromptGenerationOutput.model_validate_json(raw)
        prompt = result.scoring_prompt.lower()
        if "not_assessable" not in prompt or not all(str(score) in prompt for score in range(6)):
            raise ValueError("The scoring prompt must define 0–5 and not_assessable.")
    except (ValueError, ValidationError) as error:
        raise RelevanceError(f"Invalid generated relevance prompt: {error}") from error
    return result.model_dump(mode="json")


def parse_calibration(raw: str, expected_keys: list[tuple[str, str]]) -> dict[str, object]:
    try:
        result = CalibrationOutput.model_validate_json(raw)
        actual = [(item.source, item.source_record_id) for item in result.calibration]
        if len(actual) != len(set(actual)) or set(actual) != set(expected_keys):
            raise ValueError("Calibration must contain exactly the sampled source identities.")
    except (ValueError, ValidationError) as error:
        raise RelevanceError(f"Invalid relevance calibration: {error}") from error
    return result.model_dump(mode="json")


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _balanced_order(records: list[dict[str, object]], seed: int) -> list[dict[str, object]]:
    """Assign multi-query records once, then round-robin query × collection strata."""
    rng = random.Random(seed)
    shuffled = records[:]
    rng.shuffle(shuffled)
    strata: dict[tuple[str, str], list[dict[str, object]]] = {}
    for record in shuffled:
        queries = record["queries"]
        assert isinstance(queries, list)
        possible = [(str(query["id"]), str(record["source"])) for query in queries]
        chosen = min(possible, key=lambda pair: (len(strata.get(pair, [])), pair))
        strata.setdefault(chosen, []).append(record)
    keys = sorted(strata)
    rng.shuffle(keys)
    result: list[dict[str, object]] = []
    while keys:
        next_keys = []
        for key in keys:
            result.append(strata[key].pop())
            if strata[key]:
                next_keys.append(key)
        keys = next_keys
    return result


def build_preview(
    records: list[dict[str, object]], retrieval_job_id: str, *, scoring_limit: int | None,
    calibration_count: int, seed: int, instructions: str,
) -> dict[str, object]:
    if (scoring_limit is not None and scoring_limit < 1) or calibration_count < 1 or calibration_count > 30:
        raise RelevanceError("Choose at least one record and 1–30 calibration records.")
    if len(instructions.strip()) < 40 or len(instructions) > 20_000:
        raise RelevanceError("Relevance instructions must contain 40–20,000 characters.")
    if not records:
        raise RelevanceError("This retrieval has no saved distinct source records.")
    # A new preparation selects only the prompt-design sample. A legacy scoring
    # limit is retained solely to reproduce already-created job snapshots.
    count = min(scoring_limit if scoring_limit is not None else calibration_count, len(records))
    calibration_count = min(calibration_count, count)
    ordered = _balanced_order(records, seed)
    selected = ordered[:count]
    calibration = selected[:calibration_count]
    manifest = [{"source": row["source"], "source_record_id": row["source_record_id"]}
                for row in selected]
    # The input-text hash detects changed source metadata even when identities remain fixed.
    metadata_sha256 = _digest(selected)
    collection_counts: dict[str, int] = {}
    query_counts: dict[str, dict[str, object]] = {}
    for record in selected:
        source = str(record["source"])
        collection_counts[source] = collection_counts.get(source, 0) + 1
        for query in cast(list[dict[str, object]], record["queries"]):
            query_id = str(query["id"])
            entry = query_counts.setdefault(query_id, {
                "id": query_id, "title": str(query["title"]), "count": 0,
            })
            entry["count"] = cast(int, entry["count"]) + 1
    return {
        "algorithm_version": SAMPLE_ALGORITHM_VERSION,
        "retrieval_job_id": retrieval_job_id,
        "seed": seed,
        "available_distinct_source_records": len(records),
        "scoring_limit": count if scoring_limit is not None else None,
        "calibration_count": len(calibration),
        "selected_manifest": manifest,
        "selected_manifest_sha256": _digest(manifest),
        "selected_metadata_sha256": metadata_sha256,
        "calibration_records": calibration,
        "selected_by_collection": [
            {"source": source, "count": count}
            for source, count in sorted(collection_counts.items())
        ],
        "selected_by_query": [query_counts[key] for key in sorted(query_counts)],
        "estimated_scoring_input_tokens": estimate_scoring_tokens(selected, instructions),
    }


def estimate_text_tokens(text: str) -> int:
    """A deliberately rough planning heuristic, never a provider token count."""
    return math.ceil(len(text.encode("utf-8")) / 4)


def estimate_scoring_tokens(records: list[dict[str, object]], instructions: str) -> int:
    # Future scoring will use ten-record batches. Repeated prompt/context costs matter.
    batches = math.ceil(len(records) / 10)
    return batches * estimate_text_tokens(instructions) + sum(
        estimate_text_tokens(_canonical(record)) for record in records
    )


def estimate_scoring_per_1000_tokens(
    sample: list[dict[str, object]], scoring_prompt: str,
) -> tuple[int, int]:
    """Extrapolate ten-record batches from the *same* prompt-design sample."""
    if not sample:
        raise RelevanceError("A prompt-design sample is required for the cost estimate.")
    record_tokens = sum(estimate_text_tokens(_canonical(record)) for record in sample)
    input_tokens = 100 * estimate_text_tokens(scoring_prompt) + math.ceil(
        record_tokens * 1000 / len(sample)
    )
    return input_tokens, 100_000  # Provisional 100 output tokens per scored report.
