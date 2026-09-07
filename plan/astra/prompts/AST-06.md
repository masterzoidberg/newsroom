# AST-06 — Create typed public AI configuration metadata

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M2; size M; risk medium. Dependencies: AST-05. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Establish the canonical non-secret connection/capability configuration service.

Why now: Generic settings plus environment capture cannot support coherent provider management.

Inspect: newsroom/migrations.py; newsroom/domain.py; newsroom/domain_api.py; newsroom/article_analysis.py; tests/test_phase21_article_analysis.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Implement additive metadata/routes/generation schema from AI_PROVIDER_SETTINGS; allocate current next migration after rechecking ledger. Create a typed service with optimistic revision control, supported-capability validation and no secret storage. Retain one existing budget switch and local defaults.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Credential persistence, provider calls, remote support for all capability interfaces.

## Tests

Fresh/upgrade schema tests, invalid metadata and secret URL rejection, stale revision, local default and metadata export policy.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Only public bounded metadata and opaque references persist
- [ ] Unsupported routes/stale updates fail deterministically; local is default
- [ ] Schema-36 upgrade preserves existing data and history

## Completion evidence and required plan updates

Required: Migration/contract tests and reviewed schema diff. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Disable routes/use local; do not down-migrate a populated DB; restore verified backup only when deliberately needed.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

