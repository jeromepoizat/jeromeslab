# ADR 0010: One local application instance

- Status: Accepted
- Date: 2026-09-07

## Context

The local backend owns SQLite writes. Starting the launcher twice could create
two servers and, as the application grows, competing writers for one workspace.

## Decision

The launcher keeps a temporary running-instance record in the same per-user
platform configuration directory as the workspace pointer. A new launcher first
checks the recorded loopback server. If it is healthy, or its recorded process is
still starting, the new launcher opens that existing instance in the browser and
exits. Stale or malformed records are replaced safely. The primary launcher
removes only its own record on shutdown.

This coordinates backend processes, not browser tabs. Users may open multiple
tabs connected to the one local server.

## Consequences

Ordinary repeated starts do not create duplicate local servers. A crash can
leave a record, so the next start must tolerate and recover stale state. The
record contains only a process ID, loopback port, and random launch identifier;
it contains no workspace data or credentials.
