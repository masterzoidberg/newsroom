# Phase 16 — Windows Deployment and Final Acceptance

## Objective

Deploy the accepted mature product privately on Windows and prove the complete
intelligence loop in the production environment.

## Required work

- Build from a clean accepted commit and install under explicit production
  runtime paths outside the repository.
- Configure bounded auto-start/restart for API, worker, and scheduler.
- Serve API and PWA same-origin and expose privately through Tailscale with
  application authentication enabled.
- Configure production secrets, backups, retention, logging, health checks,
  browser notifications, and recovery procedures.
- Verify desktop, laptop, phone, tablet, PWA install/update, restart recovery,
  provider outage, budget exhaustion, backup/restore, and local-only operation.
- Run the canonical intelligence loop from Monitor creation through evidence,
  Story/report update, gap detection, follow-up, alert, and Ask Newsroom.

## Release acceptance thresholds

- Clean checkout passes all tests, type checks, lint, builds, migrations, and
  integrity checks.
- Accepted corpus has zero unsupported synthesized propositions and zero false
  merges, citation correctness at least 0.95, and important-Claim recall at least
  0.85.
- Restart/power-loss, paid-budget, provider-outage, auth, backup/restore, scale,
  private mobile access, and PWA notification tests pass.
- Release source commit, installed build identity, operations runbook, and known
  limitations are recorded.
- Run `PHASE_16_REVIEW.md`; deployment is complete only after approval.

## Completion Record

Local implementation and clean-room Windows deployment rehearsal completed
2026-08-17. Added deterministic release identity and installed-artifact
verification, explicit production process entrypoints, bounded Task Scheduler
configuration, opt-in private Tailscale Serve configuration, deployment/recovery
runbook updates, and Phase 16 acceptance tests. The rehearsal applied migrations
1–13, passed integrity, served the same-origin API/PWA, and completed verified
backup/export/restore checks outside the repository.

Final production approval remains pending as recorded in
`docs/reviews/PHASE_16_REVIEW.md`: the current checkout is dirty, no persistent
Windows tasks or Tailscale configuration were activated, and the target-device
acceptance matrix plus standalone citation/important-Claim corpus metrics still
require operator execution. The deployment script intentionally refuses to
promote a dirty worktree.
