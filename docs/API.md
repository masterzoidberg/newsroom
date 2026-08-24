# Phase 04 API Contract

The standalone API is rooted at `/api/v1`. Health and readiness are public;
core domain reads and mutations require the authenticated single local user.

## Authentication

- `POST /auth/setup` creates the one administrator account once.
- `POST /auth/login` verifies the Argon2id password and sets an HTTP-only
  `newsroom_session` cookie plus a readable `newsroom_csrf` cookie.
- `GET /auth/me` returns the authenticated username.
- `POST /auth/logout` requires `X-CSRF-Token` to match the CSRF cookie and
  revokes the session.
- Core mutations require the same CSRF header. Failed login attempts are
  persisted and throttled.
- Responses never include password hashes, submitted passwords, or session
  tokens.

## Core resources

The following resources have authenticated list/get/create/update/delete paths
where the underlying schema supports that operation:

`/categories`, `/topics`, `/subjects`, `/sources`, `/documents`, `/stories`,
`/tags`, and `/settings`.

Topic vocabulary is available under `/topics/{topic_id}/vocabulary`. Scope
suggestions are created under `/topics/{topic_id}/scope-suggestions` and an
AI-sourced suggestion remains `pending` until an explicit approve or reject
mutation is made.

Phase 08 also exposes `/topics/{topic_id}/vocabulary-suggestions` for typed
synonym, acronym, alias, broader, narrower, related-concept, ambiguity, and
exclusion candidates. `POST /topics/{topic_id}/scope-suggestions/assist` creates
local pending candidates from supplied context. Approval is the only operation
that can add an activating term to a topic; rejected candidates remain inert.

`GET/POST /monitoring-policies` and `GET/PATCH /monitoring-policies/{id}` manage
allowed channels, cadence bounds, backoff/retirement rules, and acquisition,
local-model, and paid budgets. `GET/POST /monitors`, `GET/PATCH /monitors/{id}`,
and the `/disable`, `/enable`, `/activity`, and `/scope-history` subroutes manage
validated Topic, Subject, Story, Source, and Research Question monitors.
`POST /relevance/evaluate` runs the local exact-term → vocabulary → entity →
concept → semantic → AI relevance cascade. All monitor mutations remain behind
session and CSRF protection, and paid routing remains disabled unless the
existing explicit budget controls allow it.

Stories create immutable seed revision 1. Later generated revisions must use
the evidence-bound `POST /stories/{story_id}/revisions` contract described
below. Tags attach through `/stories/{story_id}/tags`.

## Evidence Ledger

Document versions and evidence spans are append-only:

- `GET/POST /documents/{document_id}/versions`
- `GET /document-versions/{version_id}`
- `GET/POST /document-versions/{version_id}/evidence-spans`
- `GET /evidence-spans/{span_id}`

Claims are created under a Story and have append-only evidence/state history:

- `GET/POST /stories/{story_id}/claims`
- `GET /claims/{claim_id}`
- `POST /claims/{claim_id}/evidence`
- `POST /claims/{claim_id}/state`
- `POST /claims/{claim_id}/accept`
- `GET /claims/{claim_id}/evidence`
- `GET /stories/{story_id}/evidence`

Accepted Claims must be `supported` or `partially_supported` and have a
supporting Evidence Span. Accepted Claim proposition text cannot be edited;
corrections create a new Claim with `supersedes_claim_id`.

## Phase 28 Coverage, robustness, and analysis

Coverage uses authenticated routes under `/coverage/runs`: create a bounded
expected denominator with `POST /coverage/runs`, record each item with
`POST /coverage/runs/{id}/items/{item_key}`, and close it with
`POST /coverage/runs/{id}/complete`. `GET /coverage/runs/{id}` returns explicit
states, completeness, blocking states, and qualified-negative explanation.
`GET /stories/{id}/coverage` and `/research-questions/{id}/priorities` provide
bounded contextual views. Blind spots are generated/reviewed through
`/coverage/runs/{id}/blind-spots`, `/coverage/blind-spots`, and the review route.

`GET /documents/{id}/dependencies` and
`GET /sources/{id}/source-robustness` inspect dependency context. Stories and
Claims expose `/source-robustness` plus read-only
`/fragility/counterfactual` endpoints. Counterfactuals exclude evidence family
IDs in memory and do not mutate canonical Claim/Evidence state.

`GET /attention`, `POST /attention/refresh`, and
`POST /attention/{id}/feedback` expose the explainable Attention projection.
`GET/PUT /experience` stores the Simple/Advanced disclosure mode. Hypotheses
are created under `/research-questions/{id}/hypotheses`, linked to existing
Claims through `/hypotheses/{id}/claims/{claim_id}`, given Gaps, and reviewed
explicitly. These records are analytical/review state and are not factual
Claim/Evidence alternatives.

## Reports, briefings, and alerts

Phase 11 adds authenticated, evidence-bound output paths:

- `GET/POST /reports` lists and creates a Living Report for one Monitor, Story,
  Topic, Subject, Source, or Research Question target.
- `GET /reports/{id}` returns the current immutable revision and revision
  history. `POST /reports/{id}/generate` creates a new revision from the exact
  accepted Claim set, and `POST /reports/{id}/archive` stops generation.
- `POST /briefings/generate` creates or returns a deterministic daily or weekly
  briefing for selected Monitors. The request may provide an IANA timezone and
  an explicit UTC window; repeated requests for the same period are idempotent.
  `GET /briefings/{id}` returns ranked material report items.
- `GET/POST /alert-rules` and `PATCH /alert-rules/{id}` manage targeted or
  global rules for primary evidence, contradiction, correction, corroboration,
  and material-update events.
- `GET /alerts`, `GET /alerts/{id}`, and
  `POST /alerts/{id}/acknowledge` expose durable in-app alert state.
  `POST /alert-deliveries/{id}` records browser delivery outcomes.
- `GET/PUT /notification-preferences` stores browser opt-in, permission, and
  online state. Browser denial or offline delivery never removes the in-app
  alert.

Report propositions and change causes are derived from accepted Claims and
supporting Evidence Spans only. Revision and cause records are append-only;
raw article volume cannot create a report revision or alert.

## Product UI and PWA

Phase 12 uses the same authenticated `/api/v1` contract from a React workspace
served by FastAPI in production. The shell exposes deep-linkable hash routes for
Inbox, Story & Evidence, Documents, Reports, Saved, History, Topics, Subjects,
Sources, Monitors, Research Questions, Runs & Jobs, Alerts, and Settings & Cost.

The UI is a review surface, not a second domain layer: it reads and mutates
canonical resources through the API, sends the CSRF header for mutations, and
keeps destructive actions behind confirmation. Loading, empty, API-error,
offline, permission, and stale/attention states remain explicit. Exact Claim
evidence, Evidence Span locators, Story revisions, timelines, lineage, report
causes, alert delivery status, and durable review state are rendered without
requiring article-body storage in the browser.

`frontend/public/manifest.webmanifest` defines the installable standalone app;
`frontend/public/sw.js` caches the built shell and successful same-origin static
assets while bypassing `/api/` requests. Browser notification permission is
optional and does not replace durable in-app alerts. Production is same-origin,
so the PWA has no CORS dependency.

## Source discovery and acquisition

Phase 06 adds authenticated, manually invoked acquisition endpoints. They use
the server's bounded standard-library transport and preserve retrieval
provenance in `acquisition_events`:

- `GET /sources/{source_id}/profile` returns separate source-type, coverage,
  acquisition-method, activity, failure, duplication, and usefulness fields.
- `POST /sources/{source_id}/acquire` accepts `{ "url": "...", "channel":
  "direct_http" | "page" }` and performs one bounded conditional HTTP request.
- `POST /sources/{source_id}/feed/poll` accepts an optional `feed_url` and
  performs one bounded RSS/Atom poll. If omitted, the Source's configured feed
  URL is used.
- `GET /source-suggestions` lists pending or reviewed suggestions.
- `POST /source-suggestions` records a suggestion with rationale, likely
  contribution, limitations, and supported monitoring methods.
- `POST /source-suggestions/{suggestion_id}/review` explicitly approves or
  rejects a suggestion. Review never creates a Source automatically.

Requests are denied when the URL violates the configured domain policy or
response limits. A 304 response records `not_modified` without creating a new
DocumentVersion; a changed response creates a new immutable version, while an
unchanged body records only an `unchanged` acquisition event. The acquisition
layer stores bounded metadata and hashes, not the retrieved article body.

## Durable jobs, runs, and budgets

Phase 07 exposes the SQLite-backed queue and operator controls. Protected
mutations require the normal session and CSRF header:

- `GET/POST /jobs` lists or enqueues bounded Jobs. Payloads may include a
  `budget` object with `acquisition_units`, `local_model_units`,
  `paid_requests`, and `usd` estimates. An `idempotency_key` deduplicates
  repeated enqueue requests.
- `GET /jobs/{job_id}` returns lease state, attempt history, failure cause, and
  reservation state.
- `POST /jobs/{job_id}/cancel` requests cooperative cancellation or cancels a
  queued Job immediately.
- `POST /jobs/{job_id}/rerun` creates a fresh queued Job from terminal work.
- `GET /runs` and `GET /runs/{run_id}` return human-visible Run status and child
  Job outcomes.
- `POST /scheduler/tick` performs one persisted due-Monitor tick; the separate
  scheduler process uses the same service outside HTTP.
- `GET /provider-usage` returns attributable usage, optionally filtered by
  Job.
- `GET /budgets/limits`, `PUT /budgets/limits`, and
  `PUT /budgets/paid-enabled` expose caps and the explicit global paid-route
  switch. Paid routing is disabled by default.

Workers claim Jobs transactionally with leases; expired claims are recovered
with bounded backoff. Budget reservations are checked before dispatch, and
actual usage remains in `provider_usage` after a reservation is released.

Generated revisions require `claim_ids` and structured `propositions`, each
with one or more cited Claim IDs. The server checks that every cited Claim is
accepted, belongs to the Story, and is part of the revision Claim set. It then
stores the exact Claim IDs in `story_revision_claims` and computes
`claim_set_hash`; unsupported citations reject the revision before insertion.

## Story evolution, lineage, and novelty

Phase 09 adds authenticated endpoints for the conservative resolver and its
immutable provenance:

- `POST /story-evolution/resolve` evaluates a candidate against persisted Story
  signals without mutating state.
- `POST /story-evolution/process` resolves and records one Document observation,
  creating a new Story when ambiguity remains.
- `POST /stories/{story_id}/evolution` records an explicitly classified
  observation; `GET /stories/{story_id}/timeline` returns evolution events,
  revision links, and document lineage.
- `GET /stories/{story_id}/corroboration` reports publication count separately
  from independent source/lineage groups.
- `GET/POST /documents/{document_id}/lineage` manages citations, syndication,
  wire propagation, rewritten reporting, and common-primary-document edges.
- `GET/POST /stories/{story_id}/review` tracks the reviewed revision and exposes
  `new_update` without rewriting saved, dismissed, or not-useful state.

All mutations require the existing session and CSRF protections. Evolution
events, lineage edges, Story-document links, and revision-document links are
append-only; corrections are represented by the existing Claim supersession
chain and immutable Story revisions.

## Advanced Story Intelligence and correction workflows

Phase 27 keeps `claims.story_id` as the current membership pointer and exposes
controlled, authenticated correction APIs. Historical `story_documents` rows
remain observation provenance; current Story Documents and derived Story
Entities are resolved from current Claim/Evidence membership.

- `POST /claims/{claim_id}/reassign` moves a Claim with an expected current
  Story and a human reason.
- `POST /claims/{claim_id}/unassign` intentionally clears current Story
  membership and blocks stale automatic reassignment.
- `POST /stories/{story_id}/extract` moves selected Claims into a new active
  Story without creating split lineage.
- `POST /stories/{story_id}/merge-preview` and `/merge` preview and commit a
  canonical merge. The source remains historical and merge effects on
  Watches/Monitors are persisted.
- `GET /stories/{story_id}/split-preview` and `POST /stories/{story_id}/split`
  support explicit complete Claim groups; the source retires and children are
  linked with `split_into` lineage.
- `GET /stories/{story_id}/corrections` and `/lineage` expose bounded durable
  organizational history and canonical/split resolution.
- `GET /stories/{story_id}/duplicates`, plus `/duplicates/approve` and
  `/duplicates/dismiss`, provide bounded duplicate review. Approval delegates
  to the canonical merge path; dismissal is an append-only durable decision.
- `GET /story-intelligence/metrics` reports correction burden from durable
  membership history, correction aggregates, duplicate decisions, and the
  resolver algorithm version.

Every committed correction records one `story_corrections` aggregate, Claim
membership transitions, and any lineage/duplicate decision in the same
transaction, then queues the idempotent `story_correction_reconcile` Job.
Downstream Report, Alert, and Research Question reevaluation is best-effort and
isolated after the correction commits. Alerts are emitted through the existing
exact-cause ReportRevision path and remain deduplicated on replay.

## Research Questions and evidence gaps

Phase 10 adds authenticated Research Question lifecycle and follow-up routes:

- `GET/POST /research-questions` and `GET/PATCH /research-questions/{id}`;
- `POST /research-questions/{id}/resolve`, `/abandon`, and `/reopen`;
- `POST /research-questions/{id}/claims`, `/evidence`, `/notes`, and `/pursue`;
- `POST /research-question-attempts/{attempt_id}` records a bounded attempt
  outcome;
- `GET /stories/{story_id}/research-gaps` and
  `GET /claims/{claim_id}/research-gaps` derive suggestions from stored ledger
  state;
- `GET /research-gap-suggestions`, plus explicit review and question conversion
  routes; and
- `POST /research-questions/pursue-due` runs the bounded policy path.

Question lifecycle history and Claim/Evidence links are append-only. A Question
has separate attempt, query, local-model, and paid-cost budgets. Pursuit creates
one idempotent durable `research_question` Job with `max_attempts=1`; no route
creates a recursive or open-ended research loop. Notes with `note_type`
`hypothesis` remain user notes and cannot silently create Claims.

## Manual run

`POST /runs/manual` accepts a deterministic frozen fixture and transactionally
creates Source, Document, DocumentVersion, Claims, Evidence Spans, links, and
an optional evidence-bound revision. A caller may provide an existing
`source_id`, `document_id`, or `story_id`; automatic matching is deliberately
not performed in this phase, keeping resolution conservative and auditable.

## Local AI run

`POST /runs/ai` accepts the same Source, Document, and DocumentVersion parent
choices plus `content_text` and `scope_terms`. It runs the measured local-first
capability cascade for relevance, embeddings, reranking, extraction, entailment,
and synthesis, then delegates persistence to the same evidence-ledger writer.
Only accepted, evidence-supported Claims can appear in the generated revision.
The response includes an `ai` diagnostic object; provider usage metadata is
recorded in `provider_usage`. Paid escalation is disabled by default and is not
needed for this route to complete locally.

Malformed provider output, timeout, and provider failure return a safe validation
error and do not partially persist a ledger run. The router records the failure
cause and work ID when telemetry is enabled.

## Search, comparison, and diagnostics

Phase 13 adds the authenticated local research workbench:

- `GET /search` performs bounded SQLite FTS5 search over Monitors, Sources,
  Documents, Stories, Subjects, Claims, Evidence Spans, tags, Questions, and
  notes. `q` is escaped as literal terms. `entity_type`, object IDs, state,
  lifecycle, date bounds, and deterministic `page`/`page_size` filters are
  supported. Results are ordered by BM25 score, entity type, and entity ID.
- `POST /comparisons` (also available as `/compare`) accepts two to twenty
  Document IDs and returns shared/unique Claim sets, contradictions, exact
  Evidence Span IDs, date/number differences, interpretation records,
  primary-source use, and Document lineage. Every conclusion remains tied to
  stored Newsroom data.
- `POST /workbench/notes` records bounded `note`, `hypothesis`, or `context`
  notes on a Story, Subject, Document, Claim, Monitor, or Research Question.
  Existing Research Question notes remain searchable as well.
- `GET /subjects/{id}/workbench`, `/timeline`, and `/historical-context` expose
  Subject stories, revisions, evolution events, Claims, notes, and exact
  historical Evidence Spans.
- `GET /diagnostics/health`, `/diagnostics/coverage`, and
  `/monitors/{id}/diagnostics` derive health from recorded activity, acquisition
  events, and job state. `no_meaningful_change`, `content_changed`,
  `failed_acquisition`, and `failed_processing` are separate statuses;
  `content_changed` means acquisition detected changed content whose semantic
  relevance has not been evaluated yet.

The Phase 13 migrations add namespaced `user`/`smart` tags, generic notes, and
the bounded FTS projection. Dirty-state triggers invalidate the projection on
authoritative updates and soft deletions, so stale search results are not
served; no semantic index is enabled without a benchmarked benefit.

## Ask Newsroom

Phase 14 adds authenticated, local-first conversational research:

- GET/POST /ask/conversations lists or creates global or object-scoped
  conversations. Supported scopes are Stories, Claims, Evidence, Documents,
  Reports, Questions, Subjects, Monitors, and Notes.
- GET /ask/conversations/{id} returns the conversation's answer turns.
- POST /ask/conversations/{id}/turns retrieves bounded local context and
  returns structured statements classified as fact, inference, uncertainty,
  contradiction, user_hypothesis, or context.
- POST /ask creates a scoped conversation and answers one turn in one call.
- GET /ask/runs/{id} returns audit metadata; POST /ask/runs/{id}/cancel
  performs cooperative cancellation.

Every answer statement has one or more citation IDs. Citations are resolved
server-side against internal Story, Claim, Evidence Span, Document, Report
Revision, Question, Subject, Monitor, or Note rows before an answer is stored
or returned. Unsupported questions are refused; stale, ambiguous, conflicting,
and user-hypothesis material is explicitly qualified.

Prompt length, context units, citation count, and provider mode are bounded.
Local deterministic retrieval is the default. Hosted mode is disabled unless
configured and a positive per-request cost cap is supplied. Ask audit rows
store a prompt hash and length, retrieval object IDs/counts, classifications,
resolved citations, route, status, and cost—not raw prompts or secrets.

## Hardening and operations

- `GET /health` and `GET /readiness` remain public liveness/readiness probes;
  authenticated `GET /metrics` returns bounded request/status/latency and
  failure-by-subsystem counters without query strings, request bodies, article
  bodies, prompt content, or secrets.
- Request bodies over 1 MiB are rejected, including streamed bodies. The local API applies
  fixed-window client request limits of 120 requests/minute, 20
  authentication requests/minute, and 30 metrics requests/minute, returning a
  `Retry-After` header when exceeded.
- Session/auth responses are `no-store`; sessions use HTTP-only, Secure in
  production, SameSite=Lax cookies with 24-hour expiry. Mutations still
  require the CSRF header.
- `python -m newsroom.cli backup|restore|verify|upgrade|export|retain` provides
  verified operator workflows. The logical export is an allow-listed JSONL
  projection and excludes password/session material, settings, prompts, note
  bodies, search text, provider payloads, and raw Ask answers.
- Full recovery and failure-response procedures are in
  `docs/OPERATIONS_RUNBOOK.md` and `docs/RECOVERY_RUNBOOK.md`.

## Query and mutation conventions

List responses use:

```json
{"items": [], "page": 1, "page_size": 25, "total": 0}
```

List ordering is deterministic and every list accepts bounded `page` and
`page_size` values. Resource-specific `q` and relationship filters are
available on the collection paths. Soft-deleted Categories, Topics, Subjects,
Sources, and Stories are excluded by default and can be requested by the
authenticated user with `include_deleted=true`.

PATCH uses omitted-versus-null semantics: omitted fields are unchanged, an
explicit `null` clears a nullable field, and explicit `null` for a required
field is rejected. Stable slugs are create-only and cannot be renamed.

Errors use the common envelope from the application shell:

```json
{
  "error": {
    "code": "validation_error",
    "message": "request validation failed",
    "request_id": "..."
  }
}
```
