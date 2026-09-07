# Current status

Last updated: 2026-09-07

## Current milestone

**Milestone 0 — Repository foundation.** The repository is documentation-first;
there is no runnable application yet.

## Implementation state

- Source-of-truth product, architecture, workflow, data-model, roadmap, status,
  and decision documentation now exists.
- A minimal Python `src/` package and `pyproject.toml` declare the accepted backend
  dependencies and development tools.
- `frontend/` and `tests/` have documented placeholders only.
- No API, database schema, migration, UI, launcher, provider adapter, queue, or
  scientific workflow code has been implemented.
- No dependency lockfiles have been generated and no automated checks can yet be
  run in the current environment.

## Recently completed

- Converted the initial product brief into maintainable repository documentation.
- Recorded foundational ADRs for the local web stack, immutable lineage, hybrid
  storage, sequential jobs, secret handling, and LLM provenance/cost accounting.
- Made later scientific stages explicitly design-in-progress rather than finalized.
- Added repository guidance and ignores for secrets and runtime data.

## Work in progress

None. The next task should complete the reproducible development scaffold.

## Immediate next tasks

1. Install or make available `uv` and a Node package manager; confirm supported
   Python and Node versions.
2. Generate and commit `uv.lock`, scaffold React/TypeScript/Vite, and commit the
   frontend lockfile without hand-writing generated dependency state.
3. Add minimal lint, type-check, and test commands plus CI; verify them locally.
4. Implement Milestone 1 as a small vertical slice: app-data location, SQLite
   initialization/migration, health API, header-only client, local launcher.
5. Resolve the first schema decisions immediately before their implementation,
   recording an ADR only where the choice is architecturally significant.

## Known issues and blockers

- `uv`, Python, and npm were unavailable on PATH during foundation setup; Node was
  present. This blocks verified dependency locking and test execution, not design
  documentation.
- Supported minimum runtime versions have not been validated. `pyproject.toml`
  currently proposes Python 3.12 or newer.

## Open design questions and risks

- Artifact hash algorithm, canonical serialization, filesystem layout, and
  effective-version selection representation.
- Project-fork ownership/deletion semantics for shared runs and artifacts.
- Queue ordering, cancellation, and restart policy for an interrupted running job.
- LLM retry-attempt representation and the source/update process for trustworthy
  pricing snapshots.
- Publication identity precedence and conflict handling during deduplication.
- First-source confirmation (Europe PMC is proposed) and external API etiquette.
- All later-stage scientific methods: screening criteria and disagreement,
  full-text resolution, evidence schema/strength, contradiction reconciliation,
  and synthesis structure.
- Localhost security details such as session/CSRF protection before any mutating
  browser API is exposed.

