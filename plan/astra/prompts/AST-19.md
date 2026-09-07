# AST-19 — Qualify the installed daily-use release candidate

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M5; size M; risk high. Dependencies: AST-05, AST-11, AST-12, AST-13, AST-14, AST-18. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Prove the selected product can be operated without engineering assistance.

Why now: Local tests do not qualify Windows installation, update, recovery or phone use.

Inspect: scripts/phase16_windows_deploy.ps1; newsroom/release.py; docs/OPERATIONS_RUNBOOK.md; docs/RECOVERY_RUNBOOK.md; plan/astra/PRODUCT_READINESS.md. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Build a named clean artifact and qualify in isolated Windows install. Execute Start Newsroom, Add AI Provider (fake plus separately authorized live if required), Dark Experience and full local daily-use matrix. Rehearse upgrade from prior schema/artifact, rollback/recovery, phone/PWA, offline/update behavior and credentials after sign-in. Record limitations and no-go results.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Publishing automatically, modifying active trial for qualification, claiming all browsers/platforms supported.

## Tests

Full applicable offline gates, installed lifecycle/credential/recovery tests, physical supported phone/PWA, end-to-end qualified evidence workflow.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Daily-use checklist has release-specific evidence and no unresolved P0/P1 blocker
- [ ] Upgrade/recovery and credential exclusion/access survive installed lifecycle
- [ ] Phone/PWA and all special acceptance tests pass or release scope explicitly excludes unqualified promises

## Completion evidence and required plan updates

Required: Release identity/manifests, completed acceptance report and known limitations. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Retain prior artifact and verified backup; roll back compatibly through managed recovery.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

