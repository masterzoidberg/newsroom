# ADR-002 — Evidence-First Vertical Slice Before Broad Product Build

- **Status:** Accepted
- **Date:** 2026-08-16
- **Deciders:** Standalone Newsroom implementation lead

## Context

The signature capability of standalone Newsroom is the Evidence Ledger: every
substantive proposition in a synthesized Story must trace to accepted Claims,
and accepted Claims must trace to exact Evidence Spans from versioned Documents.
This is what differentiates Newsroom from a summary generator.

It would be possible to build broad monitoring, scheduling, and UI first and add
evidence later. That path risks locking in an architecture where evidence is
bolted on rather than foundational.

## Decision

The first meaningful vertical slice (Phase 2) demonstrates the full evidence
chain — Monitor -> discovery -> DocumentVersion -> Story resolution -> atomic
Claim -> exact Evidence Span -> Claim state -> evidence-bound Story revision —
before broad product expansion. Phase 0 establishes, before that slice is built,
the evaluation corpus, metrics, replay, and v1 baseline that determine whether
the slice actually improves on v1.

## Consequences

- Evaluation is a permanent product subsystem (`newsroom.evals`), not test glue.
- The closed-world synthesis invariant is a hard requirement to be enforced
  beyond prompt wording, and is measured by the "unsupported synthesized
  proposition rate" metric from Phase 0 onward.
- "False merge is worse than false split" is encoded in the corpus (dedicated
  `similar_distinct_events` and `ambiguous_merge` cases) and in the metrics.
- If the vertical slice does not improve the agreed metrics over the v1
  baseline, broader product work pauses.
