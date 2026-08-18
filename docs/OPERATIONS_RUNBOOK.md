# Newsroom Operations Runbook

This runbook covers the single-user Windows runtime. It assumes the API, worker,
and scheduler run with an explicit `dev` or `prod` `RuntimeConfig` root outside
the source repository.

## Windows release and startup

Run the deployment script from the accepted checkout. Validation is read-only
with respect to install roots, scheduled tasks, and Tailscale; production
installation refuses a dirty Git worktree and refuses to overwrite a non-empty
install directory.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 -Mode Validate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 -Mode Install -RegisterTasks
```

The default production layout is `%LOCALAPPDATA%\Newsroom\app\prod` for the
immutable application artifact and `%LOCALAPPDATA%\Newsroom\prod` for data,
backups, logs, and cache. Override both explicitly when the operator chooses a
different volume. The generated launchers bind API only to `127.0.0.1`, use the
same-origin FastAPI/PWA build, and start one bounded worker plus one scheduler.
Task Scheduler uses an at-start trigger, a five-restart limit, a one-minute
restart interval, and ignores overlapping instances. The process identity is
recorded in `release-manifest.json`; `release.py` verifies every installed
artifact hash.

After the local health checks pass, configure private HTTPS access explicitly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase16_windows_deploy.ps1 -Mode Install -RegisterTasks -ConfigureTailscale
tailscale serve get-config --all
```

Tailscale Serve must target `http://127.0.0.1:8127`; do not use Funnel or bind
the application to a LAN/public interface. Application authentication remains
required even on the private tailnet. The installer does not create passwords
or persist provider secrets; set those through the operator-controlled process
environment or secret manager before enabling an optional provider.

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

Runtime secrets must be supplied by the Windows service/task environment or a
local secret manager. Do not put them in `settings`, exports, logs, the source
tree, or command arguments. The logical export intentionally omits users,
sessions, settings, note bodies, search text, provider payloads, raw Ask
answers, and prompt metadata.

## Health and telemetry

```powershell
python -m newsroom.cli status --environment prod --root C:\Newsroom\prod
python -m newsroom.cli verify --environment prod --root C:\Newsroom\prod
```

`GET /api/v1/health` is a low-sensitivity liveness check. `GET
/api/v1/readiness` checks SQLite integrity and required schema relationships.
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

1. If readiness is not ready, stop new worker/scheduler starts and capture the
   safe output of `verify` plus the request ID from the failing API response.
2. If acquisition is failing, inspect source-profile error codes and the
   `acquisition_events` outcome; do not disable SSRF or response bounds.
3. If jobs are stuck, stop the worker, verify the database, then restart it;
   expired leases recover through the durable queue with bounded retry/backoff.
4. If a provider is unavailable or a budget is exhausted, keep the local route
   active and leave paid routing disabled; do not retry outside the persisted
   Job/Question budget.
5. Preserve the original database and logs until a verified backup and export
   have been captured.
