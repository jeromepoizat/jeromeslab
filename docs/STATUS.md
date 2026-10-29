# Current status

Last updated: 2026-10-15

## Current milestone

**Milestone 1 — Local application shell is in progress.** Milestone 0 remains
complete: self-bootstrapping installation and project checks pass on GitHub-hosted
Windows x64/ARM64, Linux x64/ARM64, and macOS ARM64/Intel runners.

## Implementation state

- ADR 0033 resolves primary XML failures covered by verified saved fallback
  text. New fallback attempts link the primary resource/failure they cover and
  atomically mark the mutable cursor recovered; immutable failed HTTP attempts
  stay unchanged. Recovered cursors are excluded from retries/failure counts and
  never counted as another saved full text. Inspectors name the recovery provider
  and covering attempt. Metadata explicitly reporting `hasSuppl=N` resolves a
  missing-primary supplement as not applicable; saved XML declarations take
  precedence. With fallback-only text and no explicit absence, supplementary
  discovery is unsupported, not indefinitely blocked or globally unavailable.
  User-authorized PROJ012 offline reconciliation removed its last retryable
  failure and resolved the blocked supplement without requests. All 375 saved
  full texts, prior jobs/attempts/records/selections and successful cursors were
  verified unchanged. Three newer bioRxiv routes remain pending for explicit
  resume (the previous worker had still used its old DOI-prefix rule); the
  separate size-limited archive remains unresolved. Restart before resuming.
  A safety snapshot is in ignored
  `.runtime/proj012-before-coverage-resolution-20261015-01.sqlite3`.
  Verified with 28 acquisition tests, Ruff, strict mypy, frontend lint and build;
  no migration, new dependency or LLM/source requests were required for repair.
- ADR 0032 separates retryable transient failures, explicit route-unavailable
  material, unsupported routes, verification/review issues and size exclusions.
  Only pending/failed/blocked resources enter ordinary retries. Queue completion
  is labelled separately from unresolved acquisition; the UI explains each
  resource count, without treating missing access as paper exclusion. BioC now
  accepts numeric/canonical PMCID forms and explicit matching PMC metadata when
  the document ID is unknown, while rejecting contradictions and unverifiable
  bodies. Versioned offline recovery verifies stored bytes/hashes, atomically
  claims the single operation, and appends corrected attempts with parent links;
  successful assets and completed history are never rewritten. Active work and
  downstream dependents block recovery. A publisher-based preprint DOI check
  replaces the obsolete `10.1101`-only filter and supports current bioRxiv IDs.
  User-authorized PROJ012 recovery saved 36 existing XML responses as usable
  full text (334 -> 370 distinct records), classified 118 explicit PMC absences
  as unavailable, and separated 779 records with no supported route. Three newer
  bioRxiv identifiers are now pending for explicit resume; 14 transient failures,
  one dependency-blocked supplement and one size-limited archive remain visible.
  No network or LLM requests were made by either recovery job. All earlier
  attempts/jobs/records/selections and successful resource cursors were verified
  unchanged; a safety snapshot is in ignored
  `.runtime/proj012-before-outcome-recovery-20261015-01.sqlite3`. Restart the app
  before resuming so future requests use the updated adapters and UI.
  The full Python suite passed 153 tests before the final preprint-prefix fix;
  focused acquisition tests, Ruff, strict mypy, ten frontend tests, lint and
  production build were also run. No new dependency or migration is required.
- New acquisition start/resume manifests prioritize each record's metadata,
  primary full text and fallback across the whole retained pool, then linked-data
  inventories, with supplements deferred to the end. Slow supplement requests
  cannot block unattempted text. Limits/retries and sequential execution remain
  unchanged; old active/completed manifests are not rewritten. Progress now names
  the current collection phase. PMC BioC's explicit leading "No result can be
  found" message is correctly unavailable, not failed; generic HTML, timeouts,
  identity mismatches and server errors remain failures. On explicit resume,
  digest-verified saved absence responses append new unavailable attempts with
  parent-attempt/hash/rule-version links without refetching or erasing failures.
  PROJ012 needs pause/restart/resume to load this behavior; no live job or history
  was changed during implementation. Verified with 20 acquisition/fallback tests,
  Ruff, strict mypy, frontend lint and production build. No migration, new
  dependency, parallel requests or LLM calls are introduced.
- Official full-text fallbacks now extend acquisition (ADR 0031): PMC BioC by
  explicit PMCID and bioRxiv/medRxiv DOI discovery followed by version-matched
  JATS XML. Identifier/body/version checks, HTTPS host/redirect restrictions,
  bounded streamed bytes/deadlines/retries and pacing prevent arbitrary scraping
  or silent document substitution. BioC is labelled as transformed repository
  text. Raw text, preprint discovery files/hashes, licensing and route diagnostics
  are preserved; supplements remain Europe PMC-specific. No PDFs, Unpaywall,
  arbitrary publisher harvesting, LLM calls or paywall bypass are added.
  New runs include fallback resources; idle old runs can explicitly add missing
  tasks and resume, guarded against downstream dependents. Original policy and
  attempts remain fixed; each new job separately freezes the resolver policy.
  Coverage counts distinct records with primary or fallback text. User-authorized
  PROJ012 preparation appended 968 pending fallback tasks, preserving its 315
  primary full texts and verified unchanged records/attempts/jobs/run/selection
  history. No job was queued or started. A safety snapshot remains in ignored
  `.runtime/proj012-before-fallback-20261014-01.sqlite3`. Restart then use
  **Resume collection**. Other old runs offer **Try missing full text elsewhere**.
  Verified with 147 Python tests, Ruff, strict mypy, ten frontend tests, lint and
  production build. Live smoke tests recovered one PMC BioC and one bioRxiv JATS
  document; an initial PMC 429 remained retryable, not misclassified as no access.
  medRxiv uses the documented shared API but has not had a live download smoke
  test. No new dependency or database migration is required.
- Source-material retry/resume action is centered using the shared action-row
  styling. Frontend lint and production build pass; no acquisition/data change.
- Source acquisition now distinguishes **Unavailable via Europe PMC**, retryable
  failures and dependency-blocked resources (ADR 0030). Successful metadata with
  `inEPMC=N` or `isOpenAccess=N` prevents known-unavailable XML requests, recording
  the metadata attempt, source flags and access-rule version. Unknown availability
  and HTTP 500 alone never prove no access. Failed XML/metadata blocks dependent
  resources rather than inflating the failed-download count; resume includes those
  dependencies, while unavailable material is excluded from later retry manifests.
  Existing saved files/history stay unchanged. On the next explicit retry, older
  failed records can receive new local availability outcomes without repeating
  known-unavailable requests. No live project data was changed automatically.
  Read-only PROJ012 inspection found 33 retained preprints: 19 bioRxiv, nine
  Research Square, five Preprints.org. All lacked Europe PMC-hosted XML in the
  saved metadata; this does not mean their publisher text is private. The app
  searches their Europe PMC metadata, not bioRxiv/publisher full text directly.
  Verified with 13 acquisition tests, including an existing-run retry that appends
  local availability outcomes without downloads or rewriting old attempts; Ruff,
  strict mypy, frontend lint and build pass.
  Restart is required for these rules; no migration or LLM calls are needed.
- Source-material access summary now has a 1.25rem top gap and a live remaining-
  resource counter during retries. Existing three-second polling refreshes current
  unavailable/failed/size-limited counts; remaining retry checks visibly decrease
  even when attempts fail again. Earlier failures only disappear from the current
  failure total when resolved, not when a retry is queued. Histories are preserved.
  Read-only PROJ012 diagnosis found 475 failed resource cursors: 191 full-text
  HTTP 500 responses, 81 generic network/timeout failures (63 supplements, 12 XML,
  six data-link inventories), and 203 supplements blocked by failed XML rather
  than an attempted supplement download. A subsequent saved-metadata snapshot
  associated 190 of those 191 HTTP 500 responses with non-open-access records;
  one open-access record also returned 500. Two public endpoints reproduced the
  generic service error. This suggests access-aware acquisition and separate
  dependency-blocked states as follow-up work, not a silent reclassification or
  modification of the existing run. Saved network diagnostics cannot distinguish
  the underlying timeout/connection causes; one public supplement probe reproduced
  a read timeout before response headers arrived. Verified with ten acquisition tests,
  Ruff, strict mypy, frontend lint and production build. No live project writes,
  acquisition-policy changes or LLM calls were made.
- Collection retry progress now subtracts distinct records with unattempted tasks
  in the latest acquisition job, even when their earlier attempt failed. A record
  returns to the processed count only after every retry task for it has an outcome;
  multiple failed resources on one record are counted once. Active retries are
  explicitly labelled, and saved resources, failure counts and immutable attempt
  history are unchanged. This also works for paused or already-running retries.
  Verified with ten acquisition regression tests, Ruff, strict mypy, frontend lint
  and production build; tests use isolated fake-provider workspaces, not live data.
- **Collect source material** now follows validated relevance selection (ADR 0029,
  migration 0030). It freezes that exact retained pool and collects Europe PMC
  metadata, available full-text XML, bounded declared supplementary ZIPs and
  data-link inventories without an LLM. Raw files, hashes, URLs, HTTP outcomes,
  dates, licenses, original retrieval/page links and failed/retried attempts stay
  preserved. Missing text never changes inclusion. ZIPs are not executed or
  extracted; linked databases are not recursively fetched. PDFs/user uploads and
  evidence extraction remain future work.
  The shared-style job card shows progress and elapsed time, aggregate access
  coverage, failures/limits and 25-record inspect pages. Pause finishes the
  current request; resume/retry skips successfully saved resources. Queue
  cancellation, worker errors and restart leave runs resumable, and future
  downstream jobs lock retry/resume. Exact per-job task manifests live in indexed
  tables rather than large global-queue JSON payloads. All network calls happen
  outside managed database transactions. HTTP requests have bounded retries,
  sizes, timeout/backoff and official-host redirects; XML/entities and ZIP paths
  are validated before marking files saved.
  Verified with 137 Python tests, a final nine-test acquisition rerun, Ruff,
  strict mypy, ten frontend tests, lint and production build. Browser QA used an
  isolated temporary fake-data workspace; public Europe PMC smoke checks verified
  metadata, XML and link inventory. The public supplementary endpoint probe timed
  out after bounded retries; ZIP handling is fixture-tested, not live-download
  verified. The temporary QA workspace was removed; no real project data or LLM
  calls were used. Restart is required to load the backend and apply migration 0030.
- Scoring and relevance-filter validation actions now use neutral grey **!** icons
  matching the shared **?** helper styling, without warm warning colors,
  on hover or keyboard focus. Scoring warns that its scored pool cannot grow or
  resume; selection warns that excluded records cannot enter later steps of the
  same project, while original records/scores remain preserved. Both selection
  validation and its final confirmation reuse the shared warning-tooltip variant.
  Verified with ten frontend tests, frontend lint and production build.
- Scoring-section titles now explicitly distinguish relevance from future score
  types: **Prepare relevance scoring**, **Score retrieved records for relevance**,
  and **Select records by relevance score**. The section navigator automatically
  uses these titles. Only presentation wording changed, not prompts or history.
- Relevance-score selection now uses a six-point threshold rail rather than the
  browser's native range styling. A numbered right-pointing arrow marks the
  minimum score and aligns with its row; the green rail/points show included
  levels. Clicking points/rows, dragging, touch and keyboard controls remain
  available until confirmation/validation locks the selection. Original scores,
  filtering semantics and saved provenance are unchanged. Verified with ten
  frontend tests, frontend lint and production build.
- Projects now have a fixed, collapsible project-tag navigator on the right.
  It discovers visible shared section headings in document order, highlights the
  viewport's current section, and smoothly scrolls to a chosen section's top.
  Dynamic stages and project switches update the list automatically; rendered
  Markdown subheadings and hidden sections are not separate navigation entries.
  The central project stays centered without shifting. Smaller screens default
  to a compact toggle; keyboard navigation, aria-current and reduced-motion
  preferences are supported. This is local UI only, not a workflow/data change.
  Section travel and highlight tracking use the fixed, scrollable
  `.project-layout` pane, not the browser window. Saved/restored project scroll
  positions use that same pane; project-tag renames update the navigator header.
  Titles stay on one line and clip/ellipsize during expansion instead of wrapping.
  The final expanded width is measured from the longest title so its full text is
  visible; viewport width remains a safety cap, with full-title hover text.
  Verified with seven frontend navigation tests, frontend lint and production
  build. The earlier scoring/database changes were committed as `cf2a1a6`;
  the navigator and relevance-selection UI have now been approved for commit.
- Fixed scoring-status lock/loading failure paths (ADR 0028): queue, scoring and
  retrieval contexts are coordinated locally and always close their connections;
  idle claims no longer reserve a writer. Charter dependency scans are skipped
  for scoring-job display. Migration 0029 adds bounded per-batch reads and a
  cached distinct retrieval count, retaining original plan/manifests and scores.
  Progress reads omit the full plan and use saved batch titles for six previews.
  Failed/timed-out status loads show an error, last known data and Retry status;
  busy databases return HTTP 503 rather than appearing to load forever.
  Read-only live diagnosis found 3,985 saved scores. On a temporary migrated
  copy, status took 0.063 seconds; optimizing irrelevant per-job charter/edit
  checks reduced the live read-only 840-job SELECT from about 2.7 seconds to
  0.093 seconds. The temporary copy was removed; no live schema migration,
  score reset, or provider calls were performed. Restart is required to load
  the fix and apply migration 0029 to the remembered workspace.
  Verified with the 129-test full suite and a final 24-test queue/charter/scoring/
  contention regression run, including retryable busy responses; Ruff, strict
  mypy, frontend lint and production build pass. No paid calls were used.
- ADR 0027 and migration 0028 add **Parallel batches** (1–8, default 1) for one
  relevance-scoring run only. The bounded worker pool and transactional claims
  prevent other operations or runs from overlapping. Out-of-order completions
  update actual completed identities, remaining estimates and validation; pause
  cancels queued attempts and drains all in-flight calls. Existing runs retain
  their records/history and migrate to concurrency 1; paused runs can change
  concurrency on resume and completed runs before extension.
  Resume no longer waits indefinitely for follow-up/global queue refreshes:
  mutations have a 20-second browser timeout, progress requests are separately
  bounded, repeated matching resumes are idempotent, and preparation/storage
  errors cannot kill the dispatcher. Cancelling pending work no longer marks
  unrelated in-flight runs failed. Restart recovery pauses interrupted or
  stranded failed runs rather than replaying uncertain requests.
  Verified with 125 Python tests, plus a 14-test worker/concurrency regression
  rerun after the final immutable-failure guard; Ruff, strict mypy, frontend lint
  and production build pass. Concurrency tests use controlled fake providers.
  No live LLM calls or user-project data mutations were performed.
- Score hover/focus previews now show up to six saved record titles per outcome.
  Additional-record input values above the remaining count are clamped to that
  count (also respecting the existing 100,000-record per-extension cap).
  Verified with all nine relevance-scoring tests and the frontend production build.
- The next local section, **Select records for further work**, now consumes the
  validated scored pool. A vertical 0–5 minimum-score slider shows counts by
  score and live included/excluded totals; not-assessable has a separate checkbox.
  Validate selection opens a confirmation, then freezes the exact included source
  IDs, criteria and parent validation digest. Original scores/excluded records
  remain unchanged, and paused validation excludes unfinished records from these
  totals. Migration 0027 and ADR 0026 record the checkpoint. No LLM/source call is
  required; later quality/extraction steps are not implemented.
  Verified with 119 Python tests, Ruff, strict mypy for source/tests, frontend
  lint and production build. Fake-provider tests cover thresholds, the separate
  not-assessable choice, paused subsets, immutable identities/hashes, API guards,
  invalid/empty selections and migrations. No live API calls or user-project
  data changes were performed.
- ADR 0025 adds one silent automatic retry per failed relevance-scoring batch;
  a second consecutive failure pauses the run. User-requested pauses suppress
  retries; explicit resume resets the allowance. Every failed/retried job, call,
  raw output, usage and cost remains saved. Shutdown-interrupted requests are
  not automatically replayed. Scoring validation is available for nonempty
  completed or fully paused results and locks only successfully scored records,
  preventing resume or additions. Its centered **Validate scoring** button has
  a hover/focus helper explaining the lock. This supersedes the older completed-
  only confirmation and no-automatic-scoring-retry descriptions below.
  Verified with 111 Python tests, Ruff, strict mypy, frontend lint and production
  build. Tests use fake providers; no live API calls or project-data resets were
  performed for this change.
- ADR 0015 narrows the product from general scientific research to
  evidence-guided therapeutic peptide discovery. The accepted path now runs from
  the original question through scientific-source evidence, an approved peptide
  design brief, candidate derivation, and modular in-silico evaluation. Existing
  generic infrastructure remains applicable. Peptide-specific defaults now cover
  the implemented direction, framing, framing-check, and charter stages; later
  evidence extraction and design stages are not yet implemented; first-source
  Europe PMC retrieval and an aggregate results overview now exist without
  screening, canonical publication deduplication, or record-level review.
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
  digest. Older calls retain `unavailable` cost; new exact-model OpenAI calls
  can attach a dated rate snapshot and a clearly labeled estimate.
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
  query drafting is implemented separately from the later source worker action.
- Europe PMC query drafting consumes the exact approved strategy and its upstream
  charter, themes, and scope answers. An optional user note is included in the
  immutable job input. Strict structured output proposes titled, described,
  purpose-linked query expressions that have not been executed. Cards allow
  per-query expansion, editing, and inclusion decisions. Every saved review
  becomes a new immutable hashed version; approval requires included queries to
  cover every mandatory theme. Drafting does not search. Approval now atomically
  locks the exact version and queues Europe PMC retrieval (ADR 0019).
- The first Europe PMC retrieval adapter runs included queries through the same
  single-worker queue, pages through `core` metadata, and saves raw JSON pages
  with SHA-256/size plus every query-to-record discovery link. Per-query hit and
  saved-record counts, failures, and an explicit 5,000-record partial limit appear
  in the project UI. Failed/interrupted attempts retain saved pages; retries
  start new jobs from the same approved query snapshot. A read-only dashboard
  now reports query hits versus saved rows, distinct Europe PMC source identities,
  cross-query overlap, abstract availability, and collection mix without loading
  article text into the browser. Distinct source identities are deliberately not
  called unique publications. Screening, canonical publication deduplication,
  and record-level review remain future work.
- The retrieval overview is a separate section after the reviewed query list.
  Query-volume bars explain their hit/saved scales on hover or keyboard focus;
  Europe PMC source codes expose their collection names there too. Duplicate
  counts use plain language that distinguishes repeat appearances from papers.
- Query bars now also distinguish saved source IDs exclusive to each query,
  calculated across all saved runs of the current retrieval. Their per-query
  count appears beside the bar and in its hover/focus detail; the legend uses
  a third color. Historical retrieval overviews gain the count automatically.
- A completed retrieval now receives a read-only provisional same-article check
  (ADR 0020), also for historical jobs such as `PROJ012`. It links different
  source IDs by DOI, PMID, PMCID, or exact normalized title and flags groups
  with differing identifiers, author, year, or journal metadata. Patent records
  are not grouped on title alone. It makes no
  new API calls, does not change immutable rows, and is not a verified publication
  identity or screening decision.
- After retrieval, relevance preparation previews a seeded, query ×
  collection-balanced sample of distinct `(source, source_record_id)` records.
  The researcher chooses a 1–30-record prompt-design sample and seed; the
  first-run scoring count is deferred to the later scoring stage. The main queued job
  generates a compact, reviewable relevance-scoring prompt from the exact
  approved strategy/charter and sampled metadata. Original and edited prompts
  are immutable artifact versions. Existing optional sample-calibration jobs
  remain readable, but preparation no longer offers a new calibration call:
  prompt generation does not score its sample. The former per-1,000-report
  estimate is no longer shown in preparation (ADRs 0021–0022).
- The relevance-preparation controls now expose field-specific help and prepare
  the selection/estimate automatically as values change. The job card retains
  one visible prompt-generation action; the extra preview button and redundant
  explanatory text are removed.
- The preparation sample can be inspected as a title list with hover/focus
  metadata (date, author, journal, abstract presence, collection, and query
  discoveries). The sample-ID manifest/hash stay in saved provenance but are no
  longer displayed. The seed is shown only in its input, while the selection
  algorithm version is available in its helper. Provider/model appears only in
  the standard job card. A first-run count and its estimate no longer appear in
  this stage. Legacy jobs retain their historical cap snapshots.
- Generated scoring-prompt output now uses the same provider/model-left and
  tokens/duration/cost-right provenance footer as other LLM jobs.
- A separate scoring section now chooses the number of distinct source records
  to score and a reproducible seed. Its preview shows the exact selected count,
  and batch sizes without a pre-run usage/cost estimate. Starting
  freezes the effective prompt artifact, provider/model, selected metadata,
  selection manifest digest, and bounded batch plan (at most ten records and a
  conservative estimated input budget per request).
- The scoring count and seed controls share the preparation form's horizontal
  layout. The scoring job card now uses the common model-change control and
  shows only the selected provider/model, not per-token rates. Both provider/model
  pickers still show dated exact-model Standard rates when available; unknown
  rates are labeled unavailable, not guessed. Remaining usage/cost estimates
  appear in the active run only after its first completed batch, using observed
  usage rather than the initial planning projection.
- Each scoring batch is a separate persistent single-worker LLM job. Validated
  exact 0–5 or not-assessable decisions, raw responses, call provenance, and
  hashed output artifacts persist atomically with batch completion. The project
  UI polls scored/remaining records and batches, score counts, observed
  tokens/cost, and a revised remaining estimate. Source-collection breakdowns
  remain in saved data, not the score display. A pause
  stops after any in-flight call; explicit resume never silently retries an
  ambiguous or failed request. The same paused or failed run may resume its
  unscored batches, but a second independent run is disallowed in the same
  project. The initial count and seed stay visible and locked; the current count
  grows only through explicit, provenance-bearing extensions. The start card
  disappears, and progress uses one animated current-batch label plus vertical
  score rows with title samples on hover/focus.
  Forking remains future work (ADRs 0023–0024).
- New scoring-batch attempts use version-2 numbered record slots. For OpenAI,
  the request includes a strict Structured Outputs schema with every slot
  required; the application maps each decision back to its frozen source ID
  and still rejects any missing, extra, or invalid score. This addresses
  observed complete-but-omitted responses in `PROJ012`. Explicit resume of an
  existing failed run creates a new version-2 attempt without changing its
  selected records, prompt, prior calls, or completed scores. The running app
  must be restarted to load this code before resuming; no paid live call has
  been used to verify provider behavior.
- Completed scoring runs can append a user-chosen number of unscored distinct
  source records using the same saved seed, retrieval, prompt, provider, and
  model. An immutable extension manifest records each addition, while the
  existing result and prior scores remain intact. The user may confirm the
  completed scored list; an immutable hashed confirmation freezes its exact
  decisions and blocks further scoring. The score display omits per-collection
  counts. Scoring validation now unlocks the local relevance-score selection
  described above, but no later quality/extraction job (ADRs 0024–0026).
- Added the official `gpt-6-sol` Standard API rate to the exact-model estimate
  table; preparation cost information is shown only after prompt generation.
- Exact-model OpenAI Standard-rate snapshots checked on 2026-10-05 (with
  `gpt-6-sol` checked on 2026-10-06) now support
  rough preview estimates and estimated costs for new calls with matching
  reported model and usable token usage. The rate snapshot is stored with the
  call. Unknown or unmatched models, ambiguous long-context rates, and old calls
  remain explicitly cost unavailable; this does not claim provider billing.
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

- Clarified prompt design versus scoring in the relevance UI: removed redundant
  hash/seed/model text and the new sample-calibration action while preserving
  historical calibration results. ADR 0023 records the future bounded scoring,
  between-call interruption, progress, and downstream-freeze rules.
- Moved relevance scoring-run sizing to the future scoring stage, made the
  prompt-design sample the sole preparation selection and cost-estimate basis,
  added hoverable sample coverage, and filled the verified `gpt-6-sol` rate.
- Added query-exclusive source-ID counts to the retrieval overview without
  changing saved records or interpreting them as verified unique papers.
- Simplified relevance-preparation copy and controls while retaining the
  read-only sample/cost calculation before the prompt-generation job is queued.
- Added distinct-source relevance preparation, a generated/editable scoring
  prompt informed by the seeded sample, optional compact calibration, and
  model-aware token/cost estimates without starting bulk scoring (ADRs 0021–0022).
- Combined query approval and retrieval queueing into one action, added the
  Europe PMC source adapter and durable raw-page/source-record storage, and
  recorded the amended decision in ADR 0019.
- Added Europe PMC query drafting, reviewable query cards, exact-version approval,
  and ADR 0018. User-visible scope/strategy headings now use scientific-source
  terminology; historical prompts and artifacts are unchanged.
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
peptide discovery. Direction, framing, bounded framing-check/follow-up, charter,
query drafting, and first-source retrieval still need evaluation across
representative project starting points. The aggregate retrieval overview and
sample-informed prompt generation and historical optional relevance calibration exist;
bounded record-level relevance scoring now exists. Publication-level identity
resolution, reviewed screening, quality assessment, and evidence extraction are
deferred.

## Immediate next tasks

1. Evaluate the peptide-specific prompts on a broad therapeutic question, a
   known target without a candidate, and an existing peptide optimization
   project.
2. Refine only newly versioned defaults when evaluation exposes a reproducible
   failure; never rewrite consumed prompts or historical artifacts.
3. Evaluate generated scoring prompts and bounded batch decisions on representative
   approved investigations; evaluate the implemented minimum-score selection,
   then design its downstream quality/extraction consumer and project forking.
4. Separately inventory candidate
   protein, structure, interaction, bioactivity, peptide, and assay sources.
5. Extend pricing coverage and add call/step/project cost aggregation without
   rewriting historical calls that lack a contemporaneous rate snapshot.

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
