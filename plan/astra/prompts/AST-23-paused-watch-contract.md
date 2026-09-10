# AST-23 — Create a resumable paused Watch setup contract

Recommended model: TIER 3; reasoning high.

## GOAL

Create a resumable paused Watch setup contract. Deliver this one outcome only.

## WHY

Make the installation-to-first-intelligence journey usable by an owner without developer documentation. This is one step in the paused setup → Sources → cadence → first-value path.

## STARTING STATE

Rebaseline main is `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`. AST-01–04 are DONE on an unmerged descendant stack, not main. Inspected AST-05 tip is `cddad09` on `astra/AST-05-start-newsroom`; recheck it for newer commits. Dependencies: AST-05. They must exist with accepted evidence in your checkout before edits. This prompt is executable only when TASKS/NEXT mark it READY; a filename is not authorization to bypass dependencies.

## READ FIRST

`plan/astra/README.md`, `plan/astra/NEXT.md`, your exact section plus inherited contract in `plan/astra/TASKS.md`, `plan/astra/CURRENT_STATE.md`, and `plan/astra/UX_AND_ONBOARDING.md` first-run section, `newsroom/intelligent_monitoring.py:WatchService`, `frontend/src/views/WatchManagementView.tsx`. Then inspect only the affected files listed below and applicable repository instructions.

## SCOPE

Add one authenticated setup composition endpoint over existing Category/Topic/MonitoringPolicy/Watch records. Accept interest, editable name and a request identity; reuse a dedicated neutral category and create a paused Watch with discovery disabled and a per-Watch zero-paid hourly policy. Put this bounded composition in one SQLite transaction using existing validation/transaction patterns; do not call independently committing service methods inside a pretend outer transaction. Persist retry identity using the existing Watch ID if its validation allows the defined UUID form; otherwise stop for a narrowly specified schema decision. Return canonical IDs and resumed draft state. Existing APIs remain unchanged. Also persist at least one explicit user-approved primary term in topic_terms within the same transaction; Topic name/description alone is not scope. Accept an editable primary_terms list, bounded using existing term validation, with the entered interest as a visible initial suggestion rather than hidden NLP. The frontend requires user review of that term before saving.

## NON-GOALS

No other roadmap task; no redesign/refactor outside the listed outcome; no merge/deploy/trial promotion. Do not contact the active Phase29 runtime, port 8127, read its database or change its observation clock, source set, provider or budget. No paid calls. No semantic provider integration, external discovery, report scheduling, paid configuration or new domain model.

## PRODUCT CONTRACT

Fresh setup creates one valid paused Watch with no Monitors/jobs; identical retry returns the same records while changed input with same identity conflicts; failure rolls back the composition and leaves unrelated objects untouched. Created Topic scope contains the exact user-approved primary terms and is never empty; no generated synonym is implicitly approved.

## TECHNICAL CONTRACT

Reuse canonical Watch→source Monitor services and existing auth/CSRF. Source-only Monitor acquisition remains unchanged. Preserve immutable scope/artifact/evidence and job replay contracts, existing route compatibility, shared Sources and zero-paid defaults. AST-23 composition must be atomic and retry-safe; existing service methods may commit independently, so do not assume nesting yields atomicity. Existing Watch ID is the proposed request identity; if validation/schema cannot support this safely, stop with the specific gap.

## UX CONTRACT

No frontend changes in this task. Return a stable typed paused-draft response and safe actionable validation/conflict errors for AST-24. API failure may not leave partially created setup. Browser screenshots are not applicable to this backend slice.

## IMPLEMENTATION GUIDANCE

Add one authenticated setup composition endpoint over existing Category/Topic/MonitoringPolicy/Watch records. Accept interest, editable name and a request identity; reuse a dedicated neutral category and create a paused Watch with discovery disabled and a per-Watch zero-paid hourly policy. Put this bounded composition in one SQLite transaction using existing validation/transaction patterns; do not call independently committing service methods inside a pretend outer transaction. Persist retry identity using the existing Watch ID if its validation allows the defined UUID form; otherwise stop for a narrowly specified schema decision. Return canonical IDs and resumed draft state. Existing APIs remain unchanged. Also persist at least one explicit user-approved primary term in topic_terms within the same transaction; Topic name/description alone is not scope. Accept an editable primary_terms list, bounded using existing term validation, with the entered interest as a visible initial suggestion rather than hidden NLP. The frontend requires user review of that term before saving. Keep changes bounded. Read preceding task evidence and reuse its contracts. Use current apiFetch/jsonBody/LoadingState/ErrorState patterns when frontend work is in scope. Never solve an unsupported prerequisite by creating a second subsystem.

## FILES/SUBSYSTEMS

newsroom/intelligent_monitoring.py; newsroom/domain_api.py; newsroom/domain.py; tests/test_phase24_intelligent_monitoring.py

## TESTS

API auth/CSRF; blank/oversize interest; duplicate/concurrent retry; injected mid-transaction failure; phase24 lifecycle tests. Use existing deterministic temporary-DB fixtures and fake transport; inspect test initialization before invoking it. Run affected existing regressions. Do not run unrelated browser/build or expensive full suites unless acceptance requires them.

## BROWSER/VISUAL VERIFICATION

Not applicable: no UI changes. Verify domain/API states and provide response examples with non-secret fixture identifiers. AST-24 owns browser acceptance.

## ACCEPTANCE CRITERIA

Fresh setup creates one valid paused Watch with no Monitors/jobs; identical retry returns the same records while changed input with same identity conflicts; failure rolls back the composition and leaves unrelated objects untouched. Created Topic scope contains the exact user-approved primary terms and is never empty; no generated synonym is implicitly approved. All mandatory evidence must be established before DONE; name any missing manual/installed checks explicitly.

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
