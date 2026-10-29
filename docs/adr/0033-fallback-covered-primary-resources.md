# ADR 0033: Fallback-covered primary resources

- Status: Accepted
- Date: 2026-10-15
- Refines: ADRs 0029–0032.

## Decision

A failed primary XML endpoint is not missing full text when verified fallback
text is already saved for that exact retained source. Mark its mutable primary
resource cursor `recovered`, exclude it from ordinary retry manifests and failure
counts, and show the fallback provider/attempt reference. Do not mark the primary
endpoint successful or unavailable, and do not count the recovered cursor as a
second saved full text. Saved fallback bytes remain the actual acquired material.

When fallback text succeeds after a primary failure in the same job, that new
immutable fallback attempt records the primary resource and failed attempt it
covers; the mutable primary cursor becomes recovered atomically. The previous
primary attempt stays failed and immutable. Existing completed runs can append a
local-only coverage-resolution attempt linked to the saved fallback, guarded by
the existing single-operation and downstream-dependency rules. No network or LLM
call is required to reconcile coverage; successful assets are not replaced.

Supplement availability is separate. If primary XML is absent and saved source
metadata explicitly says `hasSuppl=N`, record not applicable with the metadata
attempt reference. If saved primary XML does declare supplements, its declaration
takes precedence over that summary flag. If only fallback text is available and
no explicit absence is established, mark supplementary discovery unsupported by
the enabled adapter, not blocked indefinitely or unavailable everywhere. A
full-text fallback does not establish that supplementary files were retrieved.

## Consequences

No migration or new dependency is needed. Current progress can reflect effective
coverage without editing historical HTTP outcomes. The resource inspector names
recovery and preserves primary-route history; remaining size limits and genuinely
unresolved access are still shown separately. Later extraction must consume the
exact saved fallback attempt, not the recovered primary cursor as if it were XML.
