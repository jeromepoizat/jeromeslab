# ADR 0006: LLM calls as provenance with historical cost basis

- Status: Accepted
- Date: 2026-09-07

## Context

LLM operations are nondeterministic scientific transformations. Providers expose
different usage categories, and model pricing changes over time. Recalculating an
old call with current prices or losing its exact prompt/output would damage
traceability.

## Decision

Record every LLM API attempt as first-class provenance behind a provider-neutral
interface. Preserve exact supplied instructions/input, complete raw output where
practical, parsed output, settings, model/provider, template version, timing,
request ID, retries/errors, normalized usage, and provider-specific metadata.
Large payloads may be immutable artifacts.

At call time, reference an immutable pricing snapshot containing applicable rates,
units, currency, source/version, and effective/capture time. Preserve provider-
reported and locally calculated costs separately. Mark cost as reported,
estimated, or unavailable; missing usage is unknown rather than zero.

Never persist secrets or authorization material in this provenance.

## Consequences

Runs and forks can be compared by output, latency, usage, and cost, and historical
costs remain reproducible. Adapters need careful normalization without discarding
provider detail. Pricing ingestion/versioning, retry-attempt shape, redaction, and
aggregate reconciliation need implementation designs and tests.

