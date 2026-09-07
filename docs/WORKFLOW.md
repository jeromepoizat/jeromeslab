# Scientific workflow

This is the authoritative workflow description. Status terms mean:

- **implemented**: working code and tests exist;
- **planned**: product behavior is agreed enough to schedule;
- **design in progress**: goals are known, but schema or method is unresolved.

No scientific workflow step is implemented yet.

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

### Step 0 — Scientific question (planned)

The user enters a scientific question in a large text field and starts a project.
The exact original text becomes an immutable artifact. It is not normalized or
rewritten in place.

### Step 1 — Research question decomposition (planned)

An LLM expands the question into structured plain text describing the
subquestions to investigate. The user may edit the result before continuing.
Both the exact raw model response and parsed original artifact are preserved; an
edit creates a separate effective version.

The run links to complete `LLMCall` provenance, including prompt version, exact
input/output, provider/model, usage, timing, errors, and cost status.

### Step 2 — Literature investigation strategy (planned)

The user chooses enabled scientific sources, initially expected to be Europe PMC
and later PubMed. The LLM generates source-specific queries with an explicit
purpose. Exact generated queries are stored and can be edited through the same
original/effective version mechanism. Search execution consumes the effective
query version.

### Step 3 — Literature retrieval (planned)

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

