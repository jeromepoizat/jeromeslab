# Data model proposal

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

The precise representation of effective-version selection and content hashing is
unresolved.

## Execution

### Job

A persistent unit of queued work linked to its project and usually to a workflow
step/run. Expected fields include type, status (`pending`, `running`, `completed`,
`failed`, possibly `cancelled` later), enqueue/start/completion timestamps,
progress numerator/denominator/message, attempt information, error summary, and
lease/recovery metadata.

Only one job may be running in V1. Database constraints and worker transaction
design for enforcing this rule remain to be selected.

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

Whether this is a separate table or fields plus versioned JSON is unresolved.

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

## Literature search and publications

### SearchQuery

A source-specific query with purpose and links to original and effective artifact
versions. The exact generated text is never overwritten. It records intended
source and the LLM call or user action that produced it.

### SearchRun

One execution of one effective query against one source. Records the exact query
version, source/adapter version, request parameters, start/completion time, paging,
counts, status/errors, retrieval timestamp, raw-response artifacts, and job/run
links.

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

## Later-stage entities (design in progress)

### ScreeningDecision

Will preserve include/exclude/uncertain, reason, exact criteria version, stage,
model/prompt provenance, confidence representation, and human override without
deleting the original decision. Schema is unresolved.

### EvidenceItem

Will represent an atomic extracted result with source publication and exact source
location, study/method context, quantitative content, extraction provenance, and
confidence/uncertainty. Schema is unresolved.

### ScientificClaim

Will group or express a claim supported or contradicted by evidence items and
eventually connect synthesis text to its evidence chain. Reconciliation and
weighting semantics are unresolved.

## Relationship summary

```text
Project --< WorkflowStep --< StepRun --< Job
   |             |             |  `--< LLMCall >-- PricingSnapshot
   |             |             `---- consumes/produces ArtifactVersion
   |             `--< UserNote
   `--< ProjectFork >-- parent Project/checkpoint StepRun

Artifact --< ArtifactVersion

SearchQuery --< SearchRun --< PublicationSource >-- Publication

Publication --< ScreeningDecision --< EvidenceItem >-- ScientificClaim
```

Arrows describe conceptual cardinality only; final ownership and deletion rules
require migrations and ADR-backed decisions.
