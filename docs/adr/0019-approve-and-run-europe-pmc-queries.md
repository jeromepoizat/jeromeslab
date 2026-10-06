# ADR 0019: Approval queues Europe PMC retrieval

- Status: Accepted
- Date: 2026-10-05
- Amends: ADR 0018's separate approval and execution actions

## Context

The query set already has a review gate with immutable versions and mandatory-theme
coverage. An extra idle state between approval and source execution offers no useful
decision for the first Europe PMC source.

## Decision

**Approve queries and run them** is one atomic local action. It approves the exact
effective query-set artifact and queues a retrieval job referencing that artifact
and approval. Network requests begin only when the single worker claims the job.
Query generation, editing, and mere viewing still make no source request.

The source job uses a Europe PMC adapter, not an LLM call. Every included query gets
its own search run with exact expression, adapter version, timing, status, and
hit count. Cursor-paginated `core` responses are retained as SHA-256-hashed raw
page files; source records point to their exact run and page. Identical records
found by different queries remain separate discovery records. Conservative
publication identity resolution and screening are later steps.

V1 limits a single query to 5,000 retrieved records. A query exceeding that limit
is visibly marked partial, with its full reported hit count retained. Failures
and interrupted attempts retain all completed pages. Retrying creates a new job
from the same approved snapshot rather than rewriting earlier runs.

## Consequences

The user gets one clear review-to-execution action. Approval now locks the query
set because downstream retrieval may start. UI statistics describe **raw saved
records**, not unique publications or screened evidence. A completed retrieval
job can include explicitly partial queries; no partial result is presented as a
complete evidence search.
