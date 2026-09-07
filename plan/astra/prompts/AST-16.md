# AST-16 — Continue the approved observation with honest usefulness evidence

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M4; size S; risk medium. Dependencies: AST-01. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Complete the already-started observation protocol without resetting or inventing results.

Why now: Short checkpoint has insufficient active time/events; calendar duration is a real dependency.

Inspect: docs/DOGFOOD_CONTRACT.md; docs/reviews/PHASE_29_OBSERVATION_PROTOCOL.md; docs/reviews/PHASE_29_WEEK_1_CHECKPOINT.md; docs/reviews/PHASE_29_HUMAN_USEFULNESS_LOG_TEMPLATE.md; docs/reviews/PHASE_29_UAP_PROSPECTIVE_EXPERIMENT_V1.md. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Use existing approved Watch and frozen boundary; collect safe aggregates and request actual owner usefulness entries. Track active time, no-event intervals, source/content quality, missed changes and repairs. Keep raw data/logs outside git. Log any authorized runtime/config change as a segment. Extend when volume/time is insufficient.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Starting an automation without request, manufacturing usefulness ratings, redefining criteria or changing sources/provider silently.

## Tests

Validate observation interval arithmetic, provenance and event denominators; follow existing protocol check commands without modifying data unnecessarily.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Required minimum window and eligible observation evidence exist, or task stays explicitly incomplete
- [ ] Human usefulness log is real and changes/outages are accounted for
- [ ] Private data stays outside repository and safe summary cites frozen identities

## Completion evidence and required plan updates

Required: Dated safe observation report, private evidence references and human review completion. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Observation cannot be undone; preserve original records and append corrections.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

