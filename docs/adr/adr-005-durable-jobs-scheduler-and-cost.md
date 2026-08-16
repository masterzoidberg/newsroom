# ADR-005 — SQLite durable jobs, scheduler, and cost control

## Status

Accepted for Phase 07.

## Context

Monitoring work must survive HTTP disconnects, process restarts, and worker
crashes. The Phase 05 AI router already has in-process paid counters, but those
counters cannot coordinate multiple process instances or explain durable work
history. The first release needs restart-safe state without introducing a
distributed queue.

## Decision

Phase 07 keeps the queue in SQLite and hardens the existing `jobs`,
`job_attempts`, `runs`, `monitors`, and `provider_usage` tables with migration
0006:

- `JobService.enqueue` persists bounded JSON payloads, parent attribution,
  idempotency keys, priority, and maximum attempts. Repeating an idempotency key
  returns the existing job rather than creating unbounded work.
- Claims happen inside `BEGIN IMMEDIATE`. A worker receives an owner and a
  lease expiry; the attempt is recorded in `job_attempts`. Only the current
  lease owner can complete the job.
- Expired leases are converted into failed attempt history and either requeued
  with exponential backoff or terminally failed at `max_attempts`. Cancellation
  is cooperative for running jobs and terminal immediately for queued jobs.
- `SchedulerService.tick` selects due enabled Monitors, creates one cron Run,
  enqueues one idempotent `monitor_check` Job per due schedule, and advances
  `next_check_at` within the same transaction. `SchedulerProcess` and
  `WorkerProcess` are separate restartable process wrappers; handlers are an
  explicit allow-listed mapping, never request-controlled subprocesses.
- `budget_limits` stores global, policy, Job, and Research Question caps for
  acquisition units, local-model units, paid requests, and USD over daily,
  monthly, or lifetime periods. `budget_reservations` is checked and written
  in the same transaction as a claim, preventing concurrent dispatch from
  exceeding a configured hard cap.
- Paid dispatch is disabled by default and can be enabled explicitly. Actual
  provider usage remains attributable through `provider_usage`; reservations
  are released on completion, cancellation, or lease recovery, while recorded
  usage continues to count against the period cap.
- Run status is derived from child Job outcomes and becomes success, partial, or
  failed once all children are terminal.

## Consequences

The web process can enqueue and inspect work without holding an HTTP request
open. A process restart leaves truthful queued/running state, and a subsequent
claim recovers expired leases. SQLite write transactions remain short because
handlers execute outside them. Budget exhaustion is a controlled terminal
outcome, not a retry loop, and usage history can be queried by Job.

The initial implementation intentionally uses one SQLite queue and one worker
process model. Adaptive cadence, distributed workers, provider-specific cost
pricing, and durable multi-process service installation remain later work.
Every handler that can consume resources must declare a bounded `budget` plan
in its Job payload for pre-dispatch reservation.

## Evidence

Offline tests cover migration idempotence, duplicate enqueue ticks, atomic
claims, lease expiry/restart recovery, bounded retry and backoff, cancellation,
manual rerun, scheduler cadence, worker handler allowlisting, run aggregation,
budget reservation, paid disablement, actual usage attribution, and API access:

```powershell
python -m pytest -q tests/test_phase07_jobs.py
```
