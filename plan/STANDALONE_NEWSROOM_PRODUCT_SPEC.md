# Standalone Newsroom — Product Contract

Status: **Initial authority for standalone development**  
Target source workspace: `G:\Projects\Newsroom -v2`  
Predecessor/reference: `G:\Projects\hermes-newsroom`

## 1. Product decision

Standalone Newsroom is the first intended released product. Hermes Newsroom is
retained as a completed reference implementation, benchmark, and source of
proven deterministic logic; Hermes is **not** a runtime dependency, deployment
dependency, authentication boundary, scheduler, research runtime, or data owner
for the standalone product.

The product is a private, single-user, evidence-first news and event monitoring
system. It continuously maintains an evolving model of subjects and events the
user cares about, rather than merely producing periodic summaries.

## 2. Primary promise

Newsroom should answer two questions reliably:

1. **What materially changed in the things I monitor?**
2. **What evidence supports, qualifies, contradicts, or leaves unresolved the factual claims in that change?**

The signature capability is the Evidence Ledger: substantive factual assertions
in a synthesized Story must be traceable to accepted Claims, and accepted Claims
must be traceable to exact Evidence Spans from versioned retrieved Documents.

## 3. Product principles

1. **Evidence first.** Story prose is downstream of accepted claims and evidence.
2. **False merge is worse than false split.** Ambiguous event identity creates a separate Story until stronger evidence supports merging.
3. **Detect cheaply, reason expensively.** Direct feeds, deterministic checks, hashes, and local inference precede paid retrieval or frontier-model escalation.
4. **Monitoring is persistent state.** Topics, Subjects, Stories, Sources, and Research Questions can each be monitored with independent policies.
5. **Discovery and follow-up are different workflows.** Broad discovery finds candidate developments; follow-up research resolves known gaps and evolving claims.
6. **Paid operations are escalation resources.** Every paid search/model operation is budgeted, attributed, measured, and optional under normal operation.
7. **Local-first and private.** The initial release runs on the user's Windows PC and is privately reachable by LAN/Tailscale.
8. **Single-user by design.** Do not generalize prematurely for teams, tenants, organizations, RBAC, or cloud scale.
9. **Deterministic authority at persistence boundaries.** Models may interpret and propose; code validates IDs, state transitions, budgets, transactions, dedup safeguards, and persistence.
10. **Evaluation is a product subsystem.** Replayable benchmark fixtures and quality metrics are release requirements.

## 4. Explicit first-release non-goals

Do not build for the first release:

- multi-user or multi-tenant support;
- public Internet hosting;
- native iOS/Android clients;
- Kubernetes, Redis, Celery, Kafka, or microservices;
- a provider marketplace;
- simultaneous support for many LLM/search providers;
- vector database infrastructure unless benchmarks prove SQLite/local indexes insufficient;
- social posting, newsletters, or public publishing;
- automatic deletion of Topics/Subjects based on model judgment;
- full permanent archives of copyrighted article bodies;
- autonomous unbounded research loops;
- generic knowledge-graph infrastructure unrelated to monitored Stories;
- formal WCAG certification or a formal latency SLA before evidence shows either is required.

## 5. Core domain

### 5.1 Taxonomy

`Category -> Topic`

A Topic represents a broad area of interest and retains the useful v1 concepts:
name, stable slug, description, enabled state, priority, query/story budgets,
include terms, aliases, entities, excludes, and term weights.

Categories and Topics may be soft-deleted. Stable slugs do not change on rename.
Topic terms remain simple child rows; soft-delete is not required.

### 5.2 Subjects

A Subject is a durable entity worth monitoring independently from a Topic.
Examples include a person, company, product, agency, law, case, project,
technology, franchise, or organization.

Subjects have:

- canonical name;
- subject type;
- aliases;
- optional canonical identifiers/URLs;
- enabled state and priority;
- Topic relationships;
- Story relationships;
- monitoring policy.

A Subject is not merely a Topic term. Topic terms help discover; Subjects retain
identity and history.

### 5.3 Stories / Events

A Story is Newsroom's durable representation of one real-world event or
meaningful development. It can evolve through revisions.

Story lifecycle:

- `developing`
- `stable`
- `resolved`
- `archived`

Review state is separate from lifecycle. A saved/dismissed Story may later have a
material revision and require attention without losing the user's review state.

### 5.4 Sources, Documents, and Document Versions

A `Source` is a publisher/site/feed/origin identity.

A `Document` is one canonical report/page/item identified by canonical URL or an
equivalent source-native identifier.

A `DocumentVersion` is the retrieved state of that Document at a specific time.
Evidence never points merely to a mutable URL; it points to a DocumentVersion.

DocumentVersion stores sufficient provenance to know what Newsroom actually saw,
including retrieval time and normalized content hash. Long-lived storage of full
article bodies is not a first-release requirement; evaluation fixtures may retain
minimal permitted snapshots needed for deterministic replay.

### 5.5 Evidence Spans

An Evidence Span identifies the exact material used to evaluate a Claim.
Minimum data:

- document_version_id;
- exact excerpt or structured value;
- locator type/value where available (paragraph, section, timestamp, offsets,
  JSON pointer, page number, etc.);
- span hash;
- created_at.

### 5.6 Claims

A Claim is an atomic substantive proposition associated with a Story.

Initial Claim states:

- `pending`
- `supported`
- `partially_supported`
- `disputed`
- `unsubstantiated`
- `superseded`

`unsubstantiated` does **not** mean false. It means Newsroom lacks sufficient
support. Contradiction is represented by actual contradicting evidence.

Accepted Claim text is immutable. A materially corrected proposition creates a
new Claim linked through supersession. Claim state may change as new evidence is
added, with state history preserved.

Claim-to-evidence relationships initially support:

- `supports`
- `contradicts`
- `contextualizes`

Source quality, source primariness, and evidence relationship are distinct.

### 5.7 Story Revisions

Headline, summary, why-it-matters, and material-change status belong to Story
revisions so the system can distinguish what the user reviewed from what changed
later.

A review record stores the last reviewed revision. A newer material revision can
surface `NEW UPDATE` without changing a saved Story back to `new`.

### 5.8 Research Questions

A Research Question is a persistent unresolved information need. It can originate
from a Story, Claim, Subject, or user action.

Minimum first-release representation:

- question;
- origin type/id;
- priority;
- status: `open`, `resolved`, `abandoned`;
- search-attempt budget;
- last_attempt_at / next_attempt_at;
- resolution note / linked evidence when resolved.

Automatic generation/pursuit can grow after the object and manual workflow are
proven.

### 5.9 Monitors

A Monitor means: **check whether something material has changed or whether a
specific information need can now be resolved.**

Required monitor targets:

- Topic
- Subject
- Story
- Source
- Research Question

Monitor target is separate from acquisition channel. A Monitor references a
policy that determines cadence, channels, and budgets.

### 5.10 Monitoring policies

A Monitoring Policy contains:

- allowed acquisition channels;
- base cadence;
- minimum/maximum cadence;
- priority;
- query/search budget;
- paid budget;
- escalation rules;
- backoff rules;
- retirement criteria.

No provider name belongs in core domain semantics where a capability name will
do.

## 6. Acquisition / sensor principles

Preferred hierarchy for discovering new publications from a known source:

1. RSS/Atom or official structured feed/API;
2. structured listing/sitemap;
3. lightweight HTML listing fetch;
4. general/semantic web search fallback.

Preferred hierarchy for checking whether an already-known document changed:

1. conditional HTTP using ETag/Last-Modified;
2. normalized content hash;
3. structured/DOM comparison;
4. rendered browser diff only where needed.

WebSub is optional because a private Tailscale/LAN deployment is not inherently
reachable by public WebSub hubs. It must not become a first-release dependency
without a safe callback strategy.

Initial broad-discovery candidates to benchmark include RSS/direct sources,
GDELT, a best-effort self-hosted metasearch channel, and exactly one reliable
commercial search escalation provider. Provider selection is an empirical
decision, not a product invariant.

## 7. Research pipeline

The intended logical pipeline is:

1. due Monitor -> Research Job;
2. discovery/follow-up plan;
3. cheap/direct sensor acquisition;
4. deterministic candidate normalization and URL identity;
5. local relevance/semantic triage;
6. targeted escalation only if needed;
7. Document / DocumentVersion persistence;
8. candidate Story retrieval;
9. conservative event resolution;
10. atomic Claim extraction;
11. Evidence Span extraction;
12. Claim-Evidence linking;
13. contradiction/corroboration assessment;
14. Claim-state update;
15. unresolved evidence-gap generation;
16. Story revision synthesis from accepted Claims only;
17. material-change decision;
18. quiet update or UI resurfacing;
19. cost/latency/evaluation telemetry.

### Closed-world synthesis invariant

The Story synthesizer may not introduce a substantive factual proposition that
is absent from the accepted Claim set used for that revision. The implementation
must make this auditable, not merely prompt-based.

## 8. Event identity

Embeddings and lexical/entity/temporal signals retrieve plausible existing Story
candidates. They do not independently decide real-world event identity.

Final merge logic must combine:

- canonical URL/document identity;
- temporal compatibility;
- entity/subject overlap;
- semantic similarity;
- event attributes;
- deterministic exclusions;
- model adjudication only for ambiguous candidates;
- conservative thresholding.

Ambiguity -> new Story / later reconciliation.

## 9. AI architecture

Architecture is a cascade, not a fixed set of named models:

1. deterministic code;
2. local embeddings/reranking/classifiers;
3. local language model;
4. paid/frontier model escalation only when policy and value justify it.

Tasks should be benchmark-assigned. Do not freeze a specific model family or an
arbitrary percentage of API escalations before evaluation.

All providers expose narrow capability interfaces. The first vertical slice has
one implementation per needed capability.

## 10. Cost contract

Normal external-service operating target: approximately **$0/month** where
practical.

Initial optional escalation target: approximately **$0–5/month**, configurable
and hard-capped.

Every paid operation records:

- provider/capability;
- Monitor and/or Research Question attribution;
- request type;
- token/query units when available;
- estimated/actual cost;
- latency;
- outcome/usefulness.

No autonomous component may exceed a configured budget by silently retrying.

## 11. Persistence and runtime

Initial persistence: SQLite with WAL, foreign keys, busy timeout, explicit write
transactions, short-lived connections, online backups, migration ledger, and
integrity checks.

Initial runtime:

- one FastAPI web/API process;
- one durable worker process;
- SQLite-backed job queue and scheduler state;
- React/TypeScript PWA built to static assets and served from the same origin;
- Tailscale Serve for private remote access;
- application-level local authentication.

No Redis/Celery unless measured queue/concurrency needs exceed SQLite.

## 12. Durable jobs

Jobs are persistent and restart-safe. Minimum states:

- `queued`
- `running`
- `succeeded`
- `partial`
- `failed`
- `cancelled`

Workers claim jobs transactionally with a lease. Expired leases are recoverable.
Retries are bounded and recorded as attempts. Research execution never depends on
an HTTP request remaining open.

## 13. Authentication and security

Initial product is single-user but still authenticated.

Requirements:

- password stored with Argon2id or equivalent modern password hashing;
- HTTP-only session cookie;
- SameSite policy appropriate to same-origin app;
- CSRF protection for mutations;
- login throttling;
- no secrets in database export;
- secrets outside the repository;
- no raw traceback/path leakage to the browser;
- no arbitrary subprocess/provider invocation from request-controlled strings;
- private Tailscale/LAN exposure by default.

## 14. Product UI

Required first-release views:

- Inbox
- Story Detail / Evidence
- Saved
- History
- Topics
- Subjects
- Sources / Watches
- Research Questions
- Runs / Jobs
- Settings / Cost

Story Detail / Evidence is the signature view. It must expose Claims, Claim state,
exact evidence, source/document provenance, contradictions, and revision history
without requiring the user to trust generated prose.

## 15. Evaluation contract

The project must maintain a human-labeled evaluation corpus with difficult real
cases including:

- simple official announcements;
- many reports of one event;
- similar-but-distinct events;
- evolving breaking stories;
- rumors;
- conflicting reporting;
- corrections;
- official vs secondary evidence;
- multi-Topic stories;
- low-quality aggregation;
- stale reports;
- missing primary evidence.

Metrics include:

- important-Story recall;
- irrelevant Story rate / precision;
- false merge;
- false split / duplicate rate;
- time-to-first-discovery;
- primary-source discovery;
- important-Claim recall;
- citation/evidence correctness;
- unsupported synthesized proposition rate;
- contradiction detection;
- evidence coverage;
- search/model calls per useful Story;
- cost per useful Story;
- cost per resolved Research Question;
- latency;
- user usefulness.

Retrieval fixtures are frozen for deterministic replay so model/prompt/pipeline
changes can be compared without live-web drift.

## 16. Release standard

Standalone Newsroom may be considered ready for first release only when:

1. it materially improves the agreed research/evidence metrics over the v1
   reference and human-labeled baseline;
2. citation/evidence correctness meets the threshold established after baseline
   measurement;
3. unsupported synthesized claims and false merges remain below agreed limits;
4. unattended monitoring survives restart/power-loss simulations;
5. phone/PWA access works through private persistent deployment;
6. authentication, backup, restore, and integrity verification pass;
7. budget controls prevent unbounded paid usage;
8. representative scale and queue tests pass;
9. the system can run in a useful free/local mode when commercial providers are
   unavailable;
10. the source tree is clean and the released build is tied to an accepted commit.
