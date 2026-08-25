# Active Phase Plan

Phase 27 — Advanced Story Intelligence is complete.

Phase 28.5 and Phase 28.75 implemented the architecture correction chain but
remain subject to final acceptance. **Phase 28.875 — Final Acceptance Closure**
is the active phase and is the authority for the remaining semantic, Research,
benchmark, migration, documentation, and repository-artifact gates.

Phase 29 is **blocked until Phase 28.875 is independently reviewed and
accepted**. No Phase 29 implementation has started.

After acceptance, dogfood begins only with an explicitly user-approved subject
and approved Source set. Phase 29 may then proceed in parallel with the real
Watch dogfood window. Phase 30 waits for the dogfood window and the resulting
Full-vs-Lite evidence.

The live repository is implementation authority. Preserve unrelated work;
never reset, clean, rewrite history, or push as part of phase closure.

## Authority

1. `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md` — product contract.
2. `plan/MASTER_PLAN.md` — implementation sequence and gates.
3. `docs/ARCHITECTURE.md` — architecture overview.
4. `Phase 28.875` — current acceptance closure.

## Validation baseline

```powershell
python -m pytest -q
ruff check newsroom tests
```

Frontend checks run from `frontend` with `npm run lint`, `npm run typecheck`,
and `npm run build`. Mypy remains informational under the existing baseline
policy. Dogfood and a final Full-vs-Lite quality verdict remain external actions
after explicit acceptance and snapshot selection.
