# Roadmap

Milestones are sequential enough to control scope but may overlap for small
enabling work. A milestone is complete only when behavior, tests, and relevant
documentation agree.

## Milestone 0 — Repository foundation (current)

- Establish repository-as-memory documentation and agent guidance.
- Record accepted architectural and product decisions.
- Establish minimal Python package, frontend location, and test location.
- Bootstrap reproducible Python and frontend environments with generated
  lockfiles.
- Add idempotent Windows and POSIX bootstrap scripts that install pinned runtimes
  locally without administrator rights or global system changes. Windows x64 is
  verified; macOS, Linux, and ARM64 validation remains.
- Establish linting, type-checking, and test commands in CI.
- Add contribution and development setup guidance after commands are verified.

Exit criterion: a new contributor can clone and bootstrap without preinstalled
language runtimes, run checks, and understand current scope without prior
conversation.

## Milestone 1 — Local application shell

- FastAPI/Uvicorn application and health endpoint.
- React/Vite shell with the **Jerome's Laboratory** header.
- Platform application-data resolution and basic configuration.
- SQLite initialization and Alembic migration path.
- Python launcher: migration, local port selection, `127.0.0.1` binding, browser
  open, terminal logs.
- `start.ps1` and `start.sh` wrappers that invoke the project-local runtime after
  bootstrap. The wrappers and browser-opening launcher are implemented; cross-
  platform validation remains.
- Basic settings surface without secret persistence yet.

After the local shell stabilizes, add CI-built OS-specific release packages that
bundle the frontend, backend, Python runtime, and dependencies. Validate packaging
on each target OS rather than treating it as a cross-compiled artifact.

## Milestone 2 — Projects

- Create, list, select, safely delete, and restore the most recently active
  project.
- Collapsible project sidebar and New Project view.
- Preserve the exact scientific question.
- User-note foundation with explicit non-computational semantics.

## Milestone 3 — Workflow and artifact engine

- Workflow steps, dependencies, attempts, timestamps, and durations.
- Immutable completed history and enforced transition rules.
- Immutable artifacts and original/effective artifact versions.
- Manual edits that preserve originals and exact downstream inputs.
- Project forks from checkpoints with shared upstream artifacts.
- Provenance inspection APIs and reusable workflow cards/navigation.

## Milestone 4 — Sequential Research Queue

- Persistent job states and progress.
- Exactly one executing worker and ordered pending work.
- Failure handling and explicit restart/crash recovery.
- Top-right queue panel and project-level polling updates.
- Navigation independent of job execution.

## Milestone 5 — LLM provider layer and accounting

- Provider-independent request/response contracts.
- OpenAI and Anthropic adapters behind the contract.
- Native OS credential storage and configuration-state API.
- Persistent `LLMCall` provenance for successful and failed attempts.
- Exact instruction/input, raw output, and parsed output preservation.
- Prompt-template identity/version and generation settings.
- Token-usage capture and provider-specific usage normalization without losing
  original categories.
- Immutable pricing snapshots and honest reported/estimated/unavailable cost
  accounting.
- Step-level and project-level usage, duration, call-count, and cost aggregation.
- UI summaries and inspection of individual call input, raw response, parsed
  output, usage, timing, errors, and cost basis.
- Tests proving credentials and authorization data never enter logs, exceptions,
  SQLite provenance, or artifacts.

## Milestone 6 — Research question decomposition

- Queue an LLM decomposition from the preserved question.
- Store full call provenance, raw output, and parsed original artifact.
- Review/edit to an effective artifact without losing the original.
- Continue only with the exact selected effective version.

## Milestone 7 — Literature query generation

- Source selection, beginning with the source chosen for retrieval prototyping.
- Source-specific queries with purpose and exact LLM provenance.
- Original/effective query versions and pre-execution review.

## Milestone 8 — Literature retrieval prototype

- Start with one source, provisionally Europe PMC.
- Query execution, pagination, raw-response artifacts, and external-error handling.
- Normalized publication metadata without invented fields.
- Conservative deduplication with every discovery relationship preserved.
- Defined/tested retrieval statistics, progress, and expandable publication UI.
- Add PubMed and cross-source overlap only after the single-source path is sound.

## Milestone 9 and later — design before implementation

Design literature screening collaboratively, then full-text/access resolution,
evidence extraction, reconciliation/weighting, and synthesis. Each stage needs an
explicit schema, provenance contract, human-correction behavior, evaluation plan,
and ADRs where choices affect scientific validity. In-silico research is beyond
these milestones and has no committed design.
