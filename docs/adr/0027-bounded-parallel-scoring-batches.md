# ADR 0027: Bounded parallel scoring batches

- Status: Accepted
- Date: 2026-10-13
- Amends: ADR 0004's one-job execution rule only for batches within one scoring run.

## Decision

The researcher may select 1–8 parallel relevance-scoring batches, default 1.
Other research operations remain sequential, and batches from separate runs or
projects cannot overlap. SQL claims atomically enforce the active run and its
limit. The worker uses a bounded thread pool; provider calls run outside database
transactions, and every attempt remains a separate job/call with immutable
inputs, outputs, usage and cost. Per-batch snapshots record the concurrency used.
Provider rate limits may reduce throughput or produce failures; the existing
one-retry-then-pause policy applies to each failing batch.

Selection, seed, batch boundaries, prompt and model stay frozen. The concurrency
limit may change before starting, or when explicitly resuming a fully paused
run or extending a completed run. Existing runs migrate to concurrency 1.
Only the bounded window is queued, with replacement work scheduled as requests
finish. Completion may be out of order: progress, remaining estimates and scored
pool validation use actual completed batch identities, not an assumed prefix.
The retained next-batch pointer means first unfinished batch, not completed count.

Pausing or a second failure stops new dispatch, cancels queued attempts and waits
for every already-sent request to settle. Validating a paused pool includes every
completed batch, even when earlier batches remain unfinished. Resume never
re-scores completed records and is idempotent for an already-running run with
the same concurrency. Interrupted calls after restart are paused for explicit
resume, never silently replayed.

## Resume reliability

Scoring mutations have a bounded browser wait (20 seconds); a timeout explains
that the server may have accepted the action. Progress refreshes have their own
timeouts and do not keep action buttons disabled. Polling does not overlap
stalled requests. Preparation/storage errors cannot silently terminate the
background dispatcher, and cancelling a pending job must not fail unrelated
in-flight scoring runs. Recovery repairs stranded runs without erasing attempts.

## Consequences

Parallel calls can improve wall-clock time, not reduce token charges. They can
increase short-term spending and rate-limit pressure. Tests must cover genuine
overlap, out-of-order completion, bounded claims, pause/validation, window refill,
retry identity, restart recovery and repeated resume. Later quality/extraction
stages do not gain parallel execution through this decision.
