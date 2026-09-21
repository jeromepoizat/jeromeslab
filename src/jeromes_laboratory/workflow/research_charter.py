"""Versioned instructions and Markdown artifact for the current investigation."""

from importlib.resources import files

RESEARCH_CHARTER_PROMPT_VERSION = "4"


def load_research_charter_prompt(version: str) -> str:
    return files("jeromes_laboratory.workflow.prompts").joinpath(
        f"research_charter_v{version}.txt"
    ).read_text(encoding="utf-8").strip()


DEFAULT_RESEARCH_CHARTER_PROMPT = load_research_charter_prompt(RESEARCH_CHARTER_PROMPT_VERSION)


def research_charter_payload(markdown: str) -> dict[str, object]:
    """Wrap exact nonempty text; headings and length are editorial, not scientific rules."""
    if not markdown.strip():
        raise ValueError("The research charter cannot be empty.")
    if len(markdown) > 100_000:
        raise ValueError("The research charter is too long.")
    return {
        "schema_version": 1,
        "content_type": "text/markdown",
        "cycle_number": 1,
        "research_charter": markdown,
    }
