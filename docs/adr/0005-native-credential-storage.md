# ADR 0005: Native credential storage

- Status: Accepted
- Date: 2026-09-07

## Context

LLM providers require API credentials. Browser storage, plaintext SQLite, logs,
and provenance artifacts are inappropriate secret stores.

## Decision

Use Python `keyring` to store credentials in the native OS credential store where
practical. Return only configuration state to the frontend, never saved values.
Redact credentials and authorization material from logs, client errors, LLM-call
records, and artifacts.

## Consequences

Credential behavior varies by platform and may require actionable setup errors or
a future explicitly designed fallback. Tests must verify non-disclosure across
success and failure paths. First-start research remains blocked until credentials
are configured.

