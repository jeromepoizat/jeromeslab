# Repository guidance for coding agents

Jerome's Laboratory treats the repository as its durable project memory. Do not
rely on chat history for product or architecture decisions.

Before substantial work, read in this order:

1. `docs/STATUS.md`
2. `README.md`
3. the relevant files under `docs/`
4. applicable accepted ADRs under `docs/adr/`
5. the code and tests affected by the task

Keep these invariants unless a new, explicit decision supersedes them:

- bind the local server to `127.0.0.1` by default;
- keep scientific workflow logic independent of LLM and literature providers;
- preserve immutable completed history, exact inputs, original outputs, effective
  edited versions, and provenance links;
- fork at a checkpoint instead of rewriting history with downstream dependents;
- never store or return API secrets outside the native credential store;
- execute at most one research job at a time in V1;
- do not require end users to preinstall Python, Node.js, `uv`, or pnpm;
- do not present later scientific stages as settled designs.

After meaningful work, run proportionate checks and update `docs/STATUS.md`.
Update other documentation only when its subject changed. Add an ADR for a
meaningful architectural or product decision, not for routine implementation
details.
