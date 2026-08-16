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
Persistent gaps that can generate targeted follow-up jobs.

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
The worker claims queued jobs with a lease. Jobs have hard retry/query/model/cost
budgets. Monitor policy determines next cadence from recorded activity, bounded
by the configured minimum and maximum; no-change and error backoff, retirement,
and relevant-change acceleration are explicit state transitions.

No monitor is allowed to recursively create unbounded work.

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
