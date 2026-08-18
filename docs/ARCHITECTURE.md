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

### Relevance and scope governance

Topic scope is represented as exact terms, vocabulary, entities, concepts,
semantic terms, and explicit exclusions. The local cascade checks those layers
in order, then uses a bounded local classifier only when earlier stages do not
decide. An exclusion wins over every positive signal. Scope suggestions support
synonyms, acronyms, aliases, broader/narrower/related concepts, ambiguity, and
exclusions; pending or rejected suggestions are never included in a monitor
scope. Approved suggestions and direct vocabulary edits append a new visible
scope-history version.

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
but semantic relevance is not yet evaluated: it keeps the current polling
interval rather than accelerating to the minimum cadence reserved for a
confirmed `relevant_change`. `no_change` is recorded only for truthful unchanged
acquisition.

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
unattended Source → DocumentVersion loop stops after canonical persistence
(and, since Phase 18, the durable normalized content artifact referenced by
each new version), and automatic relevance, article analysis, Evidence/Claims
ingestion, Story evolution, Report revision, and Alert emission are Phase 20+
work. No monitor is allowed to recursively create unbounded work.

The current applied schema is migration 0015 / schema version 15 (see
`newsroom/migrations.py`). Migration 0015 added the Phase 18 content artifact
substrate; the post-audit reconciliation (Phase 17) added no migration.

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
