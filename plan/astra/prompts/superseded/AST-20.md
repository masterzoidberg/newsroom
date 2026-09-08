# AST-20 — Remove only proven obsolete completion scaffolding

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P2; milestone M5; size S; risk medium. Dependencies: AST-19. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Reduce permanent support burden after release paths are known.

Why now: Phase naming is not itself a defect; only demonstrated redundant entry points should be retired.

Inspect: plan/astra/DELETE_DEFER_KEEP.md; scripts/phase12_browser_smoke.py; scripts/phase12_server.py; newsroom/domain.py; README.md. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Trace callers/tests/data dependencies for each candidate in DELETE_DEFER_KEEP. Retire or guard obsolete normal-user launcher/smoke paths once replacements cover them; correct stale runtime comments. Delete only demonstrated unused code and document public compatibility impact. Keep history/eval tools and migration chains.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Bulk phase rename, deleting old plans/reference code, removing evidence history/legacy accounting or unrelated cleanup.

## Tests

Reference search, affected regression tests and clean supported entry-point smoke.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Each deletion has caller/data/coverage evidence
- [ ] Normal docs expose one startup authority and no unsafe test defaults
- [ ] Historical data/migrations/contracts remain readable and tests pass

## Completion evidence and required plan updates

Required: Candidate-by-candidate disposition and focused diff/check results. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert bounded deletion; no history/data removal.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

