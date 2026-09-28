# ADR 0017: Review and approve an evidence-investigation strategy before queries

- Status: Accepted
- Date: 2026-09-25

## Context

The approved charter and evidence-scope questionnaire identify required themes and
user decisions, but do not yet say how those obligations will be organized into
search and screening work. A direct jump to source-specific queries would make
coverage and indirect-evidence boundaries hard to review. Source adapters are not
yet implemented, so a strategy must not imply that a named source can be searched.

## Decision

Generate one compact Markdown strategy from the exact approved charter, validated
evidence themes, and current effective scope-answer artifact. The queued job
snapshots all three, including their artifact IDs and versions, in one transaction.
The provider prompt asks for purpose-labelled evidence workstreams, applicable
source categories, eligibility and stratification principles, and unresolved
search decisions. It does not generate source-specific syntax or claim that
searches have run.

The user can inspect the original output, save an edited effective version, and
explicitly approve precisely that version. Edits never alter the original and
require fresh approval. A cancelled or failed attempt can be retried with its
original workflow input; a completed attempt is not silently regenerated. The
strategy prompt is versioned and editable only before the first attempt.

Later query generation must consume both the exact approved strategy and its
preserved charter, theme, and answer inputs. Human-readable strategy prose does
not replace the structured mandatory themes or confirmed user decisions.
Concrete source selection and source-specific query review require the relevant
source adapters and separate implementation.

## Consequences

The strategy can be reviewed without exposing database syntax prematurely.
Broad or uncertain projects remain inclusive and label indirect evidence
separately. The approval is a plan checkpoint, not a claim that scientific
sources have been searched or that every source category is currently enabled.
