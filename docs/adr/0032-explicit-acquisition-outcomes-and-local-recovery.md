# ADR 0032: Explicit acquisition outcomes and local recovery

- Status: Accepted
- Date: 2026-10-15
- Refines: ADRs 0029–0031.

## Decision

Resource outcomes must distinguish acquisition completeness from access limitations:

- `saved`: verified usable material, preserved with its provenance.
- `failed`: temporary network, rate-limit or service failure; eligible for retry.
- `unavailable`: explicit absence/access denial at the checked route; never retry
  the same unavailable resource. This is not a global claim about other sources.
- `unsupported`: no enabled route/identifier; availability elsewhere is unknown.
  Do not repeat the same unsupported request or call the material unavailable.
- `needs_review`: unresolved identity, XML/format or version verification; not
  unavailable and not a blind-download retry. Preserve raw evidence for recovery.
- `blocked`: prerequisite failure; retry with the prerequisite, not as a separate
  access failure. A review/unsupported prerequisite propagates that limitation.
- `skipped_limit`: excluded by the current safety limit, not unavailable. A
  same-policy retry does not help. `pending`/`not_applicable` retain their meaning.

Only pending/failed/blocked resources enter normal acquisition retry manifests.
Finishing the queue does not establish that all available material was recovered.
The UI names unresolved outcomes and distinguishes resource counts from papers.
All retained source records remain in the investigation; missing full text must
not become silent exclusion or fabricated evidence. Later extraction must freeze
exact consumed material and explicitly handle unresolved coverage; no extraction
checkpoint or user acknowledgement workflow is implemented by this decision.

Normalize numeric and `PMC`-prefixed BioC document IDs. When the document ID is
unknown/absent, explicit PMC-specific `article-id_pmc`, `article-id_pmcid` or
`article-id_pmcaid` fields may establish the exact retained PMCID. Every declared
usable PMC identifier must agree; reject contradictions, unsupported identifiers,
multiple documents and unverified/absent full-text body passages. Do not accept
title similarity or body mentions as identity evidence. Version the parser.

An explicit recovery operation may reinterpret digest-verified saved responses
without any source or LLM requests, appending new attempts with parent attempt,
raw hash, parser/classifier and local-only job-manifest provenance. Existing
attempts/files are never rewritten, successful resources are not replaced, and
downstream dependents require a fork. Atomically claim this recovery as the one
active research operation; reject active/queued competing work. Recovery may also
correct historical no-route outcomes from unavailable to unsupported.

## Consequences

No schema migration or new dependency is needed: resource status columns are
already strings. Existing failed saved XML can be recovered instead of downloaded
again; unknown/malformed responses remain visible for review. These categories
supersede ADR 0031's use of unavailable for ambiguous versions and failed for all
malformed responses. Confirmed absence remains separate from transient HTTP errors.

Preprint routing uses the explicit bioRxiv/medRxiv publisher and a validated DOI,
not a fixed registrant prefix. bioRxiv's [current archive](https://www.biorxiv.org/archive)
also includes `10.64898` identifiers. A versioned route fix may append a pending
outcome for a newly supported record, preserving its older unsupported/review
history; fetching still requires explicit resume. Never silently classify a
newly supported identifier as unavailable because an older adapter missed it.
