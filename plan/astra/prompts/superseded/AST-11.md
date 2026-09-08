# AST-11 — Build functional AI Providers and cost settings

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M2; size M; risk medium. Dependencies: AST-10. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Let the owner configure and understand real Article Analysis routing in Settings.

Why now: The current Settings renders raw rows and budget JSON without configuration controls.

Inspect: frontend/src/views/AdminViews.tsx; frontend/src/lib/api.ts; frontend/src/lib/types.ts; frontend/src/styles.css; newsroom/domain_api.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Add named Settings sections and provider Add/Edit/Test/Enable/Disable/Model/Remove/Set-default controls. Show fixed mask/configured flag, offline explanation, supported capability, active model/generation, validation and failure, paid switch and typed existing budget controls. Clear secret after submit and label estimated usage honestly. Split a component only if needed for contained readability.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Brand catalog, remote Ask promise, browser secret storage, redesigning all Settings.

## Tests

Browser fake-provider Add AI Provider acceptance, bad inputs, stale edits, failed removal, screen-reader labels, save/refresh and next worker operation.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Full special acceptance succeeds with a fake provider and actual configured worker path
- [ ] No raw secret is returned/persisted in browser state/storage after submission
- [ ] User can see offline/active model/paid/budget/failure/reload state and recover without terminal

## Completion evidence and required plan updates

Required: Journey screenshots, API/worker identity proof and sentinel audit; live paid test remains separately authorized. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert UI only; metadata/vault remain manageable through authenticated API.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

