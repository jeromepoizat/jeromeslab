# Product vision

## Purpose

Jerome's Laboratory is a local, open-source, LLM-assisted environment for
evidence-guided therapeutic peptide discovery. It turns an initial scientific
question into a visible chain of project framing, scientific-source queries,
screening, evidence extraction, synthesis, peptide design requirements,
candidate work, and in-silico evaluation.

The core promise is traceability. A candidate, design decision, predicted
property, or narrative statement should be traceable backward through its exact
method and inputs, approved peptide design brief, scientific claims and evidence,
source records, screening decisions, searches, peptide-discovery charter, and
original question.

The application may begin broadly. A researcher can ask about a therapeutic
need, biological target, pathway, mechanism, existing peptide, or desired
intervention without already knowing the correct target, binding site, peptide
format, sequence, or development strategy. Evidence should help resolve those
unknowns instead of the interface asking the user to guess them.

## Product scope

The product supports therapeutic peptide discovery, including relevant linear,
cyclic, constrained, modified, conjugated, and peptide-mimetic strategies. It may
use other therapeutic modalities as scientific context or comparators, but it
does not design small molecules, antibodies, proteins, nucleic-acid therapeutics,
or unrelated materials.

Projects may be:

- exploratory, such as mapping target biology and known peptide modulation;
- target-defined but candidate-agnostic;
- based on a known peptide, motif, epitope, or interaction interface;
- focused on optimization, selectivity, delivery, stability, or safety; or
- ready for evidence-supported candidate generation and in-silico prioritization.

## Goals

- Make therapeutic peptide discovery reproducible, inspectable, and auditable.
- Keep LLM and computational assistance under visible human control.
- Preserve exact original inputs, generated results, manual revisions, effective
  values, source records, candidate derivations, and computational parameters.
- Separate observed experimental evidence from inference and in-silico prediction.
- Turn traceable evidence into an explicit, human-approved peptide design brief
  before candidate generation.
- Support comparison across project forks, models, providers, search strategies,
  candidate-generation methods, and evaluation methods without rewriting history.
- Integrate publications and structured scientific sources through explicit,
  provider-independent adapters.
- Record LLM and computational configuration, inputs, outputs, timing, failures,
  usage, and cost as first-class provenance.
- Run locally, protect credentials with native OS facilities, and remain useful
  to a single researcher without operating a server stack.
- Let ordinary users install and run without preinstalling language runtimes or
  package managers.

## Non-goals

- A general-purpose scientific-research or chat application.
- Designing non-peptide therapeutic modalities, except as scientific comparison.
- Treating an LLM response or computational prediction as experimental evidence.
- Producing an unexplained universal candidate score.
- Claiming clinical efficacy, safety, regulatory suitability, or experimental
  validation from literature or in-silico results alone.
- Autonomous publication of scientific or clinical conclusions.
- Hiding source records, exclusions, uncertainty, disagreement, failed runs, or
  unsuccessful candidates.
- Bypassing legal access controls or redistributing copyrighted papers.
- Operating wet-lab experiments. The application may later produce a traceable
  validation plan or export, but experimental execution remains external.
- Multi-user collaboration, distributed execution, or parallel research jobs in
  V1.

## Intended user experience

The user launches a local process and keeps its terminal available for logs. The
backend initializes application data, binds to `127.0.0.1` on an available port,
and opens the default browser.

On first start, the user may configure an LLM provider and model, with the secret
stored only in the native credential store. Projects appear in a collapsible
sidebar. A project is one long, inspectable discovery record whose completed
workflow cards remain visible while one persistent queue continues work.

The user begins with an exact scientific question. The application helps frame a
peptide-discovery investigation without converting evidence-dependent unknowns into
unsupported preferences. After approving the investigation charter, the user reviews
source and search scope, queries, screening decisions, extracted evidence,
synthesis, and eventually the design brief and candidate/evaluation records.
Every consequential generated value can be inspected, edited through a preserved
version, or rejected before downstream use.

## Design principles

1. **Provenance is product data.** It is not optional debug logging.
2. **History is immutable.** Consumed results are never silently replaced;
   alternatives start from a recorded checkpoint or fork.
3. **Originals survive editing.** Human review creates an effective version while
   preserving the generated original.
4. **Evidence precedes design commitments.** Unknown targets, mechanisms,
   sequences, formats, or validation choices are investigated before being fixed.
5. **Observed and predicted remain distinct.** Literature observations,
   database annotations, model inference, and computational prediction retain
   explicit source/type labels.
6. **No silent filtering.** Retrieval retains every returned record; exclusions
   and candidate rejection require visible reasons.
7. **Provider independence.** Scientific workflow logic depends on generic
   contracts, not a particular LLM, database, design model, or simulation tool.
8. **Modular evaluation.** Affinity, selectivity, stability, solubility,
   aggregation, toxicity, immunogenicity, delivery, and manufacturability are
   separate evidence or prediction dimensions, not one opaque score.
9. **Local and secure by default.** Bind locally and keep secrets out of browser
   storage, databases, logs, and artifacts.
10. **Honest uncertainty.** Unknowns remain unknown; unavailable measurements or
    costs never become false precision.
11. **Incremental scientific design.** Later methods are authoritative only after
    explicit design, evaluation criteria, and provenance contracts are accepted.
12. **Self-bootstrapping distribution.** Ordinary users do not install the
    language toolchain themselves.
