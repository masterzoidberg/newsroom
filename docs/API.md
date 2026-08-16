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

Generated revisions require `claim_ids` and structured `propositions`, each
with one or more cited Claim IDs. The server checks that every cited Claim is
accepted, belongs to the Story, and is part of the revision Claim set. It then
stores the exact Claim IDs in `story_revision_claims` and computes
`claim_set_hash`; unsupported citations reject the revision before insertion.

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
