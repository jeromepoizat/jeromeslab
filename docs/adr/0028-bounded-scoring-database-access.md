# ADR 0028: Bounded scoring database access

- Status: Accepted
- Date: 2026-10-13
- Refines: ADR 0027's parallel execution implementation, not its scientific workflow.

## Context and decision

Live diagnosis found the server responsive while score reads returned
`database is locked`. Failed status polls were hidden, leaving initial loading
visible indefinitely. Parallel executors also reserved the writer even when
idle, and scheduling repeatedly loaded a run's full metadata-rich batch plan.

Keep provider calls parallel, but coordinate short queue/scoring/retrieval SQLite
contexts with a process-local per-database reentrant lock. Context exit commits
or rolls back and always closes the connection. No network request runs inside
such a context. Idle claims first check for pending work without reserving a
writer. Nested record reads reuse the caller's connection. General job display
does not scan charter dependency JSON for every scoring batch.

Migration 0029 adds exact per-batch JSON read-model rows derived from the existing
frozen plan, plus the distinct retrieval count cached when the run is created.
The original plan, manifests, calls, scores and confirmations remain unchanged.
Extension appends corresponding read-model rows. Scheduling reads one bounded
batch rather than the entire plan; progress does not load the full plan or
recount all retrieved appearances. Preview titles use the exact batch input
snapshot associated with each score. The source identity and original provenance
remain authoritative; these read models introduce no new scientific decisions.

Status loading errors/timeouts are visible, with retry and the last saved status
when available. SQLite busy responses use a retryable HTTP 503. No endless
loading message or silent empty-data fallback is permitted. This does not change
journal mode, move the workspace, reset scores or automatically invoke providers.
