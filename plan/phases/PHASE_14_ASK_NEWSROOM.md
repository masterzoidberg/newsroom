# Phase 14 — Ask Newsroom

## Objective

Provide conversational research over Newsroom's structured evidence without
replacing evidence authority with model memory.

## Required work

- Retrieve from Stories, Claims, Evidence, Documents, Reports, Questions,
  Subjects, and user notes with global or object-scoped conversations.
- Require answer statements to cite resolvable internal evidence objects.
- Distinguish fact, AI inference, uncertainty, contradiction, and user hypothesis.
- Refuse or qualify answers when evidence is absent, stale, ambiguous, or
  conflicting.
- Apply authorization, prompt/input limits, context budgets, cancellation,
  provider cost caps, and safe rendering.
- Preserve enough query/retrieval/citation metadata to audit an answer without
  storing secrets or unnecessary private prompts.

## Boundaries

No autonomous general agent, arbitrary tools, web browsing outside approved
research Jobs, or uncited factual answers.

## Verification and exit gate

- Citation resolution, unsupported-answer rejection, contradiction, empty
  evidence, prompt injection, scope isolation, cancellation, and budget tests.
- Local-only mode remains useful; hosted escalation remains optional.
- Human review set confirms answer provenance and uncertainty behavior.
- Full project checks pass.

## Completion Record

Completed 2026-08-16.

- Added migration 0013 for global/object-scoped Ask conversations and
  append-only-style run audit metadata that stores prompt hashes and lengths,
  not raw prompts.
- Added bounded local Ask Newsroom retrieval across indexed Stories, Claims,
  Evidence, Documents, Questions, Subjects, Notes, and direct Report
  revisions, with scope isolation and exact citation resolution.
- Added structured fact, inference, uncertainty, contradiction, context, and
  user-hypothesis statements; unsupported, injection-like, stale, ambiguous,
  and conflicting requests are refused or qualified.
- Added prompt/context/citation limits, cooperative cancellation, local-only
  defaults, hosted provider cost-cap refusal, authenticated CSRF-protected API
  routes, and the responsive Ask Newsroom UI.
- Verification: Phase 14 backend/frontend tests, full project tests,
  frontend typecheck/build, browser smoke verification, and diff review pass.
