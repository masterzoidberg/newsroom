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
- **D-009:** Phase 06 source discovery uses bounded RSS/Atom and conditional
  HTTP acquisition with append-only provenance, multidimensional Source
  Profiles, and explicitly reviewed suggestions; it does not crawl openly,
  execute browser JavaScript, store article bodies by default, or assign a
  universal trust score. See ADR-004.
- **D-010:** Phase 07 keeps durable Jobs, Attempts, Runs, scheduler state, and
  budget reservations in SQLite. Claims are lease-based and transactional;
  retries, cancellation, idempotency, and budget exhaustion are explicit state
  transitions. Paid dispatch remains disabled by default. See ADR-005.
- **D-011:** Phase 08 keeps monitor policy, target integrity, approved scope
  snapshots, activity history, and vocabulary suggestions in SQLite. Relevance
  is a deterministic cascade from exact terms through local semantic and AI
  classification; suggestions remain pending until explicitly reviewed, and
  scheduler work carries only the monitor policy budget. See ADR-006.
- **D-012:** Phase 09 keeps Story resolution conservative and append-only. URL,
  temporal, entity/location, Claim, text/embedding, and event signals retrieve
  candidates; deterministic exclusions and low-confidence ambiguity handling
  prefer a new Story. Lineage groups repeated publications so publication count
  cannot masquerade as independent corroboration, while review attention remains
  independent from saved/dismissed state.

Phase 0 established the evaluation subsystem (`newsroom.evals`), a 30-case
labeled corpus, deterministic replay, reproducible metrics, and the v1 baseline.
The proposed first-release schema is in `plan/PROPOSED_SCHEMA_0001.md` (awaiting
architectural review; not yet implemented).
