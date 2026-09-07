# AST-14 — Wrap verified backup and recovery in owner controls

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M3; size M; risk high. Dependencies: AST-13. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Provide safe backup/recovery/update preparation without remembered commands.

Why now: Existing SQLite operations are useful but require manual runtime/process handling.

Inspect: newsroom/operations.py; newsroom/cli.py; newsroom/domain_api.py; frontend/src/views/AdminViews.tsx; docs/RECOVERY_RUNBOOK.md. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Expose named backup/status/diagnostic actions using existing verified operations and managed lifecycle. Keep restore/update as clearly reviewed workflows with exact target/backup identity and stopped writers; stage before replacement and retain failure evidence. Diagnostics use explicit non-secret allowlists. Reuse release verification rather than an auto-updater service.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Unattended destructive restore, arbitrary filesystem API, exporting credentials or raw private content in support bundles.

## Tests

Temporary populated DB backup/restore equality/integrity, corrupt backup, disk/write failure, active-writer refusal, secret exclusion, UI recovery state.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Owner can create and verify a backup through a clear action
- [ ] Restore/update preparation proves target identity, stopped writers and safe failure preservation
- [ ] Diagnostic/export output excludes credentials and gives actionable status

## Completion evidence and required plan updates

Required: Temporary installation recovery report, integrity results and UI screenshots. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Keep prior verified database/artifact; rollback only using supported recovery, not live file copies.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

