# Phase 06 — Source Discovery and Acquisition

## Objective

Discover and retrieve useful material cheaply while preserving provenance and
avoiding repeated processing.

## Required work

- Implement RSS/Atom discovery and polling, conditional HTTP, canonical URL
  handling, normalized hashes, and bounded safe HTML extraction.
- Maintain multidimensional Source Profiles: type, coverage, acquisition method,
  activity, failures, duplication behavior, and historical usefulness.
- Produce user-reviewed Source suggestions with relevance rationale, likely
  contribution, limitations, and supported monitoring mechanism.
- Persist acquisition provenance and only permitted metadata, hashes, and exact
  evidence excerpts.
- Add domain allow/deny controls, response-size limits, timeouts, and safe parser
  behavior for malformed or hostile content.

## Boundaries

No browser-rendered scraping by default, open-ended crawling, universal trust
score, or automatic approval of suggested Sources.

## Verification and exit gate

- Offline RSS/Atom/HTML fixtures cover normal, malformed, oversized, redirected,
  unchanged, and changed content.
- Unchanged material is not reprocessed; changes create DocumentVersions.
- Failures are bounded, observable, and never corrupt existing evidence.
- Full project checks pass.

## Completion Record

Completed 2026-08-16.

### Delivered

- Added migration 0005 with append-only `acquisition_events`, multidimensional
  `source_profiles`, and explicitly reviewable `source_suggestions` tables.
- Added bounded RSS/Atom parsing with canonical link normalization, malformed /
  hostile XML rejection, feed metadata versioning, conditional polling, and
  deterministic raw/normalized content hashes.
- Added replaceable standard-library HTTP transport with conditional headers,
  bounded redirects, domain allow/deny policy, literal private/loopback/local
  host blocking, response-size and timeout limits, and no browser JavaScript.
- Added safe bounded HTML extraction that drops active/embedded content and
  persists only metadata, hashes, and provenance; article bodies are not stored
  in normalized document metadata.
- Added changed-versus-unchanged `DocumentVersion` behavior, failure/blocked
  provenance, source profile counters, and authenticated API routes for manual
  acquisition, feed polling, profile reads, suggestion creation, and explicit
  suggestion review. Suggestion review never creates a Source automatically.
- Added ADR-004, API/architecture/decision-log documentation, and focused
  offline fixtures for normal, malformed, oversized, redirected, unchanged,
  changed, failed, and reviewed-source behavior.

### Verification

- `python -m pytest -q` — passed (229 tests).
- `python -m pytest -q tests/test_phase06_acquisition.py tests/test_phase02_foundation.py` — passed (20 tests).
- `python -m compileall -q newsroom` — passed.
- `python -m newsroom.evals validate` — passed (30 cases).
- `python -m newsroom.evals replay multi-outlet-hermes-v0200` — passed with the existing deterministic replay hash.
- `python -m newsroom.ai_benchmark` — passed; output matches the committed Phase 05 benchmark artifact.
- `npm run typecheck` and `npm run build` from `frontend/` — passed.
- `npm audit --audit-level=high` from `frontend/` — passed; 0 vulnerabilities.
- `git diff --check` — passed.
- `poetry run format` / `poetry run test` — unavailable for this setuptools project; the canonical Python checks above pass.

### Review

- Five-axis review completed for correctness, readability, architecture,
  security, and performance; no Critical or Required findings remain.
- Security review added literal private/loopback/local host rejection and
  redirect-time policy checks before the HTTP transport follows a redirect.
- Accepted implementation commit:
  `0f2e7fbf5254587b81eb6c80c01849d9db4258d8`.

### Limitations

- Acquisition is manually invoked in this phase; durable scheduling, leases,
  retries/backoff, and cost-aware job execution remain Phase 07 work.
- The default transport intentionally does not execute JavaScript or perform
  browser-rendered scraping, and open-ended crawling is not implemented.
- HTML extraction is bounded lexical text, not a semantic article extractor;
  exact evidence excerpts still require deliberate Evidence Ledger selection.
- Source profiles remain observational dimensions and do not claim a universal
  source-trust score.
