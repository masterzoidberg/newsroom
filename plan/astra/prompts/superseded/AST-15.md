# AST-15 — Verify representative content-to-value paths

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M3; size M; risk high. Dependencies: AST-14. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Separate working pipeline plumbing from useful article/Story yield and fix only proven blockers.

Why now: A3 broad-page path deferred and metadata-only path succeeded; neither proves normal article usefulness.

Inspect: newsroom/acquisition.py; newsroom/ai.py; newsroom/automatic_story_resolution.py; tests/test_phase21_article_analysis.py; docs/reviews/PHASE_29_PIPELINE_REHEARSAL.md. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Build a small lawful sanitized fixture set representing article body, navigation-heavy page, feed metadata, unchanged content and blocked source. Record input quality and stage outcomes through production handlers. Reproduce before any minimal content extraction/local candidate repair; preserve exact-span hashes and conservative resolution. If no proven defect, record evidence and propose a separate bounded follow-up rather than tuning thresholds.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Relaxing retrieval saturation, changing frozen trial sources/corpus, claiming metadata as full body, bypassing source restrictions.

## Tests

Representative acquisition → relevance → analysis → promotion → Story/report/alert where qualified; duplicate replay, false-merge and no-evidence negative cases.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Body/metadata/blocked/deferred outcomes are explicit with nonzero reviewed denominators
- [ ] Any repair has a reproduction and no trust-boundary regression
- [ ] At least a qualifying article-body fixture completes end to end; real usefulness remains a human gate

## Completion evidence and required plan updates

Required: Per-fixture stage/quality report, regression results and remaining unknowns. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert measured code fix; fixture report remains; no active trial changes.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

