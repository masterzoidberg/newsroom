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
