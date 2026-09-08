# Canonical task ledger

Audit-only initial state. Allowed statuses: NOT_STARTED, READY, IN_PROGRESS, BLOCKED, DONE, DEFERRED. No implementation task is DONE. A dependency means verified DONE unless a recorded decision explicitly narrows it. Promote the next eligible task to READY when updating NEXT; never treat elapsed time as paid authorization or human scoring.

| ID | Title | Status | Priority | Milestone | Dependencies | Size |
|---|---|---|---|---|---|---|
| AST-01 | Freeze the execution baseline and isolate development from observation | READY | P0 | M0 | None | M |
| AST-02 | Identify application instances and diagnose port conflicts | NOT_STARTED | P0 | M1 | AST-01 | M |
| AST-03 | Supervise existing runtime components safely | NOT_STARTED | P0 | M1 | AST-02 | M |
| AST-04 | Expose honest component status and recovery controls | NOT_STARTED | P0 | M1 | AST-03 | M |
| AST-05 | Ship one Start Newsroom entry point | NOT_STARTED | P0 | M1 | AST-04 | M |
| AST-06 | Create typed public AI configuration metadata | NOT_STARTED | P0 | M2 | AST-05 | M |
| AST-07 | Store credentials in an approved operating-system vault | NOT_STARTED | P0 | M2 | AST-06 | M |
| AST-08 | Make paid admission durable across processes and reloads | NOT_STARTED | P0 | M2 | AST-07 | M |
| AST-09 | Resolve provider configuration at operation boundaries | NOT_STARTED | P0 | M2 | AST-08 | M |
| AST-10 | Add bounded provider validation and safe API contracts | NOT_STARTED | P0 | M2 | AST-09 | M |
| AST-11 | Build functional AI Providers and cost settings | NOT_STARTED | P0 | M2 | AST-10 | M |
| AST-12 | Make first Watch and scoped use possible without IDs | NOT_STARTED | P1 | M3 | AST-11 | M |
| AST-13 | Finish dark-theme and responsive control behavior | NOT_STARTED | P1 | M3 | AST-12 | M |
| AST-14 | Wrap verified backup and recovery in owner controls | NOT_STARTED | P1 | M3 | AST-13 | M |
| AST-15 | Verify representative content-to-value paths | NOT_STARTED | P1 | M3 | AST-14 | M |
| AST-16 | Continue the approved observation with honest usefulness evidence | NOT_STARTED | P1 | M4 | AST-01 | S |
| AST-17 | Execute the frozen comparison under its exact contract | BLOCKED | P1 | M4 | AST-01 | M |
| AST-18 | Issue the evidence-based product scope verdict | NOT_STARTED | P1 | M4 | AST-15, AST-16, AST-17 | S |
| AST-19 | Qualify the installed daily-use release candidate | NOT_STARTED | P1 | M5 | AST-05, AST-11, AST-12, AST-13, AST-14, AST-18 | M |
| AST-20 | Remove only proven obsolete completion scaffolding | NOT_STARTED | P2 | M5 | AST-19 | S |
| AST-21 | Integrate paid Ask only if its value is demonstrated | DEFERRED | P2 | Conditional | AST-11, AST-18 | M |
| AST-22 | Run a bounded commercial pilot after value qualification | DEFERRED | P2 | Conditional | AST-18, AST-19 | S |

## AST-01 — Freeze the execution baseline and isolate development from observation

- **ID:** AST-01
- **Status:** READY
- **Priority:** P0
- **Milestone:** M0
- **Dependencies:** None
- **Relative size:** M
- **Risk:** medium; Current local tests pass, but Linux CI's backend job encounters an npm.cmd build test and lacks frontend dependency setup; active trial must remain frozen.
- **Reversibility:** Revert bounded docs/CI/test changes; no runtime migration.

**Objective:** Make this audited baseline reproducible and give subsequent work a safe development/qualification target.

**Why now:** Current local tests pass, but Linux CI's backend job encounters an npm.cmd build test and lacks frontend dependency setup; active trial must remain frozen.

**Files/subsystems:** README.md; .github/workflows/ci.yml; tests/test_phase12_frontend.py; frontend/package.json; docs/reviews/PHASE_29_BASELINE_ACCEPTANCE.md; docs/DOGFOOD_CONTRACT.md.

**Implementation approach:** Record current HEAD/worktree and trial boundary; establish explicit outside-repo dev/test roots and separate configured endpoint. Make the frontend build test portable and ensure its invoking CI job has required Node/frontend dependencies, or move the build responsibility cleanly to the existing frontend CI job without losing coverage. Update current authority pointers only; preserve historical claims as dated records.

**Non-goals:** Rewriting test architecture, fixing unrelated mypy annotations, changing the active trial, installing/restarting production.

**Tests:** Run backend suite, ruff, frontend build and offline eval validation; verify CI command/executable selection on Linux and Windows or record remaining hosted-run evidence.

**Acceptance criteria:**

- [ ] Reproducible baseline is recorded with exact HEAD and check results
- [ ] CI no longer depends on Windows-only npm.cmd in its Linux backend path or missing frontend installation
- [ ] Safe explicit dev/test root and port are documented; active trial and unrelated files unchanged

**Completion evidence:** Not yet executed. Required: Baseline evidence, portable CI/test diff, commands/results and root-safety proof. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-01](prompts/AST-01.md).

## AST-02 — Identify application instances and diagnose port conflicts

- **ID:** AST-02
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-01
- **Relative size:** M
- **Risk:** high; Current 8127 already serves Newsroom but duplicate startup blindly binds.
- **Reversibility:** Revert launcher preflight; retain existing explicit operator commands.

**Objective:** Add ownership-aware preflight and bind-failure diagnosis for the configured endpoint.

**Why now:** Current 8127 already serves Newsroom but duplicate startup blindly binds.

**Files/subsystems:** newsroom/runtime.py; newsroom/config.py; newsroom/app.py; tests/test_runtime_config.py; tests/test_phase16_deployment.py.

**Implementation approach:** Add a stable non-secret installation identity and process identity checks using root/role/release plus PID creation time. Use an OS exclusive lock, not a PID-file-only guard. Define status protocol for matching, unmanaged, foreign and unknown owners. Handle the bind race after preflight. Permit healthy verified reuse; never terminate or silently move ports.

**Non-goals:** Starting a new service architecture, taking over active unmanaged trial processes, arbitrary process termination.

**Tests:** Temporary sockets/processes: same instance, foreign listener, wrong root, stale PID, concurrent preflight and bind race.

**Acceptance criteria:**

- [ ] Matching healthy instance is reused without a second API bind
- [ ] Foreign/mismatched/unknown ownership gives actionable fixed-port diagnosis and no kill
- [ ] Concurrent launches and PID reuse cannot falsely identify another process

**Completion evidence:** Not yet executed. Required: Process/socket test results and redacted identity/status examples. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-02](prompts/AST-02.md).

## AST-03 — Supervise existing runtime components safely

- **ID:** AST-03
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-02
- **Relative size:** M
- **Risk:** high; Port checks alone do not ensure processing or prevent child divergence.
- **Reversibility:** Disable new supervisor in isolated install and use existing commands; no data rollback.

**Objective:** Own one API, worker and scheduler with bounded startup, shutdown and recovery.

**Why now:** Port checks alone do not ensure processing or prevent child divergence.

**Files/subsystems:** newsroom/runtime.py; newsroom/worker.py; newsroom/scheduler.py; newsroom/jobs.py; tests/test_phase07_jobs.py.

**Implementation approach:** Implement a small supervisor around existing child entry points with one shared manifest/root/release. Add component heartbeat and graceful drain/control. Coordinate migration ownership and child reconciliation. Verify 120-second job lease vs long-running handlers; implement only a demonstrated minimal renewal/ownership correction needed for safe supervision. Bound child restart/backoff and preserve uncertain paid work.

**Non-goals:** Replacing durable jobs, distributed workers, task queue rewrite, forced termination of unmanaged processes.

**Tests:** Subprocess crash/restart, supervisor crash with children alive, long handler beyond lease, cancellation, stale heartbeat, graceful drain and bounded restart exhaustion.

**Acceptance criteria:**

- [ ] One owned child per required role survives repeated/concurrent launches
- [ ] Stop/restart drains or reports deadline safely and never duplicates downstream work or uncertain paid calls
- [ ] Failure/restart bounds and long-handler lease safety have explicit test evidence

**Completion evidence:** Not yet executed. Required: Lifecycle state table, subprocess results and owned-process count evidence. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-03](prompts/AST-03.md).

## AST-04 — Expose honest component status and recovery controls

- **ID:** AST-04
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-03
- **Relative size:** M
- **Risk:** medium; Public liveness and browser network status do not prove worker/scheduler progress.
- **Reversibility:** Revert UI/control routes while retaining safe supervisor operation.

**Objective:** Replace misleading service/synced labels with actionable whole-app state.

**Why now:** Public liveness and browser network status do not prove worker/scheduler progress.

**Files/subsystems:** newsroom/app.py; newsroom/domain_api.py; frontend/src/App.tsx; frontend/src/components/AppShell.tsx; frontend/src/views/AdminViews.tsx.

**Implementation approach:** Expose authenticated bounded runtime status and named restart/stop requests to the supervisor through its protected control channel. Poll lightweight heartbeats with sensible backoff; distinguish API down, worker/scheduler degraded, idle, stopped and starting. Keep expensive integrity scans out of frequent status polling. Show an external launcher recovery path when API is unavailable.

**Non-goals:** Arbitrary command execution, exposing root paths publicly, new general diagnostics dashboard.

**Tests:** Auth/CSRF/control allowlist tests; browser component-down and network-only failure; stop acknowledgement before API closes.

**Acceptance criteria:**

- [ ] Status identifies missing/stale components and distinguishes no work from failure
- [ ] Authorized named controls work and unauthorized/CSRF-invalid calls fail
- [ ] Browser does not claim Synced based only on navigator.onLine or API liveness

**Completion evidence:** Not yet executed. Required: API contract, mocked health failures and browser screenshots. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-04](prompts/AST-04.md).

## AST-05 — Ship one Start Newsroom entry point

- **ID:** AST-05
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-04
- **Relative size:** M
- **Risk:** high; The existing installer generates three launchers and three independent tasks.
- **Reversibility:** Remove only the new installation's registration/shortcut; preserve runtime and existing legacy configuration.

**Objective:** Make normal launch and reboot/sign-in recovery require no terminal commands.

**Why now:** The existing installer generates three launchers and three independent tasks.

**Files/subsystems:** scripts/phase16_windows_deploy.ps1; newsroom/release.py; newsroom/runtime.py; docs/OPERATIONS_RUNBOOK.md; tests/test_phase16_deployment.py.

**Implementation approach:** Generate one obvious shortcut/hidden launcher invoking the supervisor and opening the product. Register only that authority at user sign-in with same-user identity. Namespace install tasks; detect legacy tasks and provide a reviewed migration action without silently disabling unrelated tasks. Document browser-close/background and pre-login limitations.

**Non-goals:** Tray framework, Windows service, pre-login monitoring guarantee, production task changes during tests.

**Tests:** Clean temporary Windows installation; Start Newsroom special acceptance including reboot/sign-in, duplicate launch, foreign port and locked/wake states.

**Acceptance criteria:**

- [ ] One shortcut starts all components and opens the product
- [ ] Repeated launch, browser close and reboot/sign-in behave as documented with one authority
- [ ] Legacy installation handling is explicit and no unrelated scheduled tasks/processes are altered

**Completion evidence:** Not yet executed. Required: Installed artifact identity, Windows qualification checklist and redacted task/process evidence. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-05](prompts/AST-05.md).

## AST-06 — Create typed public AI configuration metadata

- **ID:** AST-06
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M2
- **Dependencies:** AST-05
- **Relative size:** M
- **Risk:** medium; Generic settings plus environment capture cannot support coherent provider management.
- **Reversibility:** Disable routes/use local; do not down-migrate a populated DB; restore verified backup only when deliberately needed.

**Objective:** Establish the canonical non-secret connection/capability configuration service.

**Why now:** Generic settings plus environment capture cannot support coherent provider management.

**Files/subsystems:** newsroom/migrations.py; newsroom/domain.py; newsroom/domain_api.py; newsroom/article_analysis.py; tests/test_phase21_article_analysis.py.

**Implementation approach:** Implement additive metadata/routes/generation schema from AI_PROVIDER_SETTINGS; allocate current next migration after rechecking ledger. Create a typed service with optimistic revision control, supported-capability validation and no secret storage. Retain one existing budget switch and local defaults.

**Non-goals:** Credential persistence, provider calls, remote support for all capability interfaces.

**Tests:** Fresh/upgrade schema tests, invalid metadata and secret URL rejection, stale revision, local default and metadata export policy.

**Acceptance criteria:**

- [ ] Only public bounded metadata and opaque references persist
- [ ] Unsupported routes/stale updates fail deterministically; local is default
- [ ] Schema-36 upgrade preserves existing data and history

**Completion evidence:** Not yet executed. Required: Migration/contract tests and reviewed schema diff. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-06](prompts/AST-06.md).

## AST-07 — Store credentials in an approved operating-system vault

- **ID:** AST-07
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M2
- **Dependencies:** AST-06
- **Relative size:** M
- **Risk:** high; Metadata needs a real secret boundary before any provider controls can be safe.
- **Reversibility:** Disable provider and remove only task-created vault entries; preserve public metadata/history.

**Objective:** Implement write-only credential lifecycle without keys in SQLite, backups or responses.

**Why now:** Metadata needs a real secret boundary before any provider controls can be safe.

**Files/subsystems:** pyproject.toml; newsroom/domain_api.py; newsroom/operations.py; newsroom/article_analysis.py; AI metadata service introduced by AST-06.

**Implementation approach:** Add reviewed keyring dependency and explicit approved platform backend selection. Implement versioned credential set/rotate/read/delete through one narrow interface; same-owner namespace, two-store failure compensation, disabled-before-delete behavior and truthful removal failures. Fake store for CI; fail closed with unsupported backend. Mask model/request representations and validation errors.

**Non-goals:** Plaintext fallback, encrypted SQLite credentials, exposing stored keys, modifying existing user credentials.

**Tests:** Sentinel tests through response/validation/log/telemetry/DB/full-backup/logical-export/build; store failures, rotation rollback, locked/unavailable backend; disposable Windows same-user integration.

**Acceptance criteria:**

- [ ] Sentinel exists only in submitted request/process memory and OS vault, never persisted diagnostic/export surfaces
- [ ] Save/rotation/deletion failures preserve a truthful recoverable configuration
- [ ] Windows owner access works; non-Windows approved backend or local-only behavior is explicit

**Completion evidence:** Not yet executed. Required: Secret-leak test matrix and disposable vault integration results without secret contents. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-07](prompts/AST-07.md).

## AST-08 — Make paid admission durable across processes and reloads

- **ID:** AST-08
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M2
- **Dependencies:** AST-07
- **Relative size:** M
- **Risk:** high; Router-local counters reset across instances; new operations must not bypass existing durable analysis protections.
- **Reversibility:** Route local and retain ledger/reservations; never erase uncertain paid history.

**Objective:** Use one durable budget authority for production and explicit connection tests.

**Why now:** Router-local counters reset across instances; new operations must not bypass existing durable analysis protections.

**Files/subsystems:** newsroom/jobs.py; newsroom/ai.py; newsroom/article_analysis.py; tests/test_phase07_jobs.py; tests/test_phase21h_hardening.py.

**Implementation approach:** Extend existing BudgetService reservations narrowly for connection-test work and supported paid capabilities. Preserve analysis idempotency, uncertain-call state and blocked-is-zero accounting. Recheck paid permission/config generation at admission, bound concurrent calls, keep estimated cost distinct from actual billing and account for configured SDK retry limits.

**Non-goals:** Replacing budget ledger, fabricated billing accuracy, automatic retry of uncertain remote work.

**Tests:** Concurrent API/worker admission, restart/reset, disable race, failed/uncertain/blocked calls, explicit test allowance, global/per-work exhaustion.

**Acceptance criteria:**

- [ ] Concurrent/restarted clients cannot overspend the configured reservation limits
- [ ] Blocked calls count zero; sent/uncertain calls remain conservatively accounted
- [ ] Test-connection permission does not enable background paid routing

**Completion evidence:** Not yet executed. Required: Concurrency and cost-ledger regression results. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-08](prompts/AST-08.md).

## AST-09 — Resolve provider configuration at operation boundaries

- **ID:** AST-09
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M2
- **Dependencies:** AST-08
- **Relative size:** M
- **Risk:** high; A Settings save must affect execution without stale environment-only constructors.
- **Reversibility:** Select local in metadata; preserve generation/history and old analysis identities.

**Objective:** Make actual workers and API capabilities consume the same versioned authority.

**Why now:** A Settings save must affect execution without stale environment-only constructors.

**Files/subsystems:** newsroom/runtime.py; newsroom/article_analysis.py; newsroom/document_processing.py; newsroom/domain_api.py; newsroom/intelligent_monitoring.py.

**Implementation approach:** Implement immutable config snapshots resolved at new operation boundaries, lazy client lifecycle and effective generation telemetry. Route Article Analysis through shared metadata/vault. Keep unsupported capabilities explicitly local through the same resolver. Add explicit legacy environment import/source labeling and managed-config precedence; disable/removal must not resurrect env providers.

**Non-goals:** Changing frozen eval contracts, remote relevance/entailment, replaying historical analysis under a new identity silently.

**Tests:** Edit while worker alive, in-flight pinning, provider disable/delete, environment precedence, local fallback identity and restart persistence.

**Acceptance criteria:**

- [ ] Next work uses saved generation without restarting while in-flight work keeps its identity
- [ ] All product construction paths report supported local/remote authority coherently
- [ ] Disable/remove falls back safely and no legacy environment variable re-enables the provider

**Completion evidence:** Not yet executed. Required: Multi-process configuration-generation tests and effective-route records. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-09](prompts/AST-09.md).

## AST-10 — Add bounded provider validation and safe API contracts

- **ID:** AST-10
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M2
- **Dependencies:** AST-09
- **Relative size:** M
- **Risk:** high; Users need useful failure diagnosis before background spending.
- **Reversibility:** Disable test endpoint/route; keep metadata and credentials intact.

**Objective:** Provide explicit safe connection tests and provider-management APIs.

**Why now:** Users need useful failure diagnosis before background spending.

**Files/subsystems:** newsroom/domain_api.py; newsroom/app.py; newsroom/article_analysis.py; provider service from AST-06/09; tests/test_phase21_article_analysis.py.

**Implementation approach:** Implement proposed CRUD/credential/test/routes/status APIs with auth/CSRF/no-store, safe errors and optimistic revision. Test actual configured structured-output capability using a bounded explicit reservation; no auto-test. Validate HTTPS/loopback keyless rules, redirects, DNS/destination and host-change secret handling. Manual model entry remains sufficient.

**Non-goals:** Automatic paid checks, arbitrary provider headers, broad endpoint compatibility claims or new SDKs.

**Tests:** Fake transport for auth failure, timeout, malformed JSON/schema, host redirect/credential forwarding, unsupported model, stale validation revision, test cap exhaustion.

**Acceptance criteria:**

- [ ] Explicit test yields a safe revision-bound capability result without raw provider body
- [ ] Credential cannot be forwarded to a changed/unapproved destination
- [ ] No provider call occurs on listing, edit, startup or typing; test never enables background spend

**Completion evidence:** Not yet executed. Required: API security/error matrix and mock request counts. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-10](prompts/AST-10.md).

## AST-11 — Build functional AI Providers and cost settings

- **ID:** AST-11
- **Status:** NOT_STARTED
- **Priority:** P0
- **Milestone:** M2
- **Dependencies:** AST-10
- **Relative size:** M
- **Risk:** medium; The current Settings renders raw rows and budget JSON without configuration controls.
- **Reversibility:** Revert UI only; metadata/vault remain manageable through authenticated API.

**Objective:** Let the owner configure and understand real Article Analysis routing in Settings.

**Why now:** The current Settings renders raw rows and budget JSON without configuration controls.

**Files/subsystems:** frontend/src/views/AdminViews.tsx; frontend/src/lib/api.ts; frontend/src/lib/types.ts; frontend/src/styles.css; newsroom/domain_api.py.

**Implementation approach:** Add named Settings sections and provider Add/Edit/Test/Enable/Disable/Model/Remove/Set-default controls. Show fixed mask/configured flag, offline explanation, supported capability, active model/generation, validation and failure, paid switch and typed existing budget controls. Clear secret after submit and label estimated usage honestly. Split a component only if needed for contained readability.

**Non-goals:** Brand catalog, remote Ask promise, browser secret storage, redesigning all Settings.

**Tests:** Browser fake-provider Add AI Provider acceptance, bad inputs, stale edits, failed removal, screen-reader labels, save/refresh and next worker operation.

**Acceptance criteria:**

- [ ] Full special acceptance succeeds with a fake provider and actual configured worker path
- [ ] No raw secret is returned/persisted in browser state/storage after submission
- [ ] User can see offline/active model/paid/budget/failure/reload state and recover without terminal

**Completion evidence:** Not yet executed. Required: Journey screenshots, API/worker identity proof and sentinel audit; live paid test remains separately authorized. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-11](prompts/AST-11.md).

## AST-12 — Make first Watch and scoped use possible without IDs

- **ID:** AST-12
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M3
- **Dependencies:** AST-11
- **Relative size:** M
- **Risk:** medium; Current Watch and scoped Ask forms require canonical IDs; empty collection views cannot create needed records.
- **Reversibility:** Revert workflow UI; preserve user-created canonical records and existing APIs.

**Objective:** Complete the first-value path for a normal user.

**Why now:** Current Watch and scoped Ask forms require canonical IDs; empty collection views cannot create needed records.

**Files/subsystems:** frontend/src/views/WatchManagementView.tsx; frontend/src/views/AdminViews.tsx; frontend/src/views/AskView.tsx; frontend/src/components/AuthView.tsx; newsroom/domain_api.py.

**Implementation approach:** Use existing APIs for named topic creation/selection, reviewed source entry and simple cadence presets within Watch setup. Provide contextual or named scope selection for Ask. Detect setup availability safely, replace trial-specific defaults and API jargon. Keep advanced policy/IDs available deliberately, prevent unsupported direct Monitor creation.

**Non-goals:** Changing approved trial sources, auto-approving candidates, new Monitor target adapters, generic onboarding platform.

**Tests:** Fresh DB browser user journey: setup → named topic/source/Watch → due fixture → Home/evidence → scoped Ask/refusal; edit/disable persistence and invalid input.

**Acceptance criteria:**

- [ ] First Watch requires no copied IDs or terminal/API calls by user
- [ ] Source review/pinned scope and offline zero-spend behavior are preserved
- [ ] Contextual Ask and empty states give a working next action without inventing evidence

**Completion evidence:** Not yet executed. Required: Fresh-install journey evidence and integration checks. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-12](prompts/AST-12.md).

## AST-13 — Finish dark-theme and responsive control behavior

- **ID:** AST-13
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M3
- **Dependencies:** AST-12
- **Relative size:** M
- **Risk:** medium; Phone Settings has overlapping buttons inside two-column cards; literal colors impede consistent verification.
- **Reversibility:** Revert stylesheet/component changes; no schema/data changes.

**Objective:** Keep the dark design and fix confirmed mobile/contrast/accessibility gaps.

**Why now:** Phone Settings has overlapping buttons inside two-column cards; literal colors impede consistent verification.

**Files/subsystems:** frontend/src/styles.css; frontend/src/components/ViewPrimitives.tsx; frontend/src/components/AppShell.tsx; frontend/public/manifest.webmanifest; frontend/index.html.

**Implementation approach:** Consolidate semantic colors within existing CSS; collapse generic content grids and wrap controls at small widths; align chrome/offline surfaces. Measure contrast and fix failing pairs, focus/overlay behavior, reduced motion and zoom. Preserve dark-only default and existing design.

**Non-goals:** Light palette, redesign, CSS framework/dependency or decorative animation.

**Tests:** Dark-experience matrix at 320/390/768/1440px, 200% zoom, populated/error/loading/offline states, keyboard and component-bound checks.

**Acceptance criteria:**

- [ ] No overlapping/clipped controls including Settings buttons and no unexpected bright surfaces
- [ ] Text/focus/control contrast and keyboard checks have measured evidence
- [ ] All main views and PWA chrome retain coherent dark presentation

**Completion evidence:** Not yet executed. Required: Before/after screenshots, contrast/focus checklist and frontend build. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-13](prompts/AST-13.md).

## AST-14 — Wrap verified backup and recovery in owner controls

- **ID:** AST-14
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M3
- **Dependencies:** AST-13
- **Relative size:** M
- **Risk:** high; Existing SQLite operations are useful but require manual runtime/process handling.
- **Reversibility:** Keep prior verified database/artifact; rollback only using supported recovery, not live file copies.

**Objective:** Provide safe backup/recovery/update preparation without remembered commands.

**Why now:** Existing SQLite operations are useful but require manual runtime/process handling.

**Files/subsystems:** newsroom/operations.py; newsroom/cli.py; newsroom/domain_api.py; frontend/src/views/AdminViews.tsx; docs/RECOVERY_RUNBOOK.md.

**Implementation approach:** Expose named backup/status/diagnostic actions using existing verified operations and managed lifecycle. Keep restore/update as clearly reviewed workflows with exact target/backup identity and stopped writers; stage before replacement and retain failure evidence. Diagnostics use explicit non-secret allowlists. Reuse release verification rather than an auto-updater service.

**Non-goals:** Unattended destructive restore, arbitrary filesystem API, exporting credentials or raw private content in support bundles.

**Tests:** Temporary populated DB backup/restore equality/integrity, corrupt backup, disk/write failure, active-writer refusal, secret exclusion, UI recovery state.

**Acceptance criteria:**

- [ ] Owner can create and verify a backup through a clear action
- [ ] Restore/update preparation proves target identity, stopped writers and safe failure preservation
- [ ] Diagnostic/export output excludes credentials and gives actionable status

**Completion evidence:** Not yet executed. Required: Temporary installation recovery report, integrity results and UI screenshots. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-14](prompts/AST-14.md).

## AST-15 — Verify representative content-to-value paths

- **ID:** AST-15
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M3
- **Dependencies:** AST-14
- **Relative size:** M
- **Risk:** high; A3 broad-page path deferred and metadata-only path succeeded; neither proves normal article usefulness.
- **Reversibility:** Revert measured code fix; fixture report remains; no active trial changes.

**Objective:** Separate working pipeline plumbing from useful article/Story yield and fix only proven blockers.

**Why now:** A3 broad-page path deferred and metadata-only path succeeded; neither proves normal article usefulness.

**Files/subsystems:** newsroom/acquisition.py; newsroom/ai.py; newsroom/automatic_story_resolution.py; tests/test_phase21_article_analysis.py; docs/reviews/PHASE_29_PIPELINE_REHEARSAL.md.

**Implementation approach:** Build a small lawful sanitized fixture set representing article body, navigation-heavy page, feed metadata, unchanged content and blocked source. Record input quality and stage outcomes through production handlers. Reproduce before any minimal content extraction/local candidate repair; preserve exact-span hashes and conservative resolution. If no proven defect, record evidence and propose a separate bounded follow-up rather than tuning thresholds.

**Non-goals:** Relaxing retrieval saturation, changing frozen trial sources/corpus, claiming metadata as full body, bypassing source restrictions.

**Tests:** Representative acquisition → relevance → analysis → promotion → Story/report/alert where qualified; duplicate replay, false-merge and no-evidence negative cases.

**Acceptance criteria:**

- [ ] Body/metadata/blocked/deferred outcomes are explicit with nonzero reviewed denominators
- [ ] Any repair has a reproduction and no trust-boundary regression
- [ ] At least a qualifying article-body fixture completes end to end; real usefulness remains a human gate

**Completion evidence:** Not yet executed. Required: Per-fixture stage/quality report, regression results and remaining unknowns. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-15](prompts/AST-15.md).

## AST-16 — Continue the approved observation with honest usefulness evidence

- **ID:** AST-16
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M4
- **Dependencies:** AST-01
- **Relative size:** S
- **Risk:** medium; Short checkpoint has insufficient active time/events; calendar duration is a real dependency.
- **Reversibility:** Observation cannot be undone; preserve original records and append corrections.

**Objective:** Complete the already-started observation protocol without resetting or inventing results.

**Why now:** Short checkpoint has insufficient active time/events; calendar duration is a real dependency.

**Files/subsystems:** docs/DOGFOOD_CONTRACT.md; docs/reviews/PHASE_29_OBSERVATION_PROTOCOL.md; docs/reviews/PHASE_29_WEEK_1_CHECKPOINT.md; docs/reviews/PHASE_29_HUMAN_USEFULNESS_LOG_TEMPLATE.md; docs/reviews/PHASE_29_UAP_PROSPECTIVE_EXPERIMENT_V1.md.

**Implementation approach:** Use existing approved Watch and frozen boundary; collect safe aggregates and request actual owner usefulness entries. Track active time, no-event intervals, source/content quality, missed changes and repairs. Keep raw data/logs outside git. Log any authorized runtime/config change as a segment. Extend when volume/time is insufficient.

**Non-goals:** Starting an automation without request, manufacturing usefulness ratings, redefining criteria or changing sources/provider silently.

**Tests:** Validate observation interval arithmetic, provenance and event denominators; follow existing protocol check commands without modifying data unnecessarily.

**Acceptance criteria:**

- [ ] Required minimum window and eligible observation evidence exist, or task stays explicitly incomplete
- [ ] Human usefulness log is real and changes/outages are accounted for
- [ ] Private data stays outside repository and safe summary cites frozen identities

**Completion evidence:** Not yet executed. Required: Dated safe observation report, private evidence references and human review completion. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-16](prompts/AST-16.md).

## AST-17 — Execute the frozen comparison under its exact contract

- **ID:** AST-17
- **Status:** BLOCKED
- **Priority:** P1
- **Milestone:** M4
- **Dependencies:** AST-01
- **Relative size:** M
- **Risk:** high; Contract validation passed but is not a comparative result; paid permission and eligible data are missing gates.
- **Reversibility:** Spending cannot be reversed; invalid runs marked invalid and retained, never relabeled.

**Objective:** Obtain valid Full-vs-Lite evidence separate from the prospective trial.

**Why now:** Contract validation passed but is not a comparative result; paid permission and eligible data are missing gates.

**Files/subsystems:** newsroom/evals/phase29_protocol.py; newsroom/evals/benchmark.py; newsroom/evals/benchmark_provider.py; docs/reviews/PHASE_29_EVALUATION_PROTOCOL.md; evals/lite/20q_contract.json.

**Implementation approach:** Prepare eligible snapshot manifest mapping every case/candidate and cutoff using the frozen protocol; verify route/model/budget. Obtain explicit paid authorization before execution, preserve blinded mapping outside git, obtain actual human scoring and report insufficient categories honestly. Historical and prospective protocols remain separate.

**Non-goals:** Changing frozen question set/model/cutoff, replacing evidence with arbitrary UAP snapshot, agent self-scoring, unapproved calls.

**Tests:** Offline contract/eligibility validation, intentional wrong model/snapshot/fallback rejection, reproducible blind-score aggregation.

**Acceptance criteria:**

- [ ] Each run proves eligible snapshot and exact effective contract; no hidden fallback
- [ ] Paid execution is explicitly authorized and human blinded scores are retained
- [ ] Results show category/guardrail evidence, cost and latency without manufacturing missing coverage

**Completion evidence:** Not yet executed. Required: External snapshot/run hashes, safe report, authorization reference and scoring evidence. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-17](prompts/AST-17.md).

## AST-18 — Issue the evidence-based product scope verdict

- **ID:** AST-18
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M4
- **Dependencies:** AST-15, AST-16, AST-17
- **Relative size:** S
- **Risk:** medium; Engineering completion cannot settle value or commercial promise.
- **Reversibility:** Append a new verdict if later evidence changes; preserve original decision and experiment.

**Objective:** Decide what earns the daily product and whether broad expansion is justified.

**Why now:** Engineering completion cannot settle value or commercial promise.

**Files/subsystems:** docs/reviews/PHASE_29_DECISION_RULE.md; plan/astra/COMMERCIAL_THESIS.md; plan/astra/DELETE_DEFER_KEEP.md; observation/comparison reports from AST-16/17.

**Implementation approach:** Apply unchanged three-of-five categories and trust guardrails; distinguish historical comparison, prospective observation and owner usability. Produce KEEP/SIMPLIFY/CONTEXTUALIZE/DEFER/REMOVE per feature. Explicitly decide AST-21/22 activation and release scope. Inconclusive evidence leaves value acceptance open.

**Non-goals:** Inventing market evidence, moving thresholds, automatic Phase 30 or company-launch declaration.

**Tests:** Audit category score arithmetic, case provenance, blind scoring, effective route and evidence gaps against preregistered rules.

**Acceptance criteria:**

- [ ] Verdict is linked to actual human/eligible comparative evidence
- [ ] No trust regression or missing category is disguised as a pass
- [ ] Release scope and conditional task statuses are explicitly updated

**Completion evidence:** Not yet executed. Required: Signed-off/attributed value verdict with evidence links and task updates. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-18](prompts/AST-18.md).

## AST-19 — Qualify the installed daily-use release candidate

- **ID:** AST-19
- **Status:** NOT_STARTED
- **Priority:** P1
- **Milestone:** M5
- **Dependencies:** AST-05, AST-11, AST-12, AST-13, AST-14, AST-18
- **Relative size:** M
- **Risk:** high; Local tests do not qualify Windows installation, update, recovery or phone use.
- **Reversibility:** Retain prior artifact and verified backup; roll back compatibly through managed recovery.

**Objective:** Prove the selected product can be operated without engineering assistance.

**Why now:** Local tests do not qualify Windows installation, update, recovery or phone use.

**Files/subsystems:** scripts/phase16_windows_deploy.ps1; newsroom/release.py; docs/OPERATIONS_RUNBOOK.md; docs/RECOVERY_RUNBOOK.md; plan/astra/PRODUCT_READINESS.md.

**Implementation approach:** Build a named clean artifact and qualify in isolated Windows install. Execute Start Newsroom, Add AI Provider (fake plus separately authorized live if required), Dark Experience and full local daily-use matrix. Rehearse upgrade from prior schema/artifact, rollback/recovery, phone/PWA, offline/update behavior and credentials after sign-in. Record limitations and no-go results.

**Non-goals:** Publishing automatically, modifying active trial for qualification, claiming all browsers/platforms supported.

**Tests:** Full applicable offline gates, installed lifecycle/credential/recovery tests, physical supported phone/PWA, end-to-end qualified evidence workflow.

**Acceptance criteria:**

- [ ] Daily-use checklist has release-specific evidence and no unresolved P0/P1 blocker
- [ ] Upgrade/recovery and credential exclusion/access survive installed lifecycle
- [ ] Phone/PWA and all special acceptance tests pass or release scope explicitly excludes unqualified promises

**Completion evidence:** Not yet executed. Required: Release identity/manifests, completed acceptance report and known limitations. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-19](prompts/AST-19.md).

## AST-20 — Remove only proven obsolete completion scaffolding

- **ID:** AST-20
- **Status:** NOT_STARTED
- **Priority:** P2
- **Milestone:** M5
- **Dependencies:** AST-19
- **Relative size:** S
- **Risk:** medium; Phase naming is not itself a defect; only demonstrated redundant entry points should be retired.
- **Reversibility:** Revert bounded deletion; no history/data removal.

**Objective:** Reduce permanent support burden after release paths are known.

**Why now:** Phase naming is not itself a defect; only demonstrated redundant entry points should be retired.

**Files/subsystems:** plan/astra/DELETE_DEFER_KEEP.md; scripts/phase12_browser_smoke.py; scripts/phase12_server.py; newsroom/domain.py; README.md.

**Implementation approach:** Trace callers/tests/data dependencies for each candidate in DELETE_DEFER_KEEP. Retire or guard obsolete normal-user launcher/smoke paths once replacements cover them; correct stale runtime comments. Delete only demonstrated unused code and document public compatibility impact. Keep history/eval tools and migration chains.

**Non-goals:** Bulk phase rename, deleting old plans/reference code, removing evidence history/legacy accounting or unrelated cleanup.

**Tests:** Reference search, affected regression tests and clean supported entry-point smoke.

**Acceptance criteria:**

- [ ] Each deletion has caller/data/coverage evidence
- [ ] Normal docs expose one startup authority and no unsafe test defaults
- [ ] Historical data/migrations/contracts remain readable and tests pass

**Completion evidence:** Not yet executed. Required: Candidate-by-candidate disposition and focused diff/check results. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-20](prompts/AST-20.md).

## AST-21 — Integrate paid Ask only if its value is demonstrated

- **ID:** AST-21
- **Status:** DEFERRED
- **Priority:** P2
- **Milestone:** Conditional
- **Dependencies:** AST-11, AST-18
- **Relative size:** M
- **Risk:** high; Remote benchmark synthesis is not a production feature; do not widen first completion scope speculatively.
- **Reversibility:** Switch Ask route to local; preserve conversations/audit history.

**Objective:** Make normal Ask optionally use the same managed provider safely if the value verdict retains it.

**Why now:** Remote benchmark synthesis is not a production feature; do not widen first completion scope speculatively.

**Files/subsystems:** newsroom/ask.py; newsroom/domain_api.py; newsroom/evals/benchmark_provider.py; frontend/src/views/AskView.tsx; tests/test_phase14_ask.py.

**Implementation approach:** After explicit scope activation, reuse the production config/vault/durable budget service and a reviewed compatible synthesis adapter. Bind prose/statement citations to allowed retrieved evidence, preserve no-evidence refusal/temporal scope and cancellation. Display effective local/remote model and fallback. Do not import benchmark experiment policy into product defaults.

**Non-goals:** General web chat, remote entailment/relevance, ungrounded synthesis, changing frozen eval adapters.

**Tests:** Unsupported citation/claim rejection, insufficient evidence, temporal reads, cancellation/uncertain billing, shared reload and budget checks; authorized live test only if requested.

**Acceptance criteria:**

- [ ] Normal Ask uses selected supported managed route and reports identity
- [ ] Every generated factual statement remains bound to qualifying evidence or is rejected/qualified
- [ ] Local/refusal fallback and cost constraints survive failures without benchmark contamination

**Completion evidence:** Not yet executed. Required: Value activation decision, trust tests and product journey evidence. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-21](prompts/AST-21.md).

## AST-22 — Run a bounded commercial pilot after value qualification

- **ID:** AST-22
- **Status:** DEFERRED
- **Priority:** P2
- **Milestone:** Conditional
- **Dependencies:** AST-18, AST-19
- **Relative size:** S
- **Risk:** medium; No market/customer evidence currently justifies commercial infrastructure.
- **Reversibility:** Stop enrollment/distribution; preserve user export/recovery and honor agreed data handling.

**Objective:** Test willingness to pay and support burden with the smallest real pilot.

**Why now:** No market/customer evidence currently justifies commercial infrastructure.

**Files/subsystems:** plan/astra/COMMERCIAL_THESIS.md; plan/astra/PRODUCT_READINESS.md; release acceptance from AST-19; docs/THREAT_MODEL.md; pyproject.toml.

**Implementation approach:** After owner authorizes pilot scope, define target specialists, limited supported platform/feature promise, participant consent/data handling, purchase-intent test and support-effort log. Review distribution dependencies/licenses and source/privacy terms with appropriate expertise. Draft materials before requesting publication/contact authorization.

**Non-goals:** Unapproved outreach, fabricated pricing/traction, billing platform, multi-tenancy, enterprise features.

**Tests:** Dry-run onboarding/recovery/support flow, dependency/distribution review, actual participant outcome/retention/payment-intent evidence when authorized.

**Acceptance criteria:**

- [ ] Pilot promise and support/privacy/distribution boundaries are concrete and reviewed
- [ ] Actual user value/purchase-intent/support evidence is distinguished from hypotheses
- [ ] Continue/simplify/stop decision is recorded without speculative platform build

**Completion evidence:** Not yet executed. Required: Authorized pilot brief and actual participant findings, kept appropriately private. Record actual HEAD/artifact, changed files, commands with exit results, manual checks and remaining limitations here upon completion.

**Prompt:** [AST-22](prompts/AST-22.md).
