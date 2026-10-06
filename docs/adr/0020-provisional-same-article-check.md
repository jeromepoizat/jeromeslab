# ADR 0020: Provisional same-article check after Europe PMC retrieval

- Status: Accepted
- Date: 2026-10-05

## Context

One source record may appear in several queries, and one article may appear under
different Europe PMC source IDs. The first retrieval overview counted distinct
`(source, source_record_id)` pairs but did not compare bibliographic metadata.
The researcher wants this comparison at the end of retrieval, including for
already-completed jobs, before later screening is designed.

## Decision

For a completed retrieval job, derive provisional record groups from its saved
source records without new source or LLM requests. Collapse repeated occurrences
of the same source ID for analysis, then link different IDs sharing a normalized
DOI, PMID, PMCID, or exact normalized title. Title normalization removes markup,
case, punctuation, and spacing differences, but does not use fuzzy similarity.
Patent records are not grouped by title alone because distinct filings can share
generic titles; shared exact identifiers may still link them.
Compare available identifiers, first authors, publication years, and journals
within groups and flag differences for later review.

The result is a read-only summary over immutable retrieval rows. It is computed
when an overview is requested, so historical completed jobs receive the check
without changing their job status, database rows, or raw artifacts. It reports
provisional record groups, additional source IDs grouped, and groups with
metadata differences. No source record or discovery link is deleted. Title-only
matches can be false positives; different reports or versions of one study can
also remain separate record groups. Patent records are retained as separate
items when titles alone match. The count must not be presented as verified
unique papers or studies, and these groups must be reviewed and versioned before
becoming authoritative screening units.

## Consequences

The overview provides a transparent, zero-API-cost estimate of article-level
overlap, including for pre-existing retrievals. It does not introduce arbitrary
relevance filters, screening decisions, or quality ratings. More elaborate
identity resolution and human correction remain for the screening stage.
