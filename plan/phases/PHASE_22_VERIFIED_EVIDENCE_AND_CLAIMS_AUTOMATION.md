# Phase 22 — Verified Evidence and Claims Automation

## Objective

Make automatically generated EvidenceSpans verifiably anchored to immutable
normalized content before Claims can become accepted.

## Why this phase exists

Current EvidenceSpan creation validates an excerpt and locator structurally but
does not prove that the excerpt exists in the owning acquired version.

## Current-state gap

The manual ledger and AI vertical slice can persist caller/model-supplied
excerpts against a DocumentVersion. Acquisition now needs a durable artifact,
and Phase 21 will produce candidates that must be checked before persistence.

## Scope

- Verify artifact hash and content availability.
- Require exact excerpt membership in normalized content.
- Store deterministic offsets or locators plus excerpt/hash.
- Reject fabricated, ambiguous, or mismatched excerpts.
- Ingest candidate Claims only after EvidenceSpan verification.
- Apply entailment, support/contradiction, confidence, state, provenance,
  duplicate, and idempotency rules.

## Non-goals

- No Story matching, report generation, or browser notification.
- No acceptance of unsupported Claims merely because a model is confident.
- No raw article-body expansion beyond Phase 18 policy.

## Existing components to reuse

`EvidenceService`, `evidence_span_hash`, Claim state transitions,
`AIVerticalSliceService`, AI entailment contracts, Phase 18 artifacts, and
Phase 21 analysis records.

## Required implementation

Create a verification boundary between model output and the evidence ledger.
The verifier loads the immutable artifact, confirms its hash, finds the exact
normalized excerpt, validates locator/offset consistency, and only then creates
the EvidenceSpan and Claim relationship. A fabricated excerpt must fail the
transaction and leave no partial Claim.

## Data model/migration expectations

Extend EvidenceSpan provenance only as needed to store deterministic offsets,
artifact identity/hash, and verification status. Preserve immutable historical
spans and distinguish legacy/manual spans from automatically verified spans if
their provenance cannot be upgraded.

## Runtime integration

Phase 21 analysis results are consumed by a bounded verification step in the
processing workflow. Duplicate processing of the same version/result is
idempotent. Failure is visible as a processing outcome and never becomes a
false `no_change`.

## Security/privacy considerations

Do not trust model-provided offsets or excerpts. Recompute them from the local
artifact, bound scan work, prevent content-derived SQL or HTML execution, and
keep source text out of logs and exported operational metadata.

## Tests

- Exact excerpt and locator are accepted.
- Fabricated excerpt is rejected.
- Hash mismatch and missing artifact are rejected.
- Duplicate evidence and repeated processing are idempotent.
- Contradiction/support/unknown entailment states remain correct.
- Unaccepted or disputed Claims cannot enter report-accepted sets.

## Acceptance criteria

```text
analysis output
  → verified EvidenceSpan
  → Claim
  → evidence relationship
```

The fabricated-excerpt negative test must fail closed.

## Live-test gate

Live Test B may be rerun with evidence verification enabled. Live Test C is
permitted only after Phase 23 connects Stories, Reports, and Alerts.

## Dependencies

Phases 18, 20, and 21.

## Phase 21H design constraints — Phase 22 not started

The following constraints are prerequisites, not implementation work in this
phase:

- Use Unicode/Python `str` codepoint offsets against one canonical normalized
  evidence view. Never use byte offsets or trust model-provided offsets.
- Define and persist the canonical evidence view used for verification. HTML
  and text artifacts use the exact normalized artifact text.
- Feed artifacts require a deterministic evidence projection from the
  persisted feed-entry metadata, including projection version and field path;
  feed metadata must not be treated as raw HTML/text implicitly.
- Require a passing Phase 21H full provenance validation before any
  EvidenceSpan or Claim write.
- Treat the durable Phase 21H paid invocation/reservation state as a
  prerequisite. Evidence retries must not create another paid analysis call.

Phase 22 has not started and no evidence-promotion runtime is authorized by
this note.

## Exit criteria

Every automatically generated EvidenceSpan is content-verified and every
automatically ingested Claim has immutable, queryable provenance. Phase 23 may
connect verified intelligence to Stories and Reports.
