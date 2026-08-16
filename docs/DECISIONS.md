# Architecture Decision Log

Formal ADR records are under `docs/adr/`.

- **D-001 / ADR-001:** Standalone Newsroom is the target first released product;
  Hermes is reference-only, not a runtime dependency.
- **D-002 / ADR-002:** Evidence Ledger functionality enters the first research
  vertical slice, not a later platform phase.
- **D-003:** Monitor targets are independent from acquisition channels/providers.
- **D-004:** Source, Document, and DocumentVersion are distinct entities; Evidence
  references a version.
- **D-005:** False merges are more costly than occasional false splits.
- **D-006:** Free/direct/local processing is default; paid retrieval/inference is
  bounded escalation.
- **D-007:** SQLite is the initial DB and durable queue; infrastructure upgrades
  require measured need.
- **D-008:** Phase 05 AI capabilities are narrow, validated, local-first, and
  routed through hard global/per-work paid budgets; benchmark results and
  limitations are recorded in ADR-003.

Phase 0 established the evaluation subsystem (`newsroom.evals`), a 30-case
labeled corpus, deterministic replay, reproducible metrics, and the v1 baseline.
The proposed first-release schema is in `plan/PROPOSED_SCHEMA_0001.md` (awaiting
architectural review; not yet implemented).
