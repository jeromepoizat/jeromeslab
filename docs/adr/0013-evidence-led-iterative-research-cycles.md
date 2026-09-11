# ADR 0013: Evidence-led iterative research cycles

- Status: Accepted
- Date: 2026-09-11

## Context

Live evaluation of the intent, scope, and readiness workflow with `PROJ008`
showed that a researcher may legitimately begin without enough evidence to choose
a mechanism, candidate profile, validation endpoint, or preferred direction.
Forcing those choices before literature investigation turns scientific unknowns
into unsupported user preferences and can narrow an exploratory project before
the application has supplied evidence.

The same evaluation exposed an important boundary between two kinds of scope.
Project framing establishes what the researcher is trying to accomplish in the
current cycle. Literature-investigation scope later decides which data and
records to retrieve and screen. For example, animal production may be an intended
application, but whether animal studies are eligible evidence belongs to search
and screening design.

## Decision

Treat research as one or more evidence-led cycles rather than a single linear
question-to-answer pass.

Before the first search, clarification will establish only the immediate research
objective, later or parallel goals, conceptual subject boundary, user-known
constraints, and ordering needed to understand the next cycle. Broad exploration
and state-of-the-art mapping are valid immediate objectives. A project is ready
for a current-cycle charter when the next investigation can be planned, not when
all scientific uncertainty has been resolved.

Clarification must distinguish:

- blocking ambiguity that prevents understanding the project;
- a project boundary or preference that the user can decide without evidence;
- a scientific unknown that the investigation should answer; and
- a literature-search or screening decision that belongs to later planning.

Only the first two categories may generate early clarification questions.
Scientific unknowns become investigation objectives or deferred decisions.
Literature planning owns source selection, query concepts, study populations and
species, evidence stages, study designs, publication types, dates, languages,
outcome filters, and screening inclusion or exclusion criteria.

Each research charter applies to one current cycle. An exploratory charter may
define a broad evidence map with distinct query and evidence strata. After
retrieval, extraction, and synthesis provide evidence, the user can continue the
exploration, narrow the direction, stop, or fork several directions. A later
cycle references the exact prior charter, evidence state, and recorded user
decision rather than rewriting consumed history.

There will be no disposable or untracked reconnaissance call. An exploratory
investigation uses the same provenance-bearing query, retrieval, screening,
extraction, and synthesis infrastructure as a focused investigation.

## Consequences

Intent, framing, and readiness prompts must avoid asking the user to predict the
scientific findings. The user interface may retain existing internal artifact and
job names for compatibility, but user-facing language should distinguish current
objectives, later goals, project framing, and literature-search scope.

The future charter and literature data model must support multiple ordered cycles
inside a project. Editing remains possible only before downstream consumption;
later redirection creates a new linked cycle, and simultaneous alternatives fork
at a recorded checkpoint.

Broad searches can be expensive and noisy, so exploration must be decomposed into
purpose-labelled query families and evidence strata. Broad scope does not justify
claims of exhaustive coverage; completeness claims depend on an explicit search
protocol and retained retrieval provenance.
