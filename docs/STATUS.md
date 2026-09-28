# Current status

Last updated: 2026-09-25

## Current milestone

**Milestone 1 — Local application shell is in progress.** Milestone 0 remains
complete: self-bootstrapping installation and project checks pass on GitHub-hosted
Windows x64/ARM64, Linux x64/ARM64, and macOS ARM64/Intel runners.

## Implementation state

- ADR 0015 narrows the product from general scientific research to
  evidence-guided therapeutic peptide discovery. The accepted path now runs from
  the original question through scientific-source evidence, an approved peptide
  design brief, candidate derivation, and modular in-silico evaluation. Existing
  generic infrastructure remains applicable. Peptide-specific defaults now cover
  the implemented direction, framing, framing-check, and charter stages; later
  evidence and design stages are not yet implemented.
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
- Workspace schema initialization is process-cached and protected by a lock.
  Concurrent browser startup requests cannot enter Alembic simultaneously, which
  previously produced an intermittent `/api/jobs` 500 response with Alembic's
  process-global proxy state and appeared as a blank page in Opera.
- The application now has a projects-only left navigation panel, expanded by
  default. The central area restores the last valid project and scroll position
  from device-local UI state, or shows a minimal scientific-question/start form.
  Projects receive sequential default tags (`PROJ001`, etc.); tags are mutable,
  while the scientific question is protected as workflow input.
- Scientific-question entry and editing start at a compact one-line height and
  grow naturally into a wrapped paragraph field when the question needs more
  space, with a bounded scroll area for exceptionally long text.
- Projects retain the exact legacy question-detailing prompt and template
  version that was supplied to that workflow. Versioned defaults
  are bundled as plain-text resources rather than Python strings. The project
  page displays the prompt beneath the scientific question and supports an
  explicit edit; custom prompts remain distinct from later app-default changes.
  Active version 5 prioritizes a focused primary question, critical scope
  decisions, disconfirming evidence, query vocabulary, and purpose-specific
  search themes instead of expanding into a generic encyclopedic program.
- The header includes Settings with a confirmed **Forget workspace on this
  device** action. It removes only the saved workspace pointer and returns to the
  first-run screen; it does not delete the workspace database, artifacts, or files.
  Settings open in a dedicated right-side drawer so workspace content remains in
  view.
- First run now offers OpenAI or Anthropic configuration before workspace
  selection and can be deferred for non-LLM use. API keys stay in the native OS
  credential store; `llm-settings.json` contains only the global provider/model,
  onboarding state, and cached compatible model identifiers.
- Provider-specific catalog adapters fetch account-visible models and expose only
  identifiers accepted by the maintained text-generation compatibility filters.
  Settings can refresh or replace credentials, change the global default, and
  forget a key. The question-detailing area previews the provider/model that a
  future job will use.
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
- A persistent single-worker queue executes intent-clarification and retained
  legacy question-detailing jobs.
  Enqueueing snapshots and locks the exact question, prompt/version, provider, and
  model. Pending jobs can be cancelled; the atomic `awaiting_response` transition
  closes cancellation before dispatch, and interrupted dispatched jobs fail
  without an automatic potentially billable retry.
- OpenAI Responses and Anthropic Messages adapters preserve secret-free request
  JSON, exact raw response, parsed Markdown, provider metadata, timing, normalized
  and original usage, and sanitized failures in first-class `LLMCall` records.
- Completed question-detailing output is deterministically wrapped in JSON and
  stored as an immutable artifact version with its UTF-8 byte length and SHA-256
  digest. Cost is explicitly `unavailable` until trustworthy immutable pricing
  snapshots are implemented.
- The project page confirms enqueueing, displays live state and completed output,
  and disables cancellation once provider dispatch begins. A global header badge
  and right-side queue drawer expose work while navigating between projects.
- Completed question detailing reuses the compact job/model card, renders output
  as Markdown in the same scrollable and expandable field pattern as other
  project content, and splits provider/model from usage, duration, and cost
  metadata around the expansion control.
- Manual output edits create new immutable, hashed artifact versions and move an
  explicit effective-version selection. The UI toggles between the permanently
  read-only original provider output and the editable effective version; stale
  concurrent edits are rejected.
- New and previously unused projects now begin with a research-goal questionnaire instead
  of the legacy one-shot decomposition. A versioned, editable prompt asks the
  selected provider for strictly validated JSON containing three to seven
  question-specific directions. Active version 4 specializes those choices for
  therapeutic peptide discovery, treats broad evidence mapping as a valid current
  objective, and distinguishes later or parallel goals without entering
  literature-search scope. The UI uses the same terms while the persisted
  schema retains its version-1 field names. Generated choices and the confirmed
  decision remain separate immutable, SHA-256-addressed artifacts.
- A confirmed research direction can be edited until downstream work is queued.
  Corrections create immutable numbered selection versions, preserve the initial
  confirmation, reject stale saves, and move an explicit effective-version
  pointer. Migration 0011 selects confirmations created by the initial slice.
- Job prompts use an advanced disclosure pattern: the prompt is hidden by default
  and a Show prompt/Hide prompt control in the job card reveals the standard
  editable field directly beneath that card without burdening the normal
  workflow. Direction, framing, readiness, and charter each use one stage title
  for their job, prompt, and result rather than presenting prompts as separate
  workflow sections.
- The first project-framing round is implemented for projects with a confirmed
  direction. Its versioned prompt and queued job consume a canonical JSON
  snapshot of the original question and exact effective intent artifact version.
  Provider output is accepted only as validated JSON containing project-level
  single- or multiple-choice questions.
- Every scope question supports suggested choices, **Not sure** with an optional
  explanatory note, or a manual note that may stand alone as the answer. Not sure
  remains exclusive of suggested choices. Confirmed answer
  sets are immutable, SHA-256-addressed artifacts; edits create numbered effective
  versions until downstream work is queued. The project page and global queue
  display the scope job with the same hidden-prompt, model, status, timer, and
  navigation patterns as intent clarification. Migration 0012 backfills the
  versioned default prompt for existing projects and adds the immutable structured
  job-input snapshot field.
- Scope-readiness review is implemented as an explicit queued LLM job after a
  non-empty first answer set is confirmed. It snapshots that exact effective version and
  accepts only validated JSON containing an operational readiness decision,
  assessment, recorded uncertainties, and zero follow-up questions when ready or
  one to five when clarification is still material. It does not claim to assess
  scientific truth, evidence, or feasibility.
- At most one follow-up questionnaire is allowed. It reuses the shared scope
  answer interface and immutable versioning; accepted uncertainty never traps the
  user in another automatic loop. First-round answers lock when readiness is
  queued, and follow-up answers remain editable until the future charter job
  consumes them. Migration 0013 adds the readiness prompt and upgrades only
  unused version-1 scope prompts to the improved version 2, preserving consumed
  prompts such as `PROJ007` byte-for-byte.
- The current readiness prompt version 6 treats Not sure, note-only, broad, and inclusive
  first-round responses as completed decisions whose uncertainty is carried into
  the charter. It forbids retrying them. A backend cross-input validator rejects
  repeated follow-ups by question ID or normalized text while preserving the
  rejected raw provider response. Migration
  0014 updates only readiness prompts that no readiness job has consumed.
- Prompt migration 0015 adopts evidence-led framing for future and unused
  projects. Intent version 2 and framing/readiness version 3 established broad
  exploratory cycles, evidence-dependent unknowns as investigation objectives,
  and the prohibition on early query, retrieval, or screening-scope questions.
  Consumed prompt snapshots such as `PROJ008` remain unchanged.
- After `PROJ009` exposed a cumulative multiple-choice ambiguity, framing and
  readiness prompt version 4 use structured-output schema version 2. Every
  question declares independent or cumulative option semantics; cumulative sets
  are rejected unless single-choice, and readiness must interpret selected IDs
  literally. Migration 0016 updates only unconsumed version-3 defaults, so
  `PROJ009` remains unchanged as the exact record that revealed the problem.
- A successful framing-readiness result is presented as a compact card that is
  collapsed by default. Expanding it reveals the complete assessment, call
  provenance, and preserved open questions under the more accurate label
  **Questions carried into the charter**. A required follow-up remains expanded
  until answered; the readiness stage does not introduce a competing notes field.
- First-investigation research-charter generation is implemented from an immutable snapshot
  of the original question, effective confirmed direction, framing questionnaire
  and answers, optional readiness review, and optional final follow-up answers. Its
  versioned prompt explicitly preserves broad exploratory investigations and forbids the
  model from inventing findings, restrictions, search terms, or eligibility rules.
- Charter outputs are immutable hashed Markdown artifacts. The current draft can
  be reviewed, manually versioned, compared with the original provider output,
  and explicitly approved. Approval identifies one exact effective artifact
  version; editing invalidates effective approval without deleting its history.
- A stage prompt is editable only before that stage's first job is created. The
  exact prompt remains viewable afterward but is locked together with the job
  input it produced; this rule is enforced by both the interface and backend.
- The first Milestone 7 slice is implemented after exact charter approval. A
  versioned evidence-scope prompt and sequential LLM job generate validated,
  charter-derived mandatory evidence themes plus zero to six user-controlled
  retrieval or screening questions. The stage cannot remove a charter objective
  or make relevant negative evidence optional, and it does not generate database
  queries.
- Evidence-scope questions support advisory recommendations, independent or
  cumulative option semantics, suggested answers, note-only answers, optional
  notes, and explicit Not sure. Confirmed and edited answers are immutable hashed
  artifacts with an effective-version pointer; a zero-question result receives
  a deterministic application-created empty answer artifact. The project UI
  keeps the prompt hidden by default, displays mandatory themes separately from
  decisions, and exposes the job in the global queue.
- The next Milestone 7 slice generates a compact evidence-investigation strategy
  after scope answers are confirmed. It snapshots the exact approved charter,
  evidence themes, and effective answer version, then records prompt, model, call,
  and Markdown output provenance. Original and edited versions remain immutable;
  explicit approval applies only to the current effective version. Cancelled or
  failed jobs may be retried from the retained input snapshot. Source-specific
  query generation and retrieval are still future work.
- Explicit regeneration creates a separate queued/call/artifact attempt. Active
  replacement blocks editing and downstream consumption, failed or cancelled
  replacement restores the prior completed charter and its approval, and
  successful replacement becomes the new unapproved draft. Historical attempts
  remain inspectable in the project interface and global job list.
- The completed charter card keeps only completion status and the advanced prompt
  disclosure; it does not continue to display a generation action. The current
  output no longer repeats its used prompt below the editor, while historical
  attempts retain their exact prompt locally. Edit controls reserve additional
  vertical space before the approval card.
- ADR 0013 records iterative research cycles: evidence can inform later narrowing,
  continuation, stopping, or checkpoint forks without rewriting prior inputs or
  outputs. A project application such as animal production remains distinct from
  the later literature decision to retrieve or exclude animal studies.
- Existing projects with question-detailing jobs retain the exact legacy
  interface and output history; the application does not silently migrate or
  reinterpret those scientific records.

## Recently completed

- Added the reviewable evidence-investigation strategy job, Markdown editor,
  exact-version approval, and ADR 0017. The strategy organizes workstreams and
  source categories without claiming to have searched a source.
- Added the approved-charter evidence-search scope questionnaire and recorded the
  charter-theme/question boundary in ADR 0016. Evidence-strategy approval and
  source-specific query generation are separate stages.
- Extended the OpenAI text-generation model filter to include the GPT-6 family;
  compatible GPT-6 models returned by the user's account catalog can now be
  selected after refreshing the model list.
- Removed duplicate **Completed** badges from generated result and confirmed-answer
  boxes. Completion status now appears only in job/prompt cards and the global job
  queue, keeping result content focused on the scientific record. Completed job
  cards also share one alignment, with status consistently positioned before the
  prompt control.
- Renamed the first two user-facing stages to **Clarify the research goal** and
  **Clarify assumptions and boundaries**. Their helpers and actions now state
  explicitly that the first generates a goal questionnaire and the second asks
  only for any remaining user-controlled clarifications.
- Added concise charter prompt v4 and migration 0020. The prompt asks for each
  substantive point once, combines overlapping sections, avoids repeating the
  original question, and normally targets 350–600 words. Only unconsumed charter
  stages receive it; existing prompt snapshots and outputs remain unchanged.
- Replaced user-facing “cycle” terminology with “investigation” in the active
  workflow and documentation. Migration 0019 introduced direction v4, framing
  v6, framing-check v6, and investigation-worded charter v3 only for unconsumed
  stages, preserving historical prompt snapshots byte-for-byte.
- Made the framing check conditional. A framing result with one or more questions
  still receives the bounded LLM check, while a zero-question result skips that
  redundant call and section, proceeds directly to charter generation, and
  records `application_rule_no_questions` plus a deterministic assessment in the
  charter input provenance.
- Reworked the implemented early workflow around therapeutic peptide discovery
  with versioned direction v3, framing v5, framing-check v5, and charter v2
  prompts while preserving every consumed prompt and historical project.
- Allowed peptide-discovery framing to return zero questions when no genuine
  user-controlled decision remains. The application records an immutable empty
  answer artifact with application provenance without presenting a fake
  questionnaire.
- Established shared stage titles, helpers, prompt disclosure, job cards, and
  result sections across the direction, framing, framing-check, and charter UI.
- New advanced prompt edits retain their base generation in the version label
  (for example `custom:5`) so custom text does not lose its workflow-era
  provenance or fall back to legacy interface terminology.
- Specialized the product vision, workflow, roadmap, architecture, conceptual
  data model, README, and repository guidance around therapeutic peptide
  discovery while explicitly preserving broad evidence-led exploration.
- Recorded the design brief as the required evidence-to-candidate checkpoint and
  established that computational predictions remain distinct from experimental
  or curated source evidence.
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
- Added the first persistent project shell with exact scientific-question input,
  sequential project tags, sidebar tag renaming, and device-local view restore.
- Polished the project shell with overlay navigation, consistent reusable editable
  fields, contextual help, stable edit layouts, and expandable prompt content.
- Moved question-detailing defaults into versioned text resources and corrected
  the active prompt so it no longer implies the question appears below it.
- Replaced the fixed-section question-detailing default with version 4: an
  adaptable scientific-development prompt returning only Markdown. Application
  code will wrap the exact raw text in a deterministic versioned JSON artifact,
  avoiding model-generated JSON parse failures.
- Added question-detailing prompt version 5 after evaluating the first live
  Myostatin output. It is designed as better input for later database-query
  generation and migrates only unused version-4 prompts; prompts already consumed
  by a retained job remain byte-for-byte unchanged.
- Added secure OpenAI/Anthropic setup, live filtered model discovery, global
  provider defaults, credential forgetting, and reusable pre-job model context.
- Added the persistent sequential queue and first live OpenAI/Anthropic
  question-detailing execution path with call provenance, usage normalization,
  deterministic artifact creation, secret-redaction tests, and queue UI.
- Added rendered Markdown question-detailing results and original-versus-edited
  artifact versioning with an explicit effective selection.
- Replaced the default one-shot workflow for unused projects with the first
  intent-clarification slice: versioned prompt, validated structured generation,
  immutable choices and user selection, queue integration, and interactive UI.
- Recorded the accepted intent → scope clarification → research charter workflow
  and explicitly deferred reconnaissance search until after the formal search
  pipeline is understood.
- Implemented the first scope-question round with exact effective-intent input
  snapshots, strict provider-output validation, flexible per-question responses,
  immutable answer versioning, and the full project/queue interface.
- Added the explicit scope-readiness job, strict ready-versus-follow-up output,
  the single optional follow-up questionnaire, shared questionnaire UI, exact
  answer-version snapshots, and immutable follow-up answer corrections.
- Refined the default first-round scope prompt to version 2 while migration tests
  prove already-consumed version-1 project history is not changed.
- Prevented the readiness stage from asking an answered first-round question
  again, including when the prior answer was Not sure, without modifying the
  already-completed `PROJ007` record that revealed the issue.
- Serialized and cached per-process workspace migration initialization after
  Opera exposed a concurrent-request race; an eight-thread regression test proves
  all callers receive the workspace while Alembic runs only once.

## Work in progress

The documentation and implemented early-workflow prompts now reflect therapeutic
peptide discovery. Direction, framing, bounded framing-check/follow-up, and
first-investigation charter generation require evaluation across representative project
starting points before scientific-source query generation is designed and built.

## Immediate next tasks

1. Evaluate the peptide-specific prompts on a broad therapeutic question, a
   known target without a candidate, and an existing peptide optimization
   project.
2. Refine only newly versioned defaults when evaluation exposes a reproducible
   failure; never rewrite consumed prompts or historical artifacts.
3. Design the scientific-source investigation strategy and query-generation
   stage that consumes the exact approved peptide-discovery charter.
4. Select the first publication source and separately inventory candidate
   protein, structure, interaction, bioactivity, peptide, and assay sources.
5. Add immutable model-pricing snapshots and call/step/project cost aggregation.

## Known issues and blockers

- Native release packaging and graphical interaction still require later
  platform-specific testing beyond bootstrap CI.
- GitHub reports that the `windows-11-arm` runner label will migrate to a Visual
  Studio 2026 image on 2026-09-21. The project does not currently depend on Visual
  Studio, and normal CI pushes will detect any unexpected image regression.

## Open design questions and risks

- General artifact hash scope, filesystem layout, and effective-version selection
  scope beyond question detailing. The current question-detailing implementation
  hashes canonical UTF-8 JSON with SHA-256 and selects an effective version per
  job. The broader integrity policy would
  record a versioned byte hash for every immutable artifact, show a warning on a
  mismatch without rewriting history, and require acknowledgement before known-
  mismatched input is used in new downstream work.
- Project-fork ownership/deletion semantics for shared runs and artifacts.
- LLM retry-attempt representation and the source/update process for trustworthy
  pricing snapshots.
- Publication identity precedence and conflict handling during deduplication.
- First-source confirmation (Europe PMC is proposed), structured-source
  selection/licensing, cross-source entity resolution, and external API etiquette.
- Peptide-specific screening, full-text resolution, evidence schema/strength,
  contradiction reconciliation, and synthesis structure.
- Peptide chemical representation, design-brief schema, candidate identity and
  derivation, candidate-generation methods, and supported modifications.
- Selection, validation, applicability limits, compute/runtime distribution, and
  transparent multi-property comparison for in-silico tools.
- Localhost security details such as session/CSRF protection before any mutating
  browser API is exposed.
- Bootstrap proxy/offline behavior, disk-space reporting, musl Linux support, and
  the eventual native package/signing format.
