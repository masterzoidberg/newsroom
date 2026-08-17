# Phase 12 — Product UI and PWA

## Objective

Deliver the complete responsive review and administration experience.

## Required work

- Build Inbox, Story/Evidence, Document Analysis, Saved, History, Topics,
  Subjects, Sources, Monitors, Research Questions, Runs/Jobs, Settings/Cost, and
  Alerts views.
- Make Claims, states, exact spans, contradictions, revisions, timelines, source
  lineage, and provenance directly inspectable.
- Add Monitor creation with vocabulary review, Source approval, schedule/budget
  configuration, and Run Now.
- Implement loading, empty, error, offline, permission, and stale-data states.
- Add installable PWA behavior, responsive phone/tablet layouts, keyboard access,
  focus management, and accessible semantics.

## Boundaries

Do not hide evidence behind desktop-only controls or add UI-only domain rules.
All mutations use the canonical API and require confirmation when destructive.

## Verification and exit gate

- Component, API-contract, end-to-end, keyboard, responsive, offline, and PWA
  installation tests.
- Manual screenshots for core desktop and phone workflows.
- Production build is served same-origin with no CORS dependency.
- Full project checks pass, then run `PHASE_12_REVIEW.md`.

## Completion Record

Completed 2026-08-16.

- Implementation checkpoint: recorded after the Phase 12 UI/PWA commit.
- Added the authenticated responsive React shell with Inbox, Story/Evidence,
  Documents, Saved, History, Reports, Alerts, Topics, Subjects, Sources,
  Monitors, Research Questions, Runs/Jobs, and Settings/Cost views.
- Added API-backed inspection for Claims, exact Evidence Spans, contradictions,
  Story revisions, timelines, source lineage, report causes, alert delivery
  state, and review attention state.
- Added bounded Monitor creation with policy defaults, Source suggestion
  approval/rejection, Run Now, Research Question creation, report generation,
  alert acknowledgement, browser notification preferences, and budget/settings
  inspection.
- Added explicit loading, empty, error, offline, permission, and stale/update
  states; semantic navigation, skip navigation, focus management, responsive
  phone/tablet layouts, reduced-motion handling, and installable same-origin PWA
  manifest/service-worker behavior.
- Added `tests/test_phase12_frontend.py`, `scripts/phase12_server.py`, and
  `scripts/phase12_browser_smoke.py` for production build, PWA contract,
  authenticated navigation, responsive, offline, and console-error coverage.
- Verification: frontend build and focused frontend test pass; browser smoke
  pass with desktop/phone screenshots; full backend checks and final review
  are recorded in `docs/reviews/PHASE_12_REVIEW.md`.
