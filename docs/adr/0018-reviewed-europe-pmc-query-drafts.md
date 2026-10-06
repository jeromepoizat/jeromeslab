# ADR 0018: Review Europe PMC query drafts before any retrieval

- Status: Amended by 0019
- Date: 2026-10-05
- Amendment: ADR 0019 replaces the separate later retrieval action with atomic
  approval-and-queueing; the review gate and immutable query versions remain.

## Context

An approved scientific-source investigation plan identifies workstreams, but not
literal search expressions. Running LLM-generated queries without review could
silently narrow an exploratory investigation or misrepresent untested syntax as a
completed search. The first publication source is Europe PMC; structured sources
need separate future adapters.

## Decision

Generate a structured, purpose-labelled Europe PMC query set from the exact
approved strategy and its retained charter, mandatory themes, and scope answers.
The user may add an optional note before generation; the exact note is captured
in the immutable job input and must not override the approved investigation.
Generation is a normal sequential LLM job and **makes no Europe PMC request**.

Each proposed query has a stable ID, short title and description, theme links,
literal query text, and a user-controlled inclusion flag. All proposals initially
are included. The user can expand a card, edit its text, and include or exclude
it. Each saved review is a new immutable hashed artifact version; the original
provider output remains available. Explicit approval applies to one exact
effective version. Included queries must together cover every mandatory theme.
Approval is not execution. A later, separate retrieval action will consume the
approved version and create distinct search-run provenance. A user who changes
their mind after execution must fork from a suitable checkpoint or create a new
query-set lineage and search run rather than rewriting earlier history.

Europe PMC syntax is proposed using its documented search grammar but is not
claimed to have been tested live. Query counts and retrieved records do not exist
at this stage. Preprint status and other source metadata are matters for the
retrieval/screening stages, not reasons for hidden query exclusions.

## Consequences

The first source is deliberately narrow, while the strategy remains broad enough
to guide later protein, structure, interaction, bioactivity, peptide, and assay
adapters. The UI can show a coverage warning before approval and will never
confuse query drafting with an executed scientific search.
