# Phase 10 — Research Questions and Evidence Gaps

## Objective

Turn unresolved evidence needs into durable, bounded follow-up research.

## Required work

- Implement Research Question lifecycle, priorities, attempt budgets, schedules,
  linked Claims/Evidence, resolution notes, and abandonment.
- Detect evidence gaps from Claim state, source composition, missing evidence
  categories, contradictions, and weak independence.
- Suggest Questions, searches, and candidate Sources with rationale and expected
  information value.
- Support manual and policy-bounded automatic pursuit through durable Jobs.
- Keep Source evidence, AI analysis, and user notes/hypotheses distinct.

## Boundaries

No open-ended research loops. A Question is resolved only by explicit user action
or validated linked evidence under a defined policy.

## Verification and exit gate

- Questions survive restart and retries respect attempt/query/cost limits.
- Resolution and reopening preserve history and evidence links.
- User hypotheses cannot silently become accepted Claims.
- Gap suggestions derive from stored evidence state; full checks pass.

## Completion Record

Completed in commit `3c816b5`.

Implemented:

- additive migration 0009 for Question budgets, immutable lifecycle history,
  Claim/Evidence links, attempts, notes, and gap suggestions;
- Research Question create/list/update/resolve/abandon/reopen lifecycle with
  priorities, schedules, resolution notes, restart-safe state, and bounded
  attempt/query/local-model/paid-cost accounting;
- evidence-derived gap detection for pending/unsubstantiated Claims, missing
  support, contradictions, missing primary sources, weak independence, and
  Stories without Claims;
- reviewable Question/search/source suggestions with rationale and expected
  information value;
- explicit hypothesis notes that do not create Claims;
- authenticated API routes for lifecycle, links, notes, attempts, gaps,
  suggestion review/conversion, manual pursuit, and due policy pursuit;
- idempotent durable `research_question` Jobs with `max_attempts=1`, plus
  scheduler-process integration for due policy Questions;
- ADR-008, API/architecture documentation, and regression coverage.

Verification:

- `python -m pytest -q` — passed (all tests);
- `python -m compileall -q newsroom` — passed;
- `python -m newsroom.evals validate` — passed (30 cases);
- `git diff --check` — passed;
- `poetry run format` and `poetry run test` remain unavailable because the
  repository's Poetry scripts are misconfigured (`Required parameter missing -`
  and Windows `'test' is not recognized`); direct Python verification passes.
