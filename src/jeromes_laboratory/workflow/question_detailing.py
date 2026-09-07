"""Versioned default instructions for scientific-question detailing."""

QUESTION_DETAILING_PROMPT_VERSION = "1"
DEFAULT_QUESTION_DETAILING_PROMPT = """You are assisting with the planning of a rigorous scientific literature investigation.

Given the scientific question below, produce a structured research plan. Do not answer the scientific question or make scientific conclusions.

Return these sections: Restated question; Research subquestions; Search concepts (including useful synonyms and abbreviations); Evidence priorities; Scope and ambiguity; and Search-planning notes. Distinguish facts stated in the question from assumptions. Identify missing information rather than inventing it. Do not write final database queries yet."""
