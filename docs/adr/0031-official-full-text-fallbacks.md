# ADR 0031: Official full-text fallbacks

- Status: Accepted
- Date: 2026-10-14
- Extends: ADRs 0029–0030.

## Decision

Resolve missing full text without an LLM or changing the exact retained record
pool. V1 adds PMC BioC by explicit PMCID and bioRxiv/medRxiv's documented DOI
metadata API followed by its declared JATS XML link. Never scrape arbitrary
publisher URLs, follow citation networks, bypass paywalls, or treat access as
quality. PDF/OCR, Unpaywall and additional repositories are deferred.

Only allowlisted official HTTPS hosts, standard ports, no URL credentials, at
most three redirects, 2 MB metadata / 20 MB XML, bounded timeouts/deadlines and
one transient retry are permitted. Pace requests, respect bounded Retry-After,
and make no concurrent source requests. Reject HTML, entity declarations,
document-ID mismatches and abstract-only BioC. Retain format and licensing;
BioC is transformed full text, not original article XML. Match one preprint API
version to the retained publication date and DOI; validate the version URL path
and JATS DOI/body. Ambiguity remains unavailable, not an upgrade to a newer
preprint or published article. Availability is scoped to enabled routes only.

Add `full_text_fallback` resource cursors, never reset primary resources or erase
attempts. New runs include fallbacks. Existing idle runs can explicitly append
missing fallback resources before an explicit resume; this is forbidden once
downstream work exists. Preparation alone sends no requests. Each newly queued
job separately snapshots the resolver policy and exact resource manifest; the
original acquisition policy and completed job snapshots stay unchanged.

Successful raw XML, hashes, URLs, timestamps, provider/format, metadata-attempt
reference, route outcomes and preprint metadata/version discovery remain saved.
Full-text coverage counts distinct retained records with either representation.
Europe PMC supplements still require Europe PMC XML; BioC/JATS recovery does not
imply access to supplementary files or launch recursive requests. Pause checks
also occur between resolver routes/discovery and text download.

PMC BioC's explicit leading "[Error] : No result can be found." response is a
provider-scoped unavailable outcome even when served with HTTP 200. Generic HTML
and malformed/mismatched XML stay failed. Record the absence-rule version; on
explicit retry, a bounded, digest-verified historical response from the matching
official PMCID endpoint may append a corrected outcome without refetching or
rewriting the previous failed attempt.

## Sources and consequences

The official [PMC BioC API](https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/)
and [bioRxiv API](https://api.biorxiv.org/) describe these routes.
[PMC developer guidance](https://pmc.ncbi.nlm.nih.gov/tools/developers/)
restricts automated full-text access to supported services, not website scraping.
No credential/contact email or new dependency/migration is required. Missing
identifiers, inaccessible text, unsupported hosts and version ambiguity can
leave records abstract-only. This is bounded acquisition, not evidence extraction.
