# Phase 04 — Evidence Ledger Vertical Slice

## Objective

Prove the signature evidence-first path through a manually triggered run.

## Required work

- Ingest a frozen fixture into Source, Document, and immutable DocumentVersion.
- Resolve it conservatively into a new or existing Story.
- Create atomic Claims, exact Evidence Spans, Claim-Evidence links, Claim state
  history, contradictions, and supersession.
- Make accepted Claim text immutable; corrections create superseding Claims.
- Generate Story Revisions only from accepted Claims and persist the exact
  Claim-set hash.
- Add a post-synthesis audit that rejects unsupported propositions.
- Expose manual-run APIs and a minimal Evidence inspection view.

## Boundaries

No durable scheduler, broad source acquisition, adaptive monitoring, or provider
marketplace. Deterministic test providers are sufficient here.

## Verification and exit gate

- End-to-end fixture tests cover the complete evidence chain.
- Citation correctness is at least 0.95 on applicable fixtures.
- Unsupported proposition rate and false merges are zero on the accepted corpus.
- Evidence and revision provenance remain inspectable after restart.
- Full project checks pass, then run `PHASE_04_REVIEW.md`.

## Completion Record

Completed 2026-08-16.

### Delivered

- Added migration 0003 with persistent `story_revision_claims` provenance and
  SQLite append-only protections for DocumentVersions, Evidence Spans, Claims,
  Claim history, Claim-Evidence links, and Story Revisions.
- Implemented the manual offline vertical slice through Source, Document,
  DocumentVersion, EvidenceSpan, Claim, Claim-Evidence, Claim state history,
  contradiction, supersession, accepted Claim immutability, and revision
  Claim-set hashing.
- Added closed-world revision auditing. Revisions require accepted
  `supported`/`partially_supported` Claims and structured citations; unknown,
  pending, disputed, unsubstantiated, or superseded citations are rejected
  before insertion.
- Added authenticated manual-run, evidence-ledger, state, acceptance, and
  inspection APIs plus a minimal read-only React Evidence view.
- Updated the Phase 03 revision test and migration-forward expectations for the
  evidence-bound revision contract.

### Verification

- `python -m pytest -q` — passed.
- `python -m compileall -q newsroom` — passed.
- `npm run typecheck` — passed.
- `npm run build` — passed.
- `npm audit --audit-level=high` — 0 vulnerabilities.
- Playwright smoke path — passed; empty/error Evidence states rendered with no
  browser page errors and the screenshot was visually inspected.
- `poetry run format/test` and `pnpm format/lint/types` are unavailable for
  this setuptools/npm-script surface; the available canonical checks above
  pass.

### Review

- Required review: [docs/reviews/PHASE_04_REVIEW.md](../../docs/reviews/PHASE_04_REVIEW.md)
- Verdict: Approved; no Critical or Required findings remain.
- Accepted implementation commit: `eef6466` (includes `ce12eac`).
