# Product vision

## Purpose

Jerome's Laboratory is a local, open-source, LLM-assisted environment for
scientific research. It should turn a scientific question into a visible chain of
search, selection, extraction, evaluation, and synthesis steps while preserving
the exact evidence and transformations behind each result.

The core promise is traceability. A future narrative statement should be
traceable backward through scientific claims, evidence items, source
publications, screening decisions, search queries and runs, and the original
question.

## Goals

- Make scientific research workflows reproducible, inspectable, and auditable.
- Keep machine assistance under visible human control.
- Preserve the exact original input, generated result, manual revision, and
  effective value used downstream.
- Support comparison across project forks, models, providers, and research
  strategies without rewriting history.
- Record LLM configuration, inputs, outputs, usage, latency, failures, and costs
  as first-class provenance.
- Run locally by default and protect credentials using native OS facilities.
- Integrate scientific sources through explicit adapters and retain discovery
  provenance even after deduplication.
- Remain cross-platform and useful to a single researcher without operating a
  server stack.

## Non-goals

- A general-purpose chat interface for scientific questions.
- Autonomous publication of scientific or clinical conclusions.
- Hiding search records, exclusions, uncertainty, disagreement, or failed runs.
- Treating LLM output as evidence by itself.
- Bypassing legal access controls or redistributing copyrighted papers.
- Multi-user collaboration, distributed execution, or parallel research jobs in
  V1.
- Finalizing screening, evidence scoring, or synthesis before those methods are
  explicitly designed and justified.

## Intended user experience

The user launches a local process and keeps its terminal available for logs. The
backend initializes application data, binds to `127.0.0.1` on an available port,
and opens the default browser.

On first start, research is blocked until an LLM provider and model are selected
and a credential is saved to the native credential store. The frontend can know
whether a provider is configured but can never retrieve the credential.

Projects appear in a collapsible left sidebar. The most recently active project
opens automatically, or the New Project view appears when no project exists. A
project is primarily one long page whose completed workflow cards remain visible.
A navigation rail jumps among existing steps, while a Research Queue panel shows
the single running job and pending work. Navigation must not interrupt a running
job.

## Design principles

1. **Provenance is product data.** It is not optional debug logging.
2. **History is immutable.** A completed result with dependents is never silently
   replaced; alternative work starts from a forked checkpoint.
3. **Originals survive editing.** Human review creates an effective version while
   preserving the generated original.
4. **No silent filtering.** Retrieval retains every returned record. Screening is
   a later, explicit decision with a recorded reason.
5. **Provider independence.** Scientific logic depends on generic contracts, not
   OpenAI-, Anthropic-, PubMed-, or Europe-PMC-specific code.
6. **Local and secure by default.** Bind locally, minimize exposed interfaces, and
   keep secrets out of the database, browser storage, logs, and artifacts.
7. **Honest uncertainty.** Unknown metadata remains unknown; incomplete usage
   produces unavailable or estimated cost, never false precision.
8. **Incremental scientific design.** Only agreed early stages are authoritative.

