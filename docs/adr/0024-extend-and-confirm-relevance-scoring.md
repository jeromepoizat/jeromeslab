# ADR 0024: Extend and confirm a relevance-scoring run

- Status: Accepted
- Amended by ADR 0025: validation also permits a nonempty paused scored pool.
- Date: 2026-10-07
- Amends: ADR 0023's follow-up prohibition on extending a completed run.

## Context

A researcher may initially score only part of a retrieval to control API expense.
After seeing the result, they may want more records before committing the scored
set to downstream work. A second independent scoring run or a new result panel
would obscure the relationship between those decisions. Conversely, later work
must not consume a score list that can silently grow.

## Decision

Keep one scoring run and one cumulative result per project. Once all currently
selected batches complete, the researcher may request a positive number of
additional, previously unselected distinct source records while any remain.
Selection uses the saved seed, versioned balancing algorithm, retrieval, prompt,
provider, and model. Each extension appends batches and an immutable manifest
of the added source IDs; it never re-scores or changes earlier records or calls.
The user can pause and explicitly resume the extended work under the existing
between-call rules. Extension batches are capped at five records.

The researcher may instead confirm a fully completed run. Confirmation records
an immutable, SHA-256-addressed snapshot of the exact score decisions, their
batch-job provenance, initial selection hash, and extension hashes. Confirmation
locks further extension and resume. No later stage is unlocked merely by this
decision; a future downstream job must explicitly consume this confirmation.
If later investigation needs more records, it must fork at this checkpoint.

## Consequences

The original run selection and its completed batch history remain intact while
the current run plan and count grow. Extension events make that growth auditable.
The UI shows one accumulating score result, a continuation control only while
unscored source records remain, and confirmation beneath it. Source-collection
counts are not shown in the score-result rows, though source provenance remains
in saved records and calls.
