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

The repository is in **Milestone 0: repository foundation**. It contains the
source-of-truth product, architecture, workflow, data-model, decision, roadmap,
and status documentation plus a minimal Python package scaffold. There is not
yet a runnable application. See [current status](docs/STATUS.md) before starting
work.

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

## Install and run

The application cannot be installed or run yet. The next foundation task is to
bootstrap and lock the Python and frontend projects, add a minimal health-check
application, and document verified development commands. Planned development
tooling is `uv` for Python and a standard Vite package workflow for the frontend.

## Documentation

- [Product vision](docs/PROJECT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Scientific workflow](docs/WORKFLOW.md)
- [Data model](docs/DATA_MODEL.md)
- [Roadmap](docs/ROADMAP.md)
- [Current status](docs/STATUS.md)
- [Decision index](docs/DECISIONS.md)

Jerome's Laboratory is licensed under the [Apache License 2.0](LICENSE).

