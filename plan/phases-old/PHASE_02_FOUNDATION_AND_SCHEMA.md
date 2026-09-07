# Phase 02 — Foundation and Schema

## Objective

Create the minimum standalone application shell and immutable first migration.

## Fixed schema decisions

- Enforce polymorphic Monitor/Research Question references in transactional
  application services plus an integrity checker.
- Keep provider names as metadata text in migration 0001.
- Keep one `story_review` row per Story with `last_reviewed_revision_id`.
- Hash Evidence Span excerpt plus locator type/value.
- Defer general full-article-body persistence.

## Required work

- Implement migration ledger and migration 0001 for all first-release domain
  families in `plan/PROPOSED_SCHEMA_0001.md`.
- Add repository boundaries, integrity checks, online backup/restore primitives,
  and deterministic migration commands.
- Add explicit guarded `dev`/`prod` Windows runtime configuration.
- Add FastAPI app factory, `/api/v1`, health/readiness, request IDs, structured
  errors, and structured logging.
- Create the React/TypeScript/Vite shell and serve its production build from the
  FastAPI origin.

## Boundaries

Do not implement broad CRUD, monitoring, ingestion, or AI behavior. Do not
rewrite migration 0001 after this phase is accepted.

## Verification and exit gate

- Fresh migration and idempotent rerun tests.
- FK, WAL, integrity, backup, and restore tests.
- API health tests and production frontend build/same-origin smoke test.
- Runtime/source separation test and full backend/frontend checks.

## Completion Record

Completed.

### Implemented

- Added immutable migration 0001 and the `schema_migrations` ledger for all
  first-release domain families in `plan/PROPOSED_SCHEMA_0001.md`.
- Added a small repository boundary for transactional polymorphic monitor
  writes, evidence-span hashing, SQLite integrity checks, foreign-key checks,
  and online backup/restore.
- Added explicit guarded `dev`/`prod` runtime roots under
  `%LOCALAPPDATA%\\Newsroom\\{dev,prod}` and environment-scoped operator
  commands for migration, status, integrity, backup, and restore.
- Added the FastAPI app factory, `/api/v1/health`, `/api/v1/readiness`, request
  IDs, canonical structured errors, JSON request logging, and same-origin
  static serving.
- Added the React/TypeScript/Vite foundation shell with a production build
  served by FastAPI.

### Verification

- `python -m pytest -q`: 189 passed.
- Fresh migration and idempotent rerun, FK/WAL, integrity, polymorphic
  reference, backup/restore, runtime separation, API, request ID, structured
  logging, and same-origin serving tests pass.
- `npm run typecheck` and `npm run build` pass.
- `npm audit`: 0 vulnerabilities.
- Actual `frontend/dist` smoke test returns HTML from `/` and keeps
  `/api/v1/health` available from the same FastAPI origin.
- `poetry run format` / `poetry run test` and the prescribed `pnpm format` /
  `pnpm lint` / `pnpm types` commands are not available in this bootstrap
  because those scripts are not defined; direct pytest/npm checks above are
  the available equivalents.

### Scope and residual risk

Broad CRUD, authentication behavior, monitoring, ingestion, AI behavior,
workers, and production Windows service installation remain intentionally out
of scope for this phase. The generated frontend `dist` and `node_modules`
remain ignored and are not runtime source data.

Checkpoint commit: the Git commit containing this completion record.

## Post-Audit Status — 2026-08-18

The storage, migration, integrity, and runtime-root work remains valid. The
historical acceptance record predates migration 0014; the current schema is
version 14. Migration/version reconciliation, checksum enforcement review, and
active-job indexing are Phase 17 and Phase 28 concerns.
