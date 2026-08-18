# Phase 17 — Runtime Reconciliation and Green Baseline

## Objective

Establish a trustworthy post-remediation baseline for the current SQLite
runtime before adding intelligence functionality.

## Why this phase exists

The Source Monitor runtime was recently repaired, but the repository still has
stale Phase 16 metadata and one nondeterministic acceptance assertion. Phase 17
records the actual runtime boundary and makes verification repeatable.

## Current-state gap

The current suite collects 381 tests but has a known ordering failure in
`tests/test_monitor_runtime_acceptance.py`: second-resolution timestamps plus
random IDs can defeat the test's assumed insertion order. Current production
handler coverage is explicit for `monitor_check` and `research_question`; only
Source Monitor targets execute acquisition.

## Scope

- Make the version-ordering assertion use an explicit chronological/creation
  contract rather than random-ID ordering.
- Reconcile schema/version references to migration 0014.
- Update stale Phase 16 review metadata and runtime documentation.
- Document the verified Scheduler → Job → Worker → Acquisition boundary.
- Document executable versus accepted-but-unsupported Monitor target types.

## Non-goals

- No relevance, AI, article analysis, Evidence, Claims, Story, Report, or alert
  functionality.
- No migration redesign, provider integration, or frontend workflow work.
- No production deployment or live AI test.

## Existing components to reuse

`newsroom/runtime.py`, `newsroom/jobs.py`, `newsroom/scheduler.py`,
`newsroom/worker.py`, `newsroom/monitoring.py`,
`tests/test_monitor_runtime_acceptance.py`, and the Phase 16 release checks.

## Required implementation

Keep the production behavior unchanged unless the test contract exposes a real
runtime defect. Use a deterministic ordering field already guaranteed by the
schema, or add only the smallest test fixture/control necessary to distinguish
insertion order. Ensure the documentation states that `source` is the only
currently executable acquisition target.

## Data model/migration expectations

No migration is expected. Documentation and tests must consistently identify
the current applied schema as version 14 and must not claim that 0013 is latest.

## Runtime integration

No runtime integration is added. This phase verifies the existing production
composition and handler registry, including coalescing, restart recovery,
disabled-monitor behavior, and truthful `changed`/`no_change`/`error` outcomes.

## Security/privacy considerations

Do not loosen acquisition limits, authentication, job allow-listing, or release
clean-worktree checks while repairing the baseline.

## Tests

- Repeat the full backend suite multiple times.
- Run monitor runtime acceptance and scheduler/coalescing tests repeatedly.
- Run compile, evaluation corpus validation, frontend typecheck/build, and npm
  audit.
- Verify the Phase 16 documentation references the current commit/schema.

## Acceptance criteria

- Full backend suite passes repeatedly with 381 tests collected.
- Frontend typecheck and build pass.
- Migration 0014/schema version 14 is documented consistently.
- The current Monitor runtime boundary is documented accurately.
- Unsupported non-Source target behavior is explicit and tested.

## Live-test gate

After Phase 17, bounded real-network RSS and HTML acquisition canaries are
permitted. No AI or downstream intelligence claims may be made.

## Dependencies

Phases 01–16 historical implementation and the post-audit annotations.

## Exit criteria

The repository has a repeatable green baseline, reconciled release metadata,
and an accepted written contract for the current runtime. Phase 18 may begin.

## Completion Record — 2026-08-18

Implemented by Luna against the post-audit roadmap. Overall verdict: **PASS**.

### Files changed

- `tests/test_monitor_runtime_acceptance.py` — deterministic version-ordering
  contract and new accepted-but-unsupported target coverage (test code only).
- `docs/ARCHITECTURE.md` — Monitor target execution boundary, Phase 20+
  downstream-stage boundary, and migration 0014/schema version 14 note.
- `docs/reviews/PHASE_16_REVIEW.md` — Phase 17 reconciliation note appended
  while preserving the existing post-audit annotation and verdict.
- `README.md` — post-audit paragraph made explicit about the executable-only
  `source` boundary and current schema version.
- `plan/phases/PHASE_17_RUNTIME_RECONCILIATION_AND_GREEN_BASELINE.md` — this
  Completion Record.

Production code (`newsroom/**`, `scripts/**`) was **not modified**. No runtime
or migration behavior changed. No unrelated user files were touched.

### Exact defect fixed

`test_production_composition_source_monitor_lifecycle_aaa_to_b` (in
`tests/test_monitor_runtime_acceptance.py`) asserted positional version order
from `ORDER BY retrieved_at, id`. `retrieved_at` is second-resolution
(`utc_now()` with microseconds stripped) and ids are random
(`secrets.token_hex`), so when the first and changed acquisitions landed on the
same wall-clock second, `versions[1]` could be version A instead of version B.
The failure was a nondeterministic test-contract bug, not a runtime defect.

The test now captures the first created DocumentVersion by value at the first
acquisition step (exactly one row is asserted then), and at the end locates the
second version by set membership against that captured id rather than row
position, proving: version A exists; second unchanged acquisition leaves exactly
one version; third changed acquisition leaves exactly two versions; the two ids
and content hashes are distinct. It passed 20/20 repeated runs and the fix
cannot depend on random-ID tie-breaking.

### Runtime contract confirmed

All Phase 17 runtime invariants were verified from current code and existing
tests; none are false, so production behavior is unchanged:

- Scheduled Monitor execution does not require `candidate_text`
  (`SchedulerService.tick` payload carries only monitor_id/target/budget;
  `test_scheduler_payload_never_requires_candidate_text`).
- Source Monitor acquisition uses `AcquisitionService`
  (`MonitorExecutionService.handle` → `poll_feed` / `acquire_document`).
- `DocumentVersion` deduplication is intact (same `content_hash` short-circuits;
  HTTP 304 records `not_modified` without a new version).
- `relevant_change` is never emitted merely because acquisition changed; a
  changed acquisition records `changed` (semantic stage unset).
- `no_change` is never used for acquisition failure (error paths record
  `error`; `test_false_success_invariant_all_error_paths_never_record_no_change`
  and `_no_change_paths_to_cover`).
- Disabled Monitors do not acquire (handler short-circuits to `disabled` before
  any transport call; `test_disable_before_execution_via_production_handler_does_not_acquire`).
- Active queued/running Monitor jobs coalesce
  (`SchedulerService.tick` skips a Monitor with an active obligation).
- Direct enqueue (`JobService.enqueue` active-work `JobConflict`) and rerun
  (`_guard_monitor_check_rerun`) cannot bypass coalescing.
- Monitor ownership validation is enforced
  (`_resolve_monitor_check_monitor_id` requires canonical `monitor_id` and
  rejects payload conflicts).

### Monitor target execution boundary

The schema (`monitors.target_type` CHECK) and API accept `topic`, `subject`,
`story`, `source`, `research_question`. Actual execution: only `source`
performs real acquisition. Every other target type is handled by the production
worker and truthfully fails with `error`/`unsupported_target` monitor activity
and zero network/acquisition calls. New test
`test_non_source_monitor_targets_fail_unsupported_target_without_acquisition`
covers all four non-source target types through the production composition.
Missing target adapters are intentionally not implemented in Phase 17.

### Migration reconciliation

Current chain verified: migrations 1–14 applied; `app_meta.schema_version` =
`14`; `migration_status` =
`(1,2,3,4,5,6,7,8,9,10,11,12,13,14)`; `apply_migrations` idempotent.
`newsroom/migrations.py`, `tests/test_phase02_foundation.py`, and
`tests/test_phase08_monitors.py` already reflect version 14. No migration was
created and none is in scope. Pre-existing post-audit annotations in
`PHASE_02_FOUNDATION_AND_SCHEMA.md`, `PHASE_16_WINDOWS_DEPLOYMENT_AND_FINAL_ACCEPTANCE.md`,
and `docs/reviews/PHASE_16_REVIEW.md` already identify 0013 as historical
rehearsal evidence and 0014 as current; they were preserved.

### Commands run and results

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_monitor_runtime_acceptance.py` | **14 passed** |
| target test x20 loop | 20/20 passed (no flakes) |
| `python -m pytest -q tests/test_phase02_foundation.py tests/test_phase08_monitors.py` | **30 passed** |
| monitor + scheduler suites x5 loop | 5/5 passed (46 tests each) |
| `python -m pytest --collect-only -q` | **382 tests collected** (381 audit baseline + 1 new Phase 17 test) |
| full backend suite run 1 | **382 passed, 37 warnings** |
| full backend suite run 2 | **382 passed, 37 warnings** |
| `python -m compileall -q newsroom scripts tests` | Pass (exit 0) |
| `npm.cmd run typecheck` | Pass |
| `npm.cmd run build` | Pass (JS 210.68 kB / 62.77 kB gzip, CSS 18.69 kB) |
| `git diff --check` | Pass (existing LF/CRLF normalization warning only) |

### Remaining known limitations

- Non-Source Monitor targets remain accepted-but-unsupported
  (`error`/`unsupported_target`) until their adapters are implemented in later
  phases.
- The unattended intelligence loop stops after `DocumentVersion` persistence;
  automatic relevance/analysis/Evidence/Claims/Story/Report/Alert processing is
  Phase 20+ work.
- The full suite is green repeatedly; HTTPX deprecation warnings (37) and the
  LF/CRLF normalization warning remain pre-existing noise.
- No durable normalized content artifact, processing jobs, provider
  integration, or UX changes were made (Phase 18+).

### Live Test A readiness verdict

**READY.** The repository can execute bounded real-network Live Test A (real
public RSS Source, real public HTML Source → Scheduler → Worker → Acquisition →
DocumentVersion → truthful `changed`/`no_change`/`error`) with no AI. No public
internet live test was run in this phase; the gate is prepared only.
