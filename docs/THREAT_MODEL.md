# Newsroom Threat Model — Phase 15

## Scope and assumptions

Newsroom is a single-user Windows application. The trusted operator controls
the machine, the explicit runtime root, and the process environment. The
browser, remote private-network client, fetched web content, feed/XML/HTML
documents, provider output, query strings, and all request bodies are
untrusted. Production remote access is expected to remain private and HTTPS
protected by the deployment layer.

## Assets and trust boundaries

| Asset | Boundary | Required protection |
| --- | --- | --- |
| Password and session state | Browser/API/SQLite | Argon2id, hashed session IDs, HTTP-only session cookie, CSRF, expiry, login throttle |
| Evidence identity and provenance | API/domain/SQLite | Authenticated mutations, parameterized SQL, immutable ledger triggers, integrity checks |
| Fetched URLs and documents | Network/acquisition/parser | HTTP(S) allow policy, DNS re-check, private-address rejection, redirect/byte/time bounds, no JavaScript |
| Ask prompts and answers | Browser/API/SQLite/logs/exports | Length/context/cost bounds, closed-world retrieval, no raw prompt persistence, no prompt/body telemetry or export |
| Runtime database and backups | Process/filesystem/operator | Explicit dev/prod roots, online backup, atomic restore, verification, retention, no repository writes |
| Operational telemetry | API/logs | Low-cardinality counters only; no query/body/path IDs, secrets, article text, or prompt content |

## Threat controls and evidence

| Threat | Control | Regression evidence |
| --- | --- | --- |
| SQL/FTS injection | Parameterized values; literal-token FTS query construction | `tests/test_phase13_workbench.py`, `tests/test_phase15_hardening_operations.py` |
| SSRF and unsafe redirect | URL scheme/domain policy, DNS resolution re-check, private/link-local/reserved rejection, bounded redirects | `tests/test_phase06_acquisition.py` |
| XML entity/parser abuse | Rejects DOCTYPE/entity declarations; feed size and entry bounds; SafeHTMLExtractor ignores active tags | `tests/test_phase06_acquisition.py` |
| XSS and malicious evidence | React text rendering; no `dangerouslySetInnerHTML`; bounded parser text; exact evidence citations | `tests/test_phase14_frontend.py`, `tests/test_phase06_acquisition.py` |
| CSRF/session theft | CSRF cookie/header match, SameSite=Lax, HTTP-only session cookie, Secure in prod, 24-hour expiry, revocation | `tests/test_phase03_auth.py`, `tests/test_phase14_ask.py`, `tests/test_phase15_hardening_operations.py` |
| Brute force/request flood | Persisted login throttle plus process-local fixed-window request limiter and request-size bound | `tests/test_phase03_auth.py`, `tests/test_phase15_hardening_operations.py` |
| Prompt injection/scope crossover | Closed-world Ask retrieval, scope membership checks, refusal/qualification, raw prompt omission | `tests/test_phase14_ask.py` |
| Traceback/path/secret leakage | Safe validation errors, generic 500 envelope, path-without-query request logs, privacy telemetry and allow-listed export | `tests/test_api.py`, `tests/test_phase15_hardening_operations.py` |
| Power loss/worker crash | WAL, online backups, atomic restore, durable leases, bounded retry/backoff, migration ledger | `tests/test_phase02_foundation.py`, `tests/test_phase07_jobs.py`, `tests/test_phase15_hardening_operations.py` |

## Dependency and license audit

The runtime dependency set is intentionally small: `argon2-cffi`, FastAPI, and
Uvicorn from `pyproject.toml`; the frontend uses React, React DOM, TypeScript,
and Vite from `frontend/package.json`. The current local environment audit on
2026-08-17 reported:

| Package | Version observed | License evidence |
| --- | --- | --- |
| argon2-cffi | 25.1.0 | MIT license expression in installed metadata |
| fastapi | 0.104.1 | MIT classifier in installed metadata |
| uvicorn | 0.24.0 | BSD classifier in installed metadata |
| pytest (dev) | 7.4.3 | MIT classifier in installed metadata |
| httpx (dev) | 0.27.2 | BSD classifier in installed metadata |
| frontend lockfile | repository-pinned | `npm audit --audit-level=high` is the vulnerability gate |

The project adds no runtime dependency for rate limiting, metrics, export, or
backup. Re-run the commands in the operations runbook after dependency changes;
do not approve a Critical/High advisory or an unreviewed license change.

## Residual risks and explicit boundaries

- The in-memory request limiter is process-local by design; multi-process or
  multi-user deployment is outside this phase and would require a measured
  shared limiter.
- The application cannot make an untrusted external site safe beyond refusing
  private destinations, bounding transport/parser work, and storing only
  bounded metadata; operators must still review source provenance.
- Windows service identity, filesystem ACLs, HTTPS/private-network exposure,
  and restart policy are deployment responsibilities covered by Phase 16.
- No automatic provider or subprocess execution is introduced by hardening;
  paid routing remains explicit and budgeted.
