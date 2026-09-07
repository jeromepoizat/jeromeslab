# ADR 0002: Immutable lineage and project forks

- Status: Accepted
- Date: 2026-09-07

## Context

Changing an upstream scientific result can invalidate every dependent result.
Silent mutation would make conclusions impossible to reproduce. Human review is
also necessary for some machine-generated outputs.

## Decision

Completed workflow history is immutable once downstream work depends on it. A
manual edit preserves the original and creates an effective artifact version;
downstream runs reference the exact consumed version. The latest step may be
rerun only without dependents. Alternative work after a used checkpoint creates
a project fork that references shared immutable upstream history.

Editable user notes are outside computation unless explicitly promoted into a
new artifact.

## Consequences

The system can reproduce and compare branches without duplicating large data.
Schemas and services must enforce dependency rules, version selection, lineage,
shared ownership, and safe deletion. The UI must explain why some actions fork
instead of edit.

