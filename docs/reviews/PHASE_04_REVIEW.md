# Phase 04 Review — Evaluation Through Evidence Ledger

## Verdict

**Approved.** No Critical or Required findings remain. Phase 05 is not started.

Reviewed commits:

- `f3213df` — Phase 01 evaluation foundation
- `825d8de` — Phase 02 foundation and schema
- `70e56d3` — Phase 03 core domain and authentication
- `17bd795` — Phase 04 evidence-ledger backend
- `9976178` — Phase 04 Evidence inspection view
- `ce12eac` — Phase 04 closed-world bypass fix and API documentation

## Findings

### Optional / non-blocking

1. The repository uses setuptools metadata in `pyproject.toml`, not Poetry
   scripts. `poetry run format` and `poetry run test` therefore cannot execute
   the configured checks. The available canonical `python -m pytest -q` suite
   passes.
2. The frontend package defines `typecheck` and `build`, but not the skill
   aliases `pnpm format`, `pnpm lint`, or `pnpm types`. `npm run typecheck` and
   `npm run build` pass; `npm audit --audit-level=high` reports zero findings.
3. The test client emits an existing HTTPX deprecation warning about the
   Starlette `app` shortcut. It does not affect the Phase 04 behavior and is
   outside this phase's dependency scope.

## Logical review

### Evaluation integrity

- Phase 01 evaluation tests remain green, including malformed/empty/negative
  prediction validation, deterministic replay/baseline behavior, coverage
  metrics, Claim state semantics, evidence/citation scoring, and closed-world
  scoring.
- The Phase 04 manual fixture uses deterministic IDs only for the persisted
  chain; no network, scheduler, discovery, provider marketplace, or adaptive
  work is introduced.

### Persistence and architecture

- Migration 0003 adds `story_revision_claims` with foreign keys, unique Claim
  positions, and append-only triggers for DocumentVersions, Evidence Spans,
  Claim histories, Claim-Evidence links, Story Revisions, and revision Claim
  sets.
- Accepted Claim proposition edits fail at SQLite level; corrections use a new
  Claim with `supersedes_claim_id` and a superseded state-history row.
- Existing WAL, foreign-key, transaction, online-backup, restore, runtime-path,
  and integrity tests remain green.
- `CoreService.create_story_revision()` delegates to the evidence-bound service,
  so the old service entry point cannot bypass the closed-world audit.

### API and authentication

- All new ledger reads require the authenticated session; all writes require
  the existing CSRF double-submit check.
- Pydantic boundary models bound excerpts, locators, Claim sets, citations,
  fixture arrays, URLs, content hashes, and normalized fixture JSON.
- SQL values are parameterized. Dynamic SQL fragments are limited to internal
  table/column names or placeholder counts derived from validated input.
- Domain failures use the existing canonical error envelope and the app's
  generic exception handler does not expose tracebacks.

### Evidence invariant

`tests/test_phase04_evidence.py` verifies:

- Source → Document → immutable DocumentVersion → exact Evidence Span;
- Evidence Span hash includes excerpt and locator;
- Claim creation, support/contradiction links, state history, and distinct
  `unsubstantiated` versus `disputed` semantics;
- accepted Claim text immutability and correction through supersession;
- only accepted, supported/partially-supported Claims can ground a revision;
- unknown or pending citations reject before a revision row is inserted;
- the exact Claim set is persisted and hashed;
- evidence and revision provenance is inspectable after a fresh app instance;
- direct CoreService calls cannot bypass revision auditing;
- SQLite triggers reject direct mutation of frozen versions, spans, and accepted
  Claim text.

### Quality and verification

Completed checks:

- `python -m pytest -q` — pass;
- `python -m compileall -q newsroom` — pass;
- `npm run typecheck` — pass;
- `npm run build` — pass;
- `npm audit --audit-level=high` — 0 vulnerabilities;
- Playwright smoke test — Evidence view rendered, unauthenticated API failure
  displayed accessibly, no browser page errors, screenshot visually checked.

## Accepted evidence

The Phase 04 vertical slice meets its exit gate for the deterministic accepted
fixture corpus. Citation correctness is represented by required structured
Claim citations; unsupported proposition rate is zero for accepted revisions;
false merge behavior is conservative because the manual run accepts an
explicit existing Story or creates a new one and performs no automatic merge.
