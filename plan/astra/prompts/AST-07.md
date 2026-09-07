# AST-07 — Store credentials in an approved operating-system vault

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M2; size M; risk high. Dependencies: AST-06. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Implement write-only credential lifecycle without keys in SQLite, backups or responses.

Why now: Metadata needs a real secret boundary before any provider controls can be safe.

Inspect: pyproject.toml; newsroom/domain_api.py; newsroom/operations.py; newsroom/article_analysis.py; AI metadata service introduced by AST-06. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Add reviewed keyring dependency and explicit approved platform backend selection. Implement versioned credential set/rotate/read/delete through one narrow interface; same-owner namespace, two-store failure compensation, disabled-before-delete behavior and truthful removal failures. Fake store for CI; fail closed with unsupported backend. Mask model/request representations and validation errors.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Plaintext fallback, encrypted SQLite credentials, exposing stored keys, modifying existing user credentials.

## Tests

Sentinel tests through response/validation/log/telemetry/DB/full-backup/logical-export/build; store failures, rotation rollback, locked/unavailable backend; disposable Windows same-user integration.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Sentinel exists only in submitted request/process memory and OS vault, never persisted diagnostic/export surfaces
- [ ] Save/rotation/deletion failures preserve a truthful recoverable configuration
- [ ] Windows owner access works; non-Windows approved backend or local-only behavior is explicit

## Completion evidence and required plan updates

Required: Secret-leak test matrix and disposable vault integration results without secret contents. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Disable provider and remove only task-created vault entries; preserve public metadata/history.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

