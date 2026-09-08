# AST-03 — Supervise existing runtime components safely

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M1; size M; risk high. Dependencies: AST-02. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Own one API, worker and scheduler with bounded startup, shutdown and recovery.

Why now: Port checks alone do not ensure processing or prevent child divergence.

Inspect: newsroom/runtime.py; newsroom/worker.py; newsroom/scheduler.py; newsroom/jobs.py; tests/test_phase07_jobs.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Implement a small supervisor around existing child entry points with one shared manifest/root/release. Add component heartbeat and graceful drain/control. Coordinate migration ownership and child reconciliation. Verify 120-second job lease vs long-running handlers; implement only a demonstrated minimal renewal/ownership correction needed for safe supervision. Bound child restart/backoff and preserve uncertain paid work.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Replacing durable jobs, distributed workers, task queue rewrite, forced termination of unmanaged processes.

## Tests

Subprocess crash/restart, supervisor crash with children alive, long handler beyond lease, cancellation, stale heartbeat, graceful drain and bounded restart exhaustion.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] One owned child per required role survives repeated/concurrent launches
- [ ] Stop/restart drains or reports deadline safely and never duplicates downstream work or uncertain paid calls
- [ ] Failure/restart bounds and long-handler lease safety have explicit test evidence

## Completion evidence and required plan updates

Required: Lifecycle state table, subprocess results and owned-process count evidence. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Disable new supervisor in isolated install and use existing commands; no data rollback.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

