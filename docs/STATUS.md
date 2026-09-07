# Current status

Last updated: 2026-09-07

## Current milestone

**Milestone 0 — Repository foundation is complete.** Self-bootstrapping
installation and project checks pass on GitHub-hosted Windows x64/ARM64, Linux
x64/ARM64, and macOS ARM64/Intel runners. Milestone 1 has not started and is
waiting for owner direction.

## Implementation state

- Source-of-truth product, architecture, workflow, data-model, roadmap, status,
  and decision documentation now exists.
- Python dependencies are resolved in `uv.lock` and installed in the ignored
  local `.venv` using Python 3.12.
- The React/TypeScript/Vite frontend is resolved in `frontend/pnpm-lock.yaml` and
  installed in ignored `node_modules` using Node 24 and pnpm 11.
- A minimal FastAPI `/api/health` endpoint, API smoke test, and React application
  shell exist. The Vite development server binds to `127.0.0.1` and proxies the
  API to port 8000.
- The shell defaults to a dark theme with an accessible light/dark toggle. API
  health is represented by a minimal status dot with hover/focus detail rather
  than language that could be confused with an external LLM provider.
- `install.ps1`/`.bat` and `install.sh` download pinned project-local runtimes,
  verify runtime archive checksums, install both lockfiles, and build the client.
- `start.ps1`/`.bat` and `start.sh` call a Python launcher that binds to loopback,
  chooses an available port, waits for health, and opens the default browser. The
  backend serves the built frontend.
- `.github/workflows/ci.yml` defines bootstrap and verification jobs on GitHub-
  hosted Windows x64/ARM64, Linux x64/ARM64, and macOS ARM64/Intel runners. All
  six jobs passed in workflow run `34131271837` for commit `3a441ec`.
- `CONTRIBUTING.md` documents source installation, launch, project-local checks,
  pull-request expectations, CI review, and project invariants.
- No database schema, migration, settings persistence, provider adapter, queue,
  project feature, or scientific workflow code has been implemented.

## Recently completed

- Converted the initial product brief into maintainable repository documentation.
- Recorded foundational ADRs for the local web stack, immutable lineage, hybrid
  storage, sequential jobs, secret handling, and LLM provenance/cost accounting.
- Made later scientific stages explicitly design-in-progress rather than finalized.
- Added repository guidance and ignores for secrets and runtime data.
- Generated reproducible Python and frontend lockfiles and installed both
  dependency sets.
- Added a health endpoint, one backend smoke test, and the header-only client
  shell as the first runnable integration slice.
- Verified locked installs, Python lint/type/tests, and frontend lint/build on
  Windows.
- Added pinned x64/ARM64 runtime metadata for Windows, macOS, and Linux; added
  checksum-verifying bootstrap and start scripts for Windows and POSIX systems.
- Completed a clean project-local Windows x64 bootstrap and an idempotent second
  run without relying on system Python, Node.js, `uv`, or pnpm.
- Added the canonical browser-opening launcher and static frontend serving.
- Accepted an explicit, strict replay provider and future bundled example project
  for deterministic, zero-cost workflow demonstrations without paid-API fallback.
- Added the first cross-platform GitHub Actions workflow and user-facing guidance
  for inspecting its operating-system jobs and logs.
- Verified fresh and repeatable bootstrap, locked dependency installation, Python
  checks, frontend lint, and frontend build on GitHub-hosted Windows x64, Linux
  x64, and macOS ARM64 runners.
- Expanded CI and verified the same bootstrap and checks on Windows ARM64, Linux
  ARM64, and Intel macOS, completing all six declared platform combinations.
- Added contributor guidance using only the project-local toolchain installed by
  the bootstrap.
- Simplified the local API health display to a tooltip-enabled status dot and
  added a dark-default light/dark theme toggle.

## Work in progress

No implementation work is active. Milestone 1 is intentionally waiting for owner
direction.

## Immediate next tasks

1. Wait for owner direction before beginning Milestone 1.
2. When authorized, design the first Milestone 1 storage slice immediately before
   implementing the application-data location and SQLite migration foundation.

## Known issues and blockers

- Native release packaging and graphical interaction still require later
  platform-specific testing beyond bootstrap CI.
- GitHub reports that the `windows-11-arm` runner label will migrate to a Visual
  Studio 2026 image on 2026-09-21. The project does not currently depend on Visual
  Studio, and normal CI pushes will detect any unexpected image regression.

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
- Bootstrap proxy/offline behavior, disk-space reporting, musl Linux support, and
  the eventual native package/signing format.
