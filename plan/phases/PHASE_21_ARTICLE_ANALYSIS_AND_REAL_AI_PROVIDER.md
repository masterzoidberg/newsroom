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

## Completion Record — 2026-08-18 (Phase 21)

**Verdict: PASS (offline/architecture gate); LIVE TEST B BLOCKED — no provider
credential configured in this environment.**

### Provider selected

- **One real provider:** `OpenAICompatibleArticleAnalysisProvider` — the
  official `openai` SDK against an OpenAI-compatible `/chat/completions`
  endpoint (base URL configurable, so any OpenAI-compatible service works).
  Verified against the current official SDK documentation (openai-python
  v1.68 contract via Context7): granular `httpx.Timeout` (connect/read/write),
  bounded `max_retries`, structured JSON-schema `response_format`, usage
  metadata in the completion response. Exactly one real provider was
  implemented; the repo had no prior remote provider, and a single adapter
  satisfies the provider-neutral `AIRouter` contracts without multi-provider
  orchestration.
- **SDK:** `openai` (lazily imported; installed 1.3.7; the paid path targets
  the current documented contract and requires a modern SDK — noted as a live
  gate risk). Offline suites mock the SDK response layer and never need a key.
- **Model configuration:** `NEWSROOM_ANALYSIS_MODEL` (default `gpt-4o-mini`),
  `NEWSROOM_ANALYSIS_MAX_TOKENS` (default 1200),
  `NEWSROOM_ANALYSIS_BASE_URL` (optional).
- **Deterministic local provider:** `LocalArticleAnalysisProvider` (same
  validated schema, honestly labeled `provider=local` / `model=local`,
  zero cost, no network), plus `DeterministicArticleAnalysisProvider` for
  scripted fixtures.

### Configuration fields (safe defaults; no key required to run)

`NEWSROOM_ANALYSIS_PROVIDER` (default `local`), `NEWSROOM_ANALYSIS_API_KEY`
(required only for the paid route; never logged/stored), `_BASE_URL`,
`_MODEL`, `_TIMEOUT_SECONDS` (30), `_CONNECT_TIMEOUT_SECONDS` (5),
`_MAX_TOKENS` (1200), `_MAX_INPUT_CHARS` (24000), `_MAX_RETRIES` (2),
`_MAX_PAID_CALLS` (1), `_MAX_PAID_COST_USD` (0.10),
`_MAX_PAID_CALLS_PER_WORK` (1), `_MAX_PAID_COST_USD_PER_WORK` (0.10),
`_REQUEST_COST_USD` (0.01). The paid route additionally requires the existing
`budget.paid_enabled` settings flag (BudgetService).

### Analysis schema

`article_analysis_schema_v1` (`ArticleAnalysisOutput` in `newsroom/ai.py`):
summary, key_developments (1..25), entities (name + optional category),
dates, locations, significance, novelty (article-level only), candidate_claims
(indexed, atomic, ≤50), candidate_evidence_excerpts (candidate_claim_index +
short excerpt + optional locator hints; every index must reference a
candidate claim), confidence (0..1, explicitly not calibrated probability).
Strict Pydantic validation before persistence; malformed/oversized output
fails terminally and truthfully.

### Persistence / identity

Migration 0018 → `article_analyses` (schema version 18): document_version,
relevance_id, monitor_id, job_id, scope_version, artifact_id,
normalized_content_hash, `identity_hash` (UNIQUE), schema_version,
prompt_version, provider, model, paid, confidence, input/analyzed char
counts, truncated, validated result_json, created_at. Immutable via
append-only triggers. Canonical identity = sha256(document_version_id,
relevance_id, scope_version, schema_version, prompt_version, provider,
model): retry/recovery reuses one record (UNIQUE index, not a pre-check);
model/prompt/schema changes create a new version preserving history; nothing
is overwritten. Prompt version: `article_analysis_v1` (persisted, not stored
in exports).

### Routing / timeout / retry / budget / telemetry

- Router: `AIRouter` with `article_analysis` capability; paid route only when
  provider=openai + key + budget flag + per-call budget permits; otherwise
  deterministic local. Provider choice stays behind the capability bundle.
- Timeouts: real SDK `httpx.Timeout` (connect/read/write); router
  `Future.result` remains an outer guard with a margin. Retryable = 429/5xx /
  timeout / connection errors → bounded `RetryableJobFailure`; terminal =
  credentials/model/config/schema-validation/budget refusal.
- Telemetry: one `provider_usage` row per call via `SQLiteTelemetrySink`
  (route, provider, model, latency, outcome, token units, estimated cost —
  never fabricated). Fixed a latent concurrent ID collision in the sink
  (`time.monotonic_ns()` → `uuid4`).
- Errors sanitized: no API keys, Authorization headers, or response bodies in
  job errors or telemetry (test-proven).

### Processing integration

Inside the existing `document_version_process` handler (no second queue):
relevance evaluated/persisted → only `relevant=true` triggers analysis on the
exact verified Phase 18 artifact → durable record → job succeeds. No DB write
transaction is held during the provider call; analysis persistence precedes
processing success (no crash gap, idempotent healing on retry). `relevant
=false`, `not_applicable`, and relevance failures never construct or call an
analysis provider. Candidate Claims/Excerpts never enter `claims` /
`evidence_spans`; no Story/Report/Alert automation (all test-proven).

### Tests / results

`tests/test_phase21_article_analysis.py` — 33 tests covering all 30 required
cases (relevance gating ×4, artifact input, reopen durability, local/real
provider contracts, malformed output, candidate-only storage, injection
boundary, identity/rerun history, provenance, local-vs-paid usage, budget/
disabled/missing-key, timeout/429/5xx/terminal classification, sanitized
errors, recovery, Phase 19/20/RQ invariants, production composition,
restart, concurrency, truncation, UAP fixture, migration 0018, integrity,
API read path). Full backend suite: **488 passed, 39 warnings** (3 runs),
`compileall` clean, `git diff --check` clean. Migration-version expectations
updated in phase 02/06/07/08/15/18/20 test files for schema 18.

### Live Test B

**BLOCKED — provider credential/configuration unavailable.** The operator
must supply `NEWSROOM_ANALYSIS_PROVIDER=openai` and
`NEWSROOM_ANALYSIS_API_KEY` in the worker process environment, enable
`budget.paid_enabled` (API: `PUT /api/v1/budgets/paid-enabled`), then rerun
the relevant-source canary. No API key was embedded anywhere; offline
implementation and architecture gates are complete without it.

### Remaining risks

- Paid path not exercised against a live endpoint (blocked); SDK version
  targeting documented v1.68+ contract while the installed SDK is older —
  `pip install -U openai` required before Live Test B.
- Strict-mode JSON-schema nuances of the chat-completions `response_format`
  are unverified live; our Pydantic validation remains the authoritative gate.
- Theoretical double-paid-call if two workers simultaneously attempt the same
  never-before-analyzed identity (UNIQUE guarantees one durable record; the
  queue's active-obligation coalescing makes the simultaneous case
  effectively unreachable).

## Live Test B Completion Addendum — 2026-08-18

**LIVE TEST B: PASS — real provider call succeeded.**

### SDK compatibility

- Previous installed SDK: `openai 1.3.7` (predates the chat-completions
  `json_schema` `response_format`).
- Verified requirement (Context7, official openai-python docs, v1.68
  contract): the Phase 21 provider implementation was already correct for a
  modern SDK (case A) — client construction, `chat.completions.create`,
  `response_format` JSON-schema, `httpx.Timeout`, `max_retries`, usage shape,
  exception classes all match the documented contract; the environment simply
  lacked a compatible SDK.
- Dependency declaration: `pyproject.toml` now declares
  `openai>=1.68,<2.0` in runtime dependencies, so a fresh Newsroom install
  receives a compatible SDK.
- Final installed version actually tested: **`openai 1.109.1`**.
- Provider code changed minimally: `last_usage` now also exposes
  `input_tokens` / `output_tokens` (the telemetry sink continues to persist
  `token_units` = total); `AnalysisProviderConfig.from_env` now accepts the
  conventional `OPENAI_API_KEY` as a fallback for
  `NEWSROOM_ANALYSIS_API_KEY` (the variable the openai SDK itself reads by
  default; keys are still never logged/persisted/exported).

### Configuration used for the live canary

- provider=`openai`, model=`gpt-4o-mini`, base URL = default (api.openai.com).
- timeout 90 s (SDK `httpx.Timeout`, connect 10 s), SDK `max_retries=0`,
  `max_tokens=1200` (output capped), paid budget: lifetime USD $0.10 and 2
  paid requests in the disposable test DB, `budget.paid_enabled=true`.
- API key: taken from the operator's existing `OPENAI_API_KEY` environment
  variable; never printed, logged, persisted, or committed.

### Live source / scope

- Source: `https://science.nasa.gov/uap/` (official US government, NASA
  Science — UAP independent study page).
- Information need: Topic "UAP" with approved scope terms `UAP`, `UFO`,
  `unidentified anomalous phenomena`, `anomalous phenomena`,
  `unidentified flying object`, `flying saucer`.
- Relevance result: **evaluated, relevant=true**, stage=exact, score=1.0
  (matched term `UAP`), persisted `document_version_relevance` with
  scope_version 1.

### Live analysis

- `article_analyses` id **`ana_5bf1bb198e647fd90b81c2ba717de9dc`**;
  provider=openai, model=gpt-4o-mini, paid=true.
- Schema validation: PASS — full `ArticleAnalysisOutput` validated before
  persistence (`article_analysis_schema_v1`, prompt `article_analysis_v1`);
  all structured fields populated (summary, key_developments, entities,
  dates, locations, significance, novelty, 4 candidate claims, 4 candidate
  excerpts, confidence 0.9).
- Provenance persisted: document_version_id, relevance_id, monitor_id,
  scope_version=1, artifact_id, normalized_content_hash, schema/prompt
  versions, provider/model, paid, created_at.

### Usage / cost

- Input tokens 3514, output tokens 544, total 4058; latency ~8.7 s (wall and
  telemetry agree: 8796/8734 ms); provider billing metadata unavailable so no
  exact dollar cost is claimed — Newsroom's configured estimate
  `NEWSROOM_ANALYSIS_REQUEST_COST_USD` = $0.01 was recorded in
  `provider_usage` (one `article_analysis` row, route=paid, status=succeeded).

### Evidence boundary

`evidence_spans=0`, `claims=0`, `claim_evidence=0`, `stories=0`,
`story_revisions=0`, `story_evolution_events=0`, `living_reports=0`,
`alerts=0`, `briefings=0`. The model output remains candidate intelligence
only; Phase 22 is untouched.

### Zero-call gate (live)

A second live acquisition of `https://example.com/` (irrelevant page) through
the same harness produced `relevance=false`, zero `article_analyses` rows,
zero `article_analysis` provider_usage rows, zero paid usage — no provider
call was made.

### Regression results

- Phase 21 tests: 33 passed; Phase 20 + Phase 19 + Phase 21 combined: 85
  passed; full backend suite: **488 passed, 39 warnings**; `compileall`
  clean; `git diff --check` clean.

### Remaining risks

- Only one live model (gpt-4o-mini) and one live endpoint verified; other
  OpenAI-compatible endpoints via `NEWSROOM_ANALYSIS_BASE_URL` remain
  unverified live.
- `response_format` JSON-schema behavior validated live on gpt-4o-mini;
  strict-mode nuances on other models remain the Pydantic layer's
  responsibility.
- Theoretical double-paid-call race (unchanged, effectively unreachable via
  queue coalescing).

