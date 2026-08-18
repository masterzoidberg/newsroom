# Phase 21 — Article Analysis and Real AI Provider

## Objective

Add structured article intelligence and one real model-backed provider behind
the existing provider-neutral contracts.

## Why this phase exists

Current local providers are useful deterministic fallbacks but are not semantic
or LLM analysis, and no concrete production remote provider is wired.

## Current-state gap

`AIVerticalSliceService` only runs through a manual `/runs/ai` request carrying
caller-supplied text. There is no persisted analysis record for an automatically
processed acquired version.

## Scope

- Reuse `AIRouter`, provider protocols, Pydantic capability contracts,
  telemetry, budgets, and timeouts.
- Add exactly one real provider path first, selected by configuration and
  disabled by default.
- Persist concise summary, key developments, entities, dates, locations,
  significance, novelty, candidate Claims, candidate Evidence excerpts,
  confidence, model identity, provider identity, and prompt/version metadata.
- Validate structured output and enforce bounded retries/timeouts/cost.
- Keep deterministic provider parity for offline tests.

## Non-goals

- No multi-provider marketplace or distributed inference.
- No automatic acceptance of model Claims or EvidenceSpans.
- No Story/report/alert automation; Phase 23 owns that connection.

## Existing components to reuse

`AIRouter`, `CapabilityBundle`, `RoutePolicy`, `SQLiteTelemetrySink`, local
providers, `AIVerticalSliceService` contracts, Phase 19 Jobs, Phase 20 relevance,
and Phase 18 content artifacts.

## Required implementation

The relevant processing Job calls the selected provider with bounded normalized
content and an explicit prompt contract. Provider identity, model, route,
latency, estimated/actual cost, failure, and structured result hashes must be
persisted. Provider failure must produce a bounded retry/partial/failed outcome
without fabricating evidence.

## Data model/migration expectations

Add a durable analysis-result record keyed idempotently by DocumentVersion and
processing scope. Store structured result, schema version, provider/model,
prompt/template identity, confidence, timestamps, and provenance references.
Do not copy unrestricted prompts or secrets into exports.

## Runtime integration

Only relevant Phase 20 processing results invoke analysis. The worker remains
bounded and restart-safe. A successful analysis produces candidate outputs for
Phase 22, not accepted Claims.

## Security/privacy considerations

Treat retrieved text as prompt-injection-prone data. Delimit source content,
never allow it to alter system instructions or tool policy, redact secrets from
logs, enforce provider timeouts and hard budgets, and make remote execution an
explicit opt-in.

## Tests

- Deterministic provider produces schema-valid persisted analysis.
- Malformed output, timeout, provider failure, low confidence, cancellation,
  and budget exhaustion are safe and attributable.
- Provider/model/prompt provenance is persisted without secrets.
- One live-provider canary is isolated and opt-in.
- Relevant versions analyze; irrelevant versions do not.

## Acceptance criteria

```text
relevant changed version
  → real processing call
  → validated structured analysis
  → persisted analysis record
  → complete provider/model/telemetry provenance
```

Candidate Claims and Evidence remain unaccepted until Phase 22 verification.

## Live-test gate

After Phase 21, Live Test B may run: a real public Source change through
relevance and real model analysis. Do not promote model Claims to accepted
evidence.

## Dependencies

Phases 18–20. Provider choice and secret configuration must be explicit before
implementation.

## Exit criteria

One opt-in real provider and the deterministic fallback produce bounded,
validated, persisted, provenance-rich analysis for relevant acquired versions.
Phase 22 may automate evidence and Claims verification.
