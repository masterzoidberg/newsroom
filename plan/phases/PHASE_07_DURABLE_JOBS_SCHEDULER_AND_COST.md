# Phase 07 — Durable Jobs, Scheduler, and Cost

## Objective

Make research work restart-safe, bounded, attributable, and operable unattended.

## Required work

- Implement durable Jobs, Attempts, Runs, transactional leases, expiry recovery,
  bounded retries/backoff, cancellation, and idempotency.
- Add separate scheduler and worker processes; scheduler enqueues due work and
  workers claim it atomically.
- Persist schedules and next-run state without relying on an HTTP request.
- Enforce acquisition, local-model, paid-request, and USD budgets before dispatch.
- Attribute provider usage to Jobs, Monitors, and Research Questions.
- Expose job/run status, failure reasons, retry history, cancellation, and manual
  rerun APIs.

## Boundaries

Use SQLite and one worker initially. Do not add Redis, Celery, Kafka, or another
queue without measured contention.

## Verification and exit gate

- Crash, process restart, expired lease, duplicate tick, retry exhaustion,
  cancellation, and budget exhaustion tests.
- No duplicate unbounded work and no paid call beyond a hard cap.
- Queue transactions remain short and representative contention stays bounded.
- Full project checks pass.

## Completion Record

Completed 2026-08-16.

### Delivered

- Added migration 0006 for job run attribution, cooperative cancellation,
  durable budget limits/reservations, and persisted scheduler state while
  preserving the existing Phase 02 job/attempt/run/provider-usage tables.
- Added `JobService` with bounded JSON payloads, idempotent enqueue, atomic
  SQLite claims, owner leases, expiry recovery, append-only attempt history,
  exponential retry/backoff, cancellation, manual rerun, pagination, and
  terminal Run aggregation.
- Added `SchedulerService` and `SchedulerProcess` for persisted due-Monitor
  ticks, one cron Run per tick, deterministic cadence clamping, and duplicate
  tick protection. Added `WorkerProcess` with an explicit allow-listed handler
  map and restart-safe one-job execution.
- Added `BudgetService` for global/policy/Job/Research Question daily,
  monthly, and lifetime caps covering acquisition units, local-model units,
  paid requests, and USD. Claims reserve planned cost before dispatch;
  reservations release on completion, cancellation, or lease recovery while
  actual `provider_usage` remains attributable.
- Kept paid dispatch disabled by default and added authenticated APIs for Jobs,
  Runs, scheduler ticks, provider usage, budget limits, paid enablement,
  cancellation, and manual reruns.
- Added ADR-005, architecture/API/decision-log documentation, migration
  compatibility updates, and deterministic offline tests for crash/restart
  recovery, lease expiry, bounded retries, cancellation, idempotent scheduler
  ticks, worker execution, run status, budget exhaustion, and authorization.

### Verification

- `python -m pytest -q` — passed (238 tests).
- `python -m pytest -q tests/test_phase07_jobs.py` — passed (9 tests).
- `python -m compileall -q newsroom` — passed.
- `python -m newsroom.evals validate` — passed (30 cases).
- `python -m newsroom.evals replay multi-outlet-hermes-v0200` — passed with the existing deterministic replay hash.
- `python -m newsroom.ai_benchmark` — passed; output matches the committed Phase 05 benchmark artifact.
- `npm run typecheck` and `npm run build` from `frontend/` — passed.
- `npm audit --audit-level=high` from `frontend/` — passed; 0 vulnerabilities.
- `git diff --check` — passed.
- `poetry run format` / `poetry run test` — unavailable for this setuptools project; the canonical Python checks above pass.

### Review

- Five-axis review completed for correctness, readability, architecture,
  security, and performance; no Critical or Required findings remain.
- Queue transactions are short; worker handlers execute outside SQLite write
  transactions, are explicitly allow-listed, and cannot invoke arbitrary
  request-controlled subprocesses.
- Accepted implementation commit:
  `c11d12598ffb0677b963ee466672a048bf764e5f`.

### Limitations

- The initial deployment remains one SQLite queue and one worker process model;
  distributed workers and external queues remain intentionally deferred.
- Resource-consuming handlers must declare bounded estimates in the Job
  payload's `budget` object for pre-dispatch reservation; provider-specific
  pricing and adaptive cost forecasting are later work.
- Scheduler cadence is persisted and clamped to policy min/max values, but
  adaptive activity/lifecycle cadence is deferred to the monitoring phases.
- Process auto-start/service installation and unattended Windows supervision
  remain Phase 16 deployment work.
