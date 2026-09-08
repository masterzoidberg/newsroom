# AST-12 — Make first Watch and scoped use possible without IDs

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M3; size M; risk medium. Dependencies: AST-11. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Complete the first-value path for a normal user.

Why now: Current Watch and scoped Ask forms require canonical IDs; empty collection views cannot create needed records.

Inspect: frontend/src/views/WatchManagementView.tsx; frontend/src/views/AdminViews.tsx; frontend/src/views/AskView.tsx; frontend/src/components/AuthView.tsx; newsroom/domain_api.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Use existing APIs for named topic creation/selection, reviewed source entry and simple cadence presets within Watch setup. Provide contextual or named scope selection for Ask. Detect setup availability safely, replace trial-specific defaults and API jargon. Keep advanced policy/IDs available deliberately, prevent unsupported direct Monitor creation.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Changing approved trial sources, auto-approving candidates, new Monitor target adapters, generic onboarding platform.

## Tests

Fresh DB browser user journey: setup → named topic/source/Watch → due fixture → Home/evidence → scoped Ask/refusal; edit/disable persistence and invalid input.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] First Watch requires no copied IDs or terminal/API calls by user
- [ ] Source review/pinned scope and offline zero-spend behavior are preserved
- [ ] Contextual Ask and empty states give a working next action without inventing evidence

## Completion evidence and required plan updates

Required: Fresh-install journey evidence and integration checks. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert workflow UI; preserve user-created canonical records and existing APIs.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

