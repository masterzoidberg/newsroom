# AST-02 — Identify application instances and diagnose port conflicts

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M1; size M; risk high. Dependencies: AST-01. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Add ownership-aware preflight and bind-failure diagnosis for the configured endpoint.

Why now: Current 8127 already serves Newsroom but duplicate startup blindly binds.

Inspect: newsroom/runtime.py; newsroom/config.py; newsroom/app.py; tests/test_runtime_config.py; tests/test_phase16_deployment.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Add a stable non-secret installation identity and process identity checks using root/role/release plus PID creation time. Use an OS exclusive lock, not a PID-file-only guard. Define status protocol for matching, unmanaged, foreign and unknown owners. Handle the bind race after preflight. Permit healthy verified reuse; never terminate or silently move ports.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Starting a new service architecture, taking over active unmanaged trial processes, arbitrary process termination.

## Tests

Temporary sockets/processes: same instance, foreign listener, wrong root, stale PID, concurrent preflight and bind race.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Matching healthy instance is reused without a second API bind
- [ ] Foreign/mismatched/unknown ownership gives actionable fixed-port diagnosis and no kill
- [ ] Concurrent launches and PID reuse cannot falsely identify another process

## Completion evidence and required plan updates

Required: Process/socket test results and redacted identity/status examples. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert launcher preflight; retain existing explicit operator commands.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

