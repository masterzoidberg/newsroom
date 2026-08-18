# Phase 03 — Core Domain and Authentication

## Objective

Expose secure, consistent application services for the core user-managed domain.

## Required work

- Implement service/repository/API paths for Categories, Topics, Concept
  Vocabulary, Subjects, Sources, Documents, Stories, tags, and settings.
- Preserve stable slugs, soft deletion, aliases, acronyms, related concepts,
  exclusions, and explicit approval of AI-suggested scope changes.
- Implement single-user setup, Argon2id password hashing, HTTP-only sessions,
  CSRF protection, login throttling, logout/revocation, and security headers.
- Standardize pagination, filters, deterministic ordering, PATCH omitted/null
  semantics, validation errors, and transaction boundaries.

## Boundaries

Do not build automated discovery, monitoring, Evidence Ledger generation, or
the mature frontend. Use minimal administration surfaces or API tests.

## Verification and exit gate

- CRUD, authorization, pagination, slug, soft-delete, and transaction tests.
- Unauthorized/CSRF-invalid mutations fail without changing state.
- No secrets or password material appear in logs, exports, or API responses.
- Full backend/frontend checks pass.

## Completion Record

Completed.

### Implemented

- Added forward migration 0002 without rewriting migration 0001. It adds
  session CSRF hashes, persistent login-throttle state, concept-kind metadata,
  and auditable topic scope suggestions.
- Added single-user setup and authentication with explicit Argon2id hashing,
  opaque hashed session identifiers, HTTP-only SameSite cookies, CSRF tokens,
  login throttling, session expiry checks, and logout revocation.
- Added security headers, production HSTS, safe validation errors, dummy-hash
  login verification, and logging that excludes submitted password material.
- Added transactional services and validated API paths for Categories, Topics,
  Concept Vocabulary, scope-suggestion approval, Subjects, Sources, Documents,
  Stories/revisions, tags, story-tag relationships, and settings.
- Added stable create-only slugs, soft deletion, deterministic pagination and
  filtering, authenticated reads/mutations, explicit CSRF mutation checks,
  omitted-versus-null PATCH semantics, canonical URL storage, and transaction
  rollback coverage.
- Documented the Phase 03 API contract in `docs/API.md`.

### Verification

- `python -m pytest -q`: 202 passed.
- Fresh and forward migration tests, CRUD, authorization, CSRF, throttling,
  revocation, security-header, pagination, filtering, stable-slug, soft-delete,
  PATCH null semantics, approval, relationship, canonical URL, revision, and
  transaction-boundary tests pass.
- `python -m compileall -q newsroom tests` and `git diff --check` pass.
- `npm run typecheck` and `npm run build` pass.
- `npm audit`: 0 vulnerabilities.
- The prescribed `poetry run format` / `poetry run test` and `pnpm format` /
  `pnpm lint` / `pnpm types` commands are not available in this bootstrap
  because those scripts are not defined; direct pytest/npm checks above are
  the available equivalents.

### Scope and residual risk

Automated discovery, monitoring, ingestion, Evidence Ledger generation,
authorization roles beyond the single local user, password recovery, and the
mature frontend remain intentionally out of scope. Production deployment still
requires HTTPS/private ingress configuration before relying on `Secure` cookies.

Checkpoint commit: the Git commit containing this completion record.

## Post-Audit Status — 2026-08-18

The backend domain and authentication implementation remains valid. Its scope
did not include a complete product workflow UI, semantic automation, or final
deployment acceptance. Those later capabilities remain governed by Phases 20,
23, 27, and 28.
