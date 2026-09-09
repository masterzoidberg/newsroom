# Canonical execution ledger

Rebaseline 2026-09-08. No implementation task is authorized in this planning pass. The AST-24 candidate review is complete, but its acceptance is not: two P1 and two P2 corrections remain, and the local backend result is incomplete. IDs AST-01–22 remain reserved; new work continues at AST-23 through AST-55. The task-index.json file is a checked machine-readable mirror, never a competing status authority; update it with TASKS and run validate_plan.py.

## Contract inherited by every future task

Each record below inherits these explicit constraints in addition to its task-specific outcome, files and acceptance. These are not optional boilerplate.

- **Outcome / user value:** the named task outcome removes the specific gap identified in FEATURE_GAP_ANALYSIS; deliver that one user capability or evidence gate.
- **Exact scope:** listed subsystem and described change only. A new neighboring UI component/test file is allowed only for that outcome; no unrelated refactor, dependency or platform expansion.
- **Non-goals:** all other tasks, merger/deployment/trial promotion, active trial contact, clock/source/provider/budget changes to that trial, real paid execution without separate explicit authorization.
- **Invariants:** canonical Watch→source Monitor path; bounded jobs and replay identities; immutable artifact/scope/evidence histories; exact-match promotion; accepted Claim versus suggestion/hypothesis distinction; no evidence-free synthesis; existing auth/CSRF and private access; shared Sources remain intact; Simple/Advanced is presentation only.
- **UX/browser evidence:** every task touching UI or installed owner behavior must exercise entry/happy/loading/empty/error/recovery at desktop and an asserted 390 CSS-pixel viewport, keyboard and 200% zoom, with settled screenshots and server-state checks. The harness must record measured `innerWidth`/`clientWidth` before labeling evidence `390px`; an outer-window request alone is insufficient. For pure backend/document planning tasks browser evidence is not applicable; test API/domain state or document consistency instead.
- **Rollback/recovery:** revert only owned changes; preserve user data and the last verified artifact/backup. Additive migrations require forward compatibility/backup rehearsal and never rewrite applied migrations; code rollback is not a database downgrade. Failed multi-step UI work preserves draft identity. Credential updates follow the versioned vault compensation contract.
- **Cost/provider constraints:** deterministic/local/fake tests, zero-paid default, durable reservations for any new paid capability, safe uncertain-call accounting, no secrets in database/browser storage/logs/exports. Do not call real providers to verify implementation without explicit separate authorization.
- **Reasoning:** Tier 1 low; Tier 2 medium; Tier 3 high; Tier A high for design/evidence, not routine implementation. See MODEL_AND_PROMPT_STRATEGY.
- **Completion report:** gap, change, exact files, test command/results, browser evidence if applicable, CI status (unqueried is unknown), artifact/branch, unresolved acceptance and exact ledger status. A suite whose final result/output was not retrieved is incomplete evidence and may not support DONE.
- **Stop condition:** stop after this one task; if its contract cannot be met within scope, record evidence and return for decomposition. Do not promote DONE based only on code existing, mocks or missing installed/human checks.

Statuses: READY, NOT_STARTED, IN_PROGRESS, DONE, BLOCKED, DEFERRED, SUPERSEDED. Exactly one READY. DONE records are qualified by branch; dependencies require code/evidence available in the execution checkout, not necessarily merged to main. Before using a stack, preserve unmerged work and recheck ancestry. No merge is authorized.

## Ledger index

| ID | Title | Status | Dependencies | Tier |
|---|---|---|---|---|
| AST-01 | Baseline and isolated CI | DONE | None | Historical |
| AST-02 | Instance identity and preflight | DONE | AST-01 | Historical |
| AST-03 | Runtime supervision and lease renewal | DONE | AST-02 | Historical |
| AST-04 | Honest status and recovery UI | DONE | AST-03 | Historical |
| AST-05 | Qualify the existing Start Newsroom launcher | READY | AST-01, AST-02, AST-03, AST-04 | 3 |
| AST-06 | Create typed public AI configuration metadata | NOT_STARTED | AST-27 | 3 |
| AST-07 | Store credentials in an approved operating-system vault | NOT_STARTED | AST-06 | 3 |
| AST-08 | Make paid admission durable across processes and reloads | NOT_STARTED | AST-07 | 3 |
| AST-09 | Resolve provider configuration at operation boundaries | NOT_STARTED | AST-08 | 3 |
| AST-10 | Add bounded provider validation and safe API contracts | NOT_STARTED | AST-09 | 3 |
| AST-11 | Build functional AI Providers and cost settings | NOT_STARTED | AST-10 | 2 |
| AST-12 | Original broad task, preserved below | SUPERSEDED | Replaced by AST-23–29,32,41,42,52–55 | — |
| AST-13 | Original broad task, preserved below | SUPERSEDED | Replaced by AST-45–46 | — |
| AST-14 | Original broad task, preserved below | SUPERSEDED | Replaced by AST-43–44 | — |
| AST-15 | Original broad task, preserved below | SUPERSEDED | Replaced by AST-47 | — |
| AST-16 | Observe under the unchanged Phase 29 protocol | BLOCKED | AST-01 | 2 |
| AST-17 | Execute the frozen comparison only with eligible authorized inputs | BLOCKED | AST-01 | 3 |
| AST-18 | Issue evidence-based product value and scope verdict | BLOCKED | AST-16, AST-17, AST-47 | A |
| AST-19 | Original broad task, preserved below | SUPERSEDED | Replaced by AST-48 | — |
| AST-20 | Remove only demonstrated obsolete support entry points | DEFERRED | AST-48 | 2 |
| AST-21 | Optionally integrate paid Ask after a value decision | DEFERRED | AST-11, AST-18 | 3 |
| AST-22 | Optionally run a bounded commercial pilot | DEFERRED | AST-18, AST-48 | A |
| AST-23 | Create a resumable paused Watch setup contract | NOT_STARTED | AST-05 | 3 |
| AST-24 | Add Welcome and interest entry without raw IDs | NOT_STARTED | AST-23 | 2 |
| AST-25 | Add and reuse Watch Sources by name or URL | NOT_STARTED | AST-24 | 2 |
| AST-26 | Expose Watch cadence as plain scheduling choices | NOT_STARTED | AST-25 | 2 |
| AST-27 | Connect review and Start to honest first-value progress | NOT_STARTED | AST-26 | 2 |
| AST-28 | Implement bounded semantic vocabulary capability | NOT_STARTED | AST-11, AST-27 | 3 |
| AST-29 | Make terminology review understandable in setup | NOT_STARTED | AST-28 | 2 |
| AST-30 | Decide and freeze fresh-corpus source recommendation contract | NOT_STARTED | AST-29 | A |
| AST-31 | Implement bounded fresh-corpus source candidates | NOT_STARTED | AST-30 | 3 |
| AST-32 | Connect recommended Sources and source health to setup | NOT_STARTED | AST-31, AST-25 | 2 |
| AST-33 | Persist and query the returning-user review boundary | NOT_STARTED | AST-27 | 3 |
| AST-34 | Build Watch overview and since-visit Home | NOT_STARTED | AST-33 | 2 |
| AST-35 | Connect summary through Claim to exact source Evidence | NOT_STARTED | AST-34 | 2 |
| AST-36 | Create and read Living Reports from named Watch context | NOT_STARTED | AST-35 | 2 |
| AST-37 | Add durable user-selected briefing schedules | NOT_STARTED | AST-36 | 3 |
| AST-38 | Expose briefing preferences and first intelligence choices | NOT_STARTED | AST-37 | 2 |
| AST-39 | Make alert triage scoped and complete | NOT_STARTED | AST-38 | 2 |
| AST-40 | Expose Story changes, disagreements and correction preview | NOT_STARTED | AST-35 | 2 |
| AST-41 | Support question-first Watches and contextual research | NOT_STARTED | AST-29, AST-35 | 3 |
| AST-42 | Make search, saved and history discoverable by name | NOT_STARTED | AST-35, AST-41 | 2 |
| AST-43 | Add owner verified-backup and diagnostic controls | NOT_STARTED | AST-11, AST-05 | 3 |
| AST-44 | Provide controlled restore, update recovery and export guidance | NOT_STARTED | AST-43 | 3 |
| AST-45 | Qualify and fix bounded responsive/accessibility defects | NOT_STARTED | AST-32, AST-34, AST-38, AST-39, AST-40, AST-41, AST-42, AST-44, AST-51, AST-52, AST-53, AST-54, AST-55 | 2 |
| AST-46 | Make PWA shell update and asset failure recoverable | NOT_STARTED | AST-45 | 2 |
| AST-47 | Qualify representative content-to-intelligence journeys | NOT_STARTED | AST-32, AST-35, AST-39, AST-40, AST-41, AST-42, AST-51, AST-52, AST-53, AST-54, AST-55 | 3 |
| AST-48 | Qualify named isolated Windows release and private phone use | NOT_STARTED | AST-46, AST-47, AST-49, AST-18 | 3 |
| AST-49 | Write owner installation, use and recovery documentation | NOT_STARTED | AST-44, AST-46, AST-47 | 1 |
| AST-50 | Freeze geographic and time scope semantics | NOT_STARTED | AST-29, AST-41 | A |
| AST-51 | Implement the approved scope narrowing contract | NOT_STARTED | AST-50 | 3 |
| AST-52 | Create a Watch for a named person or organization | NOT_STARTED | AST-29, AST-23 | 2 |
| AST-53 | Start a developing-event Watch without inventing a Story | NOT_STARTED | AST-24, AST-35 | 2 |
| AST-54 | Select scoped Ask context without raw IDs | NOT_STARTED | AST-42, AST-41 | 2 |
| AST-55 | Expose explainable deterministic smart-tag browsing | NOT_STARTED | AST-42 | 2 |

## Completed history: AST-01–04

Full original task bodies, acceptance and completion evidence are preserved in [history/AST-01-04_COMPLETION_RECORD.md](history/AST-01-04_COMPLETION_RECORD.md). Local source/test branches corroborate these narrow completions; hosted results remain recorded evidence, not freshly verified status. Prompts are in `prompts/archive/AST-01.md` through `AST-04.md`. Main still lacks the implementations.

## Superseded task mapping

- **AST-12: SUPERSEDED, not DONE.** Original definition and evidence retained in [TASKS_OLD](TASKS_OLD.md); replacement AST-23–29,32,41,42,52–55. The former prompt is retained under `prompts/superseded/AST-12.md`. Do not execute its broad contract.
- **AST-13: SUPERSEDED, not DONE.** Original definition and evidence retained in [TASKS_OLD](TASKS_OLD.md); replacement AST-45–46. The former prompt is retained under `prompts/superseded/AST-13.md`. Do not execute its broad contract.
- **AST-14: SUPERSEDED, not DONE.** Original definition and evidence retained in [TASKS_OLD](TASKS_OLD.md); replacement AST-43–44. The former prompt is retained under `prompts/superseded/AST-14.md`. Do not execute its broad contract.
- **AST-15: SUPERSEDED, not DONE.** Original definition and evidence retained in [TASKS_OLD](TASKS_OLD.md); replacement AST-47. The former prompt is retained under `prompts/superseded/AST-15.md`. Do not execute its broad contract.
- **AST-19: SUPERSEDED, not DONE.** Original definition and evidence retained in [TASKS_OLD](TASKS_OLD.md); replacement AST-48. The former prompt is retained under `prompts/superseded/AST-19.md`. Do not execute its broad contract.

## AST-05 — Qualify the existing Start Newsroom launcher

- **Status:** READY
- **Outcome / why it matters:** Qualify the existing Start Newsroom launcher. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-01, AST-02, AST-03, AST-04
- **Exact scope / files:** scripts/phase16_windows_deploy.ps1; scripts/astra05_windows_smoke.ps1; newsroom/runtime_identity.py; tests/test_phase16_windows_launcher_contract.py; plan/astra/TASKS.md
- **Implementation approach:** Start from the inspected AST-05 stack, reconcile newer changes and existing qualification evidence. Run the existing smoke only in disposable Windows install/runtime/task namespaces after auditing harness cleanup and legacy task probes. Repair only a reproduced launcher defect, one cause at a time; do not rebuild supervisor/status features. Record exact artifact, launcher exit behavior and supported lifecycle evidence.
- **Acceptance criteria:** One shortcut reuses matching runtime and exits success; foreign owner/port produces actionable no-kill diagnosis; isolated installed duplicate/sign-in/wake/browser-closed/recovery matrix passes or remains explicitly open without a DONE claim.
- **Tests / verification:** Existing launcher contract and affected runtime tests; isolated Windows smoke; actual supported sign-in/wake and installed browser evidence, with human-only checks recorded as pending.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** [prompts/AST-05-qualify-existing-launcher.md](prompts/AST-05-qualify-existing-launcher.md)
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-06 — Create typed public AI configuration metadata

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Create typed public AI configuration metadata. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-27
- **Exact scope / files:** newsroom/migrations.py; newsroom/domain.py; newsroom/domain_api.py; newsroom/article_analysis.py; tests/test_phase21_article_analysis.py.
- **Implementation approach:** Implement additive metadata/routes/generation schema from AI_PROVIDER_SETTINGS; allocate current next migration after rechecking ledger. Create a typed service with optimistic revision control, supported-capability validation and no secret storage. Retain one existing budget switch and local defaults.
- **Acceptance criteria:** Only public bounded metadata and opaque references persist; Unsupported routes/stale updates fail deterministically; local is default; Schema-36 upgrade preserves existing data and history.
- **Tests / verification:** Fresh/upgrade schema tests, invalid metadata and secret URL rejection, stale revision, local default and metadata export policy.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-06-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-07 — Store credentials in an approved operating-system vault

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Store credentials in an approved operating-system vault. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-06
- **Exact scope / files:** pyproject.toml; newsroom/domain_api.py; newsroom/operations.py; newsroom/article_analysis.py; AI metadata service introduced by AST-06.
- **Implementation approach:** Add reviewed keyring dependency and explicit approved platform backend selection. Implement versioned credential set/rotate/read/delete through one narrow interface; same-owner namespace, two-store failure compensation, disabled-before-delete behavior and truthful removal failures. Fake store for CI; fail closed with unsupported backend. Mask model/request representations and validation errors.
- **Acceptance criteria:** Sentinel exists only in submitted request/process memory and OS vault, never persisted diagnostic/export surfaces; Save/rotation/deletion failures preserve a truthful recoverable configuration; Windows owner access works; non-Windows approved backend or local-only behavior is explicit.
- **Tests / verification:** Sentinel tests through response/validation/log/telemetry/DB/full-backup/logical-export/build; store failures, rotation rollback, locked/unavailable backend; disposable Windows same-user integration.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-07-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-08 — Make paid admission durable across processes and reloads

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Make paid admission durable across processes and reloads. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-07
- **Exact scope / files:** newsroom/jobs.py; newsroom/ai.py; newsroom/article_analysis.py; tests/test_phase07_jobs.py; tests/test_phase21h_hardening.py.
- **Implementation approach:** Extend existing BudgetService reservations narrowly for connection-test work and supported paid capabilities. Preserve analysis idempotency, uncertain-call state and blocked-is-zero accounting. Recheck paid permission/config generation at admission, bound concurrent calls, keep estimated cost distinct from actual billing and account for configured SDK retry limits.
- **Acceptance criteria:** Concurrent/restarted clients cannot overspend the configured reservation limits; Blocked calls count zero; sent/uncertain calls remain conservatively accounted; Test-connection permission does not enable background paid routing.
- **Tests / verification:** Concurrent API/worker admission, restart/reset, disable race, failed/uncertain/blocked calls, explicit test allowance, global/per-work exhaustion.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-08-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-09 — Resolve provider configuration at operation boundaries

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Resolve provider configuration at operation boundaries. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-08
- **Exact scope / files:** newsroom/runtime.py; newsroom/article_analysis.py; newsroom/document_processing.py; newsroom/domain_api.py; newsroom/intelligent_monitoring.py.
- **Implementation approach:** Implement immutable config snapshots resolved at new operation boundaries, lazy client lifecycle and effective generation telemetry. Route Article Analysis through shared metadata/vault. Keep unsupported capabilities explicitly local through the same resolver. Add explicit legacy environment import/source labeling and managed-config precedence; disable/removal must not resurrect env providers.
- **Acceptance criteria:** Next work uses saved generation without restarting while in-flight work keeps its identity; All product construction paths report supported local/remote authority coherently; Disable/remove falls back safely and no legacy environment variable re-enables the provider.
- **Tests / verification:** Edit while worker alive, in-flight pinning, provider disable/delete, environment precedence, local fallback identity and restart persistence.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-09-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-10 — Add bounded provider validation and safe API contracts

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Add bounded provider validation and safe API contracts. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-09
- **Exact scope / files:** newsroom/domain_api.py; newsroom/app.py; newsroom/article_analysis.py; provider service from AST-06/09; tests/test_phase21_article_analysis.py.
- **Implementation approach:** Implement proposed CRUD/credential/test/routes/status APIs with auth/CSRF/no-store, safe errors and optimistic revision. Test actual configured structured-output capability using a bounded explicit reservation; no auto-test. Validate HTTPS/loopback keyless rules, redirects, DNS/destination and host-change secret handling. Manual model entry remains sufficient.
- **Acceptance criteria:** Explicit test yields a safe revision-bound capability result without raw provider body; Credential cannot be forwarded to a changed/unapproved destination; No provider call occurs on listing, edit, startup or typing; test never enables background spend.
- **Tests / verification:** Fake transport for auth failure, timeout, malformed JSON/schema, host redirect/credential forwarding, unsupported model, stale validation revision, test cap exhaustion.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-10-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-11 — Build functional AI Providers and cost settings

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Build functional AI Providers and cost settings. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-10
- **Exact scope / files:** frontend/src/views/AdminViews.tsx; frontend/src/lib/api.ts; frontend/src/lib/types.ts; frontend/src/styles.css; newsroom/domain_api.py.
- **Implementation approach:** Add named Settings sections and provider Add/Edit/Test/Enable/Disable/Model/Remove/Set-default controls. Show fixed mask/configured flag, offline explanation, supported capability, active model/generation, validation and failure, paid switch and typed existing budget controls. Clear secret after submit and label estimated usage honestly. Split a component only if needed for contained readability.
- **Acceptance criteria:** Full special acceptance succeeds with a fake provider and actual configured worker path; No raw secret is returned/persisted in browser state/storage after submission; User can see offline/active model/paid/budget/failure/reload state and recover without terminal.
- **Tests / verification:** Browser fake-provider Add AI Provider acceptance, bad inputs, stale edits, failed removal, screen-reader labels, save/refresh and next worker operation.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-11-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-16 — Observe under the unchanged Phase 29 protocol

- **Status:** BLOCKED
- **Outcome / why it matters:** Observe under the unchanged Phase 29 protocol. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-01
- **Exact scope / files:** docs/reviews/PHASE_29_OBSERVATION_PROTOCOL.md; docs/reviews/PHASE_29_WEEK_1_CHECKPOINT.md
- **Implementation approach:** Retain the existing approved observation only when separately requested. Read permitted evidence, obtain real human usefulness input and report sufficient/insufficient observation without resetting the clock.
- **Acceptance criteria:** Recorded duration/event volume and human usefulness meet unchanged protocol or explicitly remain insufficient; no fabricated scores or silently changed sources/provider/artifact.
- **Tests / verification:** Protocol/date/event denominators and human-input audit.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-16-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-17 — Execute the frozen comparison only with eligible authorized inputs

- **Status:** BLOCKED
- **Outcome / why it matters:** Execute the frozen comparison only with eligible authorized inputs. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-01
- **Exact scope / files:** docs/reviews/PHASE_29_EVALUATION_PROTOCOL.md; docs/reviews/PHASE_29_DECISION_RULE.md; newsroom/evals/phase29_protocol.py
- **Implementation approach:** Preserve eligible snapshot/case mapping, exact effective provider and blinded human scoring. Requires separate explicit paid authorization and evidence availability; this task is not executable from this audit.
- **Acceptance criteria:** Exact contract and eligibility verified; actual human scores retained; missing categories/fallback/uncertain cost never reported as success.
- **Tests / verification:** Offline eligibility and scoring arithmetic plus separately authorized actual execution.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-17-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-18 — Issue evidence-based product value and scope verdict

- **Status:** BLOCKED
- **Outcome / why it matters:** Issue evidence-based product value and scope verdict. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-16, AST-17, AST-47
- **Exact scope / files:** docs/reviews/PHASE_29_DECISION_RULE.md; plan/astra/PRODUCT_READINESS.md
- **Implementation approach:** Apply unchanged decision rule and trust guardrails to real evidence; distinguish prospective observation, frozen comparison and improved isolated UX. An inconclusive result keeps release acceptance open.
- **Acceptance criteria:** Verdict has attributable human/eligible evidence; missing categories are explicit; release scope and conditional extensions updated without moving thresholds.
- **Tests / verification:** Adversarial evidence/provenance and arithmetic review.
- **Model:** TIER A; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-18-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-20 — Remove only demonstrated obsolete support entry points

- **Status:** DEFERRED
- **Outcome / why it matters:** Remove only demonstrated obsolete support entry points. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-48
- **Exact scope / files:** plan/astra/DELETE_DEFER_KEEP.md; scripts/phase12_server.py; scripts/phase12_browser_smoke.py
- **Implementation approach:** Apply caller/data/replacement proof per candidate; keep compatibility and historical evidence. Not a release blocker or general cleanup mandate.
- **Acceptance criteria:** Every removal has replacement/caller proof; no user data/history/runtime invariant lost; supported entrypoints remain documented.
- **Tests / verification:** Affected caller search/regressions and supported entrypoint smoke.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-20-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-21 — Optionally integrate paid Ask after a value decision

- **Status:** DEFERRED
- **Outcome / why it matters:** Optionally integrate paid Ask after a value decision. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-11, AST-18
- **Exact scope / files:** newsroom/ask.py; newsroom/domain_api.py; frontend/src/views/AskView.tsx
- **Implementation approach:** Activate only by explicit recorded scope decision. Reuse managed config, durable budgets and qualifying citations; preserve refusal, temporal scope and local fallback. Split if remote synthesis adapter architecture is unsettled.
- **Acceptance criteria:** Explicit activation exists; every factual answer is citation-bound or qualified/refused; no hidden paid retry/fallback or benchmark contract change.
- **Tests / verification:** Fake citation/temporal/budget/cancellation tests and browser route/failure evidence.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-21-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-22 — Optionally run a bounded commercial pilot

- **Status:** DEFERRED
- **Outcome / why it matters:** Optionally run a bounded commercial pilot. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-18, AST-48
- **Exact scope / files:** plan/astra/COMMERCIAL_THESIS.md; plan/astra/PRODUCT_READINESS.md
- **Implementation approach:** Requires explicit owner pilot/contact/distribution authorization; measure real value/support/purchase intent with honest platform/privacy limits. No commercial infrastructure work implied.
- **Acceptance criteria:** Authorized pilot promise and actual user evidence recorded; support/privacy constraints clear; continue/simplify/stop decision tied to evidence.
- **Tests / verification:** Dry-run onboarding/recovery and attributable actual pilot findings when authorized.
- **Model:** TIER A; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-22-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-23 — Create a resumable paused Watch setup contract

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Create a resumable paused Watch setup contract. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-05
- **Exact scope / files:** newsroom/intelligent_monitoring.py; newsroom/domain_api.py; newsroom/domain.py; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Add one authenticated setup composition endpoint over existing Category/Topic/MonitoringPolicy/Watch records. Accept interest, editable name and a request identity; reuse a dedicated neutral category and create a paused Watch with discovery disabled and a per-Watch zero-paid hourly policy. Put this bounded composition in one SQLite transaction using existing validation/transaction patterns; do not call independently committing service methods inside a pretend outer transaction. Persist retry identity using the existing Watch ID if its validation allows the defined UUID form; otherwise stop for a narrowly specified schema decision. Return canonical IDs and resumed draft state. Existing APIs remain unchanged. Also persist at least one explicit user-approved primary term in topic_terms within the same transaction; Topic name/description alone is not scope. Accept an editable primary_terms list, bounded using existing term validation, with the entered interest as a visible initial suggestion rather than hidden NLP. The frontend requires user review of that term before saving.
- **Acceptance criteria:** Fresh setup creates one valid paused Watch with no Monitors/jobs; identical retry returns the same records while changed input with same identity conflicts; failure rolls back the composition and leaves unrelated objects untouched. Created Topic scope contains the exact user-approved primary terms and is never empty; no generated synonym is implicitly approved.
- **Tests / verification:** API auth/CSRF; blank/oversize interest; duplicate/concurrent retry; injected mid-transaction failure; phase24 lifecycle tests.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** [prompts/AST-23-paused-watch-contract.md](prompts/AST-23-paused-watch-contract.md)
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-24 — Add Welcome and interest entry without raw IDs

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Add Welcome and interest entry without raw IDs. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-23
- **Exact scope / files:** frontend/src/App.tsx; frontend/src/views/InboxView.tsx; frontend/src/views/WatchManagementView.tsx; frontend/src/lib/api.ts
- **Implementation approach:** Use Watch count to show first-run Welcome and Create Watch entry. Connect interest/name form to AST-23. Retain request identity through retries; resume a selected paused Watch after reload. Existing users can add another Watch and keep all current routes. Show saved setup as paused, with next action Add Sources. No UAP default value. Show an editable primary-term field/chips seeded visibly from the entered interest; require at least one user-confirmed term for AST-23. This is manual scope review, not semantic expansion. The bounded correction gate also requires: invalidate confirmed-term approval when the interest materially changes; retain later edits separately from an immutable submitted identity/payload so retry resends the exact original request; coordinate or isolate tab drafts so storage cannot silently overwrite another tab; and qualify mobile evidence only after asserting a measured 390 CSS-pixel viewport and checking the relevant scrolled component boundaries.
- **Acceptance criteria:** Empty workspace reaches a named paused Watch without IDs; returning workspace opens ordinary Home; request failure/retry/reload neither loses the draft identity nor creates duplicates. User-approved primary terms are visible before save and persist into nonempty monitoring scope. A changed interest cannot reuse prior approval. A retry after ambiguous/failure state resends the exact submitted identity and payload even if the editable draft changed. Cross-tab edits either coordinate revisions with an explicit conflict or remain isolated, with no silent overwrite. Mobile evidence records measured 390 CSS-pixel dimensions rather than only an outer window size. The complete backend suite has a retrievable final result; otherwise AST-24 remains unaccepted.
- **Tests / verification:** Typecheck/build; isolated browser empty/returning/failed POST/reload; interest-change approval invalidation; exact-payload retry after edit or ambiguous completion; cross-tab draft coordination/isolation; keyboard and asserted 390 CSS-pixel viewport with scrolled-state/boundary checks; confirm server record count and retry identity; rerun the relevant focused tests and the full backend suite with retained final output. Hosted CI may supplement but cannot replace missing local evidence.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** [prompts/AST-24-welcome-interest.md](prompts/AST-24-welcome-interest.md)
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** The AST-24 candidate was reviewed at head `93c80b564485f8a864b085af190f8b888b0a9f98` against AST-23 base `2ab4715ff1c267d8476a88bcd997380d16976d9d`. Review found CR-01/CR-02 as P1 and CR-03/CR-04 as P2; the final local backend result was unavailable, and the harness did not prove a 390 CSS-pixel viewport. This is bounded correction evidence, not DONE evidence. AST-24 remains unaccepted; AST-25 must not start until the corrections and complete backend result are recorded. AST-05 remains the sole READY task.

## AST-25 — Add and reuse Watch Sources by name or URL

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Add and reuse Watch Sources by name or URL. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-24
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; frontend/src/views/AdminViews.tsx; newsroom/domain_api.py; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Expose existing Sources search/selection and manual page/feed candidate creation. Preview rationale and approve explicitly through source-candidate review; reject unsafe URLs through existing backend validation. Keep setup Watch paused so attached Monitors cannot collect early. Detach a Watch relationship without deleting a shared Source. Use existing source CRUD for names/feed edits and disclose shared impact.
- **Acceptance criteria:** Fresh Watch can attach a usable URL/feed or named existing Source without IDs; approval/retry converges on one relationship and does not run acquisition while paused; detach preserves other Watches and Source history.
- **Tests / verification:** Phase24 shared-source/unsafe-url/concurrent approval tests; browser manual/reuse/bad URL/empty/approval failure/retry/detach at desktop and phone.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** [prompts/AST-25-manual-watch-sources.md](prompts/AST-25-manual-watch-sources.md)
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-26 — Expose Watch cadence as plain scheduling choices

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Expose Watch cadence as plain scheduling choices. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-25
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; newsroom/monitoring.py; newsroom/domain_api.py; tests/test_phase08_monitors.py
- **Implementation approach:** Map hourly/several-times-daily/daily/custom to existing policy bounds. Edit only the draft private policy; if a selected policy is shared, choose/create a private policy before changes. Show timezone-formatted next check and supported-channel limits. Keep paid cap zero and Watch paused until review/start. Preserve existing min/max/backoff semantics.
- **Acceptance criteria:** Chosen cadence persists and is reflected by source Monitors; changing one Watch cannot silently alter another; out-of-range custom input and unsupported fast options give inline recovery.
- **Tests / verification:** Policy validation/shared-policy isolation and schedule tests; browser each preset/custom/error/reload/390px.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** [prompts/AST-26-watch-cadence.md](prompts/AST-26-watch-cadence.md)
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-27 — Connect review and Start to honest first-value progress

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Connect review and Start to honest first-value progress. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-26
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; frontend/src/views/InboxView.tsx; newsroom/domain_api.py; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Review saved interest, approved vocabulary, sources, cadence and zero-paid mode. Start via existing resume/enable semantics with at least one approved usable Source. Observe health and durable processing status with bounded polling/backoff. Distinguish scheduled/collecting/processing/no-change/irrelevant/deferred/ready/error and link to existing Documents or Stories. Do not label Start as immediate successful collection or call scheduler internals from UI.
- **Acceptance criteria:** Repeated Start does not create duplicate Monitors/jobs; real persisted outcomes drive visible state and actual last-attempt time; source error/no-evidence/unavailable API gives usable retry/refinement guidance while preserving setup.
- **Tests / verification:** Fixture-backed worker/status outcomes; browser review/back/edit/start/double-submit/no-change/error/recovery and 390px; no network acquisition in tests.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** [prompts/AST-27-start-first-value.md](prompts/AST-27-start-first-value.md)
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-28 — Implement bounded semantic vocabulary capability

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Implement bounded semantic vocabulary capability. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-11, AST-27
- **Exact scope / files:** newsroom/ai.py; newsroom/intelligent_monitoring.py; newsroom/runtime.py; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Reuse VocabularyProvider and the managed capability resolver; add a structured compatible adapter only for vocabulary. User-initiated suggestions use durable admission and approved context, bounded by existing caps. Retain deterministic/manual path, rejection memory and immutable acquired scope. No domain-specific vocabulary hardcoding.
- **Acceptance criteria:** Fake provider supplies useful varied synonyms/acronyms/aliases with rationale without automatic approval; malformed/paid-disabled/uncertain responses preserve configuration; unrelated ambiguous meanings can be rejected and stay rejected.
- **Tests / verification:** UAP variants including historical aerial wording, company/person homonyms and unrelated niche fixtures; request count/budget/validation/approval-scope regressions.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-28-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-29 — Make terminology review understandable in setup

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Make terminology review understandable in setup. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-28
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; frontend/src/lib/types.ts
- **Implementation approach:** Insert reviewed terminology step with editable kinds, expansion links, exclusions, rationale and route/cost explanation. Manual entry is always available. Suggestions never appear as enabled until server review succeeds.
- **Acceptance criteria:** Approve/edit/reject changes only intended terms; unavailable/disabled provider explains manual fallback; approved versus suggested scope is visibly distinct after reload.
- **Tests / verification:** Browser fake suggestions/empty/error/edit/rejection/reload/keyboard/390px; scope payload inspection.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-29-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-30 — Decide and freeze fresh-corpus source recommendation contract

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Decide and freeze fresh-corpus source recommendation contract. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-29
- **Exact scope / files:** plan/astra/DECISIONS.md; plan/astra/AI_PROVIDER_SETTINGS.md; newsroom/intelligent_monitoring.py; newsroom/acquisition.py
- **Implementation approach:** Tier A reviews a bounded candidate-suggestion capability using the managed compatible adapter, followed by existing safe URL/feed validation. Separate model-proposed unverified URLs from corpus-derived observed URLs. Decide whether an external search adapter is actually necessary using empty-corpus fixtures; if so record one provider/transport/cost contract and human preference only if materially needed. Deliver a small schema/API contract and refined AST-31 prompt before coding; do not promise exhaustive web discovery.
- **Acceptance criteria:** Candidate provenance, reason, validation and rejection semantics are fixed; no automatic source attachment or evidence creation; AST-31 has no unresolved provider/schema decisions.
- **Tests / verification:** Design review against empty UAP/person/event cases, SSRF limits, source approval and zero-paid fallback; no paid calls.
- **Model:** TIER A; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-30-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-31 — Implement bounded fresh-corpus source candidates

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Implement bounded fresh-corpus source candidates. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-30
- **Exact scope / files:** newsroom/intelligent_monitoring.py; newsroom/ai.py; newsroom/domain_api.py; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Implement exactly AST-30 approved adapter/contract using existing candidate persistence and durable limits. Model suggestions are unverified until safe transport validation; enrich accepted candidates with rationale, discovery provenance and limitations. Preserve corpus discovery and rejection/dedupe. Stop if adapter requires another provider or unanticipated schema.
- **Acceptance criteria:** Empty corpus can return bounded explained candidates through a fake supported capability; bad/unsafe/hallucinated URLs never activate collection or become Evidence; paid-disabled mode returns honest manual/corpus fallback.
- **Tests / verification:** Fake discovery, invalid URL/redirect/private destinations, repeated/rejected candidates, budget/cancellation and no mutation before approval.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-31-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-32 — Connect recommended Sources and source health to setup

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Connect recommended Sources and source health to setup. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-31, AST-25
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; frontend/src/views/AdminViews.tsx
- **Implementation approach:** Add recommended/search/manual/existing entry choices with rationale/provenance and unverified status. Keep user approval explicit. Show page/feed health, last failure and retry guidance; edits affect only intended relationship or disclose shared Source change.
- **Acceptance criteria:** Empty-corpus user sees working manual fallback; recommendation approval is understandable and deduped; failed source is actionable without hiding successful siblings.
- **Tests / verification:** Browser populated/empty/unsafe/unavailable discovery and partial-source failure at desktop/390px; network responses and approved-source counts.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-32-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-33 — Persist and query the returning-user review boundary

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Persist and query the returning-user review boundary. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-27
- **Exact scope / files:** newsroom/attention.py; newsroom/domain_api.py; newsroom/temporal.py; tests/test_phase29_temporal.py
- **Implementation approach:** Add an explicit owner review cursor using existing suitable user-scoped persistence; if none fits, propose one additive migration before coding. Query bounded changes since cursor without mutating Story review/attention automatically. Separate collection success time from user visit time and publication time.
- **Acceptance criteria:** Returning after days gets bounded stable range/new changes; viewing does not silently mark all items seen; future timestamps, late ingestion and timezone changes cannot omit newly known evidence.
- **Tests / verification:** Cursor boundary/late arrival/pagination/repeat visit tests using injected time; no frozen eval changes.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-33-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-34 — Build Watch overview and since-visit Home

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Build Watch overview and since-visit Home. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-33
- **Exact scope / files:** frontend/src/views/InboxView.tsx; frontend/src/views/WatchManagementView.tsx; frontend/src/views/DocumentView.tsx
- **Implementation approach:** Render named Watch context, actual freshness, since-visit range and high/low priority changes using AST-33. Link analyzed relevant material even if Story assignment deferred. Provide More/pagination instead of silently losing rows.
- **Acceptance criteria:** No-Watch Home has clear setup action; populated Home shows actual collection time and complete paged changes; relevant-but-deferred analysis is reachable without fabricated Story.
- **Tests / verification:** Browser new/returning/quiet/late updates/deferred/failure/phone and >100-item pagination fixtures.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-34-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-35 — Connect summary through Claim to exact source Evidence

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Connect summary through Claim to exact source Evidence. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-34
- **Exact scope / files:** frontend/src/views/StoryEvidenceView.tsx; frontend/src/components/EvidenceView.tsx; frontend/src/views/DocumentView.tsx; frontend/src/lib/types.ts
- **Implementation approach:** Add contextual selection/deep links through existing IDs without raw-ID entry. Show accepted/pending status, source/version/exact excerpt, analysis identity and dependent-source caveats. Preserve return context and missing legacy artifact explanation.
- **Acceptance criteria:** A factual summary link opens its Claim and correct exact source version; reload/back preserves context; unsupported/pending/legacy states never look verified true.
- **Tests / verification:** Browser known Claim/span/source chain, stale/deleted identifier, missing artifact and phone/keyboard; phase22 trust tests.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-35-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-36 — Create and read Living Reports from named Watch context

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Create and read Living Reports from named Watch context. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-35
- **Exact scope / files:** frontend/src/views/ReportsView.tsx; frontend/src/views/WatchManagementView.tsx; newsroom/reports.py; tests/test_phase11_reports_briefings_alerts.py
- **Implementation approach:** Map selected Watch to its existing supported canonical target; reuse LivingReportService uniqueness and automatic revisions. Offer create/view without target IDs, show latest successful revision and provenance; no new Watch report type unless reviewed.
- **Acceptance criteria:** Watch opens one correct report without ID input; repeat create converges; no accepted evidence or failed generation preserves last revision and truthful status.
- **Tests / verification:** Report target/duplicate/no-evidence tests; browser create/read/revision/error/390px.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-36-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-37 — Add durable user-selected briefing schedules

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Add durable user-selected briefing schedules. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-36
- **Exact scope / files:** newsroom/reports.py; newsroom/jobs.py; newsroom/scheduler.py; newsroom/migrations.py; tests/test_phase11_reports_briefings_alerts.py
- **Implementation approach:** Introduce one narrowly reviewed additive schedule record for owner timezone, cadence, scope and next due time; route due work through existing durable job/coalescing pattern and BriefingService. Preserve report revision triggers separately. Prepare exact migration and job identity before implementation review.
- **Acceptance criteria:** Due cadence generates one briefing across concurrent ticks/retry; timezone/DST and missed interval catch-up are bounded; paused schedule and zero-paid defaults prevent unwanted work.
- **Tests / verification:** Concurrent scheduler/replay/DST/wake/disable tests and schema36 upgrade/backup preservation.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-37-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-38 — Expose briefing preferences and first intelligence choices

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Expose briefing preferences and first intelligence choices. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-37
- **Exact scope / files:** frontend/src/views/ReportsView.tsx; frontend/src/views/WatchManagementView.tsx; frontend/src/views/InboxView.tsx
- **Implementation approach:** Add named periodic briefing cadence/timezone controls and read latest saved briefing; introduce onboarding intelligence preferences for report/briefing with actual supported semantics. Keep acquisition cadence distinct.
- **Acceptance criteria:** Chosen preference persists and scheduled output appears without manual refresh; disabled/no-output schedule gives clear state; timezone and next delivery are visible.
- **Tests / verification:** Browser schedule/disable/reload/latest/empty/error/timezone/mobile with fake clock and job fixtures.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-38-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-39 — Make alert triage scoped and complete

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Make alert triage scoped and complete. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-38
- **Exact scope / files:** frontend/src/views/AlertsView.tsx; newsroom/reports.py; tests/test_phase11_reports_briefings_alerts.py
- **Implementation approach:** Replace hardcoded-only 0.85 view with Important/All/history and explicit Watch-derived supported target scope and thresholds. Reuse rule update, dedupe, acknowledge and attention decisions; show cause links via AST-35. Do not alter importance computation.
- **Acceptance criteria:** Rule-matching 0.5–0.85 alerts are reachable; scope/threshold edits persist; denial of browser notifications retains in-app history without duplicate alerts.
- **Tests / verification:** Threshold/scope/dedupe tests; browser all/important/history/acknowledge/permission-denied/390px.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-39-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-40 — Expose Story changes, disagreements and correction preview

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Expose Story changes, disagreements and correction preview. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-35
- **Exact scope / files:** frontend/src/views/StoryEvidenceView.tsx; newsroom/story_corrections.py; tests/test_phase27_story_correction_api.py
- **Implementation approach:** Use existing evolution/correction APIs for a chronological change view and explicit merge/split preview. Explain new Claims, source disagreement and lineage, with known-at versus source dates. Keep all evidence immutable and cancellation harmless.
- **Acceptance criteria:** User can identify new/conflicting Claims and evidence; correction preview names affected records and cancel mutates nothing; confirmed corrections retain audit/lineage and safe replay.
- **Tests / verification:** Browser disagreement/time/preview/cancel/error/reload/phone; existing correction/reconciliation tests.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-40-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-41 — Support question-first Watches and contextual research

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Support question-first Watches and contextual research. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-29, AST-35
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; frontend/src/views/AdminViews.tsx; newsroom/domain_api.py; tests/test_phase25_autonomous_research.py
- **Implementation approach:** Extend AST-23 setup for a named existing/new Research Question only. Connect the Watch to question/gap detail and bounded pursuit. Reuse existing assessment and hypothesis/Claim separation. Person and event setup belong to AST-52/53.
- **Acceptance criteria:** Question entry creates/selects the correct canonical need without IDs and retries safely; unsuccessful pursuit leaves the gap open; question/hypothesis material never becomes an accepted Claim without existing evidence verification.
- **Tests / verification:** API question-target/retry tests; browser question/gap/no-findings/failure/phone; phase25 approval chain.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-41-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-42 — Make search, saved and history discoverable by name

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Make search, saved and history discoverable by name. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-35, AST-41
- **Exact scope / files:** frontend/src/views/WorkbenchView.tsx; frontend/src/views/AskView.tsx; frontend/src/views/ReviewViews.tsx; newsroom/knowledge.py
- **Implementation approach:** Use named paged selectors and current Watch context for search/history/saved. Preserve existing FTS and retrieval bounds. Scoped Ask and smart tags are separate AST-54/55 slices.
- **Acceptance criteria:** Ordinary search/browse needs no IDs; more than 100 results can be traversed; saved/history remain accessible with stable context and actionable empty states.
- **Tests / verification:** Browser search/context/pagination/empty/error/keyboard/phone; phase26 retrieval tests.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-42-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-43 — Add owner verified-backup and diagnostic controls

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Add owner verified-backup and diagnostic controls. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-11, AST-05
- **Exact scope / files:** newsroom/operations.py; newsroom/domain_api.py; frontend/src/views/AdminViews.tsx; tests/test_phase15_hardening_operations.py
- **Implementation approach:** Wrap existing verified backup and redacted diagnostics with authenticated owner controls. Return backup identity/time/verification, not private unrestricted paths. No restore or arbitrary filesystem endpoint in this slice.
- **Acceptance criteria:** Owner can request and identify a verified backup; failure is truthful and cannot replace good backups; credentials/private request data absent from diagnostics and backup additions.
- **Tests / verification:** Temp-root backup failure/integrity/auth/CSRF/sentinel tests; browser pending/success/fail/retry/390px.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-43-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-44 — Provide controlled restore, update recovery and export guidance

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Provide controlled restore, update recovery and export guidance. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-43
- **Exact scope / files:** newsroom/operations.py; newsroom/release.py; frontend/src/views/AdminViews.tsx; docs/RECOVERY_RUNBOOK.md
- **Implementation approach:** Use existing stopped-writer/verified artifact operations with explicit owner confirmation and isolated preflight. Separate full restore from logical export, and explain article-body exclusion. Provide a recoverable handoff to the launcher when API cannot safely restore itself. No browser endpoint may overwrite a live DB.
- **Acceptance criteria:** Owner can obtain logical export with honest limits; restore preflight rejects wrong/corrupt backup and active writers; failed update retains a compatible rollback path and truthful data-state guidance.
- **Tests / verification:** Isolated backup/restore/upgrade failure and export reconstruction; browser export/preflight/recovery guidance/390px; no production restore.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-44-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-45 — Qualify and fix bounded responsive/accessibility defects

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Qualify and fix bounded responsive/accessibility defects. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-32, AST-34, AST-38, AST-39, AST-40, AST-41, AST-42, AST-44, AST-51, AST-52, AST-53, AST-54, AST-55
- **Exact scope / files:** frontend/src/styles.css; frontend/src/components/ViewPrimitives.tsx; frontend/src/components/AppShell.tsx
- **Implementation approach:** Audit populated/error/draft states after UI slices; fix only demonstrated layout/focus/contrast/label defects in existing theme. Record per-surface findings and split any unrelated logic defect rather than broad cleanup.
- **Acceptance criteria:** Desktop/390px/200% zoom has no control overlap or inaccessible action; keyboard flow and error announcements work; long content and disabled/recovery states are readable.
- **Tests / verification:** Fresh screenshots and keyboard/contrast checklist covering onboarding, Settings, reports, evidence and recovery; typecheck/build.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-45-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-46 — Make PWA shell update and asset failure recoverable

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Make PWA shell update and asset failure recoverable. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-45
- **Exact scope / files:** frontend/public/sw.js; frontend/src/components/PwaStatus.tsx; tests/test_phase12_frontend.py
- **Implementation approach:** Version shell/cache by release artifact, restrict cache to appropriate same-origin static resources, and distinguish navigation offline fallback from missing JS/CSS. Never cache API/auth data. Show pending update/reload and recover from stale shell without promising offline evidence access.
- **Acceptance criteria:** Upgrade cannot silently mix incompatible assets; missing script never receives HTML fallback; offline/auth/session state is honest and online recovery works.
- **Tests / verification:** Browser two-version update/offline/missing-asset/session/logout traces on isolated server and phone viewport; cache contents inspect.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-46-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-47 — Qualify representative content-to-intelligence journeys

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Qualify representative content-to-intelligence journeys. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-32, AST-35, AST-39, AST-40, AST-41, AST-42, AST-51, AST-52, AST-53, AST-54, AST-55
- **Exact scope / files:** tests/test_phase23e_compatibility.py; tests/test_phase24_intelligent_monitoring.py; plan/astra/PRODUCT_READINESS.md; newsroom/evals/story_intelligence.py
- **Implementation approach:** Run reviewed offline full-page/feed/broad-page fixtures through real worker chain, including no-change/irrelevant/deferred/correction paths. Human-labeled expected usefulness is separate from pipeline convergence. File bounded defects; do not silently relax conservative relevance/Story/evidence guards or edit frozen evaluation.
- **Acceptance criteria:** Fixture report proves artifact→analysis→Claim→Story/report/alert or explicit truthful alternative; UAP/person/event/question coverage includes ambiguity and nonindependent sources; measured quality and unknowns are separated from pass/fail plumbing.
- **Tests / verification:** Focused chain/replay tests and browser evidence from journeys A–D/F; no paid/live acquisition.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-47-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-48 — Qualify named isolated Windows release and private phone use

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Qualify named isolated Windows release and private phone use. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-46, AST-47, AST-49, AST-18
- **Exact scope / files:** scripts/phase16_windows_deploy.ps1; newsroom/release.py; docs/OPERATIONS_RUNBOOK.md; plan/astra/PRODUCT_READINESS.md
- **Implementation approach:** Qualify clean named artifact on supported Windows owner context with sign-in/wake/browser-closed lifecycle, separate upgrade/restore and private phone/PWA. Respect value gate; preparation before AST-18 may be recorded but final DONE waits. Split any discovered implementation defect. No deployment or trial promotion.
- **Acceptance criteria:** All release gates link exact artifact and actual evidence; no P0/P1 blocker or unsupported privacy/background claim; human value verdict present and install/recovery/phone limits explicit.
- **Tests / verification:** Full applicable offline CI/build plus isolated installed failure/upgrade/recovery/physical phone checklist and artifact hashes.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-48-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-49 — Write owner installation, use and recovery documentation

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Write owner installation, use and recovery documentation. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-44, AST-46, AST-47
- **Exact scope / files:** README.md; docs/OPERATIONS_RUNBOOK.md; docs/RECOVERY_RUNBOOK.md; frontend/README.md
- **Implementation approach:** Replace stale current-authority statements and explain supported install→Watch→evidence→recovery in user language after behavior lands. Preserve historical phase records and frozen protocols. Add release checklist links without claiming AST-48 already passed.
- **Acceptance criteria:** A new owner can follow documented local flow without internal IDs; startup/cost/offline/export limits match code; every unqualified promise is labeled and links resolve.
- **Tests / verification:** Documentation walkthrough against isolated fixture UI and links; no new implementation.
- **Model:** TIER 1; reasoning low.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-49-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-50 — Freeze geographic and time scope semantics

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Freeze geographic and time scope semantics. See the mapped user gap in FEATURE_GAP_ANALYSIS and milestone in COMPLETION_ROADMAP.
- **Dependencies:** AST-29, AST-41
- **Exact scope / files:** newsroom/monitoring.py; newsroom/intelligent_monitoring.py; frontend/src/views/WatchManagementView.tsx; tests/test_phase20_relevance_automation.py
- **Implementation approach:** Design-only task: freeze a narrow contract distinguishing geographic contextual terms from strict filtering and monitoring/review windows from historical knowledge time. Inspect whether existing pinned scope fields suffice; specify any exact additive schema/API needs and split them before coding. Produce the AST-51 implementation prompt with fixtures for ambiguous geography and undated material. No UI or backend implementation in AST-50.
- **Acceptance criteria:** Documented controls explicitly distinguish soft guidance from hard filters; schema/API/pinned-history semantics are fully decided; AST-51 has objective tests and no unanticipated architecture prerequisite.
- **Tests / verification:** Review contract and fixture expectations against RelevanceScope, temporal reads, undated documents and user journey B; no runtime/provider calls.
- **Model:** TIER A; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-50-<bounded-title>.md` after dependencies land; retained old template (if any) is historical only.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed by this rebaseline. AST-05 has implementation on the unmerged stack but incomplete qualification; all other records describe future work or explicit external gates.

## AST-51 — Implement the approved scope narrowing contract

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Implement the approved scope narrowing contract; this removes the mapped user gap without expanding adjacent surfaces.
- **Dependencies:** AST-50
- **Exact scope / files:** newsroom/monitoring.py; newsroom/intelligent_monitoring.py; frontend/src/views/WatchManagementView.tsx; tests/test_phase20_relevance_automation.py
- **Implementation approach:** Implement only the AST-50 frozen semantics and reviewed schema/API contract. Label geographic guidance and date filtering accurately. Keep acquired scope snapshots immutable. If AST-50 requires more than this bounded slice, replace this task with new IDs before execution.
- **Acceptance criteria:** Region/date controls meet the explicit contract after reload; ambiguous or undated material is handled as specified without silently disappearing; historical temporal reads and already pinned acquisitions are unchanged.
- **Tests / verification:** Scope/undated/ambiguous-region/history tests; browser narrow/edit/reload/error/390px.
- **Model:** TIER 3; reasoning high.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-51-<bounded-title>.md` when prerequisites land.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed; future bounded work only.

## AST-52 — Create a Watch for a named person or organization

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Create a Watch for a named person or organization; this removes the mapped user gap without expanding adjacent surfaces.
- **Dependencies:** AST-29, AST-23
- **Exact scope / files:** newsroom/domain_api.py; frontend/src/views/WatchManagementView.tsx; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Extend paused setup to select/create one Subject with explicit type and aliases using existing Subject schema. Reuse Topic setup retry/rollback patterns. Suggesting a related organization must not silently make it an alias.
- **Acceptance criteria:** Named Subject setup requires no IDs and reuses selected records; same-name different people can remain separate; explicit aliases/exclusions produce the intended pinned scope without changing another Watch.
- **Tests / verification:** API Subject/retry/alias ambiguity tests; browser person/company/homonym/error/reload/390px.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-52-<bounded-title>.md` when prerequisites land.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed; future bounded work only.

## AST-53 — Start a developing-event Watch without inventing a Story

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Start a developing-event Watch without inventing a Story; this removes the mapped user gap without expanding adjacent surfaces.
- **Dependencies:** AST-24, AST-35
- **Exact scope / files:** frontend/src/views/WatchManagementView.tsx; newsroom/domain_api.py; tests/test_phase24_intelligent_monitoring.py
- **Implementation approach:** Offer named existing Story selection and descriptive Topic setup for an event with no evidence-bearing Story yet. Use existing target APIs and paused setup, and preserve later conservative Story resolution.
- **Acceptance criteria:** Existing Story can be watched by name; new event creates descriptive Topic intent rather than fabricated Story/Claim; resulting analyzed material and later Story are accessible through current context.
- **Tests / verification:** API target and no-Story-created checks; browser existing/new-event/empty/error/390px.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-53-<bounded-title>.md` when prerequisites land.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed; future bounded work only.

## AST-54 — Select scoped Ask context without raw IDs

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Select scoped Ask context without raw IDs; this removes the mapped user gap without expanding adjacent surfaces.
- **Dependencies:** AST-42, AST-41
- **Exact scope / files:** frontend/src/views/AskView.tsx; frontend/src/lib/types.ts; tests/test_phase14_frontend.py
- **Implementation approach:** Replace raw-ID entry with named paged object selection and current Watch context. Reuse the current local Ask endpoint and preserve object scope and no-evidence refusal. Do not add remote synthesis.
- **Acceptance criteria:** User chooses a valid context by name; removed/empty context gives recovery; answers keep evidence citations and effective local route/refusal visibly distinct.
- **Tests / verification:** Browser contextual Ask/pagination/no-evidence/error/reload/keyboard/390px; existing Ask grounding tests.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-54-<bounded-title>.md` when prerequisites land.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed; future bounded work only.

## AST-55 — Expose explainable deterministic smart-tag browsing

- **Status:** NOT_STARTED
- **Outcome / why it matters:** Expose explainable deterministic smart-tag browsing; this removes the mapped user gap without expanding adjacent surfaces.
- **Dependencies:** AST-42
- **Exact scope / files:** frontend/src/views/WorkbenchView.tsx; newsroom/knowledge.py; tests/test_phase26_knowledge.py
- **Implementation approach:** Show existing namespaced smart tags and assignment reason/origin in contextual browse/filter controls. Do not add learned tagging or a new automatic backfill policy.
- **Acceptance criteria:** Smart/user tags are distinguishable with reason; filters show correct bounded results; absent tags or failed read gives an actionable state without generating classifications.
- **Tests / verification:** Existing deterministic-tag tests; browser tag reason/filter/empty/error/pagination/390px.
- **Model:** TIER 2; reasoning medium.
- **Prompt filename:** Not generated: outside the six-task horizon. Generate `prompts/AST-55-<bounded-title>.md` when prerequisites land.
- **Non-goals, invariants, browser evidence, rollback, cost and stop condition:** inherited in full from Contract inherited by every future task above.
- **Completion evidence:** Not executed; future bounded work only.
