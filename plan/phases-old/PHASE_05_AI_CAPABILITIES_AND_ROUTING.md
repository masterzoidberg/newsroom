# Phase 05 — AI Capabilities and Routing

## Objective

Add measured, replaceable AI assistance without making a hosted provider a
runtime dependency.

## Required work

- Define narrow interfaces for embeddings, reranking/entailment, relevance,
  extraction, and evidence-bound synthesis.
- Implement deterministic test providers and one local implementation for each
  capability required by the vertical slice.
- Benchmark candidates per task and record selected defaults and limitations in
  an ADR.
- Validate every structured model output before domain use.
- Add confidence gates, timeout/failure behavior, and optional paid escalation
  behind global and per-work budgets.

## Boundaries

No provider marketplace or many-provider support. Do not weaken deterministic
authority or the closed-world synthesis audit.

## Verification and exit gate

- Tests run without network or credentials using deterministic providers.
- Local-only mode completes the Phase 04 vertical slice.
- Invalid output, timeout, provider failure, and disabled/exhausted paid routes
  fail safely and are attributed in telemetry.
- Benchmark and ADR are reproducible; full project checks pass.

## Completion Record

Completed 2026-08-16.

### Delivered

- Added narrow, validated capability contracts for embeddings, reranking,
  entailment, relevance, extraction, and evidence-bound synthesis in
  `newsroom/ai.py`.
- Added dependency-free local implementations and deterministic test providers.
  The local-first route is the default and requires no network, credentials, or
  hosted runtime.
- Added `AIRouter` confidence gates, per-call timeouts, provider failure and
  malformed-output handling, global/per-work paid-call and cost budgets, and
  structured telemetry. Paid escalation is disabled by default.
- Added `AIVerticalSliceService` and authenticated `POST /api/v1/runs/ai`, which
  routes validated local outputs into the existing Phase 04 transactional
  Evidence Ledger and closed-world Story revision audit.
- Added the offline reproducible benchmark and recorded output at
  `evals/benchmarks/phase05_ai_benchmark.json`, plus ADR-003 with selected
  defaults and measured limitations.
- Added focused behavior tests for validation, escalation, timeout, disabled and
  budget-blocked routes, SQLite telemetry, local vertical-slice completion, API
  authorization path, and benchmark reproducibility.

### Verification

- `python -m pytest -q` — passed (216 tests).
- `python -m compileall -q newsroom` — passed.
- `python -m newsroom.ai_benchmark` — passed; output matches the committed
  benchmark artifact exactly.
- `python -m newsroom.evals validate` — passed (30 cases).
- `python -m newsroom.evals replay multi-outlet-hermes-v0200` — passed with the
  existing deterministic replay hash.
- `npm run typecheck` — passed.
- `npm run build` — passed.
- `poetry run format` / `poetry run test` — unavailable for this setuptools
  project; the canonical Python checks above pass.

### Review

- Five-axis implementation review completed for correctness, readability,
  architecture, security, and performance; no Critical or Required findings
  remain.
- Accepted implementation commit: `d7a08850446aa419607e14286e1d13cc4b217b75`.

### Limitations

- Local providers are conservative lexical/templated baselines, not production
  semantic models. The benchmark intentionally uses small fixed offline cases.
- Paid provider adapters are injectable but no hosted provider is enabled or
  selected in this phase. Durable budget accounting remains Phase 07 work.

## Post-Audit Status — 2026-08-18

The capability contracts, deterministic local providers, routing safeguards,
and telemetry remain valid. The local implementations are lexical/templated
baselines, not full semantic or LLM analysis, and no concrete production remote
provider is wired. Real article intelligence is planned for Phase 21 and must
not be implied by this historical completion record.
