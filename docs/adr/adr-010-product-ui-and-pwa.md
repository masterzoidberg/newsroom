# ADR-010 — Product UI and same-origin PWA

## Status

Accepted — Phase 12.

## Context

The evidence-first backend has durable Stories, Documents, Claims, Evidence
Spans, Monitors, Research Questions, Jobs, Reports, Briefings, and Alerts, but
reviewers and operators need one usable workspace across desktop, tablet, and
phone. The UI must not become a second source of truth, hide provenance behind
desktop-only affordances, or treat browser notification permission as durable
delivery.

## Decision

Build a React workspace served by FastAPI from the same origin as `/api/v1`.
Use hash routes for the required review, configuration, and operations views so
links remain reloadable without adding a client-side routing dependency. Keep
all resource mutations on the authenticated canonical API with the existing
CSRF contract. Render exact evidence, source locators, contradictions,
revisions, timelines, lineage, report causes, alert delivery state, loading,
empty, error, permission, stale/attention, and offline states explicitly.

Ship a standalone PWA manifest and a service worker that caches the entry shell
and successful same-origin static assets while bypassing `/api/` requests. The
worker may preserve the application UI offline, but the UI must label the
connection state and never imply cached domain responses are live authority.
Browser notification permission is opt-in; durable in-app alerts remain the
authoritative fallback.

## Consequences

- Reviewers get one responsive surface for evidence inspection and attention
  management, with keyboard-visible focus and semantic navigation.
- Operators can create bounded Monitors, review Source suggestions, manage
  Questions, inspect Runs/Jobs, and control notification/budget state without
  client-side domain logic.
- Same-origin deployment avoids a production CORS dependency and keeps the
  service worker scope straightforward.
- Hash routing is intentionally small and sufficient for this local product;
  a larger routing dependency is deferred until route-level requirements make
  it necessary.
- Offline behavior is limited to the cached shell and static assets. API data
  remains unavailable or explicitly stale until connectivity returns.

## Rejected alternatives

- **Client-only state machine:** rejected because it would duplicate domain
  rules and risk presenting state the API does not accept.
- **Separate frontend origin:** rejected because it adds deployment and CORS
  complexity for a private local-first service.
- **Browser notifications as the alert store:** rejected because permission,
  browser support, and connectivity are not durable product state.
