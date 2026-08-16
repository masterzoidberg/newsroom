# Phase 08 — Monitors and Semantic Relevance

## Objective

Turn one-off research into persistent, concept-aware monitoring.

## Required work

- Implement Monitor targets for Topic, Subject, Story, Source, and Research
  Question with validated target integrity.
- Add monitoring policies, custom schedules, channel/budget controls, cadence
  bounds, backoff, retirement, and user-visible scope history.
- Add AI-assisted vocabulary suggestions for synonyms, acronyms, aliases,
  broader/narrower/related concepts, ambiguity, and exclusions.
- Require explicit user approval before suggestions change active scope.
- Implement the relevance cascade: exact terms, vocabulary, entities, concepts,
  semantic similarity, then AI classification.
- Add bounded adaptive cadence based on recorded activity.

## Boundaries

No silent scope broadening, recursive work creation, or paid operation outside a
Monitor policy. Alerts and mature reporting remain later phases.

## Verification and exit gate

- Representative monitors run in local-only mode and survive restart.
- Disabled targets and rejected suggestions cannot create new work.
- False-positive/false-negative relevance fixtures exercise every cascade level.
- Adaptive cadence remains within configured bounds; full checks pass.
- Run `PHASE_08_REVIEW.md` next.

## Completion Record

Completed 2026-08-16.

- Implementation checkpoint: `3f4621d` (`Complete Phase 08 monitors and semantic relevance`).
- Added migration 0007 with immutable monitor activity, versioned scope history,
  and typed vocabulary suggestions.
- Added validated monitor-policy and monitor lifecycle services for all five
  target types, bounded adaptive cadence, backoff, retirement, and policy-only
  scheduler budgets.
- Added explicit approval-gated vocabulary suggestions and the exact-term →
  vocabulary → entity → concept → semantic → local-AI relevance cascade.
- Added a restart-safe allow-listed local monitor worker handler with no
  recursive enqueue path, authenticated API routes, ADR-006, and documentation.
- Verification: `python -m compileall -q newsroom`; `python -m pytest -q`
  (247 passed); evaluation corpus validation/replay; AI benchmark; frontend
  typecheck/build; `npm audit --audit-level=high` (0 vulnerabilities).
- `poetry run format` and `poetry run test` remain unavailable because the
  repository's Poetry scripts are misconfigured; direct checks above pass.

Next: run `PHASE_08_REVIEW.md`.
