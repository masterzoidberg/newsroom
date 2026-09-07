# Phase 11 — Reports, Briefings, and Alerts

## Objective

Deliver importance-ranked changes instead of an article-volume firehose.

## Required work

- Implement versioned Living Reports tied to exact accepted Claim sets.
- Generate current status, What Changed, active Stories, evidence strength,
  contradictions, unresolved Questions, and recommended investigation sections.
- Explain which evidence caused each material report change.
- Add daily/weekly briefings across Monitors and importance ranking based on new
  primary evidence, contradiction, correction, corroboration, and material state.
- Add durable in-app alerts and opt-in browser/PWA notifications with user rules,
  deduplication, acknowledgement, and delivery status.

## Boundaries

No email/SMS, public publishing, or alert on raw keyword/article volume. Generated
prose remains subject to the closed-world audit.

## Verification and exit gate

- Duplicate/repeated information does not trigger material alerts.
- Every report proposition and change explanation resolves to accepted evidence.
- Notification denial/offline/failure degrades to durable in-app state.
- Scheduling, timezone, dedupe, and acknowledgement tests pass with full checks.

## Completion Record

Completed 2026-08-16.

- Implementation checkpoint: `a90201e` (`Complete Phase 11 reports briefings and alerts`).
- Added migration 0010 for immutable Living Report revisions and evidence
  causes, timezone-aware Briefings, alert rules, durable alerts and deliveries,
  and browser notification preferences.
- Added authenticated APIs for report generation, briefing generation, alert
  rules, alert acknowledgement/delivery state, and notification preferences.
- Report generation is closed-world: propositions use the exact accepted Claim
  set, every material cause resolves to supporting Evidence Span provenance, and
  unsupported content is rejected transactionally. Repeat generation and
  repeat delivery are deduplicated.
- Added daily/weekly Monitor briefing ranking from material evidence changes,
  contradictions, corrections, corroboration, and material Story updates.
- Added durable in-app alert fallback for browser permission denial and offline
  delivery, plus acknowledgement and delivery-state transitions.
- Added focused Phase 11 tests covering immutable revisions, evidence causes,
  repeated-information suppression, timezone/dedupe behavior, browser fallback,
  and API authentication/CSRF.
- Verification: `python -m compileall -q newsroom`; `python -m pytest -q`
  (270 passed); `python -m newsroom.evals validate`; `git diff --check`.
- `poetry run format` and `poetry run test` remain unavailable because the
  repository's Poetry commands are misconfigured; direct checks above pass.

## Post-Audit Status — 2026-08-18

Living Reports, briefings, durable in-app alerts, deduplication, and delivery
state remain implemented for existing evidence. Report generation and alert
emission are manually/API triggered; monitored changes do not automatically
create report revisions or alerts. Browser delivery currently stops at a
database delivery state and does not emit a browser notification. Automation is
Phase 23 work; real browser delivery is Phase 28 work.
