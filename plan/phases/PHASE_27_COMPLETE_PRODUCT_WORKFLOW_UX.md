# Phase 27 — Complete Product Workflow UX

## Objective

Make Newsroom fully operable without raw database IDs or manual API calls.

## Why this phase exists

The current React shell and review views are real, but setup and operational
workflows still rely on raw IDs, API-only actions, or incomplete screens.

## Current-state gap

Topics, Subjects, and Sources are listed but not fully created/edited in the UI;
Monitors accept raw target IDs; Questions lack pursuit/inspection controls; and
analysis, smart tags, and failure repair are not exposed as a complete flow.

## Scope

- Create/edit Topic, Subject, and Source.
- Review/approve Source suggestions and configure approved Sources.
- Configure Policies and Monitors with canonical target pickers that only offer
  executable targets.
- Inspect acquisition, analysis, Evidence, Claims, Story evolution, Reports,
  alerts, provenance, and processing failures.
- Create, pursue, inspect, resolve, abandon, and reopen Research Questions.
- Review vocabulary and smart tags.
- Configure alerts and diagnose/repair failed work.

## Non-goals

- Do not add UX for backend workflows that Phases 17–26 have not stabilized.
- No client-side authority over relevance, evidence, materiality, budgets, or
  publication state.
- No replacement of server-side authorization or validation.

## Existing components to reuse

React shell, `api.ts`, existing views/components, authenticated API routes,
Workbench, Document/Story Evidence views, Runs/Jobs, Reports, Alerts, PWA shell,
and server-side domain contracts.

## Required implementation

Replace raw-ID entry where a canonical collection exists with searchable
pickers. Add empty/loading/error/stale/offline states for every new workflow.
Expose server statuses and provenance without duplicating domain decisions in
the browser.

## Data model/migration expectations

No migration is expected. Add API fields only where the stabilized Phase 17–26
contracts require displayable provenance or workflow state.

## Runtime integration

The UI calls existing authenticated APIs and observes durable state. It must
not invoke AI, discovery, acquisition, or report logic directly in the browser.

## Security/privacy considerations

Respect CSRF, authorization, safe rendering, sensitive-field redaction, and
notification privacy. Do not put secrets or raw provider prompts in client
state.

## Tests

- Authenticated browser flows for setup, monitoring, inspection, Questions,
  Reports, Alerts, Search, Ask, tags, and diagnostics.
- Keyboard, responsive, offline-shell, stale-data, and error-state coverage.
- No raw-ID requirement remains in the primary workflow.
- Frontend typecheck/build and browser smoke pass.

## Acceptance criteria

A user can configure an information need, approve Sources, configure a valid
Monitor, inspect a changed version through Evidence/Story/Report/Alert, pursue a
Question, review tags, and diagnose failures without manual API calls.

## Live-test gate

Run the browser UX against the Phase 23 controlled end-to-end fixture before
real public-source production tests.

## Dependencies

Phases 17–26, especially stabilized API/state contracts from Phases 20, 23,
24, 25, and 26.

## Exit criteria

The complete supported Newsroom workflow is operable in the authenticated UI,
with canonical pickers and server-authoritative provenance/status.
