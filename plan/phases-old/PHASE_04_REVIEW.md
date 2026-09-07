# Phase 04 Review — Evaluation Through Evidence Ledger

## Scope

Independently review all changes from Phases 01-04. Do not start Phase 05.

## Required logical review areas

### Evaluation integrity

- Attempt to game metrics with empty, partial, duplicated, unknown, cross-event,
  malformed, and negative-cost predictions.
- Confirm deterministic replay/baseline behavior and meaningful coverage metrics.
- Verify Claim, state, evidence, contradiction, and closed-world scoring semantics.

### Persistence and architecture

- Review migration immutability, FK coverage, transactions, WAL behavior,
  backup/restore, runtime path guards, and domain dependency direction.
- Confirm Source, Document, DocumentVersion, Story, Claim, Evidence, and Revision
  identities remain distinct and auditable.

### API and authentication

- Review authorization, sessions, CSRF, throttling, validation, error leakage,
  pagination, ordering, and omitted/null update behavior.
- Check all SQL is parameterized and untrusted inputs are bounded.

### Evidence invariant

- Trace representative propositions back through Claim, Evidence Span,
  DocumentVersion, and Source.
- Try mutations of accepted Claims and unsupported synthesis; both must fail.
- Confirm conservative Story resolution and deterministic best-match selection.

### Quality and verification

- Review tests first, then implementation, dependencies, dead code, complexity,
  sync I/O risks, N+1 queries, and frontend build behavior.
- Run the complete backend/frontend suites, corpus validation, baseline, migration
  from zero, backup/restore, and manual evidence smoke path.

## Verdict rule

Write `docs/reviews/PHASE_04_REVIEW.md` with severity-ranked findings and exact
evidence. Fix all Critical and Required findings, rerun verification, and approve
only when Phases 01-04 jointly satisfy their exit gates. Record the accepted
commit hash. Phase 05 remains blocked until approval.

## Post-Audit Status — 2026-08-18

This review plan and its historical approval record remain part of the Phase 04
history. The post-audit finding that the Evidence Ledger is manual/API-only and
not connected to acquired content is superseding completion work for the new
Phase 18 and Phase 22 gates; it does not invalidate the manual vertical slice.
