# Standalone Newsroom Architecture

## Topology

```text
Tailscale Serve / localhost
          |
          v
+----------------------------+
| FastAPI                    |
| /api + React/PWA static    |
+-------------+--------------+
              |
              v
        SQLite (WAL)
              ^
              |
+-------------+--------------+
| Worker + scheduler loop    |
| - due monitor selection    |
| - durable job leases       |
| - retrieval/research       |
+-------------+--------------+
              |
     +--------+---------+-------------------+
     |                  |                   |
     v                  v                   v
Direct/free sensors   Local AI       Paid escalation
RSS/API/page checks   embed/model    search/frontier model
```

The web process does not own long research tasks. It enqueues/reads durable jobs.
The worker is restart-safe and obtains all authoritative work state from SQLite.

## Major bounded contexts

### Taxonomy
Category, Topic, TopicTerm, Subject, SubjectAlias and relationships.

### Monitoring
Monitor, MonitoringPolicy, due scheduling, budgets, retirement/backoff, immutable
activity history, and versioned approved scope snapshots. A monitor target must
be a live Topic, Subject, Story, Source, or Research Question; disabled or
unavailable targets are suppressed before queue insertion.

Monitor target execution boundary: the schema and API accept `topic`, `subject`,
`story`, `source`, and `research_question` targets, but only `source` targets
currently have a real acquisition mechanism. A scheduled execution of any other
target type is resolved by the production worker handler and truthfully records
`error`/`unsupported_target` monitor activity without touching the network; it
never fabricates `no_change` or `changed`. Implementing the missing target
adapters is later roadmap work.

### Acquisition
Connectors produce normalized candidate observations/documents. Provider-specific
objects do not leak into Story/Claim domain models.

Phase 06 implements bounded RSS/Atom polling and direct HTTP/page acquisition.
The transport enforces domain, redirect, timeout, and response-size policy;
conditional headers and raw/normalized hashes support cheap change detection.
`acquisition_events` preserves append-only provenance, while HTML extraction
stores only bounded metadata until exact excerpts are deliberately selected for
the Evidence Ledger. Source profiles remain multidimensional, and suggestions
require explicit human review.

### Documents
Source -> Document -> DocumentVersion. Version identity is content/provenance
state at retrieval time.

#### Durable normalized content artifacts (Phase 18)
Every newly acquired DocumentVersion references exactly one durable, immutable,
content-addressed normalized content artifact (`content_artifacts`,
`document_versions.artifact_id`). The artifact stores the exact bounded
normalized text that acquisition produced — SafeHTMLExtractor visible text for
HTML/text pages (`visible_text_v1`), the exact feed-entry metadata JSON for
RSS/Atom entries (`feed_metadata_v1`), or the bounded fallback normalization of
non-extractable responses (`fallback_text_v1`) — together with its
`normalized_content_hash` (sha256 of the exact stored text), length, kind,
normalization version, and creation time. Same normalized text reuses the same
artifact row; the content columns are protected by an immutability trigger and
the DocumentVersion FK prevents deleting a referenced artifact. A worker reloads
verified content via `ContentArtifactService.load_normalized_content /
load_verified_text`; hash or length mismatches fail closed, and pre-Phase-18
historical versions truthfully report `available=False` (no fabricated or
re-fetched content, no provenance mutation). Artifacts are SQLite rows, so the
existing online backup captures them automatically, and logical exports
continue to omit article-derived text (the `content_artifacts` table is not on
the export allow-list).

### Event Resolution
Candidate retrieval + conservative merge/new decision. URL/document identity,
time, entities, location, shared Claims, bounded text/embedding similarity, and
event attributes narrow candidates; deterministic exclusions reject incompatible
events. An adjudicator is called only for an ambiguous top candidate, and a
low-confidence or absent adjudication creates a separate Story.

Phase 09 persists Story-document links, immutable evolution classifications,
document lineage edges for citations/syndication/wire propagation/rewrites, and
revision-document provenance. Independent corroboration is counted by lineage
group and source rather than publication count.

### Evidence
Claim, EvidenceSpan, ClaimEvidence, ClaimStateHistory and supersession.

### Story
Story and immutable StoryRevision records plus Topics/Subjects/review metadata.
Review status remains independent from revision attention; a material revision
sets `review.new_update` without changing saved/dismissed/not-useful state.

### Research Questions
Persistent gaps that can generate targeted follow-up jobs. Question status,
reopen/abandon history, Claim/Evidence links, notes, and bounded attempts are
stored in SQLite. Gap suggestions are derived from persisted Claim state,
evidence relationships, source composition, contradiction, and lineage-aware
independence; they remain suggestions until explicitly reviewed or converted.
User hypotheses are stored as notes and never enter the Claim Ledger directly.

### Jobs / Runs
Durable Job + Attempt records, research Runs, telemetry and provider usage.

Phase 07 uses SQLite as the initial queue. `JobService` owns atomic claims,
leases, retry/backoff, cancellation, idempotency, and terminal Run aggregation;
`SchedulerService` advances persisted Monitor schedules and enqueues due work.
`WorkerProcess` executes only an explicitly registered handler map outside the
queue transaction. Budget limits and active reservations are evaluated during
claim, while `provider_usage` remains the actual cost ledger.

Phase 08 monitor jobs carry the policy's acquisition, local-model, and USD
budget only; they cannot silently broaden scope or recursively create work.

### DocumentVersion processing obligations (Phase 19/20)

`document_version_process` is the durable orchestration substrate between
acquisition and future intelligence stages. The canonical work item is the
persisted `DocumentVersion`:

    Source → Monitor → monitor_check Job → Worker → Acquisition
      → changed DocumentVersion + Phase 18 artifact
      → document_version_process Job (same write transaction)
      → processing Worker handler
      → verified artifact + approved relevance scope (Phase 20)
      → deterministic local relevance decision (persisted)
      → relevant=true → structured article analysis (Phase 21, opt-in real
        provider or deterministic local) → durable ArticleAnalysis record
      → terminal processing result
      → STOP before Evidence verification (Phase 22)

Phase 19 established the obligation itself and stopped before relevance;
Phase 20 executes the deterministic relevance stage inside the same handler
(see "Automatic relevance and semantic scope" below); Phase 21 adds the
structured article-analysis stage for relevant decisions (see "Structured
article analysis (Phase 21)" below).

Every changed/new acquisition — HTML/text documents and each new feed entry —
creates at most one processing obligation. `not_modified`, unchanged content,
acquisition errors, and disabled Monitors create none. A processing failure
never retroactively changes the acquisition outcome: the `monitor_check` Job
and the `document_version_process` Job are independent durable obligations with
independent retry/failure semantics.

Ownership and atomic handoff:

- `jobs.document_version_id` (Migration 0016) is the canonical owner column;
  its FK proves the referenced version exists at insert time, so no enqueue
  path can reference a nonexistent version, and the active-work coalescing
  query is indexed.
- `enqueue_document_version_processing_tx` runs inside the same `BEGIN
  IMMEDIATE` transaction that commits the DocumentVersion and its artifact, so
  a crash between version commit and obligation commit is impossible: both
  commit or neither commits. A stable `document:{version_id}` idempotency key
  (UNIQUE) coalesces duplicates, and the transaction serialization guarantees
  at most one ACTIVE obligation per version.
- The payload carries only canonical IDs (document_id, source_id, originating
  monitor_id) for traceability; mutable Source/Monitor metadata is never
  duplicated. `jobs.monitor_id` is deliberately not overloaded — it remains the
  monitor_check execution ownership column, so processing jobs that originate
  from a Monitor keep that provenance in payload JSON. The handler validates
  every payload ID against the persisted DocumentVersion/Document/Source/
  Monitor rows and rejects conflicting caller-supplied IDs.
- Queued, running, succeeded, failed, and cancelled obligations each block
  further AUTOMATIC work for that version (the idempotency key covers all
  states; active-work coalescing additionally rejects concurrent ACTIVE
  obligations regardless of key). No automatic path ever re-enqueues processed
  work. Explicit rerun of a terminal obligation is allowed (fresh
  `rerun:` idempotency key) and is refused while an active obligation exists
  or when the version no longer exists.

The Phase-19 handler resolves the canonical version, loads the hash-verified
Phase 18 normalized content artifact
(`ContentArtifactService.load_normalized_content`), and returns a bounded
deterministic result (version/artifact IDs, content hash, normalized hash,
kind, length, and — since Phase 20 — the persisted relevance decision)
written to `jobs.result_json` (Migration 0016). It never invokes AI providers,
semantic extraction, Evidence/Claims creation, Story evolution, Reports, or
Alerts, and never re-fetches remote content. Legacy pre-Phase-18 versions
without artifacts fail terminally and truthfully
(`LegacyVersionWithoutArtifact`); missing or corrupt artifacts fail terminally
via the Phase 18 fail-closed loader. Transient SQLite conditions use the
existing bounded retry semantics; all other processing failures are terminal
integrity outcomes. Lease expiry, recovery, cancellation, and restart behavior
are the repaired generic JobService semantics — no independent lease system
exists.

### Automatic relevance and semantic scope (Phase 20)

Phase 20 answers "was this acquired content relevant to the approved
monitoring scope?" with an explainable, durable, deterministic result. No
remote AI provider, no article analysis, no automated Evidence/Claims, Story,
Report, or Alert work exists here.

**Semantic scope ownership.** A Source answers *where* Newsroom looks; a
Monitor answers *what* the user is looking for. Every Monitor carries an
explicit, optional approved information-need association (`monitors.need_type`
/ `need_id`, Migration 0017) referencing a persisted Topic, Subject, Story, or
Research Question:

- A Monitor **with a need** is a semantic Monitor: its approved scope is the
  need's approved vocabulary, snapshotted into the existing immutable,
  versioned `monitor_scope_history` at creation/update and whenever the
  need's vocabulary changes (`refresh_topic_scopes` also refreshes
  need-based Monitors on approval of Topic terms).
- A Monitor **without a need** is explicitly classified **acquisition-only**:
  its obligations succeed with an explicit `not_applicable` relevance result
  and no relevance record — never a fabricated relevant/not-relevant.
- The scope is never inferred from Source name/URL, never global, and never
  caller-supplied. Pending or rejected vocabulary suggestions can never enter
  the approved snapshot (Phase 08 invariant preserved).

The approved-scope construction path is unchanged `_scope_for_target`:
Topic terms (exact/include, alias/vocabulary, entity, related_concept,
exclude), Subject canonical name + aliases, Story latest revision text,
Research Question text. Only approved vocabulary participates; broader/
narrower/related terms participate only when explicitly approved.

**Originating Monitor provenance and scope-at-acquisition pin.** The
processing obligation payload carries only canonical IDs (`document_version_id`,
`document_id`, `source_id`, `monitor_id`) plus `scope_version` — the
`monitor_scope_history` version in effect when the obligation was enqueued
inside the acquisition write transaction. Processing therefore evaluates the
exact approved scope snapshot that existed **at acquisition time**, never a
later mutable scope (the T0–T3 race resolves to historical scope). The
decision record copies the full snapshot JSON, so every decision is
reproducible even if the Monitor's scope later changes or the Monitor is
removed; historical decisions are never re-scored.

**Deterministic relevance pipeline.**

    DocumentVersion → verified artifact → evaluation text
      → approved RelevanceScope snapshot (pinned version, immutable)
      → RelevanceCascade stages:
          excluded (wins over every positive signal)
          exact → vocabulary → entity → concept
          semantic (local token-overlap approximation)
          local classifier (LocalRelevanceProvider token overlap)
      → durable decision

Evaluation text is the exact verified normalized text for HTML/text/fallback
artifacts; for feed metadata artifacts it is the entry title+summary derived
from the exact persisted metadata JSON (URLs and JSON structure never
participate in matching). Terminology is honest: the "semantic" stage is a
deterministic local token-overlap (Jaccard) approximation of the existing
cascade, not an LLM.

**Persistence and idempotency.** Migration 0017 adds
`document_version_relevance`: one canonical decision per
`(document_version_id, monitor_id, scope_version)` (UNIQUE), recording the
pinned scope version + full snapshot, relevant boolean, stage, score, matched
terms, reason, algorithm (`deterministic_relevance_cascade_v1`),
`paid_used=false`, job provenance, and created time. Retries, lease recovery,
and explicit reruns all reference the canonical decision — nothing is
duplicated or silently overwritten, and history stays auditable. Article text
is never stored in the relevance record.

**Relevant vs not-relevant vs not applicable.** Both `relevant=true`
(eligible for future Phase 21 analysis) and `relevant=false` (successfully
evaluated, outside scope) are successful processing outcomes. `not_applicable`
(no Monitor provenance, or acquisition-only Monitor) is a successful outcome
without a relevance decision. Anything that prevents evaluation — missing
scope, malformed persisted scope, pinned version missing, invalid provenance,
corrupt/legacy artifact, empty scope (no positive terms) — is a terminal
failure: **COULD NOT EVALUATE RELEVANCE**, never `relevant=false`.

**Monitor activity and cadence.** A confirmed relevance (new canonical
decision with `relevant=true`) emits the existing `relevant_change` activity
row (`relevant_items=1`) and applies the existing cadence semantics (next
check drops to the policy minimum), atomically with the decision;
`relevant=false` and `not_applicable` never write activity — the
acquisition-level `changed` row stays the truthful outcome and cadence stays
cadence-neutral. Acquisition `changed` alone can never emit `relevant_change`.

### Structured article analysis (Phase 21)

Phase 21 adds structured article analysis for content already determined to be
relevant. It runs inside the existing `document_version_process` handler — no
second queue framework — and stops exactly at the candidate boundary:

```text
relevant DocumentVersion
  → verified Phase 18 artifact
  → durable relevance=true decision
  → ArticleAnalysis request (exact artifact content + pinned scope terms)
  → AIRouter → deterministic local provider (default/offline)
             → one opt-in real provider (OpenAI-compatible chat completions)
  → validated ArticleAnalysisOutput (Pydantic, bounded fields)
  → durable article_analyses record (Migration 0018) with provenance
  → processing Job succeeds
  → STOP before Evidence verification (Phase 22)
```

**Relevance gating.** Automatic analysis happens only when the canonical
Phase 20 decision is `relevant=true`. `relevant=false`, `not_applicable`, and
relevance evaluation failures all terminate processing successfully or
truthfully without ever constructing an analysis provider or making a model
call (proven by tests with call-counting providers).

**AI analysis is not evidence.** `candidate_claims` are NOT canonical
`claims` rows and `candidate_evidence_excerpts` are NOT `evidence_spans` rows;
they live only inside `article_analyses.result_json`. Phase 21 never calls
`EvidenceService`, Story evolution, Living Reports, or Alerts, and the
production diff contains no automatic `create_evidence_span` /
`create_claim` / claim-acceptance path. A candidate excerpt may even be wrong;
Phase 22 exists specifically to verify membership against the immutable
artifact.

**Input contract.** Model input comes only from
`ContentArtifactService.load_normalized_content` (the canonical verified
Phase 18 loader). Nothing re-fetches the URL, accepts `candidate_text`, or
trusts processing payload article content. HTML/text/fallback artifacts
analyze their exact normalized visible text; feed metadata artifacts analyze
the exact JSON-decoded title plus one newline plus exact JSON-decoded summary
from the persisted metadata JSON. The newline is retained when either field is
empty; when both underlying fields contain no meaningful text the canonical
view still exists but is separately ineligible for analysis. Input is
bounded by `NEWSROOM_ANALYSIS_MAX_INPUT_CHARS` (default 24,000) with
deterministic sentence/paragraph-boundary truncation; `input_char_count`,
`analyzed_char_count`, and `truncated` are persisted with the record.

**Analysis schema (`article_analysis_schema_v1`).** A strongly typed Pydantic
`ArticleAnalysisOutput` validated before anything is persisted: summary,
key_developments (1..25), entities (name + optional category), dates,
locations, significance (relative to the pinned approved scope terms),
novelty (article-level only; no Story comparison — Phase 09/23 context is not
supplied), candidate_claims (indexed, atomic, bounded 0..50), and
candidate_evidence_excerpts (candidate_claim_index + short excerpt + optional
locator hints; every index must reference an existing candidate claim),
confidence (bounded 0..1, explicitly not a calibrated probability). Malformed
JSON, wrong types, out-of-range bounds, and unknown excerpt indexes fail
validation truthfully (`AIValidationError`, terminal) and never persist.

**Prompt and injection boundary.** The production prompt is versioned
(`article_analysis_v1`, persisted with every record) and requests structured
factual output only — never chain-of-thought. The system prompt explicitly
separates SYSTEM INSTRUCTIONS, the NEWSROOM INFORMATION NEED/approved scope
terms, and the UNTRUSTED ARTICLE CONTENT (delimited with `BEGIN/END ARTICLE`
markers and treated as data, not instructions). Article text can never alter
the output schema, provider configuration, tool behavior, or policy; no
model-driven tool calling exists in Phase 21. The prompt is never persisted
or exported, and prompts/keys are redacted from logs, job errors, and exports.

**Provider architecture — one real provider.** The AIRouter is reused
unchanged: `article_analysis` is a new capability with local, paid, and
deterministic provider slots, its own `_OUTPUT_TYPES` entry, and
`RoutePolicy` budgets. Exactly one real provider exists:
`OpenAICompatibleArticleAnalysisProvider`, which calls an OpenAI-compatible
`/chat/completions` endpoint through the official `openai` SDK with an
explicit `httpx.Timeout` (connect/read/write) and bounded `max_retries`
(default 2), requests the structured JSON-schema response format, and
re-validates the response through the Pydantic contract. No multi-provider
marketplace exists; `NEWSROOM_ANALYSIS_BASE_URL` makes the adapter usable with
any OpenAI-compatible endpoint. The deterministic local provider
(`LocalArticleAnalysisProvider`) returns the exact same schema from the
verified source text — intentionally crude, honestly labeled (`provider=local`,
`model=local`), and never presented as semantic LLM analysis.

**Configuration — safe by default.** A fresh installation with no
configuration performs zero paid calls and analyzes locally. Remote use is an
explicit opt-in requiring `NEWSROOM_ANALYSIS_PROVIDER=openai` plus an API key
(`NEWSROOM_ANALYSIS_API_KEY`; the conventional `OPENAI_API_KEY` that the
openai SDK itself reads by default is accepted as a fallback — never logged),
the bundled `openai>=1.68,<2.0` SDK, the existing `budget.paid_enabled`
settings flag, and per-call budget limits
(`NEWSROOM_ANALYSIS_MAX_PAID_CALLS`, `_MAX_PAID_COST_USD`,
`_MAX_PAID_CALLS_PER_WORK`, `_MAX_PAID_COST_USD_PER_WORK`,
`_REQUEST_COST_USD`). Missing key → explicit `AIConfigurationError`
(terminal); budget disabled/exhausted → `AIDisabled` with a `blocked`
telemetry row (no provider call). Provider choice stays behind the capability
abstraction; the processing handler never instantiates a provider directly.

**Remote-call transaction boundary.** The relevance decision is persisted in
its own short write transaction before analysis; no SQLite write transaction
is held during the provider call. The validated analysis plus its telemetry
persist in a short write transaction before the handler returns, so a provider
failure never falsely records processing success, and there is no crash gap
between a successful remote analysis and its durable record (a crash after
persistence is healed idempotently by retry).

**Persistence and identity (Migration 0018, schema 18; paid invocation
hardening in Migration 0019).** `article_analyses`
stores document_version/relevance/monitor/job references, pinned scope
version, artifact id + normalized hash, `identity_hash` (UNIQUE), analysis
schema version, prompt version, provider, model, paid flag, confidence,
input/analyzed char counts, truncation flag, validated `result_json`, and
created time — never the article body and never secrets. The canonical
identity is `sha256(document_version_id, relevance_id, scope_version,
schema_version, prompt_version, provider, model)`: retries, lease recovery,
and explicit reruns reuse one analysis (duplicate protection is the UNIQUE
index, not a race-prone pre-check); a provider/model/prompt/schema change
produces a new analysis version while preserving history; nothing is silently
overwritten. Rows are immutable (append-only triggers).

**Timeout, retry, budget, telemetry.** Real network timeouts are enforced by
the provider SDK (`httpx.Timeout` connect/read/write); the router's
`Future.result(timeout=...)` remains only an outer guard with a margin.
Retryable failures (429/5xx, timeouts, connection/network errors) raise
`RetryableJobFailure` and use the existing bounded Job retry semantics;
terminal failures (invalid credentials/model, configuration, schema
validation, budget refusal) fail without retry. The SDK's own retries are
explicitly bounded by config. Every call records one `provider_usage` row via
`SQLiteTelemetrySink` (capability, route local/paid, provider, model, latency,
outcome, token usage where the provider exposes it, estimated cost — never
fabricated). Provider exceptions stored in Jobs/telemetry are sanitized:
messages never include API keys, Authorization headers, or raw response
bodies.

Before a paid provider is constructed, Migration 0019's unique
`analysis_invocations` row reserves the request and estimated cost. Its owner
lease covers the remote call and its state is completed in the same write
transaction as the durable analysis. Concurrent work waits on that identity;
uncertain remote outcomes are not automatically replayed.

**Read path.** A bounded authenticated API read path exposes analysis
metadata + validated structured result (`GET /document-versions/{id}/analyses`,
`GET /article-analyses/{id}`) without article text, prompts, or secrets.

### Relevance and scope governance

Topic scope is represented as exact terms, vocabulary, entities, concepts,
semantic terms, and explicit exclusions. The local cascade checks those layers
in order, then uses a bounded local classifier only when earlier stages do not
decide. An exclusion wins over every positive signal. Scope suggestions support
synonyms, acronyms, aliases, broader/narrower/related concepts, ambiguity, and
exclusions; pending or rejected suggestions are never included in a monitor
scope. Approved suggestions and direct vocabulary edits append a new visible
scope-history version. Since Phase 20, a Source Monitor may bind that approved
scope to its acquisition work through an explicit information need; without
one it remains acquisition-only.

### Review
Saved/dismissed/not-useful/tags plus last-reviewed revision and material-update
attention state.

### Evaluation
Labeled corpus, frozen fixtures, replay engine, metrics, baseline comparison.

## Dependency direction

```text
HTTP/UI
  -> application services
       -> domain rules
       -> repositories/interfaces
            -> SQLite/connectors/providers
```

Domain code does not import FastAPI, React, Tailscale, provider SDKs, or Windows
service code.

## Connector capabilities

Keep capabilities narrow:

- FeedDiscovery / FeedPoller
- DocumentFetcher
- PageChangeChecker
- SearchProvider
- EventRadarProvider
- EmbeddingProvider
- Reranker / EntailmentProvider (if benchmarked useful)
- LanguageModelProvider

First slice implements the minimum number of capabilities. Interfaces exist to
prevent lock-in, not to justify many providers.

## Initial schema families

The first standalone migration should include at least:

- schema_migrations
- app_meta
- settings
- users / sessions (or add auth in the dedicated auth migration before remote use)
- categories
- topics
- topic_terms
- subjects
- subject_aliases
- topic_subjects
- monitors
- monitoring_policies
- monitor_scope_history
- monitor_activity
- vocabulary_suggestions
- jobs
- job_attempts
- runs
- acquisition_events / queries or equivalent telemetry
- sources
- documents
- document_versions
- stories
- story_revisions
- story_topics
- story_subjects
- claims
- claim_state_history
- evidence_spans
- claim_evidence
- research_questions
- research_question_history / claims / evidence / attempts / notes
- research_gap_suggestions
- tags
- story_tags
- feedback_events
- provider_usage

Exact column design is finalized in the schema phase after evaluation fixture
requirements are concrete.

## Important separation: Source vs Document

Do not repeat the v1 ambiguity where one `sources` row is effectively the report.

- Source = origin identity (publisher/site/feed/API).
- Document = one canonical item/report/page.
- DocumentVersion = what was retrieved at a specific time.
- EvidenceSpan = exact material from a version.

## Story updates and resurfacing

Review state and current revision are independent.

Example:

```text
Story review_status = saved
last_reviewed_revision_id = rev_3
current_revision_id = rev_5
rev_5.material_change = true
```

UI displays `SAVED` and `NEW UPDATE`; it does not rewrite the review status.

## Scheduling model

A small scheduler tick queries due Monitors by `next_check_at` and creates jobs.
`monitors.last_result` and `last_run_at` describe the most recent ACTUAL Monitor
execution: enqueueing (or disabling a vanished target) only advances scheduling
state, so waiting work never overwrites the last recorded execution result.
Jobs have hard retry/query/model/cost budgets. Monitor policy determines next
cadence from recorded activity, bounded by the configured minimum and maximum;
no-change and error backoff, retirement, and relevant-change acceleration are
explicit state transitions. Acquisition records `changed` when content changed
but semantic relevance is not yet evaluated at acquisition time: it keeps the
current polling interval rather than accelerating to the minimum cadence
reserved for a confirmed `relevant_change`. Since Phase 20 the `changed`
outcome is only a handoff: the durable processing job evaluates the acquired
content against the approved scope and emits the genuine `relevant_change`
(cadence acceleration) only for a confirmed relevant decision, never from
the mere fact that content changed. `no_change` is recorded only for truthful
unchanged acquisition.

### Verified runtime sequence (Prompt 4 acceptance)

The Monitor runtime has been verified end-to-end through the production
composition (no test-only shortcuts):

    due Monitor
        ↓ SchedulerProcess.run_once()  (coalesced durable monitor_check)
        ↓ JobService.enqueue  (single active obligation per Monitor)
        ↓ WorkerProcess.run_once  (MonitorExecutionService handler)
        ↓ bounded acquisition  (AcquisitionService.acquire_document / poll_feed)
        ↓ canonical persistence  (Document / DocumentVersion / acquisition_events)
        ↓ truthful monitor_activity  (changed / no_change / error)
        ↓ adaptive next cadence  (record_activity → next_check_at + last_result)

Invariants proven by `tests/test_monitor_runtime_acceptance.py`:

* At most one HTTP source acquisition per scheduler tick regardless of how
  many ticks the scheduler performs.
* `no_change` is recorded only when an evidence-bearing acquisition (HTTP 200
  with matching content hash, HTTP 304, or feed with zero delta) actually
  established that content was unchanged.
* A disabled Monitor never acquires — the worker handler short-circuits to
  `disabled` without touching the network.
* Process-like restart (discard runtime objects, reconstruct against the same
  DB) recovers queued jobs and preserves dedup state.
* Rerun via the production API creates a fresh active obligation when no
  active one exists, and returns 409 when one does.
* Acquisition provenance (source_id, canonical/final URL, content hash,
  etag, last-modified, retrieval timestamps) survives through Document →
  DocumentVersion → acquisition_events.

Downstream intelligence stages are not yet wired into this pipeline: the
unattended Source → DocumentVersion loop persists canonical provenance,
and (since Phase 18) a durable normalized content artifact referenced by each
new version; since Phase 19 every changed acquisition also leaves a durable
`document_version_process` obligation, and since Phase 20 that obligation
evaluates the verified content automatically against the Monitor's approved
semantic scope and persists a deterministic relevant/not-relevant decision;
since Phase 21, relevant versions also produce a durable structured
`article_analyses` record (candidate Claims/Excerpts only). Evidence/Claims
ingestion, Story evolution, Report revision, and Alert emission remain
Phase 22+ work; article analysis never creates accepted Evidence/Claims, and
no monitor is allowed to recursively create unbounded work.

### Phase 21H pre-evidence hardening

Paid ArticleAnalysis uses the durable `analysis_invocations` reservation
ledger (migration 0019). The reservation is created before provider execution,
counts against configured global/policy/job limits, and links provider-usage
telemetry without double-counting. A unique analysis identity gives one
canonical invocation; concurrent workers converge on its durable result, while
an uncertain remote outcome blocks automatic replay until explicitly released.
The provider SDK is not treated as an idempotency authority; Newsroom's local
state machine is the authoritative duplicate-call boundary.

`validate_analysis_provenance` is a read-only, fail-closed validator for the
complete analysis chain: relevance decision, monitor and immutable scope
history, processing job payload, DocumentVersion, ContentArtifact, Source,
analysis identity, hashes/lengths, and structured result. Database integrity
checks run this validator without invoking a model.

Subject, Story, and Research Question mutations refresh only future monitor
scope snapshots in the same transaction as the mutation. Historical snapshots
remain immutable for already-pinned processing jobs.

The production HTTP transport validates each redirect hop's raw hostname and
resolved public address, connects directly to that address, verifies the peer,
and preserves the hostname for Host/SNI. This closes validation-to-connect DNS
rebinding without changing the persisted canonical URL contract.

Phase 22.1 is the bounded correction gate for the Phase 22 trusted
Evidence/Claim boundary. Automatic EvidenceSpan provenance is distinct from
manual evidence; automatic Claims begin story-less and may only receive a
controlled, audited initial Story association. No Story matching, Story
creation, Story evolution, Report, or Alert automation is introduced here.

The current applied schema is migration 0022 / schema version 22 (see
`newsroom/migrations.py`). Migration 0015 added the Phase 18 content artifact
substrate; migration 0016 added the Phase 19 processing-ownership column
(`jobs.document_version_id`), the durable result column (`jobs.result_json`),
and the obligation index; migration 0017 (Phase 20) added the Monitor
information-need association (`monitors.need_type` / `need_id`) and the
`document_version_relevance` decision table; migration 0018 (Phase 21) added
the durable `article_analyses` table with canonical identity and
provider/model/prompt/schema provenance; migration 0019 (Phase 21H) added the
durable paid analysis invocation ledger and provider-usage invocation link; the
post-audit reconciliation (Phase 17) added no migration; migration 0021 added
the original verified Evidence/Claim substrate and migration 0022 separated
manual/automatic EvidenceSpan identity, added controlled Claim Story history,
and hardened promotion outcome integrity.

Due Research Questions use a separate bounded scheduler path: each tick can
enqueue at most one durable `research_question` Job per due Question, and the
Question's attempt/query/local-model/cost budgets are checked before insertion.
There is no recursive enqueue path or open-ended research loop.

## Reports, briefings, and alerts

Living Reports are projections over the evidence ledger, not free-standing
articles. Each revision stores the exact accepted Claim set, a deterministic
Claim-set hash, closed-world audit results, section payloads, propositions, and
append-only evidence causes. A report revision can explain a material change
only through accepted Claim/Evidence Span provenance or a material Story
evolution event linked back to accepted evidence.

Briefings select material current report revisions for Monitor targets within a
daily or weekly timezone-aware window. Importance ranking is derived from
primary evidence, contradictions, corrections, corroboration, and material
updates; a unique period key makes regeneration idempotent.

Alert rules match report, Monitor, Story, or all targets and persist an alert
dedupe key, cause payload, acknowledgement state, and per-channel delivery
state. In-app delivery is durable. Browser delivery is an optional pending,
sent, denied, offline, failed, or skipped state; no email/SMS or public
publishing path is introduced.

## Product UI and PWA

The authenticated React application is a thin, responsive projection over the
canonical API. The shell groups review, configuration, and operations views in
a keyboard-accessible sidebar and uses hash routes so a reviewer can deep-link
to a surface without inventing client-only resource state. Story/Evidence and
Document views keep Claims, exact Evidence Span locators, contradictions,
revisions, timelines, lineage, and source links visible; Reports and Alerts
render their server-side provenance and delivery state.

Monitor creation, Source suggestion approval, Research Question creation,
report generation, alert acknowledgement, and notification preferences call
the existing authenticated API. The UI supplies bounded defaults for forms but
does not decide relevance, novelty, evidence support, budgets, or publication
state. Destructive operations require confirmation.

FastAPI serves the built `frontend/dist` output from the same origin as
`/api/v1`. The PWA manifest requests a standalone installable window. The
service worker caches the application shell and successful static assets, falls
back to the cached entry document when offline, and deliberately bypasses API
requests so stale domain data is never presented as authoritative. Offline mode
therefore preserves navigation and cached UI while labeling unavailable live
data explicitly.

## Local research workbench

Phase 13 keeps research retrieval local and bounded. SQLite FTS5 indexes a
typed projection of Monitors, Sources, Documents, Stories, Subjects, Claims,
Evidence, tags, Questions, and notes. Dirty-state triggers invalidate the
projection when authoritative rows change; there is no unbounded semantic
index. Document comparison, Subject context, and Monitor diagnostics return
exact Claim/Evidence/lineage references and distinguish no meaningful change
from acquisition or processing failure.

## Ask Newsroom

Phase 14 adds AskService as a closed-world answer layer above the workbench
and evidence ledger. It retrieves only indexed Newsroom objects plus direct
Report revisions, applies global or object-scoped membership, hydrates exact
Claims/Evidence/Notes, and composes structured answer statements. It never
uses arbitrary tools or outside web context.

Conversation and run rows preserve scope, prompt hash/length, retrieval
metadata, classifications, resolved citations, status, route, and cost. Raw
prompts are intentionally not stored. Citation resolution is a hard boundary:
the service refuses unsupported answers and qualifies stale, ambiguous,
conflicting, and hypothesis material. Cancellation is cooperative and hosted
escalation remains disabled by default.

## Hardening and operations

The API applies bounded request sizes and fixed-window local-client rate limits,
uses SameSite=Lax/no-store session cookies, and records only low-cardinality
privacy-preserving telemetry. Health/readiness checks distinguish liveness from
SQLite integrity and relationship validation; authenticated metrics expose
status, latency, and failed-subsystem aggregates without request/query/prompt or
article content.

Operator persistence uses SQLite's online backup API, post-backup and
post-restore integrity verification, explicit migration upgrade rehearsal, a
bounded allow-listed logical JSONL export, and filename-scoped backup retention.
Recovery procedures cover worker lease recovery, provider outage, power loss,
and clean fallback to local-only operation.

## Direct-source strategy

Publication discovery and document-change monitoring are separate capabilities.

Publication discovery: feed/API/listing/search.  
Document change: conditional GET/hash/diff/rendered fallback.

## Free/local-first sensor policy

Normal path:

1. known feeds/APIs and cheap page/listing checks;
2. event/news radar candidate if benchmarked useful;
3. local deterministic/embedding triage;
4. reliable commercial search only when evidence/coverage gap justifies it;
5. paid frontier model only after local route fails a defined quality/confidence
   gate and budget permits escalation.

SearXNG-like metasearch may be used opportunistically but must not be a single
point of monitoring reliability because upstream engines can rate-limit/block it.

## Deployment

Production is same-origin:

- FastAPI serves `/api/*` and built React assets;
- no production CORS dependency;
- Tailscale Serve exposes the local service privately;
- application authentication remains enabled;
- web and worker auto-start as explicit Windows services/tasks with bounded
  restart behavior;
- runtime data is outside `G:\Projects\Newsroom -v2`.
