"""Versioned default instructions for scientific-question detailing."""

from importlib.resources import files

QUESTION_DETAILING_PROMPT_VERSION = "5"


def load_question_detailing_prompt(version: str) -> str:
    """Load a bundled question-detailing prompt by its immutable version."""
    prompt_file = files("jeromes_laboratory.workflow.prompts").joinpath(
        f"question_detailing_v{version}.txt"
    )
    return prompt_file.read_text(encoding="utf-8").strip()


DEFAULT_QUESTION_DETAILING_PROMPT = load_question_detailing_prompt(
    QUESTION_DETAILING_PROMPT_VERSION
)
