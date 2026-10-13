# ADR 0023: Bounded relevance scoring and downstream freeze

- Status: Accepted; extension prohibition superseded by ADR 0024, project forking remains future work
- Date: 2026-10-07
- Amended by ADR 0025: scoring failures permit one automatic retry before pausing.
- Amends: ADRs 0021–0022. Prompt-design sampling does not score records; the former optional sample calibration remains only as preserved history and a compatibility API.

## Context

A prompt-design sample helps an LLM write relevance rules suited to the varied
saved metadata. Scoring that sample during preparation confuses prompt design
with the later screening run. The researcher also needs to control API expense,
inspect results as they arrive, stop between requests, and extend an unfinished
run without changing decisions already used by downstream work.

## Decision

Preparation sends the exact approved charter and investigation plan, the
reviewable generation instructions, and as much of the seeded distinct-source
sample as fits a conservative model-specific request budget. It produces a
reviewable/editable standalone relevance-scoring prompt. It does not score the
sample. Existing calibration jobs and their provenance remain readable; the
normal preparation UI no longer starts new calibration jobs.

The next section accepts a count of previously unscored distinct source
records to score. It plans usage internally but displays remaining token/USD
estimates only after the first batch completes, using observed usage. It will
snapshot the exact effective scoring-prompt version, model, selected record IDs,
metadata, selection seed/algorithm, and estimate assumptions before dispatch.
Records found by multiple queries are scored once per distinct source identity.

Use multiple records per provider request rather than one request per record.
Batch size will be bounded by both a small record-count ceiling (initially at
most ten) and a conservative input-plus-output token budget for the selected
model. Long metadata or a long prompt reduces the number of records in a batch.
There is no universal optimal fixed count. Each response must contain exactly
one validated 0–5 or `not_assessable` decision per requested source ID. An
invalid or failed batch preserves the raw call and cost but does not silently
assign scores or automatically make another billable request.

Completed batches and their per-record decisions are committed atomically.
The UI will poll committed progress: scored/unscored counts, 0–5 and not-
assessable totals, and source-collection counts within each outcome. Reported
token use and estimated actual cost accumulate from calls that returned usage,
including responses rejected by output validation; the
remaining estimate is revised from observed usage and remains labelled as an
estimate. Unknown model prices remain unavailable, never guessed.

An interruption request stops **after the current in-flight provider request**
has finished and its result has been committed or failed; it cannot cancel a
billable call already sent. Resume selects only unscored IDs and preserves every
prior batch and decision. A researcher may extend scoring with a new limit only
while no downstream job has consumed the scored set. Queuing such a downstream
job freezes the exact scored-set version it consumes. Adding scores after that
requires a project fork at this checkpoint; no extension or resumption may
silently change the parent's evidence set. Forking itself is future work, so
the app must explain the lock until that capability exists.

## Follow-up decision: one scoring run per project

The researcher selects a count and seed once. Both remain visible but locked
after the first run starts; the start control does not reappear when it finishes.
Paused or failed batches can be resumed within that same run, preserving its
exact selection and history. A separate run or extension in the same project is
not allowed. This supersedes the earlier extension allowance above; investigating
additional records later requires a checkpoint fork, which is not yet implemented.
The UI presents one current-batch status rather than a historical batch list,
and shows a small, read-only sample of record titles for each score.

ADR 0024 supersedes only the extension prohibition: additional records may be
appended to the same completed run until its exact scored set is confirmed.

## Consequences

The scoring slice needs durable run, batch, and per-record decision identities;
an interruption flag and worker checkpoints between calls; exact output-set
validation; partial-progress APIs; and a downstream dependency gate. The
existing single-worker queue and LLM-call provenance still apply. No claim of
study quality or final paper eligibility follows from a relevance score alone.
