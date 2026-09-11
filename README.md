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

**Milestone 1: local application shell is in progress.** The Python and frontend
environments are locked, the bootstrap is verified across all six supported
OS/architecture combinations, and the local application includes its first live
research-direction and bounded project-framing workflow with immutable
provenance. See [current status](docs/STATUS.md) before starting work.

## Intended workflow

The agreed early workflow is:

1. preserve the user's exact scientific question;
2. choose a current research objective and retain later or parallel goals;
3. answer only the project-framing questions needed for the next cycle, with at
   most one follow-up round;
4. generate and approve a current-cycle research charter;
5. separately define literature-search and screening scope, then generate and
   review purpose-labelled, source-specific query families;
6. retrieve, normalize, and deduplicate literature without discarding records;
   and
7. use the resulting evidence to continue broadly, narrow, stop, or fork a new
   research direction without rewriting prior history.

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

## Planned offline replay and example project

The provider layer will include an explicit replay mode that returns versioned,
saved responses without a network request, API key, or API cost. A future bundled
example project will use it to demonstrate a realistic completed workflow. Replay
results will be visibly marked as simulated, recorded in provenance, and will
never silently fall back to a paid provider. See
[ADR 0008](docs/adr/0008-replay-provider-and-demo-project.md).

## Quick start from source

No preinstalled Python, Node.js, `uv`, or pnpm is required. The first installation
needs an internet connection and stores its runtimes and caches inside the
ignored `.runtime/` directory.

### Windows

Double-click `install.bat`, then `start.bat`, or run:

```bat
install.bat
start.bat
```

The `.bat` wrappers run `install.ps1` and `start.ps1` with a process-local
PowerShell execution-policy override; they do not change the system policy.
When opened by double-click, a failed installation or launch keeps the Command
Prompt window open so its error can be read or copied; press any key to close it.

### macOS and Linux

```sh
chmod +x install.sh start.sh
./install.sh
./start.sh
```

The install script downloads pinned, SHA-256-verified `uv` and Node.js archives,
uses a project-local Python 3.12 runtime, synchronizes both committed lockfiles,
and builds the frontend. It is safe to rerun after pulling an update. The start
script binds the server to `127.0.0.1`, chooses an available port, opens the
default browser, and keeps terminal logs visible.

The source bootstrap currently supports x64 and ARM64 Windows, macOS, and glibc-
verified Windows x64, Linux x64, and macOS ARM64; the expanded matrix subsequently
verified Windows ARM64, Linux ARM64, and Intel macOS as well.

On first launch, optionally configure OpenAI or Anthropic. Paste an API key,
fetch the compatible models available to that account, and select the global
default for future LLM jobs. The key is stored through the operating system
credential store, not in the workspace or browser. Provider setup can be deferred
until a live LLM operation is needed.

Starting research-direction clarification adds a durable job to the sequential
local queue. Queued work can be cancelled until provider dispatch begins. The
queue continues while the browser navigates between projects, and completed
output, exact call inputs/response, usage, timing, and provider/model provenance
are preserved in the workspace. API keys and authorization headers are never
stored there. The
provider's validated direction choices and the user's current objective,
optional later or parallel goals, and note are stored as separate immutable JSON
artifacts. After confirmation, the project-framing round generates one to five
validated user decisions with single- or multiple-choice answers, a manual note,
and an explicit Not sure option. It snapshots the exact effective direction
version it uses and preserves confirmed or edited answer sets as immutable JSON
artifacts.

Broad exploration is a valid current objective. Framing asks only for the
project-level purpose, conceptual boundary, or ordering needed for the next
research cycle. It does not ask the user to predict evidence-dependent scientific
answers or decide later literature-query and screening scope. An explicit
readiness job either marks the framing ready for a current-cycle charter or
generates the only permitted follow-up questionnaire. Unresolved scientific
questions are retained as investigation objectives or deferred decisions instead
of causing an indefinite clarification loop. Provider output that repeats an
answered question is rejected. Generated questions explicitly distinguish
independent choices from cumulative boundaries, and an invalid cumulative
multiple-choice question is also rejected. Raw call responses remain preserved.
Consumed prompts and outputs keep their exact historical versions.
Existing projects with completed question-detailing outputs retain their original
Markdown and manual versions as a compatibility path.

Next, choose a dedicated research workspace. The application suggests
`Documents/Jerome's Laboratory`, but you can type or paste another absolute path
or use the operating system folder picker. The workspace contains the local
database, artifacts, exports, and backups; the repository itself never stores
your research data.

## Manual developer setup (optional)

Developers who prefer their system toolchains can use the commands below.

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

Open `http://127.0.0.1:5173`. This two-process mode enables frontend hot reload;
ordinary use should go through the start script instead.

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

## Continuous integration

The `Cross-platform CI` GitHub Actions workflow runs after every push and pull
request, and can also be started manually. It provisions separate clean x64 and
ARM64 runners across Windows, Linux, and macOS, including Intel macOS. Each runner
performs a fresh bootstrap, repeats it to check idempotency, and runs the Python
and frontend checks.

To inspect a run on GitHub:

1. Open the repository and select the **Actions** tab.
2. Select **Cross-platform CI** in the left sidebar.
3. Open a workflow run, then select an operating-system job in the graph or job
   list.
4. Expand the first red step. Its command output is normally the most useful
   starting point; the **Set up job** step also identifies the exact runner image.

The log view can be searched, downloaded, and linked to a specific line. Someone
with repository write access can rerun all failed jobs or one specific job from
the run page. A green workflow means all six platform jobs passed; a red workflow
can still contain useful green results for the other systems.

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Product vision](docs/PROJECT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Scientific workflow](docs/WORKFLOW.md)
- [Data model](docs/DATA_MODEL.md)
- [Roadmap](docs/ROADMAP.md)
- [Current status](docs/STATUS.md)
- [Decision index](docs/DECISIONS.md)

Jerome's Laboratory is licensed under the [Apache License 2.0](LICENSE).
