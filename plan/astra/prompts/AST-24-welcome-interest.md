# AST-24 — Add Welcome and interest entry without raw IDs

Recommended model: TIER 2; reasoning medium.

## GOAL

Add Welcome and interest entry without raw IDs. Deliver this one outcome only.

## WHY

Make the installation-to-first-intelligence journey usable by an owner without developer documentation. This is one step in the paused setup → Sources → cadence → first-value path.

## STARTING STATE

Rebaseline main is `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`. AST-01–04 are DONE on an unmerged descendant stack, not main. Inspected AST-05 tip is `cddad09` on `astra/AST-05-start-newsroom`; recheck it for newer commits. Dependencies: AST-23. They must exist with accepted evidence in your checkout before edits. This prompt is executable only when TASKS/NEXT mark it READY; a filename is not authorization to bypass dependencies. A later AST-24 candidate review at `93c80b564485f8a864b085af190f8b888b0a9f98` found two P1 and two P2 corrections; those corrections and complete backend verification are required before AST-24 is accepted or AST-25 begins.

## REVIEW DISPOSITION

The prior candidate is bounded, not accepted. Correct CR-01 through CR-04 in this task’s owned surface:

- CR-01: changing the interest materially invalidates confirmed primary-term approval. Existing terms may remain editable candidates, but must be explicitly reconfirmed.
- CR-02: retry resends an immutable submitted identity and payload. Later edits remain separate draft state until the original operation resolves.
- CR-03: independent tabs must coordinate revisions with an explicit conflict or use isolated draft ownership; silent origin-wide overwrite is not acceptable.
- CR-04: browser qualification must set and assert a real 390 CSS-pixel viewport before recording mobile evidence, including relevant scrolled component-boundary checks.

The earlier local backend run progressed beyond 87% but its final result was unavailable. Treat that run as incomplete evidence; retain the final output of the replacement full-suite run.

## READ FIRST

`plan/astra/README.md`, `plan/astra/NEXT.md`, your exact section plus inherited contract in `plan/astra/TASKS.md`, `plan/astra/CURRENT_STATE.md`, and `plan/astra/UX_AND_ONBOARDING.md` first-run section, `newsroom/intelligent_monitoring.py:WatchService`, `frontend/src/views/WatchManagementView.tsx`. Then inspect only the affected files listed below and applicable repository instructions.

## SCOPE

Use Watch count to show first-run Welcome and Create Watch entry. Connect interest/name form to AST-23. Retain request identity through retries; resume a selected paused Watch after reload. Existing users can add another Watch and keep all current routes. Show saved setup as paused, with next action Add Sources. No UAP default value. Show an editable primary-term field/chips seeded visibly from the entered interest; require at least one user-confirmed term for AST-23. This is manual scope review, not semantic expansion. In the correction pass, invalidate confirmed-term approval after a material interest change; keep an immutable submitted identity/payload for exact retry; prevent silent cross-tab draft overwrite through explicit revision coordination or tab isolation; and make the browser harness assert the measured 390 CSS-pixel viewport and capture scrolled boundaries.

## NON-GOALS

No other roadmap task; no redesign/refactor outside the listed outcome; no merge/deploy/trial promotion. Do not contact the active Phase29 runtime, port 8127, read its database or change its observation clock, source set, provider or budget. No paid calls. No semantic provider integration, external discovery, report scheduling, paid configuration or new domain model.

## PRODUCT CONTRACT

Empty workspace reaches a named paused Watch without IDs; returning workspace opens ordinary Home; request failure/retry/reload neither loses the draft identity nor creates duplicates. User-approved primary terms are visible before save and persist into nonempty monitoring scope.

## TECHNICAL CONTRACT

Reuse canonical Watch→source Monitor services and existing auth/CSRF. Source-only Monitor acquisition remains unchanged. Preserve immutable scope/artifact/evidence and job replay contracts, existing route compatibility, shared Sources and zero-paid defaults. Represent submitted operation state separately from editable draft state. Use the smallest existing revision/storage mechanism that prevents silent cross-tab overwrite; do not introduce a broad synchronization subsystem. Do not infer process ownership or acquisition success from UI connectivity. Preserve accepted scope/version semantics and production worker scheduling.

## UX CONTRACT

Entry: installed launcher or setup step with prior saved state. Happy path: Empty workspace reaches a named paused Watch without IDs; returning workspace opens ordinary Home; request failure/retry/reload neither loses the draft identity nor creates duplicates. User-approved primary terms are visible before save and persist into nonempty monitoring scope. Loading: disable duplicate actions and expose bounded progress. Empty: show the next useful action without claiming success. Error: retain input/last good state and explain the actual failure. Recovery: retry/resume the same identity; API unreachable directs to external launcher. Responsive: desktop and an asserted 390 CSS-pixel viewport at 200% zoom; labels, visible keyboard focus and announced errors. No raw IDs in ordinary flow.

## IMPLEMENTATION GUIDANCE

Use Watch count to show first-run Welcome and Create Watch entry. Connect interest/name form to AST-23. Retain request identity through retries; resume a selected paused Watch after reload. Existing users can add another Watch and keep all current routes. Show saved setup as paused, with next action Add Sources. No UAP default value. Show an editable primary-term field/chips seeded visibly from the entered interest; require at least one user-confirmed term for AST-23. This is manual scope review, not semantic expansion. In the correction pass, invalidate confirmed-term approval after a material interest change; keep an immutable submitted identity/payload for exact retry; prevent silent cross-tab draft overwrite through explicit revision coordination or tab isolation; and make the browser harness assert the measured 390 CSS-pixel viewport and capture scrolled boundaries. Keep changes bounded. Read preceding task evidence and reuse its contracts. Use current apiFetch/jsonBody/LoadingState/ErrorState patterns when frontend work is in scope. Never solve an unsupported prerequisite by creating a second subsystem.

## FILES/SUBSYSTEMS

frontend/src/App.tsx; frontend/src/views/InboxView.tsx; frontend/src/views/WatchManagementView.tsx; frontend/src/lib/api.ts

## TESTS

Typecheck/build; isolated browser empty/returning/failed POST/reload; interest-change approval invalidation; exact-payload retry after draft edit or ambiguous completion; cross-tab coordination/isolation; keyboard and asserted 390 CSS-pixel viewport with scrolled-state/boundary checks; confirm server record count and retry identity. Use existing deterministic temporary-DB fixtures and fake transport; inspect test initialization before invoking it. Run affected existing regressions and the full backend suite, retaining its final output. A disconnected session, partial progress or unavailable final result remains incomplete. For frontend changes run `npm.cmd run typecheck` and `npm.cmd run build` on Windows (portable `npm` on other systems).

## BROWSER/VISUAL VERIFICATION

Use a newly isolated fixture runtime and explicit ephemeral/test endpoint outside the repository; never use legacy smoke defaults that point at 8127. Capture settled entry, success, loading, empty, error and recovery at desktop and an explicitly configured 390 CSS-pixel viewport, keyboard/200% zoom. Assert and record `window.innerWidth` and `document.documentElement.clientWidth` before labeling evidence `390px`; capture the relevant scrolled states and component boundaries. Record actual backend state after mutations and screenshot paths. For AST-05 include installed Start/reuse/conflict behavior and supported lifecycle evidence. TypeScript/source assertions alone are insufficient.

## ACCEPTANCE CRITERIA

Empty workspace reaches a named paused Watch without IDs; returning workspace opens ordinary Home; request failure/retry/reload neither loses the draft identity nor creates duplicates. User-approved primary terms are visible before save and persist into nonempty monitoring scope. A changed interest requires fresh term confirmation; retry uses the exact original submitted snapshot; cross-tab drafts do not silently overwrite; mobile evidence proves a 390 CSS-pixel viewport. The complete backend suite has a retrievable final result. All mandatory evidence must be established before DONE; name any missing manual/installed checks explicitly. Do not start AST-25 from a candidate that lacks these corrections or complete backend output.

## COST / PROVIDER SAFETY

Use local/deterministic/test doubles only. No real paid provider calls, discovery network requests or active trial access. Zero-paid setup stays zero. Never print secrets/environment credentials; do not alter production config or budget. A future paid test needs separate explicit authorization, not elapsed time.

## GIT / WORKTREE SAFETY

Inspect branch/HEAD/status/staged/modified/deleted/untracked state first. Preserve unrelated work and this uncommitted planning pass. Use a separate checkout descended from the verified AST stack; bring current planning authority without overwriting newer branch changes. No hard reset/clean/force push/history rewrite or merge. Before deleting/moving test files verify resolved absolute paths stay in the disposable test root; never terminate unmanaged processes.

## AUTONOMY

Make routine reversible decisions inside this contract autonomously. Do not ask about names/layout choices already settled by UX_AND_ONBOARDING. Continue through focused verification and record evidence; do not start a subsequent task.

## ESCALATION CONDITIONS

Stop and return precise evidence when a prerequisite is missing, public behavior conflicts, a new schema migration is needed beyond this contract, cleanup might affect an existing real installation, ownership cannot be verified, paid execution is needed, or unrelated subsystem redesign is required. Propose the smallest corrected task. Missing actual manual lifecycle checks must stay pending, never fabricated.

## COMPLETION REPORT

Report current gap/root cause; implementation or qualification summary; exact changed files; tests with commands and results, including retained full-backend final output; settled browser evidence with measured viewport dimensions if applicable; CI run/head/status (unknown if not queried); artifact/branch; remaining uncertainty; exact task status. Update TASKS/NEXT consistently only on supported evidence. Preserve the prior review as historical evidence, do not claim DONE from hosted CI alone, and stop.

## STOP CONDITION

Stop after this single task is complete or its exact blocker is recorded. Do not automatically execute or merge the next task.
