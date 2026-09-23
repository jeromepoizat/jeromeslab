# ADR 0016: Charter-derived evidence scope before query generation

- Status: Accepted
- Date: 2026-09-22

## Context

An approved peptide-discovery charter defines what the current investigation must
answer, but it does not fully determine which related entities, evidence stages,
populations, comparators, or publication boundaries should be retrieved. Asking
these questions during initial project framing would force literature-search
decisions before the investigation was stable. Generating database queries
directly from a charter would hide whether every objective is covered and which
retrieval restrictions came from the user.

Peptide identity, sequence, target, pathway, activity, efficacy, stability,
exposure, selectivity, safety, delivery, and clinical evidence are potentially
relevant domains, not a universal checklist. Their relevance depends on the
approved charter and the maturity of the peptide-discovery project.

## Decision

After exact charter approval and before scientific-source strategy or query
generation, the application generates one evidence-search scope questionnaire.
The job consumes the exact approved charter artifact and approval.

The provider output contains two deliberately separate layers:

1. **Charter-derived evidence themes.** Every current charter evidence objective
   must appear in at least one visible theme. These themes are included by the
   approved investigation and are not presented as optional filters.
2. **User-controlled evidence-scope questions.** Zero to six questions may ask
   about retrieval and screening choices such as related-entity breadth,
   evidence stages, populations, comparators, indirect mechanistic context, or
   exceptional operational limits.

The questionnaire must not ask the user to predict findings, select a mechanism
or candidate without evidence, remove a current charter objective, or choose
supportive evidence while excluding negative results. Relevant negative, null,
contradictory, failed, and adverse evidence is a cross-cutting requirement.

Recommendations are advisory. The user must confirm answers and may choose a
different option, provide a note-only answer, or select **Not sure**. Uncertainty
does not block progress and should produce inclusive, separately labelled
evidence strata in the later strategy. A zero-question result receives a
deterministic application-created empty answer artifact.

Generated questions, exact answers, manual edits, hashes, prompt, model, call,
and approved-charter input are preserved through the existing immutable artifact
and effective-version contracts. Answers remain editable until downstream work
consumes them.

The questionnaire does not generate database syntax or select unavailable named
sources. A later, separately reviewable evidence-investigation strategy will map
the charter themes and confirmed answers into source categories, eligibility
principles, and purpose-labelled query families. Source-specific query generation
then consumes that strategy.

## Consequences

The interface can remain approachable by showing mandatory themes and ordinary
scope decisions while keeping the versioned prompt behind advanced disclosure.
Broad exploratory projects are not forced to choose a target, candidate, or
evidence conclusion prematurely.

Query generation requires another approved design and implementation slice. The
questionnaire alone does not imply that a search protocol is complete or that
the enabled sources can satisfy every evidence theme.
