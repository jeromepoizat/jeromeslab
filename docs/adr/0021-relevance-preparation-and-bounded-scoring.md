# ADR 0021: Distinct-source relevance preparation and bounded scoring

- Status: Accepted
- Date: 2026-10-05

## Context

Europe PMC retrieval can return thousands of query appearances. A researcher may
not want to pay to score all of them. The app must preserve broad exploratory
coverage, let the researcher inspect and adjust the relevance criterion before
bulk use, and make selection and cost traceable. Provisional same-article groups
(ADR 0020) are not verified screening identities.

## Decision

The preparation unit is one distinct `(source collection, source record ID)` in a
completed retrieval. Repeated appearances across queries are sampled once;
provisional article groups are **not** collapsed into screening units. A
versioned, seeded algorithm balances records across query × collection strata.
The job snapshots the algorithm version, seed, retrieval ID, exact selected-ID
manifest and hash, source-metadata hash, approved strategy (including its
charter), editable relevance instructions, model, and pilot record metadata.
Changing a control invalidates the preview.

The researcher chooses a future scoring limit and a separate small calibration
sample. The pilot is the final action in preparation: one ordinary queued LLM
job scores only the selected pilot records and preserves its raw response,
validated output, usage, and call provenance. Calibration may be repeated with
new instructions; each attempt remains separate history. No bulk run is started
by previewing or calibrating.

Relevance outcomes are integer **0–5** or **not assessable** when the saved
title/abstract cannot justify a score. Zero means unrelated, not missing or
unassessable. Negative findings may be relevant. This stage must not assign
study quality, evidence strength, risk of bias, or scientific truth.

Preparation shows rough calibration and future-batch token estimates and a
separate USD estimate only for exact OpenAI models with a checked, dated Standard
API rate. The calculation assumes no caching/discount and a provisional
ten-record future batch size; it is not a spending cap or billing guarantee.
The model-rate snapshot and estimated actual usage cost are retained with new
completed calls where exact usage and model identity permit it. Unknown models,
historical calls without a contemporaneous snapshot, and non-Standard or
long-context ambiguity remain `unavailable`, never silently guessed.

The subsequent scoring slice will use bounded batches and may stop **between**
provider requests at the user's direction, never cancel an in-flight billable
request. It will report scored and unscored distinct records, a separate not-
assessable count, and expandable counts by score, query family, and collection.
Records found by multiple queries retain every discovery link, so query-family
subtotals can overlap and must be labeled accordingly. A later extension action
will score previously unscored records with a new user-chosen limit; it cannot
rewrite prior scores or sampling provenance.

## Consequences

The initial implementation provides deterministic preview, separate cap/sample
controls, sample inspection, an editable relevance instruction field, calibrated
pilot results, and token/cost preview. It does **not** yet provide bulk scoring,
batch interruption, score histograms, score-threshold selection, or extension.
Those actions require a separate durable batch/record decision model and UI.
