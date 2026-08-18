# Phase 08 Review — AI Through Persistent Monitoring

## Scope

Independently review all changes from Phases 05-08 and their integration with the
accepted Phase 04 baseline. Do not start Phase 09.

## Required logical review areas

### AI boundaries and evidence safety

- Confirm provider adapters cannot persist unvalidated output or bypass Claim,
  Evidence, merge, synthesis, or budget authority.
- Reproduce local-only behavior, paid-disable behavior, timeouts, malformed
  structured output, low confidence, retries, and provider failure.
- Check benchmark methodology, reproducibility, and ADR conclusions.

### Acquisition security and correctness

- Treat feeds, redirects, URLs, HTML, metadata, and provider results as hostile.
- Review SSRF protections, schemes/hosts, size/time limits, parser failure,
  canonicalization, conditional requests, content identity, and provenance.
- Verify unchanged content is cheap and mutated content creates correct versions.

### Durable concurrency and economics

- Inspect transactional Job claims, lease recovery, idempotency, retry/backoff,
  cancellation, scheduler duplication, and SQLite lock duration.
- Attempt race conditions and process crashes at each state transition.
- Verify every paid dispatch checks and atomically records the correct budget.

### Monitor scope and relevance

- Confirm all target types enforce integrity and deletion behavior.
- Try rejected vocabulary, disabled targets, ambiguous terms, cascade fallbacks,
  and adaptive cadence boundaries.
- Ensure suggestions remain distinguishable from user-approved active scope.

### Quality and verification

- Review tests first, dependencies, module direction, logs/secrets, query bounds,
  N+1 behavior, dead code, and unnecessary abstractions.
- Run full suites plus offline acquisition, worker crash/recovery, duplicate tick,
  local-only monitoring, and budget-exhaustion scenarios.

## Verdict rule

Write `docs/reviews/PHASE_08_REVIEW.md`. Fix every Critical and Required finding,
rerun verification, and approve only when Phases 05-08 work safely together and
do not regress the accepted evidence metrics. Record the accepted commit hash.
Phase 09 remains blocked until approval.

## Post-Audit Status — 2026-08-18

This review plan remains historical. The current audit distinguishes the valid
Source Monitor acquisition runtime from the missing post-acquisition relevance
handoff and unsupported non-Source execution paths. Phase 17 establishes the
correct baseline; Phase 20 owns automatic relevance.
