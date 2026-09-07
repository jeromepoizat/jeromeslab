# ADR 0008: Explicit replay provider and bundled demo project

- Status: Accepted
- Date: 2026-09-07

## Context

Developers need to exercise LLM-backed workflows repeatedly without spending API
credits, requiring provider credentials, depending on network availability, or
receiving nondeterministic outputs. New users also need a way to explore a
representative completed workflow before configuring a provider.

A conventional mock is sufficient for isolated unit tests but does not by itself
exercise the real workflow, parsing, persistence, provenance, and user interface.
Conversely, presenting saved outputs without an explicit simulation boundary
could cause example results to be mistaken for newly generated scientific work.

## Decision

Add a provider-neutral `ReplayProvider` as part of the Milestone 5 LLM layer. It
will return versioned, local fixtures through the same contract used by real
provider adapters. Normal automated tests will remain network-free and may use
smaller mocks where appropriate; integration tests and a future bundled example
project may use the replay provider to exercise complete workflows.

Replay matching is strict and deterministic. A fixture identifies the operation,
prompt-template version, relevant settings, and canonical request input. If no
fixture matches, replay mode fails with an actionable error. It never silently
falls back to a paid provider or makes a network request.

Every replay attempt creates normal call provenance and is visibly identified as
simulated. It records the replay provider, fixture identity and version, exact
input, saved raw and parsed output, timing, and errors. It has no real provider
request ID, no actual token consumption, and zero actual API cost. Historical
usage or estimated cost included for demonstration is stored separately and
labelled as reference data, never as usage incurred by the replay.

The user interface must show when a project, run, artifact, or call contains
example or simulated data. Enabling replay is an explicit project or development
choice. Bundled fixtures must contain no secrets or private research data and
must have redistribution-compatible content.

## Consequences

Contributors can test complete LLM workflows without credentials or API expense,
and users can inspect a realistic example project immediately. Tests become
deterministic and can cover provenance and parsing regressions. Fixture formats,
canonical request matching, sanitization, licensing, and migrations need explicit
implementation work when the provider layer is built. Saved responses must be
reviewed when prompts or schemas change.
