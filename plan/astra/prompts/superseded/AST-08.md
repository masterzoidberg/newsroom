# AST-08 — Make paid admission durable across processes and reloads

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M2; size M; risk high. Dependencies: AST-07. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Use one durable budget authority for production and explicit connection tests.

Why now: Router-local counters reset across instances; new operations must not bypass existing durable analysis protections.

Inspect: newsroom/jobs.py; newsroom/ai.py; newsroom/article_analysis.py; tests/test_phase07_jobs.py; tests/test_phase21h_hardening.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Extend existing BudgetService reservations narrowly for connection-test work and supported paid capabilities. Preserve analysis idempotency, uncertain-call state and blocked-is-zero accounting. Recheck paid permission/config generation at admission, bound concurrent calls, keep estimated cost distinct from actual billing and account for configured SDK retry limits.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Replacing budget ledger, fabricated billing accuracy, automatic retry of uncertain remote work.

## Tests

Concurrent API/worker admission, restart/reset, disable race, failed/uncertain/blocked calls, explicit test allowance, global/per-work exhaustion.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Concurrent/restarted clients cannot overspend the configured reservation limits
- [ ] Blocked calls count zero; sent/uncertain calls remain conservatively accounted
- [ ] Test-connection permission does not enable background paid routing

## Completion evidence and required plan updates

Required: Concurrency and cost-ledger regression results. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Route local and retain ledger/reservations; never erase uncertain paid history.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

