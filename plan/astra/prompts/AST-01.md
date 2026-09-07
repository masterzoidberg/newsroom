# AST-01 — Freeze the execution baseline and isolate development from observation

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: READY. Priority P0; milestone M0; size M; risk medium. Dependencies: None. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Make this audited baseline reproducible and give subsequent work a safe development/qualification target.

Why now: Current local tests pass, but Linux CI's backend job encounters an npm.cmd build test and lacks frontend dependency setup; active trial must remain frozen.

Inspect: README.md; .github/workflows/ci.yml; tests/test_phase12_frontend.py; frontend/package.json; docs/reviews/PHASE_29_BASELINE_ACCEPTANCE.md; docs/DOGFOOD_CONTRACT.md. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Record current HEAD/worktree and trial boundary; establish explicit outside-repo dev/test roots and separate configured endpoint. Make the frontend build test portable and ensure its invoking CI job has required Node/frontend dependencies, or move the build responsibility cleanly to the existing frontend CI job without losing coverage. Update current authority pointers only; preserve historical claims as dated records.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Rewriting test architecture, fixing unrelated mypy annotations, changing the active trial, installing/restarting production.

## Tests

Run backend suite, ruff, frontend build and offline eval validation; verify CI command/executable selection on Linux and Windows or record remaining hosted-run evidence.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Reproducible baseline is recorded with exact HEAD and check results
- [ ] CI no longer depends on Windows-only npm.cmd in its Linux backend path or missing frontend installation
- [ ] Safe explicit dev/test root and port are documented; active trial and unrelated files unchanged

## Completion evidence and required plan updates

Required: Baseline evidence, portable CI/test diff, commands/results and root-safety proof. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Revert bounded docs/CI/test changes; no runtime migration.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

