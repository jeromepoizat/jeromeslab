# ADR 0026: Reviewed relevance-score selection

- Status: Accepted
- Date: 2026-10-11
- Builds on: ADRs 0023–0025.

## Decision

After validating scoring, the researcher chooses the records to carry into
further work. A vertical slider sets a minimum numeric relevance score from
0 to 5, including that score and every higher score. Each score shows its record
count; included/excluded totals update locally. No LLM call or source request is
required. The initial threshold is 0 so the application does not silently impose
a scientific relevance cutoff before review.

Not assessable is not a numeric relevance score. A separate, explicitly labelled
checkbox controls its inclusion, initially unchecked. Its count remains visible
so researchers can retain missing-information records for later review.

Validate selection opens a confirmation with exact included/excluded totals.
Confirmation stores one immutable, hashed selection per scoring run: the parent
scoring-validation digest, threshold, not-assessable choice, counts by outcome,
and exact included source identities. It consumes only the validated scored
pool, including when scoring was validated while paused. Unscored records are
not classified as excluded by this filter. At least one included record is
required to validate a pool for further work.

The validated selection is read-only and restored after restart. Original scores,
excluded records, and retrieval history are not modified or deleted. Future
downstream work must consume this exact selection, not recompute it from current
score rows or browser state. Changing the locked selection will require a future
checkpoint fork; forking and later quality/extraction stages are not implemented
by this decision. Relevance selection is not a study-quality assessment.
