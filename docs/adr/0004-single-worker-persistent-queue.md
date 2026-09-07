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
job runs.

## Consequences

Execution and failure reasoning are simpler but throughput is limited. Atomic
claiming, ordering, cancellation, and interrupted-job recovery still require
explicit design and tests.

