# AST-09 — Resolve provider configuration at operation boundaries

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: NOT_STARTED. Priority P0; milestone M2; size M; risk high. Dependencies: AST-08. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Make actual workers and API capabilities consume the same versioned authority.

Why now: A Settings save must affect execution without stale environment-only constructors.

Inspect: newsroom/runtime.py; newsroom/article_analysis.py; newsroom/document_processing.py; newsroom/domain_api.py; newsroom/intelligent_monitoring.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Implement immutable config snapshots resolved at new operation boundaries, lazy client lifecycle and effective generation telemetry. Route Article Analysis through shared metadata/vault. Keep unsupported capabilities explicitly local through the same resolver. Add explicit legacy environment import/source labeling and managed-config precedence; disable/removal must not resurrect env providers.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Changing frozen eval contracts, remote relevance/entailment, replaying historical analysis under a new identity silently.

## Tests

Edit while worker alive, in-flight pinning, provider disable/delete, environment precedence, local fallback identity and restart persistence.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Next work uses saved generation without restarting while in-flight work keeps its identity
- [ ] All product construction paths report supported local/remote authority coherently
- [ ] Disable/remove falls back safely and no legacy environment variable re-enables the provider

## Completion evidence and required plan updates

Required: Multi-process configuration-generation tests and effective-route records. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Select local in metadata; preserve generation/history and old analysis identities.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

