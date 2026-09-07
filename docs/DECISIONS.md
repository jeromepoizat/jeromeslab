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

Routine implementation choices belong in code and tests. Add an ADR when a
choice constrains future architecture, security, scientific validity, data
compatibility, or user-visible workflow semantics.

