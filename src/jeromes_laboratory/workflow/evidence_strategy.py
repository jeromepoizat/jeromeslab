"""Versioned evidence-investigation strategy prompt and output artifact."""

from importlib.resources import files

EVIDENCE_STRATEGY_PROMPT_VERSION = "1"


def load_evidence_strategy_prompt(version: str) -> str:
    return files("jeromes_laboratory.workflow.prompts").joinpath(
        f"evidence_strategy_v{version}.txt"
    ).read_text(encoding="utf-8").strip()


DEFAULT_EVIDENCE_STRATEGY_PROMPT = load_evidence_strategy_prompt(
    EVIDENCE_STRATEGY_PROMPT_VERSION
)


def evidence_strategy_payload(markdown: str) -> dict[str, object]:
    """Preserve exact reviewable Markdown without imposing a scientific template."""
    if not markdown.strip():
        raise ValueError("The evidence-investigation strategy cannot be empty.")
    if len(markdown) > 100_000:
        raise ValueError("The evidence-investigation strategy is too long.")
    return {
        "schema_version": 1,
        "content_type": "text/markdown",
        "evidence_strategy": markdown,
    }
