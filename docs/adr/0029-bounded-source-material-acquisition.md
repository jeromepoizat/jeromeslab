# ADR 0029: Bounded source-material acquisition

- Status: Accepted
- Date: 2026-10-13
- Builds on: ADRs 0015, 0026 and 0028.

## Decision

After relevance selection is validated, collect available material for that exact
immutable source-identity pool. Acquisition is deterministic, not an LLM planning,
screening, quality-assessment or evidence-extraction operation. Missing full text
does not exclude a retained record and does not prove it is unavailable elsewhere.

V1 uses the official Europe PMC API only: refresh core metadata, retrieve supported
full-text XML by explicit identifier, collect supplements declared by saved XML,
and inventory data-literature links. Do not recursively fetch linked databases,
references, arbitrary publisher URLs, or execute downloaded files. PDFs, OCR,
user uploads and additional repositories remain future extensions.

Freeze the inclusion digest, retrieval metadata/page references, adapter version,
limits and task identities. Store raw responses as immutable files with request URL,
HTTP status, retrieval timestamp, SHA-256, byte size, source-native metadata, XML
license statements and inventories. Source annotations and links are not validated
experimental evidence. An article license is recorded as supplement context, not
assumed to cover every supplementary file.

The initial fixed limits are 2 MB per metadata/data-link response, 20 MB per XML,
50 MB per supplement archive, and 200 MB declared uncompressed size / 1,000 ZIP
entries. ZIPs are inventoried without extraction or execution; per-file CRC/content
verification is not claimed. Data links request up to 1,000 entries; incomplete
inventories are explicitly marked partial and preserve the reported count. Reject
XML internal entities and unsafe archive paths. Only official HTTPS redirect hosts
are allowed. Transient network requests retry at most twice, with bounded timeouts
and backoff; unavailable, unsupported and oversized material has explicit states.

There is one acquisition run per project. Each start/resume is a sequential queue
job. Pause finishes the current request and saves its outcome before stopping.
Resume retries unfinished/failed resources only, never replaces successful assets,
and appends immutable attempts. A run can complete with individual failures and
offer an explicit retry. Queue cancellation, unexpected errors and restart leave
it paused; restart never silently starts network traffic. Downstream jobs lock
resume/retry in this project and must snapshot exact consumed material versions.

Separate per-job task rows retain exact manifests without bloating global job
responses. Status queries return aggregated counts and at most 25 record previews;
full inventories remain saved locally. Network activity happens outside short,
managed database transactions.

## Consequences

Migration 0030 adds acquisition runs, frozen source snapshots, resource cursors,
immutable attempts and job task manifests. Later extraction needs a reviewed
protocol and material-version checkpoint; it must not infer missing observations
from access failures. This step does not resolve publication/study identity,
access bias, scientific reliability, or peptide-design decisions.
