# Phase 12 Review — Product UI and PWA

## Verdict

**Approved.** No Critical or Required findings remain.

Reviewed range:

- Phase 09 Story evolution, lineage, novelty, and review state;
- Phase 10 Research Questions and evidence gaps;
- Phase 11 Reports, Briefings, and Alerts;
- Phase 12 responsive product UI, operator surfaces, and PWA shell.

## Findings

### Required — resolved

1. **Offline shell caching initially covered only the entry document.** The
   service worker now caches successful same-origin static responses while still
   bypassing `/api/`, so an installed shell can reload its built JavaScript and
   CSS offline. The UI labels the state as “Offline · cached shell only” and
   does not treat API failure as authoritative cached domain data.
2. **Navigation semantics needed to remain link-based.** The sidebar now uses
   semantic anchors with `aria-current="page"`, a named primary navigation, a
   skip link, focus-visible styling, and hash deep links. The browser smoke test
   follows the same accessible contract.
3. **Saved Story review needed the API’s nested revision shape.** The view now
   renders `current_revision.headline` and `current_revision.summary` when the
   Story record provides them, while preserving the durable review state and
   `new_update` marker.

### Optional / non-blocking

1. The mobile menu intentionally overlays the workspace. A future iteration
   could add a backdrop and close-on-outside-click behavior, but the current
   menu is keyboard-focusable, exposes its expanded state, and leaves the full
   navigation reachable.
2. The local PWA manifest uses the repository SVG mark. Platform-specific icon
   rasterization can be added if distribution requirements later require
   explicit 192px/512px PNG assets.

## Logical review

### Product surfaces and evidence safety

- Inbox, Story/Evidence, Documents, Saved, History, Topics, Subjects, Sources,
  Monitors, Research Questions, Runs/Jobs, Reports, Alerts, and Settings/Cost
  are available from one authenticated shell.
- Story and Document views expose Claims, accepted/disputed state, exact spans,
  contradictions, source links, revisions, timeline events, and lineage.
- Reports render immutable revisions, causes, propositions, and evidence span
  identifiers. Alerts render acknowledgement and per-channel delivery state;
  browser permission does not remove the in-app record.
- Mutations use `apiFetch` against `/api/v1` with same-origin credentials and
  CSRF headers. The UI provides bounded form defaults but does not implement
  relevance, novelty, evidence support, budgets, or publication rules.

### Responsive and accessibility review

- Desktop and phone screenshots were captured from the authenticated product
  shell. The sidebar collapses into a mobile menu at the responsive breakpoint.
- All visible form fields have labels and stable names; navigation is semantic;
  focus-visible styles, reduced-motion behavior, skip navigation, status/error
  states, table scopes, and decorative icon hiding are present.
- Loading, empty, error, offline, permission, and stale/attention states are
  rendered as explicit product states rather than blank or silent failures.

### PWA and deployment review

- `manifest.webmanifest` requests a standalone app with a same-origin `/`
  start URL and theme metadata.
- `sw.js` caches the shell and successful static assets, bypasses API requests,
  cleans old cache versions, and falls back to `index.html` for offline
  navigation.
- FastAPI production serving and the Vite production build share one origin;
  no CORS-only production path was introduced.

## Verification

- `npm.cmd run build` from `frontend` — pass;
- `python -m pytest tests/test_phase12_frontend.py -q` — pass;
- `scripts/phase12_browser_smoke.py` through `with_server.py` — pass;
- desktop and phone screenshots — captured and visually inspected;
- full backend tests, compile/evaluation checks, and the available frontend
  check fallbacks are recorded in the completion record below.

Accepted implementation and review checkpoints are recorded in
`plan/phases/PHASE_12_PRODUCT_UI_AND_PWA.md` after the final verification run.
