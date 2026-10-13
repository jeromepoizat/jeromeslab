# ADR 0025: Bounded scoring retries and paused validation

- Status: Accepted
- Date: 2026-10-11
- Amends: ADR 0023's prohibition on automatic scoring retries and ADR 0024's completed-only confirmation rule.

## Decision

A failed relevance-scoring batch gets one automatic retry without a user-facing
failure interruption. Two consecutive failures of the same batch pause the run.
Explicit resume begins a new two-attempt allowance; a successful batch resets
the allowance for the next batch. A user-requested pause suppresses automatic
retry. Ambiguous external calls interrupted by application shutdown are not
automatically replayed. Other research jobs retain their existing retry policy.

Each attempt remains a separate job and LLM call, with exact inputs, raw output,
failure, usage and cost retained. Retry snapshots identify the preceding failed
job and automatic-attempt number; the call also records this retry count. Failed
outputs never create partial score decisions. Retrying may incur additional API
cost, which accumulates in the same run.

The researcher may validate a nonempty scored pool when its run is completed or
fully paused, with no queued or in-flight scoring requests. Validation snapshots
only successfully completed batch decisions, recording the planned count and
the selected-but-unscored count as well. It locks additions and resumption;
unfinished records are not silently included or assigned scores. The centered
Validate scoring action has a helper explaining this irreversible pool lock.
Downstream jobs must consume the exact validation snapshot. Forking for further
scoring remains future work.
