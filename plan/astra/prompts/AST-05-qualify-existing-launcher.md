# AST-05 — Qualify the existing Start Newsroom launcher

Recommended model: TIER 3; reasoning high.

## GOAL

Qualify the existing Start Newsroom launcher. Deliver this one outcome only.

## WHY

Make the installation-to-first-intelligence journey usable by an owner without developer documentation. Existing launcher code needs trustworthy acceptance, not replacement.

## STARTING STATE

Rebaseline main is `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`. AST-01–04 are DONE on an unmerged descendant stack, not main. Inspected AST-05 tip is `cddad09` on `astra/AST-05-start-newsroom`; recheck it for newer commits. Dependencies: AST-01, AST-02, AST-03, AST-04. They must exist with accepted evidence in your checkout before edits. This prompt is executable only when TASKS/NEXT mark it READY; a filename is not authorization to bypass dependencies.

## READ FIRST

`plan/astra/README.md`, `plan/astra/NEXT.md`, your exact section plus inherited contract in `plan/astra/TASKS.md`, `plan/astra/CURRENT_STATE.md`, and `plan/astra/STARTUP_AND_RUNTIME.md`, `plan/astra/history/AST-01-04_COMPLETION_RECORD.md`. Then inspect only the affected files listed below and applicable repository instructions.

## SCOPE

Start from the inspected AST-05 stack, reconcile newer changes and existing qualification evidence. Run the existing smoke only in disposable Windows install/runtime/task namespaces after auditing harness cleanup and legacy task probes. Repair only a reproduced launcher defect, one cause at a time; do not rebuild supervisor/status features. Record exact artifact, launcher exit behavior and supported lifecycle evidence.

## NON-GOALS

No other roadmap task; no redesign/refactor outside the listed outcome; no merge/deploy/trial promotion. Do not contact the active Phase29 runtime, port 8127, read its database or change its observation clock, source set, provider or budget. No paid calls. Do not rebuild AST-02/03/04 or broaden launcher work to provider settings.

## PRODUCT CONTRACT

One shortcut reuses matching runtime and exits success; foreign owner/port produces actionable no-kill diagnosis; isolated installed duplicate/sign-in/wake/browser-closed/recovery matrix passes or remains explicitly open without a DONE claim.

## TECHNICAL CONTRACT

Reuse canonical Watch→source Monitor services and existing auth/CSRF. Source-only Monitor acquisition remains unchanged. Preserve immutable scope/artifact/evidence and job replay contracts, existing route compatibility, shared Sources and zero-paid defaults. Do not infer process ownership or acquisition success from UI connectivity. Preserve accepted scope/version semantics and production worker scheduling.

## UX CONTRACT

Entry: installed launcher or setup step with prior saved state. Happy path: One shortcut reuses matching runtime and exits success; foreign owner/port produces actionable no-kill diagnosis; isolated installed duplicate/sign-in/wake/browser-closed/recovery matrix passes or remains explicitly open without a DONE claim. Loading: disable duplicate actions and expose bounded progress. Empty: show the next useful action without claiming success. Error: retain input/last good state and explain the actual failure. Recovery: retry/resume the same identity; API unreachable directs to external launcher. Responsive: desktop/390px/200% zoom; labels, visible keyboard focus and announced errors. No raw IDs in ordinary flow.

## IMPLEMENTATION GUIDANCE

Start from the inspected AST-05 stack, reconcile newer changes and existing qualification evidence. Run the existing smoke only in disposable Windows install/runtime/task namespaces after auditing harness cleanup and legacy task probes. Repair only a reproduced launcher defect, one cause at a time; do not rebuild supervisor/status features. Record exact artifact, launcher exit behavior and supported lifecycle evidence. Keep changes bounded. Before smoke execution inspect every task/file/process cleanup target; pre-existing real legacy tasks must be refused, not rewritten. Use isolated Windows CI/VM if the current host cannot guarantee this. Hosted success does not replace unperformed sign-in/wake/physical interaction checks; record them as open.

## FILES/SUBSYSTEMS

scripts/phase16_windows_deploy.ps1; scripts/astra05_windows_smoke.ps1; newsroom/runtime_identity.py; tests/test_phase16_windows_launcher_contract.py; plan/astra/TASKS.md

## TESTS

Existing launcher contract and affected runtime tests; isolated Windows smoke; actual supported sign-in/wake and installed browser evidence, with human-only checks recorded as pending. Use existing deterministic temporary-DB fixtures and fake transport; inspect test initialization before invoking it. Run affected existing regressions. Do not run unrelated browser/build or expensive full suites unless acceptance requires them.

## BROWSER/VISUAL VERIFICATION

Use a newly isolated fixture runtime and explicit ephemeral/test endpoint outside the repository; never use legacy smoke defaults that point at 8127. Capture settled entry, success, loading, empty, error and recovery at desktop and 390px, keyboard/200% zoom. Record actual backend state after mutations and screenshot paths. For AST-05 include installed Start/reuse/conflict behavior and supported lifecycle evidence. TypeScript/source assertions alone are insufficient.

## ACCEPTANCE CRITERIA

One shortcut reuses matching runtime and exits success; foreign owner/port produces actionable no-kill diagnosis; isolated installed duplicate/sign-in/wake/browser-closed/recovery matrix passes or remains explicitly open without a DONE claim. All mandatory evidence must be established before DONE; name any missing manual/installed checks explicitly.

## COST / PROVIDER SAFETY

Use local/deterministic/test doubles only. No real paid provider calls, discovery network requests or active trial access. Zero-paid setup stays zero. Never print secrets/environment credentials; do not alter production config or budget. A future paid test needs separate explicit authorization, not elapsed time.

## GIT / WORKTREE SAFETY

Inspect branch/HEAD/status/staged/modified/deleted/untracked state first. Preserve unrelated work and this uncommitted planning pass. Use a separate checkout descended from the verified AST stack; bring current planning authority without overwriting newer branch changes. No hard reset/clean/force push/history rewrite or merge. Before deleting/moving test files verify resolved absolute paths stay in the disposable test root; never terminate unmanaged processes.

## AUTONOMY

Make routine reversible decisions inside this contract autonomously. Do not ask about names/layout choices already settled by UX_AND_ONBOARDING. Continue through focused verification and record evidence; do not start a subsequent task.

## ESCALATION CONDITIONS

Stop and return precise evidence when a prerequisite is missing, public behavior conflicts, a new schema migration is needed beyond this contract, cleanup might affect an existing real installation, ownership cannot be verified, paid execution is needed, or unrelated subsystem redesign is required. Propose the smallest corrected task. Missing actual manual lifecycle checks must stay pending, never fabricated.

## COMPLETION REPORT

Report current gap/root cause; implementation or qualification summary; exact changed files; tests with commands and results; settled browser evidence if applicable; CI run/head/status (unknown if not queried); artifact/branch; remaining uncertainty; exact task status. Update TASKS/NEXT consistently only on supported evidence. Preserve historical records and stop.

## STOP CONDITION

Stop after this single task is complete or its exact blocker is recorded. Do not automatically execute or merge the next task.
