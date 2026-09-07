# AST-13 — Finish dark-theme and responsive control behavior

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P1; milestone M3; size M; risk medium. Dependencies: AST-12. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Keep the dark design and fix confirmed mobile/contrast/accessibility gaps.

Why now: Phone Settings has overlapping buttons inside two-column cards; literal colors impede consistent verification.

Inspect: frontend/src/styles.css; frontend/src/components/ViewPrimitives.tsx; frontend/src/components/AppShell.tsx; frontend/public/manifest.webmanifest; frontend/index.html. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Consolidate semantic colors within existing CSS; collapse generic content grids and wrap controls at small widths; align chrome/offline surfaces. Measure contrast and fix failing pairs, focus/overlay behavior, reduced motion and zoom. Preserve dark-only default and existing design.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Light palette, redesign, CSS framework/dependency or decorative animation.

## Tests

Dark-experience matrix at 320/390/768/1440px, 200% zoom, populated/error/loading/offline states, keyboard and component-bound checks.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] No overlapping/clipped controls including Settings buttons and no unexpected bright surfaces
- [ ] Text/focus/control contrast and keyboard checks have measured evidence
- [ ] All main views and PWA chrome retain coherent dark presentation

## Completion evidence and required plan updates

Required: Before/after screenshots, contrast/focus checklist and frontend build. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert stylesheet/component changes; no schema/data changes.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

