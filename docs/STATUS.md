# Current status

Last updated: 2026-09-07

## Current milestone

**Milestone 1 — Local application shell is in progress.** Milestone 0 remains
complete: self-bootstrapping installation and project checks pass on GitHub-hosted
Windows x64/ARM64, Linux x64/ARM64, and macOS ARM64/Intel runners.

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
  health is polled every three seconds and represented by a minimal status dot
  with hover/focus detail rather than language that could be confused with an
  external LLM provider.
- First run asks the user to choose a research workspace. The path field is
  pre-filled with a Documents-based recommendation, supports typing/pasting, and
  has a native folder-picker action. A small platform-configured pointer remembers
  the selected workspace; workspace data itself remains together in the selected
  folder.
- The workspace initializes SQLite through a packaged Alembic migration chain and
  creates dedicated `artifacts`, `exports`, and `backups` directories. The launcher
  applies migrations before starting an already-configured workspace.
- A moved or missing remembered workspace opens a recovery screen rather than
  failing launch. It can reconnect only an existing recognized workspace or forget
  the pointer. Settings can explicitly move the one workspace by copy, per-file
  SHA-256/size verification, then pointer switch; it never deletes the source.
- The launcher coordinates one loopback backend process per user. A second start
  opens the existing healthy or starting instance and exits; stale records recover.
- The header includes Settings with a confirmed **Forget workspace on this
  device** action. It removes only the saved workspace pointer and returns to the
  first-run screen; it does not delete the workspace database, artifacts, or files.
  Settings open in a dedicated right-side drawer so workspace content remains in
  view.
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
- No provider adapter, queue, project feature, or scientific workflow code has
  been implemented.

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
- Made the local API health indicator refresh periodically and when the browser
  regains focus so it cannot remain green after the local service stops.
- Began Milestone 1 with user-selected local workspace setup, SQLite initialization,
  Alembic migration support, and a protected first-run setup API.
- Added the first safe configuration-forgetting control for testing first-run
  behavior without deleting local research data.
- Added single-instance launch coordination, missing-workspace recovery, and a
  verified, non-destructive single-workspace move operation.

## Work in progress

Preparing the next Milestone 1 local-shell slice.

## Immediate next tasks

1. Verify the local-shell slice on the full cross-platform CI matrix.
2. Add the next basic settings surface without secret persistence.
3. Design the project and scientific workflow entry point.

## Known issues and blockers

- Native release packaging and graphical interaction still require later
  platform-specific testing beyond bootstrap CI.
- GitHub reports that the `windows-11-arm` runner label will migrate to a Visual
  Studio 2026 image on 2026-09-21. The project does not currently depend on Visual
  Studio, and normal CI pushes will detect any unexpected image regression.

## Open design questions and risks

- Artifact hash algorithm, canonical serialization, filesystem layout, and
  effective-version selection representation. A proposed integrity policy would
  record a versioned byte hash for every immutable artifact, show a warning on a
  mismatch without rewriting history, and require acknowledgement before known-
  mismatched input is used in new downstream work.
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
