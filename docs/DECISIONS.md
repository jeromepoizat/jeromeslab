# Decision index

Accepted decisions are authoritative until superseded by a newer ADR. Proposed or
unresolved ideas in other documentation are not decisions.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](adr/0001-local-web-application-stack.md) | Local React client and FastAPI service | Accepted |
| [0002](adr/0002-immutable-lineage-and-project-forks.md) | Immutable workflow lineage and checkpoint forks | Accepted |
| [0003](adr/0003-sqlite-and-file-artifact-storage.md) | SQLite metadata with immutable file artifacts | Accepted |
| [0004](adr/0004-single-worker-persistent-queue.md) | Persistent sequential queue with one V1 worker | Accepted |
| [0005](adr/0005-native-credential-storage.md) | Native credential store and non-disclosure | Accepted |
| [0006](adr/0006-llm-calls-as-provenance.md) | First-class LLM call and historical cost provenance | Accepted |
| [0007](adr/0007-self-bootstrapping-installation.md) | No preinstalled language runtimes for ordinary users | Accepted |
| [0008](adr/0008-replay-provider-and-demo-project.md) | Explicit replay provider and bundled demo project | Accepted |
| [0009](adr/0009-user-selected-research-workspace.md) | User-selected research workspace | Accepted |
| [0010](adr/0010-single-local-application-instance.md) | One local application instance | Accepted |
| [0011](adr/0011-global-llm-provider-configuration.md) | Global provider defaults with filtered live model discovery | Accepted |
| [0012](adr/0012-intent-and-scope-clarification-before-search.md) | Clarify research intent and scope before formal search | Amended by 0013 |
| [0013](adr/0013-evidence-led-iterative-research-cycles.md) | Evidence-led iterative research cycles | Accepted |
| [0014](adr/0014-charter-drafts-and-approval.md) | Charter drafts, explicit version approval, and preserved regeneration attempts | Accepted |
| [0015](adr/0015-specialize-in-therapeutic-peptide-discovery.md) | Specialize the product in evidence-guided therapeutic peptide discovery | Accepted |
| [0016](adr/0016-charter-derived-evidence-scope.md) | Separate charter-derived evidence themes from user-controlled search scope before query generation | Accepted |
| [0017](adr/0017-reviewed-evidence-investigation-strategy.md) | Approve a reviewable evidence-investigation strategy before source-specific queries | Accepted |
| [0018](adr/0018-reviewed-europe-pmc-query-drafts.md) | Review Europe PMC query drafts before execution | Amended by 0019 |
| [0019](adr/0019-approve-and-run-europe-pmc-queries.md) | Approval atomically queues exact-version Europe PMC retrieval | Accepted |
| [0020](adr/0020-provisional-same-article-check.md) | Read-only provisional same-article grouping after retrieval | Accepted |
| [0021](adr/0021-relevance-preparation-and-bounded-scoring.md) | Distinct-source sampling, relevance-only calibration, and bounded future scoring | Accepted |
| [0022](adr/0022-sample-informed-relevance-scoring-prompt.md) | Generate and review a compact relevance prompt from approved context and a seeded sample before calibration | Accepted; amends 0021 |

Routine implementation choices belong in code and tests. Add an ADR when a
choice constrains future architecture, security, scientific validity, data
compatibility, or user-visible workflow semantics.
