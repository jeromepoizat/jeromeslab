# ADR 0015: Specialize the product in therapeutic peptide discovery

- Status: Accepted
- Date: 2026-09-21

## Context

The original product direction covered scientific research broadly. That made the
provenance, workflow, queue, and evidence principles reusable, but left later
questions, extraction schemas, source integrations, and computational stages too
open-ended to design rigorously. A generic application would need to accommodate
unrelated research methods without one clear definition of success.

The intended use is now clearer: begin with a scientific question relevant to a
therapeutic need or biological system, refine the purpose without forcing
unsupported choices, acquire literature and structured scientific data, extract
traceable knowledge and evidence, use that evidence to define peptide design
requirements, and then generate or adapt peptide candidates for explicit
in-silico evaluation.

## Decision

Jerome's Laboratory is an evidence-guided therapeutic peptide discovery
application, not a general scientific-research platform. It supports exploratory
and focused projects, including projects that begin with a disease or biological
question before a target, mechanism, binding site, peptide format, or candidate
is known.

The durable workflow is:

1. preserve the original scientific question;
2. clarify the current peptide-discovery objective and later goals;
3. frame only user-controlled project boundaries;
4. approve a current-cycle peptide-discovery charter;
5. plan and execute provenance-bearing searches across publications and relevant
   structured scientific sources;
6. screen and extract atomic peptide-relevant evidence;
7. synthesize that evidence into a human-approved peptide design brief;
8. generate, adapt, or prioritize candidates using recorded methods and inputs;
9. perform modular in-silico evaluations; and
10. iterate, narrow, stop, or fork without rewriting prior history.

The peptide design brief is a required conceptual checkpoint between evidence
synthesis and candidate generation. It may cover therapeutic purpose, target and
mode of action, interaction region, peptide class, modifications, delivery,
selectivity, stability, safety, and manufacturability, but only where these are
supported by evidence or explicitly chosen by the user. Unknowns remain explicit.

The scope includes linear, cyclic, constrained, modified, conjugated, and
peptide-mimetic strategies when relevant to the project. Comparisons with small
molecules, antibodies, proteins, nucleic acids, or other modalities may be used
as evidence or context, but designing those modalities is not a product goal.

Computational measurements and predictions are not experimental evidence. The
application must preserve the tool, version, parameters, inputs, outputs, and
applicability limits of each calculation and must not collapse heterogeneous
properties into an unexplained universal score. It does not establish clinical
efficacy or safety, autonomously publish conclusions, or replace experimental
validation.

Existing provider-independent infrastructure and implemented clarification,
readiness, charter, artifact, and provenance behavior remain valid. Their active
prompts are still broad scientific prompts at the time of this decision and will
be replaced through new versions. Consumed prompts and existing project history
remain byte-for-byte preserved; only unused defaults or newly created projects
may adopt specialized prompt versions automatically.

## Consequences

Product documentation, user-facing terminology, prompts, future source adapters,
evidence schemas, evaluation plans, and roadmap milestones must be evaluated
against therapeutic peptide discovery rather than generic scientific utility.

Narrowing permits peptide-specific structured entities and validation while the
workflow and provider layers stay independent of any LLM, database, or
computational vendor. Literature remains important but is no longer the only
evidence source: protein, structure, interaction, bioactivity, peptide, and assay
sources can participate through explicit adapters with retained raw provenance.

The narrower domain does not justify premature design choices. Early framing
must still avoid asking a user to guess the best target, sequence, mechanism,
peptide architecture, delivery strategy, or validation method when the evidence
investigation is intended to establish those facts.
