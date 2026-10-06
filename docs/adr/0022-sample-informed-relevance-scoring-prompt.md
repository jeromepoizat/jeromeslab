# ADR 0022: Generate a reviewable, sample-informed relevance prompt before calibration

- Status: Accepted
- Date: 2026-10-05
- Amends: ADR 0021's preparation order and first-run-cap timing; its distinct-source sampling, relevance-only outcomes, and future bounded-scoring decisions remain in force.

## Context

ADR 0021's first implementation treated the preparation endpoint mainly as a small scoring pilot using an editable generic rubric. That pilot did not produce the compact, investigation-specific scoring rules the researcher intends to review and reuse across many later batches. Repeating the entire approved charter and investigation plan in every batch could raise token use; omitting them without a careful derived prompt could erase important scope.

## Decision

The main preparation LLM job generates a **standalone relevance-scoring prompt** from the exact approved charter and investigation plan, a versioned starting rubric, and a reproducibly seeded sample of saved titles/abstracts. The seed drives the prompt-design/calibration sample. The first-run record limit is chosen later in the scoring stage, not during prompt preparation. The sample informs terminology and ambiguous cases, but cannot justify new exclusions or claims about corpus prevalence. The generated prompt must retain the current investigation objectives, mandatory themes, relevant negative findings, accepted uncertainty, 0–5 score boundaries, and `not_assessable`; it must not score quality or decide final inclusion.

The original generated prompt and each user edit are immutable hashed artifact versions with one effective pointer. A calibration call can then test that exact effective prompt on the seeded sample. Its input records the generating job and artifact version, and does not resend the full charter/plan. Once a downstream calibration is queued, the consumed prompt version is locked. Existing legacy calibration jobs remain valid history; they are not reinterpreted as prompt-generation jobs.

After prompt generation, the UI shows a provisional per-1,000-report token and USD estimate extrapolated from that same sample and the effective generated prompt. No full-run count or estimate appears in preparation; those belong to the later bounded scoring stage. Estimates do not predict model behavior or guarantee billing. The later bounded scoring worker will use an explicitly reviewed effective prompt, not a generic rubric or repeated full charter/plan, while retaining links to the source context. A small sample is a design aid, not independent validation of scoring accuracy; bulk scoring still needs separate review and interruption controls.
