# Scientific workflow

This is the authoritative workflow description. Status terms mean:

- **implemented**: working code and tests exist;
- **planned**: product behavior is agreed enough to schedule;
- **design in progress**: goals are known, but schema or method is unresolved.

Research-direction clarification, the first project-framing round, and the
bounded framing-readiness/follow-up stage are implemented. Their internal names
retain `intent` and `scope` for data compatibility. The current-cycle research
charter and later scientific stages remain planned or in design.

## Cross-cutting workflow rules

- Preserve the exact input and every output used in a computation.
- A completed step is immutable once downstream work depends on it.
- A human edit creates an effective artifact version and preserves the original.
- Downstream steps record the exact artifact version they consumed.
- User notes remain editable and do not affect computation unless explicitly
  promoted into an artifact.
- Rerun the latest step only when it has no dependents. Otherwise fork from a
  checkpoint and share immutable upstream artifacts.
- Record each job and external call, including failure and retry provenance.
- Never silently discard a retrieved publication.

## Agreed early workflow

### Step 0 — Scientific question (implemented as project creation)

The user enters a scientific question in a large text field and starts a project.
The initial project shell stores the exact text in the project record; an
immutable artifact version will replace that storage representation when the
artifact engine is implemented. The question is not normalized or rewritten in
place once a started or completed workflow job uses it as input. Project tags
remain separately mutable display metadata; users can also add notes later
without altering the question.

### Step 1 — Current research direction (implemented)

Each project snapshots a versioned, editable intent-clarification prompt before
the first call. An LLM reads only the preserved original question and returns a
strictly validated JSON questionnaire with three to seven distinct, relevant
research directions. The active version 2 treats broad evidence mapping as a
valid immediate objective and distinguishes the current cycle from later or
parallel goals. It does not define literature-search scope or generate queries.

The user selects exactly one current objective, may check multiple later or
parallel goals, and may add a free-form qualification. The persisted version-1
artifact schema retains the field names `primary_intent_id` and
`secondary_intent_ids` for compatibility. Generated choices and the user's
confirmed decision are separate immutable, SHA-256-addressed JSON artifacts. The
selection records the exact question artifact it answers and cannot be silently
rewritten. Enqueueing snapshots the question, prompt/version, provider, model,
and generation settings. Pending cancellation and dispatched-call behavior follow
the global queue rules.

A confirmed intent remains editable until a downstream job is queued. Each save
creates another immutable selection artifact and advances an explicit effective
version; earlier confirmations remain inspectable provenance. Queueing downstream
work locks the effective intent because that job must retain the exact input it
consumed.

Intent clarification is one logical stage. A cancelled or failed call may be
retried without deleting the retained attempt. The generated questionnaire and
confirmed decision for a completed attempt are not iteratively regenerated.

### Step 2 — Project framing (implemented; internally scope clarification)

The first LLM round uses the original question and exact effective confirmed
direction artifact to generate one to five material project-framing questions as
validated JSON. Each question
declares whether it is single-choice or multiple-choice, explains why the choice
matters, provides concise options, and accepts a manual note or a "not sure"
response that is exclusive of suggested choices. A manual note may explain that
uncertainty, qualify selected choices, or serve as the complete answer when the
generated options do not fit. The active version 4 prompt asks only about the
purpose, conceptual boundary, user-known constraints, or ordering of the current
cycle. It explicitly forbids questions that belong to later query and screening
scope and forbids asking the user to decide scientific unknowns that evidence is
supposed to resolve. It may return fewer questions rather than manufacture
search-scope choices. Its version-2 output schema declares options as independent
or cumulative; cumulative boundaries must be single-choice, while multiple-choice
options must be independent. Generated questions and
each confirmed or edited answer set are separate immutable, SHA-256-addressed
artifacts. Downstream enqueueing locks the effective answer version.

After the user confirms the first round, a separate explicit LLM job evaluates
whether the project is framed clearly enough to construct a current-cycle
research charter. It does not judge scientific truth, supporting evidence, or
feasibility. A broad exploratory project can be ready while retaining unknown
mechanisms, candidates, outcomes, and validation strategies as investigation
objectives or deferred decisions. The job
snapshots the exact effective first-round answer artifact it consumes and returns
validated JSON containing a readiness decision, concise assessment, remaining or
accepted uncertainties, and either zero follow-up questions when ready or one to
five questions when a material ambiguity remains.

Only one follow-up questionnaire is permitted. It reuses the first-round answer
controls: suggested single- or multiple-choice answers, a manual note, and an
explicit Not sure response. Its confirmed answers are immutable numbered
artifacts and remain editable only until the charter job is queued. After this
round, the workflow advances with unresolved uncertainty recorded rather than
starting an open-ended clarification loop. Not sure, note-only, broad, and
inclusive responses are treated as completed answers: the readiness provider
must preserve their uncertainty rather than ask the same decision again. The
active version 4 prompt also prohibits follow-ups about study eligibility,
sources, queries, or screening criteria and requires literal interpretation of
selected IDs without silently including an unselected option. The application
rejects structurally inconsistent option sets and any follow-up that repeats an
answered first-round question by ID or normalized wording.
First-round answers lock as soon as the readiness job is queued. Reconnaissance
search is intentionally deferred until formal search/query generation and later
workflow behavior have been designed and tested.

### Step 3 — Current-cycle research charter (planned)

The LLM will turn the original question, confirmed direction, project-framing
answers, notes, investigation objectives, deferred decisions, and accepted
uncertainties into a readable charter for the next cycle. An exploratory charter
states the subject and purpose without pretending that evidence-dependent
mechanisms, candidates, or conclusions are already decided. The user reviews and
explicitly approves an effective version before downstream work may consume it.

### Legacy question detailing (implemented compatibility path)

Projects that already started the former one-shot question-detailing workflow
retain that exact interface, prompt, call provenance, Markdown output, and manual
artifact versions. They are not silently converted to the new workflow. A future
explicit transition or fork from a legacy output remains to be designed.

### Step 4 — Literature investigation strategy (planned)

This stage, not project framing, owns the scope of literature data acquisition.
The user chooses enabled scientific sources and decides applicable search and
screening dimensions such as study populations or species, evidence stages,
study designs, publication types, dates, languages, outcomes, and inclusion or
exclusion rules. An intended animal application captured during framing is
distinct from the later decision to include animal studies as evidence.

The first source is expected to be Europe PMC and later PubMed. The LLM generates
purpose-labelled, source-specific query families rather than forcing a broad
exploration into one query. Exact generated queries are stored and can be edited
through the same original/effective version mechanism. Search execution consumes
the effective query version.

### Step 5 — Literature retrieval (planned)

Each effective query is executed through its source adapter. A `SearchRun`
preserves source, exact query/version, timestamps, request details, paging state,
errors, and raw results where useful. Each returned record is represented and
linked to the query that discovered it.

Records are normalized into publications without inventing missing values.
Deduplication merges publication identity, not discovery history: every source
record and query relationship survives.

The first implementation will define and report at least:

- **raw records**: source records returned across all executed query runs, before
  cross-record deduplication;
- **unique publications**: normalized publication identities after the documented
  identity-resolution rules;
- **duplicate records**: raw records minus unique publications, with caveats when
  ambiguous records cannot be merged;
- records per source and per query;
- source-exclusive publications; and
- cross-source overlap.

Identity precedence and treatment of multiple results from the same source remain
to be specified before implementation.

### Evidence-informed research-cycle iteration (planned)

After enough retrieval, screening, extraction, and synthesis exists for a useful
decision, the application presents a checkpoint. The user may continue the broad
exploration, narrow one direction, stop, or fork several directions. A subsequent
cycle links to the exact prior charter, evidence state, and user decision. It does
not edit or reinterpret the consumed history of the earlier cycle.

## Later workflow: design in progress

### Screening

Expected stages are title/abstract and possibly full-text screening. Inclusion and
exclusion criteria must be explicit, visible, and editable before screening, with
original and effective versions preserved. Every paper needs an
include/exclude/uncertain decision, reason, model/prompt provenance, and preserved
manual override. Excluded papers are never deleted.

The criteria schema, batching, confidence representation, model disagreement, and
human-review protocol are unresolved.

### Full-text and access resolution

The system needs explicit states such as `FULLTEXT_OPEN`, `ABSTRACT_ONLY`,
`FULLTEXT_CLOSED`, `FULLTEXT_USER_PROVIDED`, and `NO_ABSTRACT`. Candidate legal
resolution sources include PMC/Europe PMC, Unpaywall, publisher open access,
repositories, preprints, and user-provided PDFs. Acquisition ordering, local
retention, copyright boundaries, and document identity require further design.

### Evidence extraction

The goal is atomic structured evidence rather than a paper summary. Candidate
fields include claim, source location, study type, experimental system, method,
result, quantitative evidence, and confidence. The schema and validation process
are unresolved. Every evidence item must link to its source publication and the
exact accessible text used.

### Evidence reconciliation and weighting

The system should expose support, contradiction, evidence type, methodological
strength, independence, replication, and uncertainty. No scoring formula has
been accepted. An arbitrary numeric evidence score must not be introduced without
scientific justification and a recorded decision.

### Scientific synthesis

Narrative synthesis comes only after structured evidence. The intended chain is:

```text
synthesis sentence -> scientific claim -> evidence item -> publication
                   -> screening decision -> search run/query -> original question
```

The narrative schema, citation rendering, contradiction presentation, and
confidence language remain unresolved.

### Downstream computational research

In-silico drug discovery and related computation are long-term possibilities and
are outside the current design scope.
