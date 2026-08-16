# ADR-008: Bounded Research Questions and Evidence Gaps

## Status

Accepted in Phase 10.

## Decision

Research Questions remain first-class workflow objects, separate from Claims and
Evidence. Their lifecycle transitions, Claim/Evidence links, user notes, and
bounded pursuit attempts are persisted in SQLite. History and evidence links
are append-only; attempts and suggestion review state are mutable operational
state.

Evidence-gap suggestions are derived only from stored ledger state: Claim state,
support/contradiction relationships, source quality/composition, and lineage-aware
independence. Suggestions can propose a question, search, or candidate source,
with rationale and expected information value, but require explicit review or
conversion.

Manual and policy pursuit each enqueue one idempotent durable Job with
`max_attempts=1`. Question-level attempt, query, local-model, and paid-cost
budgets are checked before enqueue. The scheduler has a fixed due-item limit;
there is no recursive or open-ended research loop. User hypotheses are notes and
never silently create accepted Claims.

## Consequences

- Restart and retry behavior is inspectable from the database.
- Contradictions and insufficient support remain distinct gap signals.
- A future provider/search implementation can consume the durable Job contract
  without changing the Question or Evidence Ledger models.
- Gap detection is intentionally conservative and may produce several reviewable
  suggestions for one Claim.
