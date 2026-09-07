# ADR 0003: SQLite metadata and file artifact storage

- Status: Accepted
- Date: 2026-09-07

## Context

The application is local and single-user, but raw search responses, LLM payloads,
full text, and exports may be large. Project forks should share data.

## Decision

Use SQLite through SQLAlchemy with Alembic migrations for metadata, relationships,
status, and indexes. Store large/raw immutable payloads in an OS-appropriate
application-data directory and reference them from SQLite. Do not assume the
repository is a writable runtime-data location. Use `platformdirs` and `pathlib`.

## Consequences

Deployment remains simple and large blobs do not dominate the database. Backup,
integrity, garbage collection, and deletion must coordinate the database and
filesystem. Content hashing is promising but its exact design remains open.

