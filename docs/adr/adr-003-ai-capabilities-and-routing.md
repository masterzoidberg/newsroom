# ADR-003 — Local-first AI capabilities and bounded routing

## Status

Accepted for Phase 05.

## Context

The Phase 04 evidence ledger needs AI assistance for relevance triage, candidate
similarity, entailment, Claim/evidence extraction, and evidence-bound Story
synthesis. These operations must remain replaceable, testable without network or
credentials, and unable to bypass deterministic domain validation.

## Decision

Newsroom exposes narrow capability contracts in `newsroom.ai`:

| Capability | Selected local default | Measured limitation |
|---|---|---|
| Embedding | `local-token-hash-v1` | Lexical hash vectors are not semantic embeddings. |
| Reranking | `local-token-overlap-v1` | Scores do not understand negation or entity identity. |
| Entailment | `local-token-entailment-v1` | Contradictions rely on a small marker vocabulary. |
| Relevance | `local-scope-overlap-v1` | Scope terms are treated as independent tokens. |
| Extraction | `local-sentence-extraction-v1` | Sentence boundaries are heuristic and need review. |
| Synthesis | `local-claim-join-v1` | Output is a conservative template, not stylistic writing. |

`AIRouter` always tries an enabled local provider first. A paid provider can be
injected per capability, but escalation requires all of the following:

- the global paid route is enabled;
- a provider is configured;
- the global paid-call and cost budgets have remaining capacity; and
- the per-work paid-call and cost budgets have remaining capacity.

Paid routing is disabled by default. The current in-process defaults permit no
paid calls unless a caller explicitly enables the route and supplies a positive
budget. Phase 07 may replace the in-process counters with durable Job/Run budget
ledger enforcement without changing the capability contracts.

Provider responses are parsed through closed Pydantic models with forbidden extra
fields and bounded numeric/string/list fields. Invalid output, provider errors,
and timeouts never reach the domain writer. The router records route, provider,
model, confidence, decision signal, latency, token/compute units, cost,
escalation reason, work ID, and failure code in `TelemetryEvent`.
`SQLiteTelemetrySink` serializes that metadata into the existing `provider_usage`
ledger; no provider-specific object enters the domain model.

`AIVerticalSliceService` calls all selected local capabilities, turns only
validated output into the Phase 04 `EvidenceService.run_manual` contract, and
leaves accepted Claim and StoryRevision authority with the existing ledger
transaction and closed-world audit.

## Evidence

Run the reproducible offline benchmark with:

```powershell
python -m newsroom.ai_benchmark
```

The recorded output is [phase05_ai_benchmark.json](../../evals/benchmarks/phase05_ai_benchmark.json).
The benchmark has fixed cases, no network access, no timing-dependent values,
and compares each local candidate with a test-only deterministic reference.

## Consequences

Normal operation has no hosted provider dependency and can complete the Phase 04
vertical slice locally. The local implementations are intentionally conservative
and useful as routing baselines, not claims of production-grade semantic quality.
The benchmark must be expanded with labeled corpus cases before replacing any
default with a heavier local model or enabling paid escalation. Durable budget
accounting and richer model adapters remain later-phase work.
