# AST-17 — Execute the frozen comparison under its exact contract

## Repository context

Read plan/astra/README.md, CODEX_EXECUTION_RULES.md, DECISIONS.md, CURRENT_STATE.md, TASKS.md and NEXT.md. Audit baseline was aad7d17ec91b56b68e1252c70bdf6521060c0bd1/schema 36; inspect current HEAD rather than assuming it is unchanged. The approved phase29-trial is already observing and must not be altered by isolated implementation. Runtime data belongs outside the repository.

## Gate

Initial status: BLOCKED. Priority P1; milestone M4; size M; risk high. Dependencies: AST-01. Verify current ledger before editing. If this task is DEFERRED or BLOCKED, do only explicitly authorized preparation and record the unmet gate; do not silently activate it.

## Objective and exact scope

Obtain valid Full-vs-Lite evidence separate from the prospective trial.

Why now: Contract validation passed but is not a comparative result; paid permission and eligible data are missing gates.

Inspect: newsroom/evals/phase29_protocol.py; newsroom/evals/benchmark.py; newsroom/evals/benchmark_provider.py; docs/reviews/PHASE_29_EVALUATION_PROTOCOL.md; evals/lite/20q_contract.json. Also read the relevant STARTUP_AND_RUNTIME, AI_PROVIDER_SETTINGS, UX_AND_APPEARANCE, PRODUCT_READINESS and TEST_STRATEGY contracts before touching their subsystem. Files introduced by earlier tasks are discovered from their completion records; do not create duplicate services.

## Implementation requirements

Prepare eligible snapshot manifest mapping every case/candidate and cutoff using the frozen protocol; verify route/model/budget. Obtain explicit paid authorization before execution, preserve blinded mapping outside git, obtain actual human scoring and report insufficient categories honestly. Historical and prospective protocols remain separate.

Use the smallest contained diff, preserve architecture/conventions and data. If the proposed slice has grown beyond one focused session, split it in TASKS/NEXT with specific acceptance before coding; do not widen it silently.

## Non-goals

Changing frozen question set/model/cutoff, replacing evidence with arbitrary UAP snapshot, agent self-scoring, unapproved calls.

## Tests

Offline contract/eligibility validation, intentional wrong model/snapshot/fallback rejection, reproducible blind-score aggregation.

Run existing affected regressions and applicable build/lint gates. Use synthetic credentials and mocked providers. Never run the old browser smoke script against port 8127 or active production. No real paid call without explicit authorization.

## Acceptance

- [ ] Each run proves eligible snapshot and exact effective contract; no hidden fallback
- [ ] Paid execution is explicitly authorized and human blinded scores are retained
- [ ] Results show category/guardrail evidence, cost and latency without manufacturing missing coverage

## Completion evidence and required plan updates

Required: External snapshot/run hashes, safe report, authorization reference and scoring evidence. Update this task's TASKS entry with exact HEAD/artifact, files, commands/results and verification limits. Mark DONE only after all acceptance criteria are evidenced; otherwise keep an honest partial/blocked status. Update NEXT, record deviations in DECISIONS and reconcile any changed architecture/prompt/dependency. Reversibility: Spending cannot be reversed; invalid runs marked invalid and retained, never relabeled.

## Stop conditions

Stop dependent work if it would alter the frozen trial without its change decision, expose/store secrets outside the approved vault, spend without authorization, weaken provenance, overwrite unrelated changes, rely on missing dependency acceptance, or require a larger unrelated change. Preserve evidence and report the precise blocker; continue only independent authorized work. Do not manufacture human scoring/approval. Finish this primary task and report the next task; do not automatically implement another task.

