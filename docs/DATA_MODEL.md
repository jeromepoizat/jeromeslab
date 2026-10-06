# Therapeutic peptide discovery data model proposal

This is a conceptual model for the agreed product behavior, not an implemented
schema. SQLAlchemy models and Alembic migrations will make types, constraints,
indexes, deletion policies, and naming concrete. Identifiers should be stable and
timestamps should be timezone-aware UTC.

## Lineage and workflow

### Project

A user-visible research project. Holds display metadata, creation and last-active
timestamps, and a reference to its root scientific-question artifact. It does not
own duplicate copies of shared immutable artifacts.

### ProjectFork

Records that a child project started from a parent project's checkpoint. Expected
fields include parent project, child project, checkpoint `StepRun`, creator/time,
and optional rationale. Shared history is expressed through references to the
same immutable runs/artifacts.

### WorkflowStep

A logical step instance in a project lineage, including type, order/dependency,
display status, and project/checkpoint context. Step definitions and executions
are separate so repeated attempts do not erase prior runs.

### StepRun

One execution attempt for a workflow step. Records status, start/completion time,
duration, code/workflow version, exact input artifact-version references, output
references, associated job/calls, retry/rerun lineage, and error summary. A
completed run with downstream consumers is immutable.

Allowed status transitions and terminal-state immutability must be enforced in
the service/domain layer and tested, not trusted to the UI.

### UserNote

Editable plain text associated with a project, step, run, or page position.
Notes have update timestamps and never invalidate workflow history. If a note is
intentionally promoted into computational input, that operation creates an
immutable artifact/version rather than changing the note's semantics.

## Artifacts

### Artifact

Stable logical identity for a workflow value or stored payload. Expected metadata
includes kind, media/schema type, storage class, creation time, and integrity
identity. An artifact can have one or more versions.

### ArtifactVersion

An immutable representation of artifact content. Expected fields include artifact
ID, version/order, content reference or safe inline value, content hash and size,
creator type (`user`, `llm`, `source`, `system`), creation time, and derivation
links.

The generated/ingested version is preserved as the original. A human edit creates
a new version and an explicit effective-version selection for the relevant
workflow context. Downstream `StepRun` inputs reference the exact version, not a
mutable "latest" lookup. Selecting an effective version is allowed only before a
dependent run exists; otherwise the user forks.

Question-detailing now implements this pattern with immutable numbered
`artifact_versions`, a mutable `artifact_effective_versions` selection record,
and SHA-256 over canonical UTF-8 JSON bytes. Generalizing the selection scope and
hash policy across later artifact kinds remains unresolved.

Research-direction clarification stores the validated provider questionnaire as
an immutable `intent_clarification_questions` artifact and the confirmed user
decision as a separate immutable `intent_clarification_selection` artifact. The
selection contains the exact questionnaire artifact identifier, one
current-objective ID, zero or more later or parallel goal IDs, and the user's
note. The persisted field names remain `primary_intent_id` and
`secondary_intent_ids` for compatibility. It is not represented as an edit of
the provider output. A correction creates another numbered selection artifact
and moves the effective-version pointer while no downstream job exists; the
generated questions and all prior confirmations remain unchanged.

The first project-framing round follows the same separation. A
`scope_clarification_questions` artifact stores only the validated provider
questionnaire. A `scope_clarification_answers` artifact references that exact
questionnaire and contains one response per question: selected option IDs, a
manual note, or an explicit uncertainty that excludes suggested choices but may
carry an explanatory note. Answer corrections create
numbered immutable versions and advance the job's effective-version pointer only
until downstream work exists. The scope job also stores canonical JSON input that
identifies and embeds the exact effective intent version consumed by the call.

When framing contains one or more questions, the readiness job stores a canonical
input snapshot that embeds the exact effective first-round answers and their
source questionnaire. Its immutable
`scope_readiness_review` artifact contains the operational readiness decision,
assessment, recorded uncertainties, and zero or one bounded follow-up
questionnaire. When needed, each confirmation or correction of that questionnaire
creates an immutable numbered `scope_follow_up_answers` artifact linked to the
readiness-review artifact. The effective follow-up version can move only before a
future charter job consumes it; no third automatic clarification round exists.
When framing contains no questions, the empty application-created answer artifact
is retained and charter input records a deterministic no-check source and
assessment. No readiness job, provider call, or synthetic readiness artifact is
created for that path.
Framing-question schema version 2 marks each option set as `independent` or
`cumulative`. Cumulative sets are valid only as single-choice boundaries;
multiple-choice sets contain independent options. Older schema-version-1
artifacts remain readable without adding or inferring this metadata.

Readiness prompt version 6 defines every first-round response—including Not sure
and a note-only response—as answered, accepts broad exploration, and keeps later
literature-search eligibility out of project framing. A deterministic cross-input
validator rejects repeated questions and structurally invalid cumulative options
before a readiness review becomes a trusted artifact. The rejected provider
response remains available in the associated call record. The prompt requires
selected option IDs to be interpreted literally rather than silently adding an
unselected option.

### Research charter and approval (implemented for the first investigation)

Projects store the next `research_charter_prompt` and its version. Charter jobs
retain their own prompt and canonical workflow-input snapshots, including the
preserved direction/framing context, the framing-check source and readiness
artifact when one exists, and the exact final answer version when applicable.
The original Markdown and each manual revision are
immutable `research_charter` artifacts using the existing effective-version
selection and content hash mechanism.

Charter approvals are append-only records of an exact artifact version and UTC
time. Approval is effective only for the current version of the current completed
charter and never transfers to an edit or regenerated output. Earlier approvals
remain historical records. A pending replacement prevents downstream consumption;
failure or cancellation restores access to the most recent completed charter.

The repository exposes an approved-input snapshot containing the charter artifact,
version, job, approval, Markdown, and investigation number. The persisted
`cycle_number` key is retained for backward compatibility. Later jobs must retain that
exact reference when enqueueing. The backend locks consumed charter versions;
attempts to approve or edit stale versions are rejected. Multiple-investigation execution
remains a later feature.

### Evidence-search scope questionnaire (implemented)

Projects store a versioned `evidence_scope_prompt`. The first questionnaire job
consumes an exact approved-charter snapshot containing the charter job, artifact,
effective version, approval, approval time, and Markdown. Its immutable provider
artifact contains charter-derived evidence themes and zero to six evidence-scope
questions. Each theme records a stable ID, label, purpose, applicable evidence
domains, and whether negative evidence is meaningful for that theme.

Questions use the established independent/cumulative option semantics and may
carry advisory recommended option IDs with a reason. Recommendations are not
stored as user decisions. Confirmed responses create a separate
`evidence_scope_answers` artifact that supports suggested options, note-only
answers, optional notes, and explicit uncertainty. Manual corrections append a
new version and move the effective pointer until a downstream strategy job is
queued. When no question is needed, the application creates an empty answer
artifact with application provenance.

### Evidence-investigation strategy (implemented)

Projects store a versioned `evidence_strategy_prompt`. Enqueueing a strategy job
atomically snapshots the current approved charter, evidence-scope question
artifact, and effective answer artifact with their IDs, versions, and content.
The provider's Markdown is wrapped in a hashed `evidence_strategy_output`
artifact and selected as the effective version. A manual edit appends another
immutable artifact and moves the effective pointer; the original remains
available. `evidence_strategy_approvals` records an append-only approval of one
exact artifact version. Editing makes the current version unapproved without
deleting prior approvals. Later query work must consume the exact approval and
the structured upstream themes and answers retained in the job snapshot.

### Europe PMC query drafts and retrieval (implemented)

Projects store a versioned `source_queries_prompt`. A `source_queries` job
snapshots the exact approved strategy (including its charter, themes, and scope
answers), source identifier, and optional user note. Provider output is validated
as a structured `source_queries_output` artifact containing 1–16 proposed query
cards with stable IDs, titles, descriptions, mandatory-theme links, literal query
text, and default inclusion. User edits and inclusion choices append immutable
hashed versions while preserving the original provider output. The effective
version is explicitly approved in `source_queries_approvals` only if included
queries cover every mandatory theme. Approval atomically creates a pending
`source_retrieval` job with the exact query artifact and approval IDs. Query
drafting itself creates no `SearchRun` or external request.

### Proposed integrity-verification behavior

Each immutable `ArtifactVersion` (including a workflow step or job output) should
record the byte length plus a versioned content hash when it is committed. A
future integrity verifier can recompute that hash from the stored bytes and
report `verified`, `mismatch`, or `not yet verified` without changing the
artifact, run, or project history.

A mismatch is evidence that the stored bytes no longer match the recorded
output; it is not by itself evidence that the scientific conclusion is true or
false. The UI should show a visible warning on the affected artifact and its
related step, retain the original provenance, and offer details and a
re-verification action. It must not silently rewrite the recorded hash, delete
the data, or retroactively change completed workflow status. Before a future
downstream computation consumes known-mismatched input, the interface should at
least require an explicit acknowledgement; this preserves user control without
presenting the result as integrity-verified.

The exact algorithm, hash scope, verification schedule, and recovery behavior
remain to be decided before the artifact engine is implemented. The initial
candidate is a named SHA-256 hash over the exact bytes stored, rather than an
ambiguous reconstruction of structured content.

## Execution

### Job

A persistent unit of queued work linked to its project and usually to a workflow
step/run. The implemented records contain type, status
(`pending`, `awaiting_response`, `completed`, `failed`, or `cancelled`),
enqueue/start/completion timestamps, immutable input snapshots, provider/model,
prompt identity/version, and a sanitized error summary. General progress,
attempt, step-run, and lease fields remain future schema work.

Only one process and one worker run in V1. That worker claims the oldest pending
job with a short `BEGIN IMMEDIATE` transaction. Cancellation is allowed only
while a job is pending. The atomic transition to `awaiting_response` commits the
worker to provider dispatch before the request may leave the process, so that
state is not cancellable. An interrupted `awaiting_response` job is marked failed
on restart and is not automatically retried because the provider may have billed
the lost request.

## LLM provenance and cost

### LLMCall

A first-class record for one provider API attempt. It may exist for successful or
failed calls and links to scientific workflow context without embedding
provider-specific behavior in that workflow.

Conceptual fields:

- `id`
- nullable `project_id`, `step_run_id`, and `job_id`
- `provider`, exact `model`, and API `operation`
- execution mode (`live` or `replay`) and, for replayed calls, fixture identity
  and version
- `purpose`
- `prompt_template_id` and `prompt_template_version`
- references to exact system/developer instructions and input content artifacts
- references to complete raw-response and parsed-output artifacts
- `provider_request_id`
- `started_at`, `completed_at`, and duration
- status, retry/attempt count, and sanitized error information
- normalized usage fields: input, output, total, cached input, reasoning, and other
  categories when reported
- optional provider-specific usage/settings metadata in a versioned, non-secret
  structure
- generation parameters/settings relevant to reproduction
- pricing snapshot/reference
- locally estimated/calculated cost and provider-reported cost as distinct values
- calculation method/version, currency, and `cost_status`

Replay calls are explicitly simulated: actual provider usage and API cost are
zero, while optional historical usage or estimated cost carried by a fixture is
separate reference data. A replay call never receives a real provider request ID.

Large prompt and response bodies should be immutable artifacts rather than large
SQLite columns. The call record references the exact artifact versions used.
Neither storage path may contain API keys, authorization headers, credential-store
values, or unredacted secret-bearing exceptions.

A single high-level operation may retry. Each provider attempt should remain
traceable; the exact relationship between a logical call and retry attempts will
be resolved before schema implementation rather than collapsing failure history.

### LLMUsage

Normalized optional usage associated with a call/attempt. Common categories are
input tokens, output tokens, cached input tokens, reasoning tokens, and total
tokens. Additional provider categories remain in provider metadata with units and
names preserved. Missing values are null/unknown, never zero by assumption.

The initial implementation stores normalized nullable fields on `llm_calls` and
also preserves the complete provider usage object as canonical JSON. This can be
normalized into related tables later without discarding provider categories.

New OpenAI calls with an exact model match and usable usage may now store an
estimated USD cost plus the dated Standard-rate snapshot used to calculate it.
Older calls are not retroactively repriced; unknown model/tier/long-context
cases remain unavailable. The preview estimate for a future scoring plan is
not itself a completed-call cost record.

### PricingSnapshot

Immutable rates used for a cost calculation. Expected fields include provider,
exact model/pattern, source/version, pricing currency, effective/published and
captured timestamps, input/output/cached/reasoning or other rates, rate units, and
applicability notes. A call references the snapshot used at execution time.

Pricing snapshots must be append-only so a later price update cannot rewrite
historical cost. Provider-reported cost is retained separately. Cost status should
distinguish at least `reported`, `estimated`, and `unavailable`; `estimated` must
not be presented as exact.

Aggregated step/project/global usage and cost should normally be derived from
call records. Materialized summaries may be added later for performance with a
documented reconciliation rule.

## Scientific searches and source records

### SearchQuery

A source-specific query with purpose and links to original and effective artifact
versions. The exact generated text is never overwritten. It records intended
source and the LLM call or user action that produced it.

### SearchRun

One execution of one effective query against one source. Records the exact query
version, source/adapter version, request parameters, start/completion time, paging,
counts, status/errors, retrieval timestamp, raw-response artifacts, and job/run
links.

The implemented `search_runs`, `search_pages`, and `publication_source_records`
tables preserve one run per included Europe PMC query, raw response page file
path/size/SHA-256/cursor/request URL, and one row per returned item linked to its
run and page. A retry gets a new job and new runs; failed attempts are not
overwritten. Source-native identity (`source`, `id`) is required, while missing
title, abstract, DOI, PMID, and PMCID remain null. The V1 per-query 5,000-record
limit sets `truncated` when total hits exceed saved records.
The retrieval summary is a read-only aggregation of these immutable rows; it
does not create a new publication identity or screening decision. Its distinct
record key is `(source, source_record_id)`, which may still represent the same
publication as a different key in another collection.
For completed jobs, the overview derives provisional record groups from exact
normalized DOI, PMID, PMCID, or title matches. This read-only calculation does
not create `Publication` rows or change source records. Available first-author,
year, journal, and identifier disagreements are counted for later review. A
screening-ready identity version and correction model remain undesigned (ADR 0020).

Relevance preparation reuses immutable `jobs`, `llm_calls`, and
`artifact_versions`. A `relevance_prompt_generation` job snapshots the approved
strategy/charter reference, retrieval ID, sample algorithm version and seed,
exact prompt-design distinct-source-ID sample manifest/hash and metadata hash,
generation prompt, and sample records. Its structured output holds a standalone
scoring prompt and sample observations. The original and manually edited prompt
are separate immutable `relevance_prompt_generation_output` versions with an
effective pointer. A later calibration snapshot references the exact generated
prompt artifact/version it consumes; its provider request uses that compact
prompt without repeating the full strategy. A `relevance_calibration_output`
artifact contains one relevance-only outcome (0–5 or `not_assessable`) and reason
per sample ID. Legacy calibration-only jobs remain unchanged. These sample
outcomes are not bulk screening decisions; durable per-batch and per-record
scoring decisions are still to be designed (ADRs 0021–0022).
Older preparation and calibration jobs retain their historical first-run cap
snapshot; new prompt-generation jobs have no cap. A later scoring-run decision
will choose its own record limit. The per-1,000-report estimate is derived from
the exact prompt-design sample and current effective scoring prompt, not stored
as a completed LLM call or enforced spending limit.

### Publication

A normalized scholarly work identity. Candidate fields include title, authors,
journal, publication date/year, abstract, DOI, PMID, PMCID, publication types, and
access links. Fields are nullable; unavailable source data is never invented.

Identity resolution may use DOI, PMID, PMCID, and conservative metadata matching,
but precedence and merge/conflict rules must be documented before implementation.

### PublicationSource

Preserves every source record/discovery even when multiple records resolve to one
`Publication`. Expected fields include publication, source, source record ID,
search run and query, retrieval timestamp, raw-record artifact/reference, and
source-specific metadata. This entity is the basis for per-query, per-source,
exclusive, and overlap statistics.

### StructuredSourceRecord

Preserves a source-native record from a protein/target, structure, interaction,
bioactivity, peptide, sequence/motif, assay, or other accepted scientific adapter.
Expected fields include source and adapter version, source record identity,
query/search-run relationship, retrieval time, raw record artifact, parsed schema
version, and source-specific metadata. Publication deduplication rules do not
apply automatically; cross-source entity resolution retains every contributing
record and its conflicts.

## Later-stage entities (design in progress)

### ScreeningDecision

Will preserve include/exclude/uncertain, reason, exact criteria version, stage,
model/prompt provenance, confidence representation, and human override without
deleting the original decision. Schema is unresolved.

### EvidenceItem

Will represent an atomic peptide-relevant result with a source publication or
structured source record and exact source location/field, study or assay context,
experimental system, method, quantitative content and units, extraction
provenance, and confidence/uncertainty. It must distinguish direct observation,
curated annotation, source-author interpretation, application inference, and
computational prediction. Candidate domains include target/pathway, interaction
interface, peptide identity/sequence/modification, structure, activity/affinity,
efficacy, selectivity, safety, immunogenicity, stability, degradation, delivery,
and manufacturability. Schema is unresolved.

### ScientificClaim

Will group or express a claim supported or contradicted by evidence items and
eventually connect synthesis text to its evidence chain. Reconciliation and
weighting semantics are unresolved.

### PeptideDesignBrief

A reviewed, versioned bridge from evidence synthesis to candidate work. Expected
dimensions include therapeutic purpose, target and intended modulation,
interaction region or motif, peptide class, sequence/structure constraints,
modifications, delivery context, selectivity, stability, safety,
immunogenicity, and manufacturability. Each populated requirement references
supporting evidence or an explicit user decision; unknown and conflicting
requirements remain representable. Approval identifies one exact effective brief
version, and candidate work consumes that version.

### PeptideCandidate

A stable candidate identity with immutable versions for exact sequence and an
eventual chemical representation capable of recording relevant termini,
cyclization, noncanonical residues, modifications, conjugates, and constraints.
Expected provenance includes parent candidate(s), derivation operation, design
brief version, creator, generator/tool/model version, parameters, seed where
applicable, and creation time. Import, generation, user editing, and optimization
must not erase lineage.

### ComputationalEvaluation

One attempt to evaluate one exact candidate version for one declared capability.
Expected fields include capability, tool/provider/model and version, parameters,
hardware/runtime context where material, exact input artifacts, raw output,
parsed values and units, applicability-domain information, uncertainty, status,
timing, error, and cost. Experimental and predicted values remain distinct;
cross-capability ranking is not stored as an unexplained universal score.

## Relationship summary

```text
Project --< WorkflowStep --< StepRun --< Job
   |             |             |  `--< LLMCall >-- PricingSnapshot
   |             |             `---- consumes/produces ArtifactVersion
   |             `--< UserNote
   `--< ProjectFork >-- parent Project/checkpoint StepRun

Artifact --< ArtifactVersion

SearchQuery --< SearchRun --< PublicationSource >-- Publication
                         `--< StructuredSourceRecord

Publication --< ScreeningDecision --< EvidenceItem >-- ScientificClaim
StructuredSourceRecord ----------------^                    |
ScientificClaim --< PeptideDesignBrief --< PeptideCandidate
PeptideCandidate --< ComputationalEvaluation
```

Arrows describe conceptual cardinality only; final ownership and deletion rules
require migrations and ADR-backed decisions.
