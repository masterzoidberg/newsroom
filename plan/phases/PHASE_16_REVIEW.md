# Phase 16 Review — Mature Product Release Acceptance

## Scope

Independently review Phases 13-16 and perform a final cross-product audit of all
accepted phases and the deployed Windows environment.

## Required logical review areas

### Search, comparison, and diagnostics

- Test query injection/escaping, authorization, stale indexes, ranking stability,
  pagination, update/deletion behavior, scale, and semantic fallback.
- Verify comparison, historical context, coverage, and health statements derive
  from stored evidence and operational facts.

### Ask Newsroom safety and provenance

- Attack with prompt injection, malicious evidence text, unsupported questions,
  conflicting evidence, scope crossover, citation spoofing, oversized context,
  cancellation, and exhausted budgets.
- Confirm every factual answer citation resolves and uncertainty is explicit.

### Security, privacy, recovery, and performance

- Recheck authentication/session/CSRF/XSS/SSRF/injection boundaries, secrets,
  logs, exports, notifications, provider adapters, filesystem paths, and service
  privileges.
- Review dependency vulnerabilities/licenses and verify no unnecessary runtime
  service or network exposure.
- Rehearse backup restoration, integrity failure, upgrade, worker crash, power
  loss, provider outage, and local-only recovery.
- Validate representative database, queue, search, API, UI, and memory behavior.

### Deployment and full intelligence loop

- Verify installed artifacts correspond exactly to the recorded clean commit.
- Test same-origin API/PWA, Tailscale privacy, desktop/mobile access, PWA update,
  browser notification permissions, service restart bounds, and operator docs.
- Execute the canonical loop and audit each transition from Monitor scope through
  acquisition, Evidence Ledger, Story/report update, gap follow-up, alert, and
  evidence-grounded conversation.

### Regression and release evidence

- Run all backend/frontend/unit/integration/end-to-end/security/performance tests,
  corpus validation, baseline, migrations, integrity, and backup/restore.
- Confirm the release thresholds in Phase 16 and all earlier review gates remain
  satisfied; inspect residual TODOs, dead code, disabled tests, and dirty files.

## Verdict rule

Write `docs/reviews/PHASE_16_REVIEW.md` with severity-ranked findings, commands,
results, acceptance metrics, deployed build identity, and residual risks. Fix all
Critical and Required findings and rerun affected plus full verification. Approve
only when the mature product and deployed environment satisfy every release gate.
Record the final accepted commit; do not push automatically.
