# AST-21 — Integrate paid Ask only if its value is demonstrated

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: DEFERRED. Priority P2; milestone Conditional; size M; risk high. Dependencies: AST-11, AST-18. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Make normal Ask optionally use the same managed provider safely if the value verdict retains it.

Why now: Remote benchmark synthesis is not a production feature; do not widen first completion scope speculatively.

Inspect: newsroom/ask.py; newsroom/domain_api.py; newsroom/evals/benchmark_provider.py; frontend/src/views/AskView.tsx; tests/test_phase14_ask.py. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

After explicit scope activation, reuse the production config/vault/durable budget service and a reviewed compatible synthesis adapter. Bind prose/statement citations to allowed retrieved evidence, preserve no-evidence refusal/temporal scope and cancellation. Display effective local/remote model and fallback. Do not import benchmark experiment policy into product defaults.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

General web chat, remote entailment/relevance, ungrounded synthesis, changing frozen eval adapters.

## Tests

Unsupported citation/claim rejection, insufficient evidence, temporal reads, cancellation/uncertain billing, shared reload and budget checks; authorized live test only if requested.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Normal Ask uses selected supported managed route and reports identity
- [ ] Every generated factual statement remains bound to qualifying evidence or is rejected/qualified
- [ ] Local/refusal fallback and cost constraints survive failures without benchmark contamination

## Completion evidence and required plan updates

Required: Value activation decision, trust tests and product journey evidence. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Switch Ask route to local; preserve conversations/audit history.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

