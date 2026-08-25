# Active Phase Plan

Phase 27 — Advanced Story Intelligence is complete.

Phase 28.5, Phase 28.75, and Phase 28.8 completed and accepted the architecture
correction chain. **Phase 29 — Prove the Intelligence** is the active
implementation phase and is the authority for temporal truth, closed-loop
Research proof, dogfood readiness, and controlled Full-vs-Lite validation.

Dogfood still requires an explicitly user-approved subject and approved Source
set; those inputs must not be invented. Phase 29 engineering may proceed while
that external configuration is pending. Phase 30 is not active and waits for
the Phase 29 dogfood window, frozen Full-vs-Lite evidence, and the intelligence
value decision gate.

The live repository is implementation authority. Preserve unrelated work;
never reset, clean, rewrite history, or push as part of phase closure.

## Authority

1. `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md` — product contract.
2. `plan/MASTER_PLAN.md` — implementation sequence and gates.
3. `docs/ARCHITECTURE.md` — architecture overview.
4. `Phase 29` — current intelligence-proof implementation and validation plan.

## Validation baseline

```powershell
python -m pytest -q
ruff check newsroom tests
```

Frontend checks run from `frontend` with `npm run lint`, `npm run typecheck`,
and `npm run build`. Mypy remains informational under the existing baseline
policy. Dogfood and a final Full-vs-Lite quality verdict remain external actions
after explicit acceptance and snapshot selection.
