# Architecture

This document records the accepted architecture and the proposed component
boundaries. A minimal FastAPI health endpoint and React shell exist; except where
noted in `STATUS.md`, the remaining components are not yet implemented.

## Runtime shape

Jerome's Laboratory is a single-user local web application:

```text
Browser (React/TypeScript)
        |
        | HTTP on 127.0.0.1
        v
FastAPI application
  |-- workflow services ------> persistent sequential job worker
  |-- LLM service ------------> provider adapters
  |-- literature service -----> scientific-source adapters
  |-- repositories -----------> SQLite
  |-- artifact service -------> immutable files in application data
  `-- credential service -----> native OS credential store
```

The browser is a presentation client. FastAPI routes validate requests, call
application services, and map results to response schemas; they do not contain
scientific business logic.

## Frontend

React, TypeScript, and Vite are accepted. The interface requires persistent
project navigation, expandable workflow cards, long-page navigation, queue state,
settings, forks, and polling-based live updates. Streamlit would constrain these
interactions, and Next.js adds server-rendering machinery that a local client does
not currently need.

The initial client will poll job and project endpoints. WebSockets are out of
scope for V1; Server-Sent Events can be evaluated later if polling becomes
inadequate.

## Backend boundaries

The Python package will evolve toward these logical modules:

```text
jeromes_laboratory/
  api/             HTTP routes and response/request schemas
  application/     use cases and transaction boundaries
  database/        SQLAlchemy models, repositories, migrations
  workflow/        step rules, runs, dependency and fork logic
  jobs/            persistent queue and single worker
  artifacts/       immutable payload storage and version selection
  llm/             generic contracts, provider adapters, usage and cost
  sources/         scientific database adapters
  literature/      normalization, identity resolution, deduplication
  security/        credential-store boundary and redaction
  launcher/        initialization, port selection, server and browser startup
```

Names may change as code makes the boundaries concrete. Dependency direction is
inward: routes and provider adapters depend on generic application/domain
contracts, while workflow services do not import UI or provider SDK details.

## Database and artifact storage

SQLite, SQLAlchemy, and Alembic are accepted for relational metadata, state,
links, and indexes. One local backend process owns database writes.

Large or raw payloads—LLM prompts and responses, database API responses, JSONL
record sets, full-text XML, legal local PDFs, and exports—belong in an
OS-appropriate application-data directory located with `platformdirs`, not in the
repository. SQLite stores artifact identity, integrity metadata, and relationships
to those payloads.

Artifacts are immutable. An edit creates a new `ArtifactVersion`; a pointer or
explicit relationship selects the effective version. Project forks reference
shared upstream artifacts rather than copying files. Content hashing is a
candidate for integrity and deduplication, but its exact algorithm and canonical
serialization are unresolved.

## Workflow and jobs

A `WorkflowStep` describes a step in a project lineage. A `StepRun` records one
attempt and its precise inputs and outputs. Completed runs with downstream
dependents are immutable. The latest step may be rerun only while it has no
dependent results; otherwise, the user creates a `ProjectFork` from a checkpoint.

Jobs are persistent database records. In V1 exactly one worker executes one job at
a time; other jobs remain pending. State transitions and restart recovery rules
must be transactional and tested. The exact recovery policy for a job found in
`running` state after a crash remains unresolved.

## LLM layer and call accounting

Scientific workflows call a provider-neutral interface such as `LLMProvider`.
OpenAI and Anthropic are planned adapters, not branches in workflow code. Generic
requests cover content, operation, template identity, and generation settings;
adapter results normalize common usage while retaining optional provider-specific
metadata.

Every attempt creates an `LLMCall` record linked where applicable to its project,
step run, and job. Exact supplied instructions/input, raw output, parsed output,
provider request ID, settings, timing, retries, errors, usage categories, and cost
calculation basis are preserved. Large payloads may be immutable artifacts.
Secrets and authorization material must be redacted before data crosses this
boundary.

Cost is calculated against a stored pricing snapshot selected at call time—not
against today's price table later. Provider-reported and locally calculated costs
remain separate. A status distinguishes reported, estimated, and unavailable
costs. Aggregates are derived from calls at step and project level; they are not a
replacement for call-level records.

### Replay and example data

The provider-neutral boundary will also support an explicit `ReplayProvider` for
deterministic, network-free integration tests and a future bundled example
project. Replay requests match versioned local fixtures strictly; a missing match
fails and never falls back to a paid provider. Replayed calls retain ordinary
provenance but are marked simulated and identify their fixture and version. Their
actual usage and API cost are zero; optional historical usage or cost is separate,
clearly labelled reference data. The interface must visibly distinguish all
example or simulated results from live research results. See
[ADR 0008](adr/0008-replay-provider-and-demo-project.md).

## Scientific source integrations

Each source adapter owns request construction, pagination, source-specific
response parsing, rate/error handling, and raw-response capture. Literature
services normalize without inventing missing fields and deduplicate publications
while retaining a `PublicationSource` record for every discovery through every
query and search run.

Europe PMC is the proposed first retrieval adapter. PubMed follows after the
single-source pipeline works. This ordering is a roadmap proposal, not a claim of
implementation.

## Secrets and local security

API credentials are stored through Python `keyring` in the native OS credential
store. They are never stored in frontend local storage, plaintext SQLite, logs,
exceptions returned to the client, prompts, artifacts, or LLM-call provenance.
The API returns configuration state such as `configured: true`, never a saved
secret. Redaction and non-persistence require explicit tests.

The server binds to `127.0.0.1`, not `0.0.0.0`, by default. Broader binding would
require an explicit future security decision.

## Launch process

The canonical Python launcher currently chooses a port, starts the server on
loopback, opens the browser after the health endpoint responds, and keeps terminal
logging active. As Milestone 1 continues, it will perform the full sequence:

1. locate platform application data;
2. initialize configuration and migrate SQLite;
3. inspect/recover the job queue;
4. choose an available local port;
5. start Uvicorn on `127.0.0.1`;
6. open the default browser with Python's `webbrowser` module; and
7. keep terminal logging active without exposing secrets.

The committed `start.ps1`, `start.bat`, and `start.sh` wrappers call the canonical
Python launcher through the project-local environment; application logic remains
cross-platform Python. Docker may be optional later and is not the normal runtime
architecture.

## Installation and distribution

Ordinary users must not need Python, Node.js, `uv`, or pnpm preinstalled. Two
delivery paths serve different audiences:

1. Source-checkout bootstrap scripts (`install.ps1`/`install.bat` on Windows and
   `install.sh` on macOS/Linux) download pinned tool versions into ignored local
   storage, use `uv` to install the pinned Python line and locked Python
   dependencies, download a pinned Node.js distribution, install the locked
   frontend dependencies, and build the static client. Subsequent start wrappers
   use only those local assets. The Windows x64 path is implemented and verified,
   including an idempotent second run. The POSIX implementation awaits Linux and
   macOS CI verification.
2. Release artifacts will eventually bundle the built frontend, Python runtime,
   backend, and dependencies into OS-specific packages. These are the preferred
   non-developer experience and require neither Git nor a first-run toolchain
   download.

Bootstrapping must be idempotent, avoid administrator rights and global PATH
changes, verify published checksums where available, fail with actionable errors,
and never install credentials. Runtime versions and download origins are pinned
and reviewed explicitly. Because native application bundlers are not
cross-compilers, Windows, macOS, and Linux releases are built and tested on their
respective operating systems.

## Development layout and tooling

Python uses a `src/` layout and `uv`; the frontend lives under `frontend/` and
uses pnpm. `pytest` is the Python test runner, and external calls use fixtures or
mocks in normal tests. Generated `uv.lock` and `pnpm-lock.yaml` files make both
dependency sets reproducible.

GitHub Actions exercises the user-facing bootstrap twice on Windows, Linux, and
macOS across x64 and ARM64, including Intel macOS, then runs Python linting, type
checking, tests, and frontend linting. The second bootstrap verifies idempotency;
each bootstrap also performs the locked frontend build. `fail-fast` is disabled
so a failure on one platform does not hide results from the others.
