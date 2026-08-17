# Newsroom

Standalone, evidence-first personal news intelligence.

Target workspace: `G:\Projects\Newsroom -v2`

This repository is the standalone successor to the completed Hermes Newsroom
reference implementation. **Hermes is not a runtime dependency.**

## Current state

The standalone deterministic core, evaluation foundation, evidence-ledger
vertical slice, Phase 05 local-first AI routing, Phase 06 bounded source
discovery/acquisition, Phase 07 durable jobs/scheduling, and Phase 08 persistent
monitors with semantic relevance are implemented. Phase 09 Story evolution,
lineage, novelty classification, and review-independent material-update
resurfacing are implemented. Phase 10 Research Questions, evidence-gap
suggestions, and bounded follow-up Jobs are implemented. Phase 11
evidence-bound Living Reports, timezone-aware Monitor briefings, durable alert
rules, acknowledgement, deduplication, and optional browser delivery state are
implemented. Phase 12 adds the responsive authenticated product workspace,
evidence/provenance inspection views, operator/admin surfaces, accessible
keyboard navigation, and an installable same-origin PWA shell with offline
fallback behavior.
Hosted providers remain optional and disabled by default.

## Authority

1. `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md` — product contract.
2. `plan/MASTER_PLAN.md` — implementation sequence and gates.
3. `docs/ARCHITECTURE.md` — architecture overview.
4. `docs/PORTING_AUDIT.md` — what was reused, redesigned, or rejected from v1.

## Bootstrap validation

```powershell
python -m pytest -q
```

The imported deterministic core and standalone storage tests must remain green.

## Runtime-data rule

No runtime database, logs, backups, secrets, provider caches, or downloaded
article bodies belong in this repository. The planned standalone runtime roots
are under `%LOCALAPPDATA%\Newsroom\...` with explicit dev/prod selection.

## v1 provenance

Reference implementation Git HEAD used for bootstrap:
`76a0be19ea3e0978743024d9283433a827c9e901`.

The v1 implementation report is retained under `reference/hermes-v1/`.
