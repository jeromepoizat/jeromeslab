# Therapeutic peptide discovery workflow

This is the authoritative workflow description. Status terms mean:

- **implemented**: working code and tests exist;
- **planned**: product behavior is agreed enough to schedule;
- **design in progress**: goals are known, but schema or method is unresolved.

Jerome's Laboratory is specialized in evidence-guided therapeutic peptide
discovery under ADR 0015. Research-direction clarification, project framing,
conditional bounded framing-check/follow-up, and first-investigation charter generation and approval are
implemented with peptide-specific prompt defaults. Internal names retain
`intent` and `scope` for data compatibility, while consumed older prompts remain
preserved with their original wording and versions. Scientific-source
investigation, peptide evidence extraction, design, and in-silico stages remain
planned or in design.

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
- Keep observed evidence, source annotations, model inference, and computational
  predictions explicitly distinguishable.
- Require a reviewed peptide design brief before candidate generation or
  optimization consumes synthesized evidence.
- Do not turn an evidence-dependent target, mechanism, sequence, peptide format,
  delivery strategy, or validation method into an early user preference.

## Agreed early workflow

### Step 0 — Scientific question (implemented as project creation)

The user enters a scientific question and starts a peptide-discovery project.
The question may already name a target or peptide, or it may begin broadly with a
therapeutic need or biological system whose peptide opportunity is to be explored.
The initial project shell stores the exact text in the project record; an
immutable artifact version will replace that storage representation when the
artifact engine is implemented. The question is not normalized or rewritten in
place once a started or completed workflow job uses it as input. Project tags
remain separately mutable display metadata; users can also add notes later
without altering the question.

### Step 1 — Research-goal questionnaire (implemented)

Each project snapshots a versioned, editable direction-clarification prompt
before the first call. An LLM reads only the preserved original question and
returns a strictly validated JSON questionnaire with three to seven distinct,
relevant directions. Active version 4 fixes therapeutic peptide discovery as the
domain while accepting projects that begin from a broad therapeutic problem, a
known target without a peptide, or an existing peptide. It treats evidence
landscape mapping as valid immediate work and distinguishes it from later target
assessment, peptide design, optimization, and evaluation goals. Non-peptide
modalities may be context or comparators, not design outputs. It does not define
source-search scope, select scientific answers, or generate queries.

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

Direction clarification is one logical stage. A cancelled or failed call may be
retried without deleting the retained attempt. The generated questionnaire and
confirmed decision for a completed attempt are not iteratively regenerated.

### Step 2 — Assumptions and boundaries (implemented; internally scope clarification)

The first LLM round uses the original question and exact effective confirmed
direction artifact to generate zero to five material project-framing questions
as validated JSON. Active version 6 asks only for user-controlled premises,
fixed starting points, project boundaries, or ordering decisions in therapeutic
peptide discovery. Each question declares whether it is single-choice or
multiple-choice, explains why the choice
matters, provides concise options, and accepts a manual note or a "not sure"
response that is exclusive of suggested choices. A manual note may explain that
uncertainty, qualify selected choices, or serve as the complete answer when the
generated options do not fit. The prompt explicitly forbids questions that
belong to later query and screening scope and forbids asking the user to decide
scientific unknowns that evidence is supposed to resolve. In particular, it must
not demand an unsupported target, mechanism, interaction site, peptide class,
sequence constraint, modification, delivery route, or validation strategy. Its
version-3 output schema may return an empty question list instead of manufacturing
a decision. The application then creates an immutable empty answer artifact with
`application` provenance so later lineage remains structurally complete without
pretending the user answered anything. Generated questions otherwise declare
options as independent or cumulative; cumulative boundaries must be
single-choice, while multiple-choice options must be independent. Generated
questions and each confirmed or edited answer set are separate immutable,
SHA-256-addressed
artifacts. Downstream enqueueing locks the effective answer version.

When the first round contains one or more questions, a separate explicit LLM job
evaluates the confirmed answers for a material contradiction or a genuinely new
blocking user-controlled decision before the investigation charter is created.
It does not judge scientific truth, supporting evidence, or feasibility. A broad
exploratory project can be ready while retaining unknown mechanisms, candidates,
outcomes, and validation strategies as investigation objectives or deferred
decisions. The job snapshots the exact effective first-round answer artifact it
consumes and returns validated JSON containing a readiness decision, concise
assessment, remaining or accepted uncertainties, and either zero follow-up
questions when ready or one to five questions when a material ambiguity remains.

When framing returns no questions, the separate check would have no user answer
to evaluate and is skipped. The application records that deterministic reason,
the empty immutable answer artifact, and a ready result in the charter's input
provenance. It does not create a synthetic LLM call or readiness artifact.

Only one follow-up questionnaire is permitted. It reuses the first-round answer
controls: suggested single- or multiple-choice answers, a manual note, and an
explicit Not sure response. Its confirmed answers are immutable numbered
artifacts and remain editable only until the charter job is queued. After this
round, the workflow advances with unresolved uncertainty recorded rather than
starting an open-ended clarification loop. Not sure, note-only, broad, and
inclusive responses are treated as completed answers: the readiness provider
must preserve their uncertainty rather than ask the same decision again. Active
version 6 presents this as a compact framing check. It declares a project not
ready only for a material contradiction or a genuinely missing user-controlled
decision that makes the current investigation impossible to state. It prohibits
follow-ups about study eligibility, sources, queries, screening criteria, or
evidence-dependent peptide design choices and requires literal interpretation
of selected IDs without silently including an unselected option. The application
rejects structurally inconsistent option sets and any follow-up that repeats an
answered first-round question by ID or normalized wording.
First-round answers lock as soon as the readiness job is queued. Reconnaissance
search is intentionally deferred until formal search/query generation and later
workflow behavior have been designed and tested.

### Step 3 — Peptide-discovery charter (implemented for the first investigation)

The LLM turns the original question, confirmed direction, project-framing
answers, notes, investigation objectives, deferred decisions, and accepted
uncertainties into a readable charter for the current investigation. An exploratory charter
states the subject and purpose without pretending that evidence-dependent
mechanisms, candidates, or conclusions are already decided. The user reviews and
explicitly approves an effective version before downstream work may consume it.

The prompt is a versioned text resource, hidden by default and editable only
before this stage's first job is created. The exact prompt remains viewable but
locked afterward. Active version 4 asks for concise, flexible Markdown containing
an explicit refined investigation question, confirmed purpose and boundaries,
distinct evidence objectives, important unknowns, deferred design decisions, and
the link to later peptide discovery or optimization. It tells the model to state
each substantive point once, combine overlapping material, omit a separate copy
of the original question, and normally stay within approximately 350–600 words.
It preserves explicit user constraints, keeps the framing check advisory, and
distinguishes hypotheses from commitments. It must not invent findings, queries,
search criteria, candidates, sequences, or design specifications.

Charter generation becomes available when a non-empty framing questionnaire
passes its check, the one final follow-up is confirmed, or framing returned no
questions. Enqueueing snapshots the complete confirmed inputs and
locks any follow-up answer version it consumes. The generated Markdown is
wrapped by the application in an immutable, hashed JSON artifact. The user can
inspect the original, save manual versions, and explicitly approve the effective
version. Editing produces a draft that requires fresh approval.

Earlier general and peptide-specific research-charter prompts remain preserved
for jobs that already consumed them. Version 4 becomes the default only for
unconsumed stages and new projects.

The backend retains a replacement-attempt lifecycle in which another generation
creates a separate job and LLM call rather than overwriting history. Active
replacement temporarily prevents changes or downstream use of the earlier
charter; a successful new output becomes the current draft, while a failed or
cancelled attempt leaves the most recent completed charter usable. The completed
charter card does not currently expose a regeneration action. Neither editing nor
replacement is allowed after downstream consumption. Later investigation creation is
not implemented by this slice.

### Legacy question detailing (implemented compatibility path)

Projects that already started the former one-shot question-detailing workflow
retain that exact interface, prompt, call provenance, Markdown output, and manual
artifact versions. They are not silently converted to the new workflow. A future
explicit transition or fork from a legacy output remains to be designed.

### Step 4 — Scientific-source investigation strategy (planned)

This stage, not project framing, owns the scope of evidence acquisition. The user
chooses enabled publication and structured-data sources and decides applicable
search and screening dimensions such as study populations or species, evidence
stages, study designs, publication types, dates, languages, outcomes, and
inclusion or exclusion rules. An intended therapeutic application captured
during framing is distinct from the later decision to include a study type as
evidence.

The first retrieval slice is still expected to use Europe PMC, with PubMed later.
Future adapters may cover protein/target annotation, structure, interaction,
bioactivity, peptide, sequence/motif, and assay sources. Each source requires its
own accepted identity, licensing, query, pagination, normalization, and
provenance rules before implementation. The LLM generates purpose-labelled,
source-specific query families rather than forcing target biology, known peptide
modulators, interaction interfaces, efficacy, safety, stability, and delivery
into one query. Exact generated queries are stored and reviewed through the same
original/effective version mechanism.

### Step 5 — Scientific-source retrieval (planned)

Each effective query is executed through its source adapter. A `SearchRun`
preserves source, exact query/version, timestamps, request details, paging state,
errors, and raw results where useful. Each returned record is represented and
linked to the query that discovered it.

Publication records are normalized without inventing missing values.
Deduplication merges publication identity, not discovery history: every source
record and query relationship survives. Structured scientific records keep their
source-native identity and raw representation; cross-source entity resolution is
a separate, conservative operation rather than publication deduplication reused
without justification.

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

### Evidence-informed investigation iteration (planned)

After enough retrieval, screening, extraction, and synthesis exists for a useful
decision, the application presents a checkpoint. The user may continue the broad
exploration, narrow one direction, stop, or fork several directions. A subsequent
investigation links to the exact prior charter, evidence state, and user decision.
It does not edit or reinterpret the consumed history of the earlier investigation.

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

The goal is atomic peptide-relevant evidence rather than a paper or database
summary. Candidate entities include therapeutic need, biological target,
pathway, mechanism, interaction interface, peptide sequence or identity, peptide
class and modification, assay, experimental system, structure, activity or
affinity measurement, efficacy outcome, selectivity/off-target result, toxicity,
immunogenicity, stability, degradation, delivery, and manufacturability finding.

Every item must link to its publication or structured source record and exact
source location or field. It must distinguish direct observation, curated source
annotation, author interpretation, application inference, and computational
prediction. The final schema and validation process are unresolved.

### Evidence reconciliation and weighting

The system should expose support, contradiction, evidence type, methodological
strength, independence, replication, and uncertainty. No scoring formula has
been accepted. An arbitrary numeric evidence score must not be introduced without
scientific justification and a recorded decision.

### Scientific synthesis

Narrative synthesis comes only after structured evidence. The intended chain is:

```text
synthesis sentence -> scientific claim -> evidence item -> source record
                   -> screening decision -> search run/query -> discovery charter
                   -> original scientific question
```

The narrative schema, citation rendering, contradiction presentation, and
confidence language remain unresolved.

### Peptide design brief

Before candidate generation, the application converts approved evidence and
explicit user decisions into a reviewed design brief. Candidate dimensions
include therapeutic objective, target and intended modulation, binding region or
motif, peptide class, sequence/structure constraints, modifications, delivery
context, selectivity, stability, safety, immunogenicity, and manufacturability.
Every requirement must link to evidence or an explicit user decision. Unsupported
or conflicting dimensions remain unknown or become design alternatives rather
than silently selected defaults.

The brief is versioned and explicitly approved. Any candidate-generation or
optimization run consumes one exact approved brief version.

### Candidate generation and adaptation

Candidate work may start from a known peptide, motif, epitope, interaction
interface, structural model, or de-novo method. Each candidate records its exact
sequence and chemical representation, modifications, parent/derivation links,
generation or editing method, model/tool version, parameters, random seed where
applicable, input brief, and creator. User-created and imported candidates use
the same provenance rules.

The generation methods, supported peptide representations, validity rules, and
vendor/tool integrations remain design decisions. No generated candidate is
presented as efficacious merely because it satisfies a model or syntax check.

### In-silico evaluation and prioritization

Candidate evaluation is modular. Potential analyses include physicochemical and
sequence liabilities, solubility, aggregation, proteolytic stability, structure,
target interaction, selectivity/off-target behavior, toxicity, immunogenicity,
delivery-related properties, and manufacturability. Every result preserves the
tool, version, parameters, exact candidate/input structure, raw output, parsed
value, units, applicability domain, and failures.

Experimental observations and computational predictions remain separate.
Prioritization must expose per-dimension results, uncertainty, missing values,
and user-defined trade-offs; the product will not invent one opaque universal
fitness score. Evaluation ordering, local-versus-remote execution, supported
tools, resource requirements, and validation benchmarks are unresolved.

### Evidence-guided iteration

After evidence synthesis, design-brief review, or candidate evaluation, the user
may continue broadly, narrow, revise an unconsumed brief, stop, or fork competing
strategies from a checkpoint. Later investigations reference the exact evidence state,
brief, candidate set, and decision that motivated them rather than rewriting
earlier history.
