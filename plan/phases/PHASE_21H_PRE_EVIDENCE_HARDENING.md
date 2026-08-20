# Phase 21H — Pre-Evidence Hardening

## Status

Active remediation gate after the completed Phase 21 audit and Live Test B.
Phase 22 remains blocked. This phase does not promote candidate excerpts into
EvidenceSpans, Claims, Stories, Reports, or Alerts.

## Objective

Close only the five required pre-evidence correctness and security gaps:

1. durable paid-budget reservation before a provider call;
2. durable paid-call invocation identity and duplicate-call protection;
3. complete ArticleAnalysis relevance/analysis provenance validation;
4. mutable Subject, Story, and Research Question scope refresh;
5. DNS rebinding protection between URL validation and socket connection.

## Implemented boundary

Migration 0019 adds `analysis_invocations` and links paid provider-usage rows
to the invocation. Reservation is atomic with budget checks and is held while
the provider runs. A concurrent worker waits for the canonical persisted
analysis; an uncertain provider outcome is retained and blocks automatic
re-execution until an explicit operator release. Confirmed provider rejection
can be retried without treating it as an unknown remote result.

The provenance validator checks the ArticleAnalysis → relevance decision →
pinned Monitor scope history → processing Job (when present) →
DocumentVersion → immutable ContentArtifact → Source chain, including
cross-reference identity, hashes, lengths, JSON schema, monitor need, job
payload, and scope ownership. Integrity checks invoke the validator read-only.

Subject edits/aliases, Story revisions, and Research Question edits append a
new scope snapshot in the same transaction as the mutation. Historical
snapshots remain immutable, so already-pinned processing keeps its original
scope.

HTTP acquisition validates every hop's raw hostname and DNS answers, connects
to the validated address directly, verifies the connected peer, and preserves
the hostname for the Host header and HTTPS SNI. The old redirect helper remains
covered for compatibility, but the production transport no longer performs a
second hostname resolution behind the policy check.

## Explicit non-goals

- No `EvidenceSpan` rows, canonical `Claims`, Story evolution, Reports, or
  Alerts automation.
- No Phase 22 runtime integration or evidence promotion.
- No automatic rerun of the paid Live Test B call.
- No unrelated refactor, dependency, or service introduction.

## Design constraints recorded for Phase 22

Phase 22 may start only after this phase is independently re-reviewed. Its
implementation must preserve the following constraints recorded in
`PHASE_22_VERIFIED_EVIDENCE_AND_CLAIMS_AUTOMATION.md`:

- offsets are Unicode/Python `str` codepoint offsets over the canonical
  normalized evidence view, never byte offsets or model-supplied offsets;
- HTML/text evidence uses the exact immutable normalized artifact view;
- feed evidence uses a deterministic projection of the persisted feed-entry
  metadata artifact, with the projection version and field path retained;
- the full Phase 21H provenance validator must pass before any EvidenceSpan or
  Claim write;
- paid analysis consumption requires the durable reservation and invocation
  state machine; no new provider call may be introduced by evidence retries.

## Verification record

Targeted hardening, Phase 21, acquisition, monitoring, document-processing,
and research-question tests were run during implementation:

- `tests/test_phase21h_hardening.py`: 11 passed;
- Phase 21: 33 passed; Phase 20: 28 passed; Phase 19: 24 passed;
- Phase 18: 20 passed; acquisition: 15 passed; jobs: 9 passed;
- operations/integrity: 5 passed; research-question worker: 31 passed;
- final `poetry run pytest -q`: 499 passed, 39 warnings;
- `python -m compileall -q newsroom tests`: passed;
- `npm run typecheck` and `npm run build` in `frontend`: passed;
- `git diff --check`: passed;
- network smoke: public `https://example.com/` and a bounded
  `https://httpbin.org/redirect-to` → `https://example.com/` redirect both
  returned HTTP 200. No paid AI call was made.

The repository has no `poetry run format`, `poetry run test`, or Ruff entry
point, so those skill-prescribed aliases were checked and reported as
unavailable rather than adding tooling or dependencies.

## Exit gate

`READY FOR CODEX RE-REVIEW BEFORE PHASE 22` is permitted only when concurrency,
budget, provenance, scope-refresh, SSRF, schema/migration, and regression
invariants all pass and the Git diff contains no evidence-promotion path.

## Phase 21H.1 — Final pre-evidence corrections (2026-08-19)

One bounded pre-gate snapshot that closes the remaining provenance gaps before
Phase 22:

- **Historical provenance.** `validate_analysis_provenance` now separates
  historical validity from current need eligibility. A historically valid
  ArticleAnalysis stays valid against its pinned `monitor_scope_history`
  snapshot and relevance scope snapshot even when the current
  Topic/Subject/Story/Research Question is later deleted, disabled, or retired
  (reported as `current_need_available` / `current_need_status` metadata).
  Future processing still fails closed or becomes explicitly non-semantic at
  enqueue time (`current_information_need_status`) rather than silently
  reusing a stale scope; historical scope history remains immutable.
- **Automatic processing-Job provenance.** Every ArticleAnalysis now carries a
  classified chain: `automatic` (analysis.job_id == the durable relevance
  decision's `document_version_process` Job, full chain validated through
  relevance → Job → DocumentVersion → Monitor → pinned scope snapshot →
  ContentArtifact → Source), `standalone` (no Job on either side; readable but
  never automatically promotable), or inconsistent (rejected at
  creation and by the read-only validator). The processing handler records the
  analysis under the decision's canonical Job (stable across rerun/lease
  recovery), and the analysis service fails closed before any provider call
  when an automatic analysis is missing its Job or a standalone analysis
  claims one. Deterministic promotion eligibility is a derived flag
  (`eligible_for_automatic_promotion`), distinct from historical readability.
- **Phase 22 evidence-coordinate specification.** `PHASE_22_
  VERIFIED_EVIDENCE_AND_CLAIMS_AUTOMATION.md` now carries a binding
  deterministic contract: canonical evidence views (exact artifact text /
  `feed_entry_projection_v1` feed metadata projection with field path),
  view hashing, Unicode code-point offsets, exact substring matching,
  zero-match and ambiguous multiple-match rejection with the only permitted
  deterministic resolution, locally recomputed offsets, artifact/view
  provenance, truncation bounds, atomic promotion, deterministic promotion
  identity, and the source-membership vs logical-support distinction. The
  next Phase 22 implementation agent must not invent these rules.
- **Verification.** `tests/test_phase21h_hardening.py` grown to 34 tests
  (retry reauthorization, historical validity vs current eligibility,
  automatic/standalone classification, missing/wrong Job/DocumentVersion/
  Monitor/scope relationships, migration, concurrency, SSRF pinning).
  Post-audit suites: Phase 21 33, Phase 20 28, Phase 19 24, Phase 18 20 all
  pass; focused regression 139 passed; full backend suite **522 passed, 39
  warnings** (twice); `npm run typecheck` and `npm run build` in `frontend`
  pass; `python -m compileall -q newsroom scripts tests` passes;
  `git diff --check` passes.

Evidence boundary unchanged: this checkpoint still stops at persisting
ArticleAnalysis; no EvidenceSpan, Claim, ClaimEvidence, Story, Report, or
Alert automation exists in the diff.
