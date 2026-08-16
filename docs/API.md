# Phase 03 API Contract

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

Stories create immutable revision 1 and add later revisions through
`/stories/{story_id}/revisions`. Tags attach through
`/stories/{story_id}/tags`.

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
