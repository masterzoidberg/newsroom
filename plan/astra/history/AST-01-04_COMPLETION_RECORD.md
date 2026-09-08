# Historical branch completion evidence

Source: `git show astra/AST-05-start-newsroom:plan/astra/TASKS.md` at `cddad09`. This preserves the four completed task sections verbatim except prompt links relocated to the archive. Historical statuses/PR claims are records, not a live queue or fresh hosted verification. Main does not contain these implementations.

## AST-01 — Freeze the execution baseline and isolate development from observation

- **ID:** AST-01
- **Status:** DONE
- **Priority:** P0
- **Milestone:** M0
- **Dependencies:** None
- **Relative size:** M
- **Risk:** medium; Current local tests pass, but Linux CI's backend job encounters an npm.cmd build test and lacks frontend dependency setup; active trial must remain frozen.
- **Reversibility:** Revert bounded docs/CI/test changes; no runtime migration.

**Objective:** Make this audited baseline reproducible and give subsequent work a safe development/qualification target.

**Why now:** Current local tests pass, but Linux CI's backend job encounters an npm.cmd build test and lacks frontend dependency setup; active trial must remain frozen.

**Files/subsystems:** README.md; .github/workflows/ci.yml; tests/test_phase12_frontend.py; tests/test_phase13_frontend.py; tests/test_phase14_frontend.py; docs/reviews/ASTRA_EXECUTION_BASELINE.md. Inspected without changing frontend/package.json, docs/reviews/PHASE_29_BASELINE_ACCEPTANCE.md, docs/DOGFOOD_CONTRACT.md, newsroom/config.py and tests/test_runtime_config.py.

**Implementation approach:** Record current HEAD/worktree and trial boundary; establish explicit outside-repo dev/test roots and separate configured endpoint. Make the frontend build test portable and ensure its invoking CI job has required Node/frontend dependencies, or move the build responsibility cleanly to the existing frontend CI job without losing coverage. Update current authority pointers only; preserve historical claims as dated records.

**Non-goals:** Rewriting test architecture, fixing unrelated mypy annotations, changing the active trial, installing/restarting production.

**Tests:** Run backend suite, ruff, frontend build and offline eval validation; verify CI command/executable selection on Linux and Windows or record remaining hosted-run evidence.

**Acceptance criteria:**

- [x] Reproducible baseline is recorded with exact HEAD and check results
- [x] CI no longer depends on Windows-only npm.cmd in its Linux backend path or missing frontend installation
- [x] Safe explicit dev/test root and port are documented; active trial and unrelated files unchanged

**Completion evidence:**

- Started from remote `main` HEAD `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f` and created `astra/AST-01-baseline` directly from that commit. Schema remains 36; no migration or runtime behavior changed.
- Frozen observation boundary remains `2026-09-06T21:20:48Z` with earliest four-week boundary `2026-10-04T21:20:48Z`. The logical trial `phase29-trial/prod`, its Watch/Sources/provider/budget/processes/data and port `8127` were not contacted or modified.
- Astra development is explicitly isolated at `%LOCALAPPDATA%\Newsroom\astra-dev\dev` on `127.0.0.1:18127`; manual tests use per-run outside-repository roots ending in `dev`. Existing `RuntimeConfig` suffix/source-tree guards remain the single root authority.
- Initial isolated reproduction: `python -m pytest -q tests/test_phase12_frontend.py tests/test_runtime_config.py` failed exactly on Windows-only `npm.cmd`; all five runtime-root tests passed. After the first refactor the same command passed 6/6.
- The first draft-PR run `34076549706` at implementation commit `99aa49c3047f31ccc18b5e6f6a3869811e36abff` passed Ruff and the complete frontend job, then exposed two additional identical `npm.cmd` calls in `tests/test_phase13_frontend.py` and `tests/test_phase14_frontend.py`. The task stayed open rather than treating partial CI as success.
- The supplied repository snapshot's Phase 13/14 test blobs exactly matched remote `main`; repository-wide test scanning found no other `npm.cmd` build invocations. After removing those duplicate build subprocesses, `python -m pytest -q tests/test_phase12_frontend.py tests/test_phase13_frontend.py tests/test_phase14_frontend.py tests/test_runtime_config.py` passed 8/8.
- Offline eval checks passed: `python -m newsroom.evals validate` (46 valid cases), `python -m newsroom.evals lite-contract` (20-question contract valid; no comparative execution), and `python -m newsroom.evals baseline` (20 baseline/semantic cases executed; diagnostic only).
- Clean Ubuntu draft-PR run `34076899509` at code commit `1d22282955c3dfa9057c0c765dd8b4988de58236` passed backend `python -m pytest -q`, Ruff, frontend `npm ci`, lint, typecheck and production Vite build. This is the authoritative full-suite/build evidence for the implementation code.
- Local full pytest was not claimed: the bounded local container run exceeded its execution window. Local Ruff was unavailable, and the uploaded Windows-shaped `node_modules` lacked Rollup's Linux optional binary; hosted clean CI superseded those local limitations.
- No paid provider call was made. No secrets, runtime DB/log/backup/content artifacts, private trial data or historical acceptance records were changed.
- Detailed baseline/root/CI evidence is recorded in `docs/reviews/ASTRA_EXECUTION_BASELINE.md`. Draft PR #1 remains unmerged.

**Prompt:** [AST-01](../prompts/archive/AST-01.md).

## AST-02 — Identify application instances and diagnose port conflicts

- **ID:** AST-02
- **Status:** DONE
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-01
- **Relative size:** M
- **Risk:** high; Current 8127 already serves Newsroom but duplicate startup blindly binds.
- **Reversibility:** Revert launcher preflight; retain existing explicit operator commands.

**Objective:** Add ownership-aware preflight and bind-failure diagnosis for the configured endpoint.

**Why now:** Current 8127 already serves Newsroom but duplicate startup blindly binds.

**Files/subsystems:** `newsroom/runtime.py`; `newsroom/app.py`; new `newsroom/runtime_identity.py`; new `tests/test_runtime_identity.py`; new `tests/test_runtime_identity_recovery.py`. Existing `newsroom/config.py`, `tests/test_runtime_config.py`, `tests/test_phase16_deployment.py` and release/install contracts were inspected and exercised without schema or installer behavior changes.

**Implementation approach:** Add a stable non-secret installation identity and process identity checks using root/role/release plus PID creation time. Use an OS exclusive lock, not a PID-file-only guard. Define status protocol for matching, unmanaged, foreign and unknown owners. Handle the bind race after preflight. Permit healthy verified reuse; never terminate or silently move ports.

**Non-goals:** Starting a new service architecture, taking over active unmanaged trial processes, arbitrary process termination.

**Tests:** Temporary sockets/processes: same instance, foreign listener, wrong root, stale PID, concurrent preflight and bind race.

**Acceptance criteria:**

- [x] Matching healthy instance is reused without a second API bind
- [x] Foreign/mismatched/unknown ownership gives actionable fixed-port diagnosis and no kill
- [x] Concurrent launches and PID reuse cannot falsely identify another process

**Completion evidence:**

- AST-02 was implemented on `astra/AST-02-instance-preflight`, stacked from verified AST-01 head `4dfc950c3b574cac37d0f149730dd3b97716d880` because AST-01 remains an unmerged draft dependency. Remote `main` remained at `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f` during implementation.
- Final implementation head before plan-only closure is `b180e0f138f7ba1c544f7e91166de945515bf81c`. Schema remains 36. No migration file, provider route, budget authority, evidence/provenance rule or data model changed.
- `runtime_identity.py` persists a stable installation UUID under the canonical runtime root, holds an OS-backed exclusive API lock, records diagnostic owner metadata with canonical root/role/release/PID/process-creation token, verifies process identity against PID reuse, and classifies endpoints as `available`, `matching`, `mismatched`, `unmanaged`, `foreign` or `unknown`.
- `GET /api/v1/runtime/identity` exposes only bounded non-secret identity needed for local verification and is marked `Cache-Control: no-store`; filesystem paths are not returned publicly.
- API startup now establishes ownership/preflight before applying API migrations or binding. A healthy verified same-installation/same-release API returns a successful reuse result without a second Uvicorn bind. A matching HTTP identity without the expected OS lock is treated as unknown rather than trusted.
- Different-root Newsroom, unmanaged Newsroom, unrelated foreign listeners and unverifiable/ambiguous listeners all fail on the configured fixed endpoint with recovery guidance. No diagnostic path terminates a process or silently chooses another port.
- Concurrent same-root launches converge through the OS lock plus a bounded reconciliation window. A discovered edge where the first lock holder can die before publishing a usable API was corrected: the waiting launcher may take the released OS lock and proceed, but only after actually owning it. No infinite retry loop was introduced.
- A post-preflight Uvicorn bind failure is diagnosed through the same ownership-aware fixed-port path, covering the bind race without fallback port selection.
- Packaged release identity remains supported: the larger installed `release-manifest.json` uses a separate bounded reader rather than weakening the small runtime-owner metadata bound. Corrupt stale owner metadata degrades to untrusted/unknown rather than crashing or being trusted.
- Final local affected command `python -m pytest -q tests/test_runtime_identity.py tests/test_runtime_identity_recovery.py tests/test_runtime_config.py tests/test_phase16_deployment.py tests/test_api.py` passed all 22 collected tests. `python -m compileall -q newsroom tests` also passed. Local Ruff was unavailable, so no local Ruff pass is claimed.
- Hosted GitHub Actions run `34082005737` at implementation head `b180e0f138f7ba1c544f7e91166de945515bf81c` passed Ruff, the full backend pytest suite, frontend `npm ci`, lint, typecheck and production build.
- Redacted managed identity example: `{"managed":true,"installation_id":"<uuid>","role":"api","release_id":"<release>","pid":"<pid>","process_creation_token":"<creation-token>"}`. Matching status reuses the owner; mismatched/unmanaged/foreign/unknown status returns fixed-port recovery guidance and explicitly performs no kill/no alternate-port action.
- Tests used ephemeral loopback ports and temporary roots only. The active `phase29-trial/prod` runtime, its data/processes and port `8127` were not contacted or modified. No paid provider call was made and no secret/private trial artifact was read or committed.
- Remaining qualification boundary: the Windows-specific process creation-time implementation is source/compile reviewed but was not exercised in a clean installed Windows lifecycle during AST-02. Installed Windows lifecycle qualification remains AST-05/AST-19; this does not weaken the tested ownership contract or justify claiming that later gate complete.
- Draft PR #2 remains open, stacked on `astra/AST-01-baseline`, and is not merged.

**Prompt:** [AST-02](../prompts/archive/AST-02.md).

## AST-03 — Supervise existing runtime components safely

- **ID:** AST-03
- **Status:** DONE
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-02
- **Relative size:** M
- **Risk:** high; Port checks alone do not ensure processing or prevent child divergence.
- **Reversibility:** Disable new supervisor in isolated install and use existing commands; no data rollback.

**Objective:** Own one API, worker and scheduler with bounded startup, shutdown and recovery.

**Why now:** Port checks alone do not ensure processing or prevent child divergence.

**Files/subsystems:** `newsroom/runtime.py`; new `newsroom/runtime_managed.py`; new `newsroom/runtime_supervisor.py`; new `newsroom/job_lease.py`; `newsroom/worker.py`; new `tests/test_runtime_supervisor.py`; new `tests/test_worker_lease.py`. Existing scheduler/job/runtime-identity/Phase 7/Phase 16 contracts were exercised without schema or provider changes.

**Implementation approach:** Keep the existing three child entry points and place one small per-runtime supervisor around them. Use one root/release/endpoint manifest, OS-backed per-role ownership locks, PID-creation-token verification, heartbeats, token-bound stop controls, all-role preflight, bounded child restart/backoff, and cooperative writer drain. Managed migrations are owned by the supervisor only when every component lock is free. Preserve AST-02 endpoint/no-kill invariants. Renew a running Job lease only while the same worker still owns the synchronous handler.

**Non-goals:** Replacing durable jobs, distributed workers, task queue rewrite, forced termination of unmanaged processes, AST-04 browser controls or AST-05 installer/shortcut work.

**Tests:** Subprocess crash/restart, supervisor crash with children alive, long handler beyond lease, cancellation, stale heartbeat, unmanaged component, graceful drain and bounded restart exhaustion.

**Acceptance criteria:**

- [x] One owned child per required role survives repeated/concurrent launches
- [x] Stop/restart drains or reports deadline safely and never duplicates downstream work or uncertain paid calls
- [x] Failure/restart bounds and long-handler lease safety have explicit test evidence

**Completion evidence:**

- AST-03 was implemented on `astra/AST-03-supervisor`, stacked from AST-02 closure head `db5d94bc6ed531d130bdc853e54474f403425fc6` because AST-01/02 remain verified unmerged draft dependencies. Implementation head before plan-only closure is `6c2b17edf83f3ea72401b1b2291c48748b8977cd`; schema remains 36.
- `RuntimeSupervisor` owns/reconciles one API, worker and scheduler for one installation/root/release/endpoint manifest. Each managed role uses an OS-backed lock plus installation/root/release/PID/process-creation identity and a fresh heartbeat. A second supervisor converges on the verified existing supervisor/children rather than spawning duplicates.
- Actual subprocess evidence kills the supervisor process while its three children remain alive, then starts a replacement supervisor and asserts exact child PID reconciliation. Repeated launch likewise retains the same three child PIDs, giving one verified owner per required role.
- Startup preflights all roles before spawning missing siblings. A stale, ambiguous or verified unmanaged component blocks managed startup rather than causing a partial new child set. No path treats stale metadata as permission to kill or take over a process.
- Child crash recovery is per-role and bounded. A missing owned child restarts with capped exponential backoff; healthy siblings keep their PIDs. After the configured retry cap, status becomes `restart_exhausted` rather than looping forever.
- Stop/restart requests are written only for verified `supervisor_managed` owners and bind the target PID plus process-creation token. Shutdown stops scheduler/worker first, waits for a bounded drain, then stops API cooperatively through Uvicorn's exit flag. An unmanaged/ambiguous role is reported, not terminated. A busy managed writer that exceeds the deadline is reported as remaining rather than force-killed.
- Normal managed migration ownership moves to the supervisor only when all three component locks are free. A replacement supervisor reconciling active same-release children performs no migration write. Advanced/direct commands remain available and are marked unmanaged relative to supervisor authority.
- The existing 120-second running-job lease had a demonstrated supervision risk: synchronous handlers did not renew it. AST-03 adds bounded periodic renewal while the same `worker_id` still owns the running Job. Renewal stops before durable completion; if ownership is lost, the original worker does not write a competing terminal outcome.
- Long-work/cancellation evidence uses a one-second lease with a handler running beyond the original expiry. Recovery does not create a second attempt while renewal is active; cancellation remains durable and the worker does not overwrite it. No paid provider is invoked, so uncertain paid work is not synthetically retried or relabeled.
- Lifecycle state evidence: `healthy` → reuse verified owner; `missing` → start/restart within bounds; `stale`/`ambiguous`/`unmanaged` → degraded/no duplicate/no kill; supervisor loss with healthy children → reconcile exact owners; restart cap reached → `restart_exhausted`; drain deadline with active writer → report remaining role and keep API up rather than force termination.
- Local isolated command `python -m pytest -q tests/test_runtime_supervisor.py tests/test_worker_lease.py tests/test_phase07_jobs.py tests/test_phase16_deployment.py` passed 20/20. `python -m compileall -q newsroom tests` passed. A broader local full-pytest attempt exceeded the container execution window and local Ruff was unavailable, so neither is misreported as a local pass.
- Hosted GitHub Actions run `34088867948` at implementation head `6c2b17edf83f3ea72401b1b2291c48748b8977cd` completed successfully: full backend pytest PASS, Ruff PASS, frontend `npm ci`/lint/typecheck/production build PASS.
- Draft PR #3 is open, draft, mergeable, stacked on `astra/AST-02-instance-preflight`, and unmerged. Plan-only closure reconciles NEXT/CURRENT_STATE/DECISIONS/STARTUP_AND_RUNTIME/TASKS; final closure-head CI is tracked on the PR rather than inferred from the implementation run.
- Remaining qualification is explicit: clean installed-Windows lifecycle, Task Scheduler migration, sign-in/reboot/lock/wake behavior and owner-facing controls remain AST-04/05/19. This task does not claim those gates complete.
- All tests used temporary isolated roots and fixture/ephemeral endpoints. The active `phase29-trial/prod` runtime, its data/processes/provider/budget and port `8127` were not contacted or modified. No paid call was made.

**Prompt:** [AST-03](../prompts/archive/AST-03.md).

## AST-04 — Expose honest component status and recovery controls

- **ID:** AST-04
- **Status:** DONE
- **Priority:** P0
- **Milestone:** M1
- **Dependencies:** AST-03
- **Relative size:** M
- **Risk:** medium; Public liveness and browser network status do not prove worker/scheduler progress.
- **Reversibility:** Revert UI/control routes while retaining safe supervisor operation.

**Objective:** Replace misleading service/synced labels with actionable whole-app state.

**Why now:** Public liveness and browser network status do not prove worker/scheduler progress.

**Files/subsystems:** `newsroom/app.py`; new `newsroom/runtime_status.py`; `frontend/src/App.tsx`; `frontend/src/components/AppShell.tsx`; new `frontend/src/lib/runtime.ts`; `.github/workflows/ci.yml`; new `scripts/astra04_browser_smoke.py`; new `tests/test_runtime_status_api.py`; new `tests/test_runtime_status_frontend.py`. AST-03 `runtime_managed.py` and `runtime_supervisor.py` remain the lifecycle authority and were reused rather than duplicated.

**Implementation approach:** Expose authenticated bounded runtime status and named restart/stop requests through the existing AST-03 cooperative control primitive. Poll lightweight heartbeats plus active-job counts with bounded backoff; distinguish API down, worker/scheduler degraded, idle, queued/processing, stopped and starting. Keep `/readiness` integrity scans out of frequent status polling. Keep browser network state separate and show an external launcher recovery path when API is unavailable.

**Non-goals:** Arbitrary command execution, exposing root paths/PIDs/process tokens publicly, force-kill controls, random-port recovery, new general diagnostics dashboard.

**Tests:** Auth/CSRF/control allowlist tests; bounded status payload; idle/queued/processing work; stale worker; browser component-down and network-only failure; stop/restart acknowledgement; isolated rendered browser states.

**Acceptance criteria:**

- [x] Status identifies missing/stale components and distinguishes no work from failure
- [x] Authorized named controls work and unauthorized/CSRF-invalid calls fail
- [x] Browser does not claim Synced based only on navigator.onLine or API liveness

**Completion evidence:**

- AST-04 was implemented on `astra/AST-04-status-controls`, stacked directly from verified AST-03 closure head `85f41e1e3c80eba3eb65407c57433f1fa34dbde9`. The corrected implementation head before plan-only closure is `371ff0e24d72f1f0de72eb7f08ff8d1a6c74a659`; schema remains 36 and no migration was added.
- Authenticated `GET /api/v1/runtime/status` reuses AST-03 supervisor/component ownership and heartbeat state and adds only queued/running Job counts. It is `Cache-Control: no-store`; the public payload excludes runtime root, PID and process-creation token. The heavier `/readiness` database-integrity check is not part of ordinary polling.
- Authenticated, CSRF-protected `POST /api/v1/runtime/control` has a strict Pydantic allowlist: `restart_api`, `restart_worker`, `restart_scheduler`, `stop_newsroom`. Invalid arbitrary actions fail validation; unavailable/unmanaged targets fail closed. A restart cooperatively stops one verified managed child and AST-03 remains responsible for bounded restart/backoff. Stop targets the verified supervisor so writer-drain ordering remains scheduler/worker before API. No force-kill or arbitrary PID/command path was introduced.
- Control acknowledgement returns HTTP 202 with an explicit `restarting` or `stopping` transition before the cooperative stop primitive is dispatched as background work, so a Stop Newsroom request can be acknowledged before the API closes.
- `App.tsx` no longer calls `/health` for service truth and `AppShell.tsx` no longer renders `Synced`. The browser polls `/runtime/status` every five seconds when healthy and backs failures off from 3 seconds to a bounded 30 seconds. `navigator.onLine` remains a separately labeled browser-network signal and an immediate retry trigger, never a health conclusion.
- Owner-facing states include `Ready · idle`, `Work queued`, `Processing`, `Needs attention`, `Starting`, `Stopping`, `Stopped` and `Service unavailable`. When the API is unavailable/stopped, the UI explains that browser network availability does not prove the local service is running and points to the installed Newsroom launcher.
- Focused local verification before push passed 20/20 across the new API/status/frontend-contract tests and affected auth/API behavior. Frontend TypeScript no-emit also passed. Local Vite production bundling was not claimed because the supplied `node_modules` was Windows-shaped; clean Ubuntu CI remained the build authority.
- First hosted implementation run `34147352639` at `ad5b38a5e3732ec34fa3fe20995c24f5fe30a393` passed backend pytest, Ruff and the frontend build/smoke mechanically, but browser artifact `10028137244` failed human visual review because the expanded recovery panel escaped the narrow sidebar and overlapped Settings content. The task remained open; that artifact is retained as failed visual evidence rather than called acceptance.
- The recovery panel was contained within the scrollable sidebar without a new design system or general dashboard. Corrected implementation head `371ff0e24d72f1f0de72eb7f08ff8d1a6c74a659` then passed hosted run `34147588347`: full backend pytest PASS, Ruff PASS, frontend `npm ci`/lint/typecheck/production build PASS, isolated browser smoke PASS and artifact upload PASS.
- Corrected browser artifact `10028215213`, digest `sha256:2720fce46a269e67dcc4c1d08fef021b6f034dd71b06b1c18790cc4d6606f8d6`, contains `01-idle.png`, `02-worker-stale.png`, `03-api-unavailable.png` and a manifest. Human visual review accepted all three: idle is compact/truthful; stale worker shows `Needs attention`, the stale role and all four named controls without overlap; API unavailable separates browser-network availability from local API failure and shows launcher recovery guidance.
- The browser-evidence harness binds only an ephemeral `127.0.0.1` fixture port and contains no `8127` default; its manifest records `trial_contacted=false`. The active `phase29-trial/prod` runtime, data/processes/provider/budget and port `8127` were not contacted or modified. No paid provider call was made.
- Remaining qualification boundary: AST-04 does not create or qualify the installed Windows one-click launcher, sign-in/reboot/lock/wake behavior or legacy Task Scheduler migration. Those remain AST-05/AST-19 and are not inferred from mocked browser evidence.
- Draft PR #4 remains open, draft, mergeable, stacked on `astra/AST-03-supervisor`, and unmerged.

**Prompt:** [AST-04](../prompts/archive/AST-04.md).
