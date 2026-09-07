# AST-18 — Issue the evidence-based product scope verdict

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M4; size S; risk medium. Dependencies: AST-15, AST-16, AST-17. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Decide what earns the daily product and whether broad expansion is justified.

Why now: Engineering completion cannot settle value or commercial promise.

Inspect: docs/reviews/PHASE_29_DECISION_RULE.md; plan/astra/COMMERCIAL_THESIS.md; plan/astra/DELETE_DEFER_KEEP.md; observation/comparison reports from AST-16/17. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Apply unchanged three-of-five categories and trust guardrails; distinguish historical comparison, prospective observation and owner usability. Produce KEEP/SIMPLIFY/CONTEXTUALIZE/DEFER/REMOVE per feature. Explicitly decide AST-21/22 activation and release scope. Inconclusive evidence leaves value acceptance open.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Inventing market evidence, moving thresholds, automatic Phase 30 or company-launch declaration.

## Tests

Audit category score arithmetic, case provenance, blind scoring, effective route and evidence gaps against preregistered rules.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Verdict is linked to actual human/eligible comparative evidence
- [ ] No trust regression or missing category is disguised as a pass
- [ ] Release scope and conditional task statuses are explicitly updated

## Completion evidence and required plan updates

Required: Signed-off/attributed value verdict with evidence links and task updates. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Append a new verdict if later evidence changes; preserve original decision and experiment.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

