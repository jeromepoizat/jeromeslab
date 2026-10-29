# ADR 0030: Provider-scoped access limitations and dependency-blocked resources

- Status: Accepted
- Date: 2026-10-14
- Refines: ADR 0029.

## Decision

Distinguish unavailable material at the enabled provider from acquisition failures
that may be retried. Europe PMC metadata can describe publicly readable papers or
preprints whose full text is not hosted there or is outside the supported XML
open-access subset. Neither an abstract-only record nor the absence of a PMCID
proves a paywall or globally private material.

Before requesting XML, source-owned availability rules check successful metadata:
explicit `inEPMC=N` or `isOpenAccess=N` yields a local `unavailable` outcome with
the metadata-attempt reference, flags, rule version and provider-only scope. Missing
flags remain unknown and permit an endpoint request. HTTP 500 or network errors
alone never become a no-access classification. Already-saved XML stays unchanged.

When a resource cannot be attempted because another failed, use `blocked`, not
another failure count. A failed metadata lookup can block missing-identifier text;
failed XML blocks supplementary discovery. Resume includes blocked tasks after
their prerequisites alongside unfinished/failed tasks. Unavailable resources do
not enter later retry manifests. No-supplement declarations remain not applicable;
bounded-size exclusions remain separate from both access and failures.

Old attempts are immutable. Existing failed cursors can acquire new local access
decisions on the next explicit resume/retry, without repeating known-unavailable
downloads. The new queue snapshot records the access-rule version; prior limits,
selection, files, attempts and completed history are not rewritten. No live run is
automatically reclassified or started when code is installed.

Europe PMC search already includes preprint metadata when queries permit it. XML
acquisition may use supported hosted PPR identifiers, but this is not a direct
bioRxiv/Research Square/publisher downloader. Adding legally supported full-text
resolution elsewhere is a separate future integration; it must preserve document
identity, preprint versions, licensing and the fixed retained source pool.

## Consequences

The UI uses **Unavailable via Europe PMC**, **Retryable failure**, **Blocked by
dependencies**, and **Size limit** rather than a blanket no-access/failure label.
This refines acquisition outcomes without a database migration or changes to
scientific relevance, source selection, or study quality.
