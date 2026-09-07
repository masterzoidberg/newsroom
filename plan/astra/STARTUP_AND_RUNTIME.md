# Startup and runtime

## What caused the 8127 experience

At audit time `Get-NetTCPConnection -LocalPort 8127 -State Listen` returned `127.0.0.1:8127`, PID **48036**, Python 3.12, started 2026-09-06 18:03:19 local. Sanitized process inspection identified `newsroom.runtime api` against the `phase29-trial` root. Worker PID **38908** and scheduler PID **59636** shared parent **54688** and the same start time. Public `GET /api/v1/health` returned `service=newsroom`, `status=ok`, `version=0.1.0-dev`.

At the audited baseline `runtime.py:main` resolved the root, created directories, applied migrations, then `_run_api` called `uvicorn.run(create_app(...), host, port)`. There was no preflight listener identification or application-instance lock. A second command attempted to bind an already occupied endpoint and Windows rejected it with 10048. The **observed conflict was explained by an already-running Newsroom API**. The audit did not launch a duplicate on 8127 or reproduce the historical failure destructively; no historical error timestamp proves the owner at the exact original event.

No `Newsroom*` scheduled tasks were returned by the read-only query. Do not attribute this specific instance to Task Scheduler. The installer can nevertheless produce the same experience: `IgnoreNew` prevents another instance of each registered task, not an independent manual Python command. Fixed task names also do not describe multiple installations/roots cleanly.

## Implementation status after AST-04

AST-02 remains the API endpoint-ownership authority. `newsroom/runtime_identity.py` provides the stable non-secret installation UUID, OS-backed API lock, root/role/release/PID creation-token verification, bounded endpoint classification and redacted public identity. API startup reuses only a verified matching fixed-port API, fails closed for mismatched/unmanaged/foreign/unknown ownership, diagnoses bind races, never kills a listener and never silently selects another port.

AST-03 adds `runtime_managed.py` and `runtime_supervisor.py` around the existing API, worker and scheduler rather than replacing them. One supervisor validates a shared non-secret root/environment/release/host/port manifest and coordinates one managed owner per role with OS-backed role locks, PID creation-token verification, fresh heartbeats and token-bound stop-control files. A replacement supervisor reconciles surviving verified same-release children by exact identity instead of spawning duplicates. Stale, ambiguous or unmanaged roles block sibling startup; they are not adopted, killed or restarted over.

Normal managed migration ownership belongs to the supervisor. It applies migrations only when API/worker/scheduler managed locks are all free. A supervisor reconciling active same-release children validates the manifest but performs no migration write. Advanced/direct child commands remain available and are explicitly `unmanaged` from the supervisor's perspective.

Managed shutdown requests scheduler and worker stop before API and waits for a bounded drain deadline. If a busy managed worker remains after the deadline, shutdown reports it and does not force-kill it. The managed API maps its cooperative stop event to Uvicorn's `should_exit`. Unexpectedly missing managed children use capped per-role exponential restart/backoff; after the bound the supervisor remains degraded with `restart_exhausted` rather than retrying forever. Stale/ambiguous/unmanaged owners are never automatic restart targets.

AST-03 also closes the demonstrated long-handler lease gap. `WorkerProcess` renews the existing Job lease while that Job is still `running` and owned by the same worker. If durable ownership/status is lost, renewal stops and that worker does not issue a stale completion.

AST-04 exposes that existing lifecycle truth without creating a parallel health or control service. Authenticated `GET /api/v1/runtime/status` returns bounded supervisor/API/worker/scheduler state plus only queued/running Job counts. It does not return runtime roots, PIDs or process-creation tokens and does not invoke the heavier database-integrity `/readiness` path. Authenticated, CSRF-protected `POST /api/v1/runtime/control` accepts only `restart_api`, `restart_worker`, `restart_scheduler` and `stop_newsroom`. A restart request cooperatively stops one verified managed child and leaves AST-03's bounded supervisor policy responsible for the restart. A whole-app stop targets the verified supervisor, preserving its writer-drain ordering. The 202 acknowledgement is prepared before the cooperative control is dispatched so the API can acknowledge a stop before it begins closing.

The browser now polls authenticated whole-runtime state with bounded backoff and uses labels such as `Ready · idle`, `Work queued`, `Processing`, `Needs attention`, `Starting`, `Stopping`, `Stopped` and `Service unavailable`. `navigator.onLine` is separately labeled as browser network state and is never promoted to Newsroom health. When the API is unavailable/stopped, the shell tells the owner to use the installed Newsroom launcher rather than claiming synchronization from network connectivity or API liveness.

This is still not the full normal-user launch experience. The Windows installer still creates its legacy independent task topology and does not yet expose one obvious `Start Newsroom` entry point; that is AST-05. Clean installed-Windows lifecycle, locked/wake/reboot and process-creation-token qualification remain AST-05/19. AST-04 did not contact or modify the active trial or port 8127.

## Current failure modes

| Question | Current answer |
|---|---|
| Can components get out of sync? | The managed supervisor prevents a second verified role owner, reconciles surviving children and restarts only missing managed roles. Stale/ambiguous/unmanaged state remains deliberately degraded rather than being overwritten. AST-04 exposes that state to the owner. The old independent installed task topology remains until AST-05. |
| How does UI know health? | Authenticated `/runtime/status` projects AST-03 component ownership/heartbeats plus cheap active-job counts. The browser separately reports network connectivity and no longer treats `/health` or `navigator.onLine` as “Synced.” Frequent status polling does not run database integrity scans. |
| What happens after reboot? | Existing registered tasks still use their historical AtStartup/S4U topology. AST-03 provides the supervisor command and AST-04 exposes runtime state/control, but AST-05 must make one sign-in launcher/task authoritative and migrate legacy task handling explicitly. |
| After update? | Supervisor manifest/release matching and stopped-writer migration ownership reduce divergence, but installed artifact staging/backup/rollback remains AST-14/19. Active old-release children are not silently crossed by a new-release supervisor. |
| Graceful exit? | AST-04 Stop Newsroom requests the verified supervisor. Managed scheduler/worker get cooperative stop controls first, API last. A busy worker can outlive the deadline and is reported instead of force-killed. Unmanaged/ambiguous processes are never stopped. |
| Crash recovery? | Missing managed children restart with capped backoff; supervisor-process loss can be reconciled against surviving exact child identities. Fresh-process/stale-heartbeat ambiguity does not trigger a duplicate. Long handlers renew their Job lease while ownership remains valid. AST-04 exposes degraded state and named recovery requests without bypassing these rules. |

## Minimum architecture

Keep API, worker and scheduler as the separate existing processes. AST-03 implements **one small per-user supervisor** above them. AST-05 should make a `Start Newsroom` shortcut and one optional Task Scheduler entry start that same supervisor **at user sign-in**. No tray framework, Windows service rewrite, Electron wrapper, Docker requirement, scheduler replacement or distributed task queue is required.

Why: child separation already matches durable Job design; a per-user process can use the same user's future credential store. Three independent scheduled tasks preserve the confusing topology. A Windows service adds account/profile/credential and installation complexity; a tray is useful later but unnecessary for one-action startup.

Tradeoff: the initial supported unattended promise remains “while this Windows user is signed in,” including browser closed/desktop locked where qualified. No acquisition during sleep, power-off or logged-out pre-sign-in operation is promised. On wake/sign-in, catch up through existing coalescing. If operation before login is required later, qualify a separate account/service design rather than silently changing credential scope. Microsoft documents S4U restrictions on network/encrypted-file access; do not assume the current deployment principal works with a new credential backend. See [Task logon types](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).

## Single authority and identity

- A non-secret runtime manifest outside the repository records installation UUID, explicit environment/root, fixed host/port and selected release identity. `RuntimeConfig` remains the root guard. AST-02 owns the root-stable installation identity; AST-03 implements the runtime manifest; AST-05 will make the installer/shortcut its normal entry point.
- OS-backed exclusive locks are the ownership authority. PID/owner files are diagnostic/verification metadata, never locks. Managed owners include role, installation, release, PID and process creation token to defend against PID reuse.
- The supervisor is the normal managed migration/startup writer. Managed children skip migration writes. Direct/dev child entry points remain available but are marked unmanaged and cannot be silently taken over.
- API root/release identity is still verified through AST-02's bounded endpoint protocol. A health response saying “newsroom” alone is not proof of same root or release.
- AST-03's local control protocol accepts only a token-bound cooperative stop request for a verified managed owner. AST-04 places authenticated/CSRF-protected named web actions in front of that primitive. It exposes no arbitrary commands, arbitrary process IDs or runtime root paths.

## Launch algorithm

1. Read/validate the runtime root and installation identity; acquire/reuse the supervisor ownership lock. Concurrent supervisor invocations converge on the verified existing supervisor or acquire the lock after a crashed owner disappears.
2. Validate the shared runtime manifest. A structural root/environment/endpoint mismatch fails. A release change is allowed only when component locks are all free; active same-release children may be reconciled without a migration write.
3. Preflight all API/worker/scheduler role states before spawning. Healthy verified managed roles are reused. Any stale, ambiguous or unmanaged role blocks sibling spawning so startup cannot create a half-managed topology around an owner it cannot safely control.
4. For the API endpoint, retain AST-02 fixed-port diagnosis. Matching healthy API is reused; foreign/mismatched/unmanaged/unknown endpoint ownership fails closed. Never kill a listener or choose a random port.
5. With no managed component locks held, apply migrations once under supervisor authority. Then start only missing roles with the identical root/release context and bounded startup deadline.
6. Require fresh role heartbeat plus verified PID creation token; API additionally requires AST-02 matching endpoint readiness. Process presence alone is insufficient.
7. Monitor missing managed children with capped exponential backoff. Never restart stale/ambiguous/unmanaged roles over their owner. After the cap, retain degraded `restart_exhausted` state.
8. AST-04 surfaces the resulting whole-runtime state and named cooperative recovery controls. AST-05 must make the installed launcher start/reuse this same supervisor and open the product with no terminal interaction.

No infinite retry loops are part of the managed runtime.

## Shutdown, failure and update

Stop scheduler submissions and worker claims cooperatively, let current work drain for a bounded deadline, then stop API. Do not force-terminate an unmanaged, ambiguous or merely busy process. If owned work exceeds the deadline, return the remaining role(s) and leave the work running. Closing the browser leaves background operation running. AST-04 provides explicit authenticated Stop/Restart requests; AST-05 must provide the installed Start/reopen path.

Unexpectedly missing managed children restart with capped per-role backoff. Stale heartbeats remain degraded because process identity still exists and spawning a replacement would risk duplicate work. A replacement supervisor reconciles surviving verified children rather than duplicating them. Running Job handlers renew their existing lease while the same worker retains durable ownership, reducing false expiry/recovery during long synchronous work. Existing paid invocation uncertainty/idempotency records are untouched; AST-03/04 create no new paid-call route.

Upgrade: stage/verify a new artifact, stop writers, create a verified backup, migrate/rehearse as appropriate, start and check all components, then confirm. The runtime manifest refuses release changes while managed component locks are active. Do not roll old binaries onto an incompatible new schema. Full owner-controlled backup/update/rollback remains AST-14/19.

Developer startup uses the same supervisor logic with an explicit dev manifest/root and a separately configured port. Vite remains an optional developer tool, never part of the owner's startup procedure. No developer test may default to active 8127 or the trial root.

## AST-03 lifecycle evidence

| Scenario | Verified behavior |
|---|---|
| Repeated supervisor launch | Exact existing API/worker/scheduler child PIDs are reused; second supervisor spawns no child. |
| Supervisor process crash | Children remain alive; replacement supervisor reconciles the same three PIDs rather than duplicating them. |
| One child crash | Only the missing role restarts; healthy sibling PIDs remain unchanged. |
| Stale heartbeat with live owner | State becomes stale/degraded; no replacement is spawned; resumed heartbeat restores the same PID. |
| Existing unmanaged role | All-role preflight blocks managed sibling startup; shutdown reports the role and does not stop it. |
| Restart crash loop | Per-role count/backoff reaches `restart_exhausted`; no infinite respawn. |
| Busy worker at shutdown deadline | Shutdown reports worker remaining and leaves it alive; it can drain naturally before API stop. |
| Long handler beyond Job lease plus cancellation | Lease renews while worker ownership remains valid; competing recovery/claim does not occur; original attempt finishes through durable cancellation. |

Focused local regression: `python -m pytest -q tests/test_runtime_supervisor.py tests/test_worker_lease.py tests/test_phase07_jobs.py tests/test_phase16_deployment.py` passed 20/20. `python -m compileall -q newsroom tests` passed. Hosted GitHub Actions run `34088867948` at implementation head `6c2b17edf83f3ea72401b1b2291c48748b8977cd` passed Ruff, full backend pytest, frontend install/lint/typecheck and production build.

## AST-04 status/control evidence

- Focused local backend/API/frontend-contract verification passed 20/20 and frontend TypeScript no-emit passed. Local Vite production bundling was not claimed because the supplied dependencies were Windows-shaped; clean Ubuntu CI remained the build authority.
- First hosted implementation run `34147352639` was mechanically green but its browser artifact `10028137244` failed human visual review because expanded recovery controls escaped the sidebar and overlapped Settings. That artifact is retained as failed visual evidence, not accepted completion evidence.
- Corrected implementation head `371ff0e24d72f1f0de72eb7f08ff8d1a6c74a659` passed hosted run `34147588347`: Ruff, full backend pytest, frontend `npm ci`, lint, typecheck, production build, isolated browser smoke and artifact upload all passed.
- Corrected artifact `10028215213`, digest `sha256:2720fce46a269e67dcc4c1d08fef021b6f034dd71b06b1c18790cc4d6606f8d6`, was visually reviewed. Idle is compact and truthful; stale worker displays `Needs attention`, the stale role and all four controls within the sidebar; API unavailable separates browser-network availability from local service failure and gives installed-launcher recovery guidance.
- The browser harness binds only an ephemeral `127.0.0.1` fixture port and its manifest records `trial_contacted=false`. It never uses port 8127. No paid provider call occurred.

## Start Newsroom final acceptance (AST-05 and AST-19)

On a clean Windows user profile, install and launch from one obvious shortcut. No terminal input is needed. All three required components become healthy; the product opens; Settings shows honest status. Close the browser and confirm a due fixture Watch still processes. Relaunch twice and concurrently: one supervisor and one of each role remain. Stop and Restart complete safely without duplicate downstream objects. Reboot, sign in, and verify automatic recovery with preserved data and credentials. Test locked desktop, wake from sleep and missed cadence explicitly.

Occupy the configured test port with a known unrelated process: the launcher names it where permissions permit, gives a recovery action, uses no alternate port and kills nothing. Repeat with matching healthy Newsroom, mismatched-root Newsroom, stale PID metadata, owner permission failure and a bind race. Save redacted process counts/status and recovery results with release identity. Pre-login availability is explicitly outside this milestone.
