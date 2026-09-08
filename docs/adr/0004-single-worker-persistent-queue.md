# ADR 0004: Single-worker persistent research queue

- Status: Accepted
- Date: 2026-09-07

## Context

Research tasks are long-running and need progress that survives browser
navigation. Parallel execution would introduce early API-rate, database-write,
and recovery complexity.

## Decision

Represent jobs persistently and execute exactly one research job at a time in V1.
Pending jobs start automatically in queue order after the running job reaches a
terminal state. The frontend polls for progress and may view any project while a
job runs. A user may cancel a pending job before the worker commits to sending
its provider request. Once the worker atomically transitions the job into the
sending/awaiting-response state, cancellation is unavailable because the remote
provider may already have received and billed the request. Cancelled pending jobs
remain recorded rather than being deleted.

## Consequences

Execution and failure reasoning are simpler but throughput is limited. The
worker's atomic claim/send boundary and interrupted-job recovery still require
explicit implementation and tests. The UI must confirm enqueueing because the
inputs lock at that point and cancellation is intentionally unavailable after
dispatch begins.
