# Startup and runtime

## What caused the 8127 experience

At audit time `Get-NetTCPConnection -LocalPort 8127 -State Listen` returned `127.0.0.1:8127`, PID **48036**, Python 3.12, started 2026-09-06 18:03:19 local. Sanitized process inspection identified `newsroom.runtime api` against the `phase29-trial` root. Worker PID **38908** and scheduler PID **59636** shared parent **54688** and the same start time. Public `GET /api/v1/health` returned `service=newsroom`, `status=ok`, `version=0.1.0-dev`.

At the audited baseline `runtime.py:main` resolved the root, created directories, applied migrations, then `_run_api` called `uvicorn.run(create_app(...), host, port)`. There was no preflight listener identification or application-instance lock. A second command attempted to bind an already occupied endpoint and Windows rejected it with 10048. The **observed conflict was explained by an already-running Newsroom API**. The audit did not launch a duplicate on 8127 or reproduce the historical failure destructively; no historical error timestamp proves the owner at the exact original event.

No `Newsroom*` scheduled tasks were returned by the read-only query. Do not attribute this specific instance to Task Scheduler. The installer can nevertheless produce the same experience: `IgnoreNew` prevents another instance of each registered task, not an independent manual Python command. Fixed task names also do not describe multiple installations/roots cleanly.

## Implementation status after AST-02

AST-02 implements the API-side ownership and fixed-port diagnosis slice without starting the supervisor architecture. `newsroom/runtime_identity.py` now provides a stable non-secret installation UUID bound to the canonical runtime root, an OS-backed exclusive API lock, owner metadata containing canonical root/role/release/PID/process-creation token, bounded local endpoint classification, and redacted public identity data. `runtime.py:_run_api` performs preflight before API migration/bind, reuses only a healthy verified matching API, fails closed for mismatched/unmanaged/foreign/unknown ownership, and diagnoses a bind race through the same fixed-port path. It never kills a listener or silently selects another port.

Concurrent same-root launches converge through the OS lock plus a bounded reconciliation window. If the first lock holder dies before becoming usable, the waiting launcher may take the released OS lock and continue; if ownership remains ambiguous after the bound, startup fails with recovery guidance. PID creation time is part of verification so stale metadata/PID reuse cannot by itself establish ownership. The public `/api/v1/runtime/identity` response intentionally omits filesystem paths.

This is not yet the normal-user startup authority. Worker/scheduler singleton ownership, child reconciliation, heartbeats, stop/restart/drain and one-action launch remain AST-03 through AST-05. Windows process-creation-token code is implemented but clean installed-Windows lifecycle qualification remains a later acceptance boundary. The active trial and port 8127 were not contacted or modified by AST-02 development.

## Current failure modes

| Question | Current answer |
|---|---|
| Can components get out of sync? | Yes. AST-02 protects API ownership, but worker/scheduler still use independent roots/commands/installation versions and separate failures; API liveness says nothing about worker readiness. |
| How does UI know health? | `App.tsx` checks `/health` at mount and browser online/offline changes. `navigator.onLine` is not API health; “Synced” overstates the result. |
| What happens after reboot? | Registered tasks use AtStartup/S4U. Manual processes have no automatic resurrection. The current trial must not be assumed installed as tasks. |
| After update? | Runbook requires manual writer shutdown/restart; no single version/migration transition authority. |
| Graceful exit? | Worker/scheduler observe a stop event between operations; worker finishes synchronous handler. Task stopping is not demonstrated as graceful Python shutdown. |
| Crash recovery? | API concurrent-start crash handoff is bounded by AST-02. Aggregate child restart is not implemented. Job leases/retries and stage identities exist; `WorkerProcess` does not periodically renew a running job lease, so validate long-handler behavior before relying on automatic crash restarts. |

## Recommended minimum architecture

Keep API, worker and scheduler as separate existing processes. Add **one small per-user launcher/supervisor**, a `Start Newsroom` shortcut, and one optional Task Scheduler entry that starts that same supervisor **at user sign-in**. It owns one runtime manifest, lifecycle lock, child identities and bounded restart policy. No tray framework, Windows service rewrite, Electron wrapper, Docker requirement, or scheduler replacement.

Why: child separation already matches durable job design; a per-user process can use the same user's credential store. Three independent scheduled tasks preserve the confusing topology. A Windows service adds account/profile/credential and installation complexity; a tray is useful later but unnecessary for one-action startup.

Tradeoff: the initial supported unattended promise is “while this Windows user is signed in,” including browser closed/desktop locked where qualified. No acquisition during sleep, power-off or logged-out pre-sign-in operation is promised. On wake/sign-in, catch up through existing coalescing. If operation before login is required later, qualify a separate account/service design rather than silently change credential scope. Microsoft documents S4U restrictions on network/encrypted-file access; do not assume the current deployment principal works with a new credential backend. See [Task logon types](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/ne-taskschd-task_logon_type).

## Single authority and identity

- A non-secret install/runtime manifest outside the repository holds install path, explicit environment/root, fixed host/port, stable installation UUID and selected release identity. Existing `RuntimeConfig` remains the root guard. AST-02 implements the root-stable UUID and API ownership metadata; AST-03/05 will make the supervisor/installer the normal manifest authority.
- Use an OS-backed exclusive lock scoped to user + canonical root. A PID file is diagnostic metadata, not a lock. Store PID, process creation time, component role, installation UUID and release generation. Defend against PID reuse. AST-02 implements this for the API role.
- Supervisor is the only normal startup writer/migration owner. Child entry points retain advanced/dev use, but validate schema/identity and refuse conflicting managed ownership. This remains AST-03 work; AST-02 only moves API migration behind API ownership/preflight.
- Root/role identity is verified locally using owner metadata and process identity; public HTTP responses need not expose filesystem paths. A health response saying “newsroom” alone is not proof of same root or executable. AST-02 implements this API identity boundary.
- Use a same-user protected local control channel for stop/restart/status. Web lifecycle actions require the existing auth/CSRF guard and only allow named operations; never accept arbitrary commands or arbitrary process IDs. This remains AST-03/04 work.

## Launch algorithm

1. Read/validate manifest and root; acquire the instance lock or contact its verified owner. Concurrent shortcuts converge on one supervisor.
2. Inspect configured endpoint before starting children. If occupied, retrieve bounded liveness information and validate PID creation time, executable/installation and root identity.
3. Matching healthy managed Newsroom: reuse it, repair only verified missing components, open browser. Matching old unmanaged API: permit browser reuse with a clear unmanaged/degraded status; require explicit controlled migration before taking ownership or stopping it.
4. Foreign listener, mismatched root/release, inaccessible owner or ambiguous identity: do not bind or kill. Display port, available process name/PID and “Close that application, then Retry” / “Open diagnostics.” Advanced endpoint changes update one manifest coherently and are explicit. Never choose a random replacement port.
5. Verify installed artifacts, schema compatibility and writable runtime paths. Run migrations only with all relevant writers stopped; on failure preserve data and show recovery action.
6. Start API/worker/scheduler with identical root and release context, hidden windows, bounded startup deadline. Use short component heartbeats plus readiness, not process presence alone.
7. Open the same-origin browser/PWA when usable. Show Starting / Ready / Degraded / Stopping / Stopped / Needs attention; distinguish collecting, processing and serving.

AST-02 implements the API subset of steps 2-4 and handles a successful-preflight/failed-bind race through the same diagnostic path. The supervisor-wide convergence, writer coordination and component repair in steps 1 and 5-7 remain later tasks. No infinite retry loops.

## Shutdown, failure and update

Stop scheduler submissions, stop worker claims, drain current work for a bounded deadline, then stop API. Do not force-terminate another user's or unmanaged process. If owned work exceeds the deadline, surface status; forced termination must preserve uncertain paid-call state and rely on safe recovery. Closing the browser leaves background operation running; an explicit Stop Newsroom command stops it. Restart follows the same authority and does not duplicate work.

Restart an unexpectedly failed owned child with capped exponential backoff; after the cap, remain degraded with an actionable reason. Supervisor restart must reconcile existing children rather than duplicate them. Test crash, long handler, lease expiry and cancellation interactions together.

Upgrade: stage/verify new artifact, stop writers, verified backup, migrate/rehearse as appropriate, start and check all components, then confirm. Do not roll old binaries onto an incompatible new schema. Rollback means the verified prior artifact plus a deliberate compatible backup recovery path. Preserve diagnostics on failure.

Developer startup uses the same launcher logic with an explicit dev manifest/root and a separately configured port. Vite remains an optional developer tool, never part of the owner's startup procedure. No developer test may default to active 8127 or the trial root.

## Start Newsroom final acceptance (AST-05 and AST-19)

On a clean Windows user profile, install and launch from one obvious shortcut. No terminal input is needed. All three required components become healthy; the product opens; Settings shows honest status. Close the browser and confirm a due fixture Watch still processes. Relaunch twice and concurrently: one supervisor and one of each role remain. Stop and Restart complete safely without duplicate downstream objects. Reboot, sign in, and verify automatic recovery with preserved data and credentials. Test locked desktop, wake from sleep and missed cadence explicitly.

Occupy the configured test port with a known unrelated process: the launcher names it where permissions permit, gives a recovery action, uses no alternate port and kills nothing. Repeat with matching healthy Newsroom, mismatched-root Newsroom, stale PID metadata, owner permission failure and a bind race. Save redacted process counts/status and recovery results with release identity. Pre-login availability is explicitly outside this milestone.
