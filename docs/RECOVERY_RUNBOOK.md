# Newsroom Recovery Runbook

## Stop and restart the Windows runtime

Stop writers before restore or upgrade. The installed task names are explicit;
do not kill unrelated Python processes.

```powershell
Stop-ScheduledTask -TaskName Newsroom-Worker,Newsroom-Scheduler,Newsroom-API -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName Newsroom-API,Newsroom-Worker,Newsroom-Scheduler
Get-ScheduledTask -TaskName Newsroom-API,Newsroom-Worker,Newsroom-Scheduler | Get-ScheduledTaskInfo
```

The task settings cap automatic restarts at five attempts with a one-minute
interval. If that bound is exhausted, preserve the process logs and run the
health, integrity, and backup checks below before manually starting a task.

## Restore a verified backup

Restore into the explicit environment root only after confirming the source
backup is the intended file. The command verifies the backup before replacement
and verifies the restored database afterward:

```powershell
python -m newsroom.cli verify --environment prod --root C:\Newsroom\prod --database C:\Newsroom\prod\backups\newsroom-20260817T000000Z-scheduled.db
python -m newsroom.cli restore --environment prod --root C:\Newsroom\prod --backup C:\Newsroom\prod\backups\newsroom-20260817T000000Z-scheduled.db
python -m newsroom.cli verify --environment prod --root C:\Newsroom\prod
```

The restore path uses SQLite's online API and removes stale `-wal`/`-shm`
sidecars after atomic replacement. Do not copy a live SQLite database file by
hand.

## Upgrade rehearsal

Before upgrading a production-like database, restore a copy into a temporary
environment, apply pending migrations, and verify it:

```powershell
python -m newsroom.cli restore --environment dev --root C:\Newsroom\rehearsal\dev --backup C:\Newsroom\prod\backups\newsroom-latest.db
python -m newsroom.cli upgrade --environment dev --root C:\Newsroom\rehearsal\dev
python -m newsroom.cli verify --environment dev --root C:\Newsroom\rehearsal\dev
```

Only promote the migration when the rehearsal reports `verified: true`, the
schema versions are contiguous, readiness is ready, and the full project checks
pass. The migration ledger and integrity checks are the acceptance evidence.

## Worker crash, power loss, or provider outage

- Restart the API, worker, and scheduler with the same explicit environment
  root. The queue reads persisted state; it does not depend on an HTTP request.
- Running jobs whose leases expired are recorded as failed attempts and either
  re-queued with bounded backoff or terminally failed at the retry cap.
- Cancel requests are cooperative. A handler must finish or lease recovery
  must take over; no unbounded process restart loop is allowed.
- Provider failures are recorded by safe error code/type. Keep the local-first
  path enabled and check budget limits before retrying.

## Data-loss decision tree

1. If the database opens and `verify` is healthy, do not restore; capture a new
   backup and investigate the subsystem using readiness, metrics, jobs, and
   acquisition diagnostics.
2. If integrity fails, preserve the original file, restore the newest verified
   backup to a separate rehearsal root, and verify it before switching the
   service root.
3. If the backup fails verification, do not use it. Try the next retained
   backup and record the failed file and safe verification codes.
4. If all backups fail, retain the original files for forensic recovery and
   use the logical export only for evidence of what can be reconstructed; it is
   intentionally not a full secret/session/article-body dump.

## Recovery evidence

Record the environment, backup path, schema versions, verification result,
restore/upgrade timestamps, service restart result, and the request ID of any
user-visible failure. Never paste passwords, cookies, prompt text, note bodies,
article bodies, or full exception tracebacks into the incident record.
