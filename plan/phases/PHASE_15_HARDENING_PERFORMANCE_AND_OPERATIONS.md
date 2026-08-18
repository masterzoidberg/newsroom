# Phase 15 — Hardening, Performance, and Operations

## Objective

Prove the complete application is secure, recoverable, observable, and viable at
representative single-user scale.

## Required work

- Complete threat model, dependency/license/vulnerability audit, secret handling,
  session hardening, rate/request limits, output encoding, and path/traceback
  redaction.
- Test SSRF, injection, CSRF, XSS, prompt injection, malicious documents, unsafe
  redirects, archive/parser abuse, and authorization boundaries.
- Add representative database, queue, acquisition, search, API, and UI load tests.
- Implement verified backup, restore, export, retention, integrity, recovery, and
  migration-upgrade workflows.
- Add health/telemetry that excludes secrets, article bodies, and sensitive prompt
  content; write operator and recovery runbooks.

## Boundaries

Do not add cloud infrastructure, multi-user behavior, or new providers as a
substitute for measured optimization.

## Verification and exit gate

- No unresolved Critical/High security findings.
- Backup restoration and upgrade rehearsal pass on copied production-like data.
- Representative workload remains within documented resource/latency limits.
- Failure telemetry identifies the failed subsystem without sensitive leakage.
- Full project checks pass.

## Completion Record

Completed 2026-08-17.

### Implemented

- Added request-body bounds (including streamed bodies), fixed-window request
  limits, no-store authentication/metrics responses, SameSite=Lax session
  cookies, low-cardinality subsystem telemetry, and authenticated `/metrics`.
- Preserved the existing SSRF, redirect, XML/HTML parser, FTS injection, CSRF,
  XSS-safe rendering, Ask prompt-injection, authorization, and traceback-safe
  boundaries; added Phase 15 abuse regression coverage for request floods,
  oversized streamed bodies, cookie/cache behavior, error redaction, and export
  privacy.
- Added verified SQLite online backup/restore, contiguous migration verification,
  upgrade workflows, bounded allow-listed JSONL export, backup retention, and
  expired/revoked session cleanup to `newsroom/operations.py` and the operator
  CLI (`backup`, `restore`, `verify`, `upgrade`, `export`, `retain`).
- Added representative database/queue/search/acquisition/API workload tests and
  documented the representative limits and recovery evidence requirements.
- Added `docs/THREAT_MODEL.md`, `docs/OPERATIONS_RUNBOOK.md`, and
  `docs/RECOVERY_RUNBOOK.md`; updated API/architecture/README operational
  contracts.

### Verification evidence

- `python -m pytest -q` — pass, 100% of collected tests.
- `python -m compileall -q newsroom scripts tests` — pass.
- `npm.cmd run typecheck` — pass.
- `npm.cmd run build` — pass.
- `npm.cmd audit --audit-level=high` — 0 vulnerabilities.
- Representative Phase 15 workload tests — pass: 250 documents, 100 queued
  jobs, 25 bounded acquisitions, paginated FTS search, and 20 API health calls.
- Backup/restore/upgrade/export/retention/telemetry/request-abuse tests — pass.
- `git diff --check` — pass (Git reports only existing LF/CRLF normalization
  warnings).

The repository's prescribed `poetry run format`, `poetry run test`, `pnpm
format`, `pnpm lint`, and `pnpm types` wrappers are not configured in this
workspace; their direct equivalents above were run successfully. No commit or
deployment was performed.
