# AST-22 — Run a bounded commercial pilot after value qualification

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: DEFERRED. Priority P2; milestone Conditional; size S; risk medium. Dependencies: AST-18, AST-19. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Test willingness to pay and support burden with the smallest real pilot.

Why now: No market/customer evidence currently justifies commercial infrastructure.

Inspect: plan/astra/COMMERCIAL_THESIS.md; plan/astra/PRODUCT_READINESS.md; release acceptance from AST-19; docs/THREAT_MODEL.md; pyproject.toml. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

After owner authorizes pilot scope, define target specialists, limited supported platform/feature promise, participant consent/data handling, purchase-intent test and support-effort log. Review distribution dependencies/licenses and source/privacy terms with appropriate expertise. Draft materials before requesting publication/contact authorization.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Unapproved outreach, fabricated pricing/traction, billing platform, multi-tenancy, enterprise features.

## Tests

Dry-run onboarding/recovery/support flow, dependency/distribution review, actual participant outcome/retention/payment-intent evidence when authorized.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Pilot promise and support/privacy/distribution boundaries are concrete and reviewed
- [ ] Actual user value/purchase-intent/support evidence is distinguished from hypotheses
- [ ] Continue/simplify/stop decision is recorded without speculative platform build

## Completion evidence and required plan updates

Required: Authorized pilot brief and actual participant findings, kept appropriately private. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Stop enrollment/distribution; preserve user export/recovery and honor agreed data handling.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

