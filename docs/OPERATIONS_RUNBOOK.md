# Newsroom Operations Runbook

This runbook covers the single-user Windows runtime. It assumes the API, worker,
and scheduler run with an explicit `dev` or `prod` `RuntimeConfig` root outside
the source repository.

## Windows release and startup

Run the deployment script from the accepted checkout. Validation is read-only
with respect to install roots, shortcuts, scheduled tasks, and Tailscale;
production installation refuses a dirty Git worktree and refuses to overwrite a
non-empty install directory.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 -Mode Validate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 -Mode Install -RegisterTasks
```

The default production layout is `%LOCALAPPDATA%\Newsroom\app\prod` for the
immutable application artifact and `%LOCALAPPDATA%\Newsroom\prod` for data,
backups, logs, cache, and managed runtime identity. Installation creates one
**Start Newsroom** shortcut under the current user's Start Menu and one hidden
`start-newsroom.ps1` launcher in the install root. The shortcut starts or reuses
the AST-03 supervisor on the configured fixed loopback port, waits for the
matching managed API identity, and opens the product. Repeated shortcut launches
reuse the verified managed instance. They never kill a listener or choose an
alternate port.

When `-RegisterTasks` is selected, the installer registers exactly one
installation-namespaced Task Scheduler entry such as
`Newsroom-<installation-prefix>-Start`. It runs the same launcher with
`-NoBrowser` **at interactive user sign-in**, under the same Windows identity as
the installer. The task keeps the existing five-restart/one-minute bound,
`StartWhenAvailable`, and `IgnoreNew`; it does not use S4U and it does not
create separate API, worker, and scheduler tasks. This milestone makes no
pre-login guarantee.

Historical installs may contain the fixed task names `Newsroom-API`,
`Newsroom-Worker`, and `Newsroom-Scheduler`. The installer detects those names
before copying install files. If task registration is requested while legacy
tasks are present, installation stops without changing install files or tasks
unless `-MigrateLegacyTasks` is supplied explicitly. Migration removes only
those three exact names after verifying that each action still points to the
known historical `run-api.ps1`, `run-worker.ps1`, or `run-scheduler.ps1`
launcher. Any unrecognized action is left untouched and causes migration to
stop for manual review. Unrelated scheduled tasks are never enumerated as
migration targets.

```powershell
# Only after reviewing the detected historical Newsroom task names/actions:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 `
  -Mode Install -RegisterTasks -MigrateLegacyTasks
```

`release-manifest.json` records the source and installed artifact digests,
runtime installation UUID, generated launcher/shortcut hashes, the single task
name, trigger/logon type, and whether a reviewed legacy migration occurred.
`release.py` continues to verify the copied application artifact hashes.

Closing the browser or the Start Newsroom launcher does **not** stop background
monitoring. The supervisor and its API/worker/scheduler children are independent
background processes. Use the authenticated Status & recovery controls in the
product to stop or restart the managed runtime. A locked desktop does not by
itself request shutdown, but acquisition cannot occur while the computer is
asleep or powered off. On wake, the running scheduler uses existing durable
coalescing/catch-up behavior. On reboot, Newsroom starts only after the configured
Windows user signs in. Pre-login/logged-out operation is outside the supported
milestone and must not be inferred from the old S4U task topology.

After the local health checks pass, configure private HTTPS access explicitly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 -Mode Install -RegisterTasks -ConfigureTailscale
tailscale serve get-config --all
```

Tailscale Serve must target `http://127.0.0.1:8127`; do not use Funnel or bind
the application to a LAN/public interface. Application authentication remains
required even on the private tailnet. The installer does not create passwords
or persist provider secrets. Future OS-vault credentials are intentionally tied
to this same-user startup identity; do not move the scheduled task to a service
or different account without separately qualifying credential access.

## Safety boundaries

- The API accepts JSON bodies up to 1 MiB and applies a fixed-window request
  limit of 120 requests/minute per local client, with a 20 requests/minute
  authentication limit and a 30 requests/minute authenticated metrics limit.
- Authentication uses Argon2id password hashes, an HTTP-only session cookie, a
  separate CSRF cookie/header pair, SameSite=Lax cookies, 24-hour expiry,
  persisted failed-login throttling, and no-store auth responses.
- Acquisition allows only HTTP(S), rejects private/loopback/link-local/reserved
  destinations after DNS resolution, bounds redirects, bytes, feed entries,
  HTML nodes/text, and transport timeouts, and never executes page JavaScript.
- SQL values are parameterized. FTS queries are tokenized and quoted. React
  renders stored text as text; no user or evidence content is injected as HTML.
- Error responses contain request IDs and safe messages only. Logs contain
  method, path without query string, status, subsystem, and error type; they do
  not contain request bodies, passwords, session tokens, prompts, article
  bodies, or tracebacks.

## Dependency and secret audit

Run these checks before a release from the repository root:

```powershell
python -m pytest -q
python -m compileall -q newsroom scripts tests
python -m pip list --outdated
Push-Location frontend
npm.cmd audit --audit-level=high
npm.cmd run typecheck
npm.cmd run build
Pop-Location
```

Runtime secrets must be supplied only through the approved configuration path
for the release being qualified. Do not put them in `settings`, exports, logs,
the source tree, scheduled-task arguments, or launcher arguments. The logical
export intentionally omits users, sessions, settings, note bodies, search text,
provider payloads, raw Ask answers, and prompt metadata.

## Health and telemetry

```powershell
python -m newsroom.cli status --environment prod --root C:\Newsroom\prod
python -m newsroom.cli verify --environment prod --root C:\Newsroom\prod
```

`GET /api/v1/health` is a low-sensitivity API liveness check, not whole-runtime
health. `GET /api/v1/readiness` checks SQLite integrity and required schema
relationships. Authenticated `GET /api/v1/runtime/status` projects the managed
supervisor/API/worker/scheduler state plus bounded active-job counts. The product
Status & recovery surface is the normal owner view for starting, idle,
processing, degraded, stopping, stopped, and unavailable states.

Authenticated operators can use `GET /api/v1/metrics`; it returns only bounded
counters and latency aggregates. A non-empty `failure_counts_by_subsystem`
identifies whether failures cluster in auth, acquisition, research, jobs, Ask,
domain, or runtime handling without exposing the failed payload.

Representative local limits are documented and tested at 250 documents, 100
queued jobs, and paginated 25-result search requests. The performance gate is
under 5 seconds to enqueue 100 bounded jobs and under 1 second median for a
three-run FTS search after index construction on the test workstation. Re-run
the performance test on production-like hardware before changing these limits.

## Scheduled maintenance

Create a verified online backup, export safe metadata when needed, and retain
only the configured backup set:

```powershell
python -m newsroom.cli backup --environment prod --root C:\Newsroom\prod --destination C:\Newsroom\prod\backups\newsroom-latest.db
python -m newsroom.cli export --environment prod --root C:\Newsroom\prod --destination C:\Newsroom\prod\backups\newsroom-export.jsonl
python -m newsroom.cli retain --environment prod --root C:\Newsroom\prod --keep 7 --older-than-days 30
```

Backups use SQLite's online backup API and are integrity-checked before being
published. Retention deletes only `newsroom-*.db` files in the selected backup
directory; unrelated files are left untouched. The same maintenance command
also removes expired or long-revoked sessions.

## Failure response

1. If Start Newsroom reports that the configured endpoint cannot be used, do
   not start a second port or terminate the existing listener. Review the
   runtime status/logs, identify whether the owner is matching, unmanaged,
   mismatched, foreign, or unknown, resolve that owner explicitly, and retry the
   same shortcut.
2. If readiness is not ready, stop new worker/scheduler starts and capture the
   safe output of `verify` plus the request ID from the failing API response.
3. If acquisition is failing, inspect source-profile error codes and the
   `acquisition_events` outcome; do not disable SSRF or response bounds.
4. If jobs are stuck, use the managed Status & recovery controls first. Do not
   force-kill an ambiguous/unmanaged owner; expired leases recover through the
   durable queue with bounded retry/backoff.
5. If a provider is unavailable or a budget is exhausted, keep the local route
   active and leave paid routing disabled; do not retry outside the persisted
   Job/Question budget.
6. Preserve the original database and logs until a verified backup and export
   have been captured.
