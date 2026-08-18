# Phase 12 Review — Story Intelligence Through Product UI

## Scope

Independently review all changes from Phases 09-12 and their integration with the
accepted monitoring system. Do not start Phase 13.

## Required logical review areas

### Story correctness and lineage

- Stress ambiguous merges, shared entities, temporal boundaries, corrections,
  mutable documents, syndication, citation chains, and common-source dependence.
- Confirm strongest-candidate resolution is deterministic and ambiguity splits.
- Verify novelty and corroboration classifications against exact evidence.

### Research and report integrity

- Trace gap detection and Question suggestions to stored evidence deficiencies.
- Review attempt budgets, lifecycle/history, resolution evidence, and hypothesis
  separation.
- Audit every Living Report/briefing proposition and material-change explanation
  against the accepted Claim set.

### Importance and alerts

- Attempt duplicate alert storms, timezone errors, retry duplication, permission
  denial, offline delivery, stale subscriptions, and low-value article spikes.
- Confirm browser notifications reveal no sensitive content beyond configured
  policy and in-app state remains authoritative.

### UI and accessibility

- Review API/domain consistency, authorization, error handling, stale state,
  optimistic updates, destructive confirmations, XSS/output encoding, and
  sensitive-data rendering.
- Exercise desktop/phone/tablet, keyboard, focus, screen-reader semantics,
  offline/PWA, empty/loading/error states, and direct evidence navigation.

### Quality and verification

- Review tests first, frontend state architecture, render/query performance,
  pagination, N+1 APIs, bundle/dependency impact, dead code, and duplication.
- Run full backend/frontend suites and end-to-end Story, Question, Report, Alert,
  and PWA workflows with screenshots.

## Verdict rule

Write `docs/reviews/PHASE_12_REVIEW.md`. Fix all Critical and Required findings,
rerun verification, and approve only when the end-to-end review product preserves
evidence and monitoring invariants. Record the accepted commit hash. Phase 13
remains blocked until approval.
