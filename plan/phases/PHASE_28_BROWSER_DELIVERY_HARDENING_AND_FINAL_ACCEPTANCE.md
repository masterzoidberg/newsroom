# Phase 28 — Browser Delivery, Hardening, and Final Live Acceptance

## Objective

Finish real user notification delivery and prove the complete Newsroom product
is secure, recoverable, deployable, and viable for unattended operation.

## Why this phase exists

The current service worker handles install/activate/fetch only, browser alert
delivery stops at a pending row, and Phase 16 deployment is a rehearsal rather
than final acceptance.

## Current-state gap

No Notification API/Push API emission, service-worker notification event
handling, device acceptance, multi-day run, live provider acceptance, or final
Source-to-Report release gate has been completed.

## Scope

- Implement Notification API and/or Push API delivery.
- Add service-worker push and notification-click handling.
- Reconcile permission, online/offline, pending, sent, failed, and retry states.
- Run real browser/device acceptance.
- Complete DNS rebinding mitigation if not completed in Phase 24.
- Decide and implement migration checksum enforcement.
- Add active-monitor job composite index and expanded polymorphic integrity
  checks where justified by query/verification evidence.
- Verify provider timeout/thread/resource behavior.
- Complete Windows scheduled tasks, private Tailscale deployment, clean release,
  backup/restore, and recovery acceptance.
- Run scored citation/important-Claim acceptance metrics and multi-day runtime.

## Non-goals

- No new product domain capability.
- No public Tailscale Funnel or broad network exposure.
- No release from a dirty worktree.

## Existing components to reuse

`frontend/public/sw.js`, notification preference/delivery tables,
`reports.py`, release tooling, runtime entrypoints, deployment script,
operations/recovery runbooks, backup/restore, telemetry, and all prior phase
acceptance fixtures.

## Required implementation

Make browser delivery an actual observable operation from Alert creation through
browser emission and acknowledgement/click handling. Reconcile delivery state
transactionally and retry only bounded failures. Complete the operator
deployment matrix and record final artifact identity and acceptance metrics.

## Data model/migration expectations

Add delivery subscription/correlation fields only if required by the chosen
Notification/Push design. Add indexes/checksum metadata only with migration,
backup/restore, and historical-data tests. Preserve alert durability when
permission is denied or a device is offline.

## Runtime integration

The end-to-end chain must be:

```text
public Source → acquisition → relevance → real AI analysis
  → verified Evidence/Claims → Story → Living Report
  → in-app alert → real browser delivery
```

Windows API, Worker, and Scheduler processes must restart within documented
bounds and preserve leases, jobs, and database integrity.

## Security/privacy considerations

Keep API loopback/private ingress, do not enable Funnel, protect notification
content, validate push subscriptions, preserve CSRF/authentication, redact
secrets, enforce SSRF and provider budgets, and verify backups before restore.

## Tests

- Real browser Notification/Push and notification-click tests.
- Permission denial/offline/retry/reconciliation tests.
- Migration upgrade/checksum/integrity tests.
- Active-job query plan and polymorphic integrity tests.
- Provider timeout/resource exhaustion tests.
- Windows task/restart/recovery tests.
- Backup/restore and clean-release tests.
- Multi-day unattended run with restart injection.
- Scored citation correctness and important-Claim recall corpus.

## Acceptance criteria

- Clean release artifact installs and verifies on the target Windows host.
- Private API/PWA access works through the approved tailnet path.
- Browser delivery reaches a real supported browser/device.
- Full public-source workflow reaches a real browser alert.
- Backup/restore, restart recovery, and multi-day unattended execution pass.
- Final quality thresholds are emitted and meet the approved release values.

## Live-test gate

This is the Final Live Test: full public-source production workflow, real
browser delivery, and multi-day unattended runtime.

## Dependencies

Phases 17–27, including Live Tests A, B, and C and the Phase 16 historical
deployment tooling.

## Exit criteria

The final independent review records an accepted clean commit, deployed
artifact identity, live-test results, quality metrics, residual risks, and an
Approved production verdict.
