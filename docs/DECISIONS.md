# Architecture Decision Log

Formal ADR files will be added as Phase 0 begins. Initial decisions accepted by
this scaffold:

- **D-001:** Standalone Newsroom is the target first released product; Hermes is
  reference-only, not a runtime dependency.
- **D-002:** Evidence Ledger functionality enters the first research vertical
  slice, not a later platform phase.
- **D-003:** Monitor targets are independent from acquisition channels/providers.
- **D-004:** Source, Document, and DocumentVersion are distinct entities; Evidence
  references a version.
- **D-005:** False merges are more costly than occasional false splits.
- **D-006:** Free/direct/local processing is default; paid retrieval/inference is
  bounded escalation.
- **D-007:** SQLite is the initial DB and durable queue; infrastructure upgrades
  require measured need.
