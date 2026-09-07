# Current status

Last updated: 2026-09-07

## Current milestone

**Milestone 0 — Repository foundation.** Self-bootstrapping installation works on
Windows x64; cross-platform CI and contributor setup remain.

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
- `install.ps1`/`.bat` and `install.sh` download pinned project-local runtimes,
  verify runtime archive checksums, install both lockfiles, and build the client.
- `start.ps1`/`.bat` and `start.sh` call a Python launcher that binds to loopback,
  chooses an available port, waits for health, and opens the default browser. The
  backend serves the built frontend.
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

## Work in progress

Cross-platform bootstrap verification and CI setup.

## Immediate next tasks

1. Add CI for bootstrap coverage, locked installs, Python lint/type/tests, and
   frontend lint/build on Windows, Linux, and macOS.
2. Exercise the POSIX installer on Linux/macOS and all declared ARM64 paths;
   correct any platform-specific archive or shell behavior.
3. Add contribution guidance based on the verified bootstrap and check commands.
4. Begin the remaining Milestone 1 slice: app-data location and SQLite
   initialization/migration.
5. Add the initial settings/configuration boundary without storing credentials.
6. Resolve the first schema decisions immediately before their implementation,
   recording an ADR only where the choice is architecturally significant.

## Known issues and blockers

- Windows x64 with the project-local Python 3.12, Node 24, pnpm 11, and uv 0.12
  bootstrap is the only environment verified so far. Linux, macOS, and ARM64
  still require CI or hardware coverage.

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
