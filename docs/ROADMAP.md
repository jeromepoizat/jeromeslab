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
- Settings surface with native credential storage, global OpenAI/Anthropic model
  defaults, and filtered live model discovery. Scientific generation calls remain
  part of Milestone 5.

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
- Native OS credential storage and configuration-state API (implemented early as
  a Milestone 1 prerequisite).
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
- Strict, deterministic replay-provider fixtures for network-free integration
  tests, with simulated provenance and no fallback to paid APIs.

## Milestone 6 — Research goal, assumptions and boundaries, and charter

- Generate validated dynamic research-direction choices from the preserved
  question and confirm one current objective, optional later or parallel goals,
  and a note.
- Generate one project-framing round and at most one material follow-up round,
  without moving literature-search eligibility or evidence-dependent scientific
  decisions into early clarification.
- Preserve every generated questionnaire, user decision, note, uncertainty,
  call, and prompt as exact provenance.
- Generate and approve an effective current-investigation research charter without
  losing its original.
- Continue only with the exact approved charter version.
- Maintain the implemented versioned peptide-discovery prompt defaults while
  preserving every consumed prompt and project artifact.
- Validate the specialized flow with broad therapeutic exploration, a known
  target without a candidate, and an existing peptide optimization project.
- Add a bundled example project once enough end-to-end workflow exists, using
  clearly labelled replayed outputs so it requires no provider key or API cost.

## Milestone 7 — Peptide evidence-investigation strategy and queries

- Generate charter-derived mandatory evidence themes and zero to six dynamic
  user-controlled evidence-scope questions (implemented).
- Preserve recommendations as advisory, accept notes and uncertainty, and
  version confirmed answers until downstream consumption (implemented).
- Generate and approve a compact evidence-investigation strategy from the exact
  approved charter, themes, and effective scope answers (implemented).
- Source selection across publications and relevant structured scientific data,
  beginning with one publication source for retrieval prototyping.
- Explicitly decide data-search and screening scope here, including applicable
  species or populations, evidence stages, study designs, publication types,
  dates, languages, outcomes, and inclusion or exclusion rules.
- Source-specific queries with purpose and exact LLM provenance.
- Purpose-labelled query families for broad exploratory evidence mapping.
- Peptide-relevant query purposes such as target biology, mechanism, known peptide
  modulators, interaction interfaces, efficacy, safety, stability, and delivery.
- Original/effective query versions and pre-execution review.

## Milestone 8 — Scientific-source retrieval prototype

- Start with one source, provisionally Europe PMC.
- Query execution, pagination, raw-response artifacts, and external-error handling.
- Normalized publication metadata without invented fields.
- Conservative deduplication with every discovery relationship preserved.
- Defined/tested retrieval statistics, progress, and expandable publication UI.
- Add PubMed and cross-source overlap only after the single-source path is sound.
- Specify adapters for protein/target, structure, interaction, bioactivity,
  peptide, sequence/motif, and assay sources individually before adding them.

## Milestone 9 — Peptide evidence extraction and synthesis

- Design publication screening and full-text/access resolution.
- Define atomic peptide-relevant evidence with explicit source location and
  observed/annotated/inferred/predicted type.
- Reconcile supporting, contradictory, negative, and missing evidence without an
  arbitrary universal evidence score.
- Produce traceable synthesis whose statements resolve to evidence and sources.

## Milestone 10 — Peptide design brief and candidate provenance

- Convert approved evidence and explicit user decisions into a versioned,
  human-approved peptide design brief.
- Preserve unknown or conflicting requirements rather than inventing defaults.
- Define peptide representations, modifications, parent/derivation lineage, and
  validity rules.
- Record imported, user-edited, adapted, and generated candidates through the
  same immutable provenance contracts.

## Milestone 11 — Modular in-silico discovery

- Select and validate one computational capability at a time rather than adding
  an opaque end-to-end score.
- Preserve tool/model version, parameters, seeds where applicable, exact inputs,
  raw output, units, failures, applicability limits, timing, and cost.
- Keep predictions distinct from experimental evidence and expose missing or
  conflicting evaluation dimensions.
- Support transparent prioritization and checkpoint forks for competing design
  strategies.

Every later scientific stage requires an explicit schema, provenance contract,
human-correction behavior, evaluation plan, and ADRs where choices affect
scientific validity.

After the first evidence-bearing end-to-end path exists, add investigation
checkpoints that let the user continue exploring, narrow a direction, stop, or
fork alternatives without rewriting any consumed charter or evidence history.
