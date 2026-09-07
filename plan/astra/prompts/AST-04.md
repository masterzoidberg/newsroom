# AST-04 — Expose honest component status and recovery controls

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M1; size M; risk medium. Dependencies: AST-03. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Replace misleading service/synced labels with actionable whole-app state.

Why now: Public liveness and browser network status do not prove worker/scheduler progress.

Inspect: newsroom/app.py; newsroom/domain_api.py; frontend/src/App.tsx; frontend/src/components/AppShell.tsx; frontend/src/views/AdminViews.tsx. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Expose authenticated bounded runtime status and named restart/stop requests to the supervisor through its protected control channel. Poll lightweight heartbeats with sensible backoff; distinguish API down, worker/scheduler degraded, idle, stopped and starting. Keep expensive integrity scans out of frequent status polling. Show an external launcher recovery path when API is unavailable.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Arbitrary command execution, exposing root paths publicly, new general diagnostics dashboard.

## Tests

Auth/CSRF/control allowlist tests; browser component-down and network-only failure; stop acknowledgement before API closes.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Status identifies missing/stale components and distinguishes no work from failure
- [ ] Authorized named controls work and unauthorized/CSRF-invalid calls fail
- [ ] Browser does not claim Synced based only on navigator.onLine or API liveness

## Completion evidence and required plan updates

Required: API contract, mocked health failures and browser screenshots. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert UI/control routes while retaining safe supervisor operation.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

