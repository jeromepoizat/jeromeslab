# ADR 0009: User-selected research workspace

- Status: Accepted
- Date: 2026-09-07

## Context

Jerome's Laboratory will store valuable, potentially large local research data.
Users need to know where it lives and may prefer a specific drive or backup
location. At the same time, first-run setup must remain simple for users who do
not want to reason about filesystem conventions.

## Decision

Keep only a small, safe configuration pointer in the platform-specific user
configuration directory located with `platformdirs`. On first run, require the
user to select the one research-workspace folder that contains the SQLite
database, immutable artifacts, exports, and backups.

The first-run screen pre-fills a Documents-based recommendation, accepts a typed
or pasted absolute path, and offers a native operating-system folder picker.
It validates the chosen path before creating workspace data. A non-empty folder
requires an explicit confirmation; an existing recognized workspace can be
reopened. The launcher applies Alembic migrations to a configured workspace
before serving the application.

Changing a location later is a future explicit workspace-move operation: copy,
verify, then switch the pointer without automatically deleting the old copy. It
is not a silent change to which projects happen to be displayed. Opening a
separate workspace is a distinct advanced action.

Settings may include an explicit **Forget workspace on this device** action for
testing and recovery. It removes only the small configuration pointer and never
deletes workspace files. The same principle applies to future saved settings:
each persistent configuration needs a clear, scoped forget action. Future API
credential removal will clear the credential-store entry only; it will not erase
provenance or research data.

## Consequences

Research data is visible and user-controlled while the launcher still has a
reliable location from which to recover it. The application must retain a small
configuration file outside the workspace, provide recovery behavior when a
saved workspace is missing, and implement workspace relocation with database and
artifact verification before exposing it in settings. Settings must explain
precisely what a forget action does and does not delete.
