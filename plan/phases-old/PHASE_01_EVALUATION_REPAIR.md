# Phase 01 — Evaluation Repair

## Objective

Make the Phase 0 evaluation foundation trustworthy before adding application
architecture.

## Required work

- Strictly validate case, fixture, and prediction types, IDs, references,
  timestamps, URLs, candidate assignments, enum values, and nonnegative usage.
- Reject duplicate IDs and candidates assigned to multiple gold/predicted groups.
- Prevent empty or incomplete predictions from receiving perfect event scores;
  add candidate coverage and important-Story recall.
- Match Claims within the correct event and evaluate expected Claim state.
- Measure closed-world synthesis against accepted Claims only.
- Include scheme, host, and non-default port in URL identity; reject HTTP(S)
  URLs without a host.
- Rank every eligible dedupe target and choose the strongest with deterministic
  tie-breaking instead of the first input candidate.
- Add regression tests for every defect from the repository audit.

## Boundaries

Do not add FastAPI, migrations, providers, or frontend work. Preserve committed
corpus and baseline data unless a documented validation correction requires a
minimal fixture update.

## Verification and exit gate

- `python -m pytest -q`
- `python -m newsroom.evals validate`
- `python -m newsroom.evals baseline --json`
- Empty/malformed predictions fail validation or receive appropriately degraded
  scores; replay and baseline output remain deterministic.

## Completion Record

Implemented.

### Completed work

- Added strict case, fixture, and prediction validation for types, IDs, enums,
  references, UTC timestamps, HTTP(S) URL hosts, candidate assignments, and
  nonnegative usage values.
- Added candidate coverage and important-Story recall, event-score degradation
  for empty/partial predictions, event-scoped Claim matching, expected Claim
  state accuracy, and accepted-Claim-only synthesis scoring.
- Made URL fingerprints scheme/hostname/port aware and made dedupe rank all
  eligible candidates with deterministic tie-breaking.
- Added regression coverage in `tests/test_phase01_hardening.py` and updated
  the evaluation contract documentation.

### Verification

- `python -m pytest -q` — passed (174 tests).
- `python -m newsroom.evals validate` — passed (30 cases).
- `python -m newsroom.evals baseline --json` — passed; two consecutive outputs
  were byte-for-byte identical.
- `python -m newsroom.evals replay multi-outlet-hermes-v0200` — passed.
- `git diff --check` — passed.
- `poetry run format` / `poetry run test` — unavailable because Poetry could
  not create its cached virtualenv (`WinError 183`) and this project does not
  define those wrapper scripts; direct Python verification passed.

### Residual risk

The evaluation subsystem remains intentionally standalone and does not add any
FastAPI, migration, provider, or frontend work from later phases.

### Checkpoint

Implementation checkpoint commit: `f3213df`.

## Post-Audit Status — 2026-08-18

This phase remains a historical, valid implementation record. The evaluation
subsystem is complete within its stated standalone scope; it is not evidence
that the current Newsroom runtime automatically produces intelligence outputs.
The post-audit completion gates begin at Phase 17.
