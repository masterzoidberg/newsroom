# PHASE 29.5 — TEMPORAL & BENCHMARK PROOF-INTEGRITY CLOSURE

## 0. STATUS AND BOUNDARY

Phase 29.5 is a bounded engineering closure for the Phase 29 proof surfaces.
It is not Phase 30 and does not fabricate dogfood or human-evaluation evidence.
The live repository, schema, and tracked review snapshot are authoritative.

## 1. OBJECTIVES

Close the demonstrated proof-integrity gaps while preserving the Phase 29
architecture:

1. enforce one reusable knowledge-time eligibility boundary for Historical Ask;
2. reconstruct historical Story, Report, Question, Gap, and Task state from
   canonical timestamps and histories, using truthful unknowns where necessary;
3. execute Full and Lite through the same frozen synthesis contract while
   preserving effective-execution verification and fail-closed behavior;
4. prove future-object, lifecycle, citation, staleness, and benchmark-route
   negative controls through executable tests; and
5. derive review artifacts from tracked repository state and remove the
   Phase 28.8/28.875 naming ambiguity.

## 2. IMPLEMENTATION PLAN

The implementation is intentionally limited to the existing temporal service,
Historical Ask retrieval path, benchmark adapters/contract verifier, semantic
fixtures, tests, review-snapshot validation, and phase documentation. No
schema migration, event-sourcing subsystem, new product surface, or Phase 30
feature is in scope.

Historical mutable state is reconstructed only from stored revisions, history,
correction, and lineage records. If those records cannot establish a value at
the requested boundary, the result must be marked unknown or unavailable rather
than populated from current state.

## 3. ACCEPTANCE GATES

The following must be green before engineering closure:

- `python -m compileall -q newsroom tests`;
- full backend pytest suite and targeted Phase 29/29.5 suites;
- `ruff check newsroom tests` and the repository's informational mypy check;
- `python -m newsroom.evals validate` and benchmark contract validation;
- frontend lint, typecheck, and production build;
- production-runner Full/Lite integration with a controlled contract-bound
  provider and explicit mismatch negative controls; and
- review snapshot generation from `git ls-files`, including tracked CI and
  excluding caches, dependencies, databases, and temporary output.

The frozen benchmark contract remains unchanged. Provider, model, temperature,
determinism, prompt version, context, retrieval, citation, question order,
snapshot identity, and effective route must remain verifiable.

## 4. SCHEMA AND REPOSITORY AUTHORITY

The Phase 29 schema remains version 36. Existing canonical timestamps,
revisions, histories, corrections, and lineage records are sufficient for this
closure; no migration is justified. `Phase 28.875.md` is the authoritative
filename for the document whose heading and content identify Phase 28.875.

Unrelated tracked deletions and untracked user artifacts are preserved. A
Phase 29.5 commit may include only the bounded implementation, tests, snapshot
validation, and authority-document corrections.

## 5. POST-CLOSURE DOGFOOD BOUNDARY

Engineering closure prepares the repository for the real Phase 29 acceptance
window. It does not supply the remaining observational evidence: an approved
subject and Source set, the dogfood window, usefulness log, frozen benchmark
snapshot, real contract-valid Full/Lite outputs, blinded scoring, the
preregistered decision rule, or the intelligence-value verdict. Phase 30
remains blocked until those conditions are actually satisfied.

## 6. COMPLETION RULE

Phase 29.5 passes only when Historical Ask is knowledge-time bounded, temporal
negative controls pass, Full/Lite effective conditions are genuinely comparable
and fail closed on mismatch, review artifacts are authoritative, and the full
engineering validation matrix is reported command-by-command.
