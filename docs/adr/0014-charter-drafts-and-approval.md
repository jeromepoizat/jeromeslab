# ADR 0014: Research charter drafts and explicit version approval

- Status: Accepted
- Date: 2026-09-13

## Context

The confirmed direction and framing need a readable reference for subsequent
research. A generated summary may omit a user decision, invent a restriction,
or confuse a current investigation objective with a later decision. Human
review must precede downstream use, while original outputs and every consumed
input remain reproducible.

## Decision

Generate the first cycle's research charter as flexible Markdown. Headings and
length follow the supplied material; no fixed scientific framework, section
count, or word count is required. The charter distinguishes the current purpose,
questions to investigate now, explicit boundaries, decisions deferred until
evidence exists, and later or parallel goals where applicable.

Snapshot the original question and exact confirmed direction, first framing
answers, readiness review, and any confirmed final follow-up answers. Include
the source questionnaire and artifact identifiers so selected choices and notes
retain their meanings. Explicit corrections can clarify earlier decisions;
unresolved tensions remain visible for review. Readiness commentary is advisory
and cannot create user commitments. The model may organize the information but
must not invent scientific findings, preferences, restrictions, or literature
eligibility rules. Explicit user-supplied constraints are preserved.

Every generated charter begins as a draft. Manual editing creates another
immutable artifact version, preserving the original. Approval is an append-only
record referring to the exact effective artifact version and approval time.
Editing requires fresh approval of the new version. Approval denotes agreement
with the research framing, not validation of scientific truth.

The user may explicitly regenerate before downstream use. Each request creates
a separate queue attempt with preserved prompt, model, inputs, call, and output.
A successful replacement becomes the current draft. While generation is active,
the earlier charter cannot be changed or consumed. If that attempt fails or is
cancelled, the most recent completed charter becomes usable again with its
original approval, if any. Historical completed attempts remain inspectable.
There is no automatic potentially billable retry.

Downstream operations must obtain the current approved charter and reference its
exact artifact and approval. Once consumed, editing and regeneration are locked.
The first implementation covers cycle 1; starting later evidence-informed cycles
and checkpoint forks remains planned under ADR 0013.

## Consequences

The UI reuses the hidden prompt, queue confirmation, Markdown editor, original
versus edited display, usage metadata, and elapsed-time patterns. Explicit
approval adds one meaningful review checkpoint. Stale edits, stale approvals,
and concurrent replacement requests are rejected by backend transactions.

Automated tests verify data preservation, eligibility, approval, stale-operation
protection, and lifecycle behavior using simulated responses. They do not establish that
every live model produces a scientifically faithful charter. Live evaluation
should include broad exploration, focused research, note-only answers, accepted
uncertainty, explicit corrections, and tensions between recorded decisions.
