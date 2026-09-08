# ADR 0011: Global LLM provider configuration and live model discovery

- Status: Accepted
- Date: 2026-09-08

## Context

The first live scientific transformation needs a provider and model, while users
must still be able to open local projects without spending API credits. Provider
catalogs change over time and may include models that cannot perform the text
generation required by the workflow.

## Decision

Initially support the direct OpenAI and Anthropic APIs. Store one device-global
provider and model default; changing it affects future jobs only. Fetch the model
catalog using the account's credential, then show only identifiers that pass a
small provider-specific text-generation compatibility filter. Do not offer a
manual model identifier or an unfiltered "other models" list in V1.

Store API keys exclusively behind the native credential-store boundary. Store
the selected provider, selected model, deferred-onboarding state, and last
successfully filtered model lists in device-local non-secret configuration. A
successful model fetch validates and saves a supplied key. Provider setup appears
before workspace selection but may be deferred; only a live LLM job requires a
complete provider configuration.

Before each future LLM job, display the current global provider/model and offer a
route to change it. Every attempted job snapshots its actual provider and model
in immutable provenance rather than referring back to the mutable global default.

## Consequences

The normal selector remains current for models returned to that account while
avoiding obviously incompatible audio, image, embedding, search, realtime, and
specialized models. Newly named OpenAI text-model families require a filter
update before appearing. Cached lists support a stable settings display but must
not be treated as proof that a model remains callable. A future local provider
can implement the same catalog/configuration boundary without changing workflow
code and may omit API-key requirements.
