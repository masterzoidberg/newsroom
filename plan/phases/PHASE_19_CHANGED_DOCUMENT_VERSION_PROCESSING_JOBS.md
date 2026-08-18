# Phase 19 — Changed DocumentVersion Processing Jobs

## Objective

Create the durable orchestration primitive that connects acquisition to
downstream processing without making MonitorExecutionService synchronous or
AI-coupled.

## Why this phase exists

The current monitor correctly records a changed version and returns. There is no
durable obligation representing the work that should process that version.

## Current-state gap

The production handler registry contains `monitor_check` and
`research_question`, but no DocumentVersion processing job. A changed version
has no restart-safe downstream lifecycle.

## Scope

- Define the explicit job type `document_version_process`.
- Make `document_version_id` the canonical owner and carry Source, Document,
  Monitor, and effective-scope traceability.
- Add idempotent enqueue/coalescing and explicit rerun semantics.
- Add retry, lease recovery, cancellation, budgets, and terminal outcomes.
- Register the handler in the production runtime.
- Add completion/recovery hooks only where state reconciliation requires them.
- Implement a deterministic no-op/test processor only.

## Non-goals

- No relevance, AI provider, semantic extraction, accepted Claims, Story
  updates, Reports, or alerts.
- No synchronous processing inside the acquisition transaction.
- No arbitrary request-controlled handler execution.

## Existing components to reuse

`JobService`, `_active_monitor_check_id_tx`, `WorkerProcess`,
`merge_handlers`, `compose_completion_hooks`, `MonitorExecutionService`,
`runtime.build_worker_handlers`, and the existing budget/recovery patterns.

## Required implementation

When acquisition commits a new or changed DocumentVersion, create at most one
active processing obligation using a stable idempotency key derived from the
version. The enqueue must be transactionally linked to the acquisition outcome
or use a recovery-safe outbox/hand-off mechanism. The no-op processor must load
and verify the Phase 18 artifact and persist a lifecycle result.

## Data model/migration expectations

Use the existing Jobs schema where possible. Add only the ownership/index/state
fields required to query processing obligations by DocumentVersion and status.
Document processing records should preserve job ID, version ID, monitor/source
context, status, attempt, timestamps, and failure cause.

## Runtime integration

The Source Monitor remains responsible for acquisition and truthful monitor
activity. A successful changed acquisition hands off to the durable worker. A
no-change or failed acquisition must not create a processing obligation.

## Security/privacy considerations

Require canonical ownership validation, bounded payloads, allow-listed handler
registration, budget reservation, and safe artifact access. Do not place article
content in Job payload JSON.

## Tests

- Source change creates exactly one processing Job.
- Repeated scheduler ticks do not duplicate it.
- A completed version does not reprocess unless explicitly rerun.
- Lease expiry, retry, cancellation, and worker restart preserve consistency.
- Unknown job types fail safely.
- Monitor and processing failures remain separately observable.

## Acceptance criteria

Production-composition test proves:

```text
Source change → one DocumentVersion → one durable processing Job
               → persisted processing lifecycle
```

No manual API call may be required after Monitor setup.

## Live-test gate

After Phase 19, public-source canaries may verify processing-job creation and
restart behavior, but the processor must remain deterministic and non-semantic.

## Dependencies

Phase 17 baseline and Phase 18 durable content artifacts.

## Exit criteria

Every changed DocumentVersion has a durable, idempotent, restart-safe processing
obligation and a registered worker path. Phase 20 may add automatic relevance.
