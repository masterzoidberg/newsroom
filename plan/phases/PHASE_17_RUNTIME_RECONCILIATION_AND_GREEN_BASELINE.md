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
