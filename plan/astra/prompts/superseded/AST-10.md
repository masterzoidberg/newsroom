# AST-10 — Add bounded provider validation and safe API contracts

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M2; size M; risk high. Dependencies: AST-09. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Provide explicit safe connection tests and provider-management APIs.

Why now: Users need useful failure diagnosis before background spending.

Inspect: newsroom/domain_api.py; newsroom/app.py; newsroom/article_analysis.py; provider service from AST-06/09; tests/test_phase21_article_analysis.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Implement proposed CRUD/credential/test/routes/status APIs with auth/CSRF/no-store, safe errors and optimistic revision. Test actual configured structured-output capability using a bounded explicit reservation; no auto-test. Validate HTTPS/loopback keyless rules, redirects, DNS/destination and host-change secret handling. Manual model entry remains sufficient.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Automatic paid checks, arbitrary provider headers, broad endpoint compatibility claims or new SDKs.

## Tests

Fake transport for auth failure, timeout, malformed JSON/schema, host redirect/credential forwarding, unsupported model, stale validation revision, test cap exhaustion.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Explicit test yields a safe revision-bound capability result without raw provider body
- [ ] Credential cannot be forwarded to a changed/unapproved destination
- [ ] No provider call occurs on listing, edit, startup or typing; test never enables background spend

## Completion evidence and required plan updates

Required: API security/error matrix and mock request counts. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Disable test endpoint/route; keep metadata and credentials intact.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

