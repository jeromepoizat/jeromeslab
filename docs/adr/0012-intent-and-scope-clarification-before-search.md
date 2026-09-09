# ADR 0012: Clarify intent and scope before formal search

- Status: Accepted
- Date: 2026-09-09

## Context

The first implemented workflow transformed an initial scientific question into
one detailed Markdown brief and expected that result to guide query generation.
Live examples showed that a one-shot expansion can preserve major ambiguity,
silently choose an unintended interpretation, or combine discovery, mechanism,
efficacy, and translation into an impractically broad research program. Output
quality also varied materially with the chosen model and the quality of the
initial question.

The application needs human decisions before formal literature queries, but one
fixed scientific framework would not suit evidence mapping, intervention review,
mechanistic research, diagnosis, candidate discovery, and other project types.

## Decision

Replace the default one-shot path with three explicit checkpoints:

1. An LLM generates dynamic research-intent choices from the immutable original
   question. The user chooses one primary intent, zero or more secondary intents,
   and an optional note. Intent clarification is one logical round.
2. An LLM generates dynamic scope questions appropriate to that intent. Questions
   declare single- or multiple-choice behavior and accept a note or "not sure."
   One first round is required and at most one material follow-up round is
   automatically proposed.
3. An LLM produces a flexible research charter from the exact original question
   and confirmed decisions. The user reviews and approves the effective charter
   before later query generation, screening, or extraction consumes it.

Generated questionnaires, user decisions, accepted uncertainties, and charter
versions are provenance-bearing artifacts. Completed inputs are preserved and
downstream jobs reference exact versions. Existing projects that used the former
question-detailing path retain their history and compatibility interface.
A confirmed decision may be corrected by creating a new effective artifact
version until a downstream job is queued; it is never overwritten in place.

Reconnaissance literature search is not part of these clarification stages yet.
It is deferred until the formal query-generation and later literature workflow
have been implemented and evaluated.

## Consequences

The workflow requires additional LLM calls and explicit user interaction before
search, but it is less likely to build a costly research pipeline around an
unintended or ambiguous interpretation. Structured JSON is required for generated
question interfaces, while the eventual charter can remain flexible Markdown.
The application must validate provider JSON before displaying it, preserve
answers separately from generated choices, prevent endless clarification loops,
and keep legacy question-detailing projects readable.
