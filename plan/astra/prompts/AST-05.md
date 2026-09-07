# AST-05 — Ship one Start Newsroom entry point

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M1; size M; risk high. Dependencies: AST-04. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Make normal launch and reboot/sign-in recovery require no terminal commands.

Why now: The existing installer generates three launchers and three independent tasks.

Inspect: scripts/phase16_windows_deploy.ps1; newsroom/release.py; newsroom/runtime.py; docs/OPERATIONS_RUNBOOK.md; tests/test_phase16_deployment.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Generate one obvious shortcut/hidden launcher invoking the supervisor and opening the product. Register only that authority at user sign-in with same-user identity. Namespace install tasks; detect legacy tasks and provide a reviewed migration action without silently disabling unrelated tasks. Document browser-close/background and pre-login limitations.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Tray framework, Windows service, pre-login monitoring guarantee, production task changes during tests.

## Tests

Clean temporary Windows installation; Start Newsroom special acceptance including reboot/sign-in, duplicate launch, foreign port and locked/wake states.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] One shortcut starts all components and opens the product
- [ ] Repeated launch, browser close and reboot/sign-in behave as documented with one authority
- [ ] Legacy installation handling is explicit and no unrelated scheduled tasks/processes are altered

## Completion evidence and required plan updates

Required: Installed artifact identity, Windows qualification checklist and redacted task/process evidence. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Remove only the new installation's registration/shortcut; preserve runtime and existing legacy configuration.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

