# Jerome's Laboratory

Jerome's Laboratory is an open-source, local, LLM-assisted scientific research
application. It is intended to make a research process reproducible and
inspectable: a scientific conclusion should be traceable through structured
claims and evidence to publications, screening decisions, search runs, exact
queries, and the original question.

It is not intended to be an opaque scientific chatbot. The product will expose
the workflow, preserve machine-generated and human-edited material, and record
the provenance and cost of every LLM-assisted transformation.

## Current status

The repository is in **Milestone 0: repository foundation**. The Python and
frontend environments are locked, and a minimal FastAPI health endpoint and
React shell are runnable. Scientific workflow features are not implemented. See
[current status](docs/STATUS.md) before starting work.

## Intended workflow

The agreed early workflow is:

1. preserve the user's exact scientific question;
2. generate and review a research-question decomposition;
3. generate and review source-specific literature queries;
4. retrieve, normalize, and deduplicate literature without discarding records.

Screening, full-text resolution, evidence extraction, reconciliation, synthesis,
and downstream computational research are later design areas. They are not yet
finalized.

## Architecture at a glance

- React, TypeScript, and Vite for a browser interface.
- Python, FastAPI, Uvicorn, and Pydantic for a local HTTP service.
- SQLite with SQLAlchemy and Alembic for metadata and relationships.
- Immutable large artifacts on disk in an OS-appropriate application-data
  directory.
- A provider-independent LLM layer and source-specific literature adapters.
- A persistent queue with a single worker in V1.
- Native OS credential storage for API keys.
- Local binding to `127.0.0.1`; the default browser opens on launch.

These are accepted directions, but most are not implemented yet. Details and
status labels are in [Architecture](docs/ARCHITECTURE.md).

## Development setup

The commands below describe the currently verified developer setup. The accepted
distribution requirement is a self-bootstrapping `install.ps1`/`install.sh` path
with no preinstalled Python or Node.js, followed by self-contained native release
packages. That bootstrap is the next implementation task; see
[ADR 0007](docs/adr/0007-self-bootstrapping-installation.md).

Prerequisites:

- Python 3.12 or newer;
- [`uv`](https://docs.astral.sh/uv/);
- Node.js 20.19 or newer; and
- [`pnpm`](https://pnpm.io/) 11 or newer.

Install the locked dependencies:

```shell
uv sync --all-groups
cd frontend
pnpm install --frozen-lockfile
```

Run the backend from the repository root:

```shell
uv run uvicorn jeromes_laboratory.api.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal, run the frontend:

```shell
cd frontend
pnpm dev
```

Open `http://127.0.0.1:5173`. The final single-command launcher and automatic
browser opening belong to Milestone 1.

Run Python checks from the repository root:

```shell
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Run frontend checks from `frontend/`:

```shell
pnpm lint
pnpm build
```

## Documentation

- [Product vision](docs/PROJECT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Scientific workflow](docs/WORKFLOW.md)
- [Data model](docs/DATA_MODEL.md)
- [Roadmap](docs/ROADMAP.md)
- [Current status](docs/STATUS.md)
- [Decision index](docs/DECISIONS.md)

Jerome's Laboratory is licensed under the [Apache License 2.0](LICENSE).
