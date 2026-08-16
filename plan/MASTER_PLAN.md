# Standalone Newsroom — Master Build Plan

Status: **Execution planning authority after acceptance**  
Product authority: `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md`  
Porting evidence: `docs/PORTING_AUDIT.md`  
Target source workspace: `G:\Projects\Newsroom -v2`

## 0. Executive decision

Build the next Newsroom directly as a **fully standalone** application. Do not
build a hybrid Hermes runtime. The completed Hermes implementation is retained as
a reference/benchmark and source of proven deterministic behavior only.

The implementation strategy is not "rebuild v1 and add evidence later." The
first meaningful vertical slice must already demonstrate:

```text
Monitor -> discovery -> DocumentVersion -> Story resolution
        -> atomic Claim -> exact Evidence Span
        -> Claim state -> evidence-bound Story revision
```

If that pipeline does not improve research quality, broader product work pauses.

## 1. Authority and change control

When implementation details conflict:

1. `STANDALONE_NEWSROOM_PRODUCT_SPEC.md` controls product invariants.
2. This `MASTER_PLAN.md` controls sequence and engineering gates.
3. ADR/decision records document evidence-based implementation changes.
4. Current code/test evidence may supersede stale implementation assumptions but
   may not silently change product invariants.

Any change to the closed-world synthesis rule, false-merge policy, cost contract,
or standalone runtime decision requires an explicit ADR.

## 2. Repository / runtime boundaries

### Canonical source

`G:\Projects\Newsroom -v2`

No runtime database, logs, secrets, model cache, backups, or downloaded article
content live in the Git repository.

### Suggested runtime roots

Use explicit environment roots rather than Hermes-style profiles:

```text
%LOCALAPPDATA%\Newsroom\dev
%LOCALAPPDATA%\Newsroom\prod
```

Operator scripts always require an explicit environment (`dev` or `prod`) and
resolve the canonical root themselves. A pre-existing environment variable must
never silently redirect a command to another environment.

Tests always use temporary directories/databases.

### Git discipline

- one coherent local checkpoint commit per accepted phase;
- no production deployment from a dirty tree;
- record the exact acceptance commit;
- no migration rewriting after it has been used on persistent data;
- no generated runtime data committed.

## 3. Bootstrap already completed in this scaffold

The new repo has been initialized independently and contains:

- standalone package marker;
- standalone path resolution;
- standalone SQLite connection/transaction/backup baseline;
- v1 URL normalization;
- v1 headline similarity;
- v1 event-signature logic;
- v1 conservative dedupe decision engine;
- their copied regression tests plus standalone storage tests;
- v1 implementation report/README as reference material;
- evaluation directory structure.

These were copied from canonical v1 Git HEAD where appropriate, not from
Hermes-installed output.

This is deliberately a **thin bootstrap**, not a port of the Hermes app.

# PHASE 0 — Evidence and Benchmark Foundation

## Goal

Establish how v2 will be judged before building substantial new orchestration.

## Work

### 0.1 Build the evaluation data contract

Define JSON schemas for:

- evaluation case;
- monitored target(s);
- retrieval fixture manifest;
- candidate Documents;
- gold Story/Event grouping;
- gold important Claims;
- gold Evidence Spans;
- contradictions;
- expected primary/authoritative sources;
- known noise/non-events;
- reviewer notes.

### 0.2 Construct initial corpus

Start with 30–50 high-quality cases, then grow toward 100. Pull from:

- actual v1 Topics and results;
- official announcements;
- multi-outlet stories;
- similar-but-distinct developments;
- breaking/evolving reports;
- rumors and later confirmation;
- contradictions/corrections;
- stale/aggregated noise;
- cross-Topic stories.

Do not bulk-save copyrighted articles. Store only permitted/minimum fixture data
needed for replay, plus URL/provenance.

### 0.3 Score v1 baseline where comparable

Measure v1 for:

- important Story recall on recoverable cases;
- irrelevant Story rate;
- false merges;
- duplicate/split behavior;
- source/primary-source discovery;
- time-to-discovery where historical timing is known;
- user usefulness.

Evidence-specific metrics are scored against human gold and may be applied
retrospectively to factual statements in v1 output where possible.

### 0.4 Define metric implementation

Implement reproducible metrics for:

- event precision/recall;
- false merge / false split;
- claim recall/precision;
- evidence/citation correctness;
- unsupported synthesized proposition rate;
- contradiction detection;
- evidence coverage;
- cost/request/model telemetry.

### 0.5 Freeze retrieval/replay format

A replay must be able to run downstream logic without live web access. Store
provider response metadata, retrieval timestamps, permitted normalized source
content/minimal excerpts, and hashes.

## Exit gate

- corpus schema documented and validated;
- >=30 labeled cases;
- at least one replay case executes deterministically;
- baseline scoring command produces repeatable output;
- initial v1 baseline recorded;
- no major architecture code beyond what evaluation needs.

# PHASE 1 — Standalone Foundation + Data Model

## Goal

Create the minimum reliable application shell and v2 schema without yet building
broad monitoring.

## Backend

- Python 3.11+ project;
- FastAPI app factory;
- structured configuration;
- same-origin static frontend mounting placeholder;
- canonical API error envelope;
- request IDs / structured logging;
- health/readiness endpoints;
- no Hermes imports.

## Persistence

Create standalone migrations and repository boundaries for:

- meta/settings;
- taxonomy;
- Subjects;
- Sources/Documents/DocumentVersions;
- Stories/StoryRevisions;
- Claims/Evidence/Claim history;
- Research Questions;
- Monitors/Policies;
- Jobs/Attempts/Runs;
- review/tags/feedback;
- provider usage.

Do not port the v1 migration as migration 0001. This is a new product schema.

## Runtime path/config safety

Implement explicit dev/prod roots and operator guards before any live service
installation. Configuration precedence must be deterministic and testable.

## Frontend shell

- React + TypeScript;
- normal npm build, no Hermes SDK;
- static production output served by FastAPI;
- routing/layout/theme foundation;
- no second production web server requirement.

## Exit gate

- fresh DB migrates from zero;
- migration rerun is idempotent;
- FK/WAL/integrity tests pass;
- API health runs independently of Hermes;
- frontend builds and is served same-origin;
- source/runtime separation verified;
- full tests green.

# PHASE 2 — Evidence-First Research Vertical Slice

## Goal

Prove the signature v2 workflow before broad product expansion.

## Scope

Use one or a few manually selected Topics/Subjects and one deliberately limited
retrieval path. Manual Run is sufficient. No full adaptive scheduler yet.

## Pipeline

1. create/select a Topic or Subject Monitor;
2. execute a discovery query/feed pull;
3. normalize candidate URL/document identity;
4. retrieve source content;
5. persist Source, Document, DocumentVersion;
6. retrieve plausible Story candidates using v1 deterministic signals plus an
   initial semantic signal if available;
7. conservative event decision;
8. extract atomic Claim candidates;
9. identify exact Evidence Spans;
10. persist Claim-Evidence relationships;
11. evaluate support/contradiction/unsubstantiated state;
12. synthesize one StoryRevision strictly from accepted Claims;
13. verify every factual sentence maps to Claim IDs;
14. render Story Detail / Evidence in the UI.

## Closed-world enforcement

Do not rely solely on the synthesis prompt. Persist the Claim set supplied to the
writer and run a post-synthesis proposition/citation audit. A failed audit blocks
publication of the revision or marks it invalid for evaluation.

## Research Questions

Implement the basic object now. At minimum the user/system can record an open
question from a Claim and resolve/abandon it manually. Automatic retries are
later.

## Exit gate — first major product gate

On the evaluation subset:

- exact Evidence can be opened for every accepted Claim;
- changed source versions do not rewrite historical Evidence;
- contradictions can coexist without forced resolution;
- unsubstantiated != contradicted;
- generated Story prose introduces no known unsupported factual propositions;
- false-merge policy remains conservative;
- replay produces equivalent ledger output for the same fixture;
- user can inspect why a Story says what it says.

If this does not work convincingly, **do not proceed to broad monitoring/UI**.

# PHASE 3 — Monitoring and Free Sensor Layer

## Goal

Turn one-off research into persistent low-cost monitoring.

## Monitor types

Implement:

- Topic Monitor;
- Subject Monitor;
- Story Monitor;
- Source Monitor;
- Research Question Monitor.

## Policy engine

Each policy controls:

- cadence/backoff;
- permitted channels;
- priority;
- max retrieval/search attempts;
- max local-model calls;
- paid escalation allowance;
- retirement/expiration rules.

## Initial sensor capabilities

### Build first

- RSS/Atom polling;
- direct HTTP fetching with conditional requests;
- official/simple JSON APIs through connector interface;
- listing/sitemap discovery where useful;
- deterministic page/document change hashing;
- one broad-news radar candidate if the Phase-0 benchmark justifies it;
- one reliable web-search escalation connector.

### Benchmark / optional

- GDELT;
- SearXNG or other metasearch;
- RSSHub;
- changedetection.io integration.

Do not make best-effort metasearch a reliability-critical dependency.

### Defer

WebSub until Newsroom has a safe callback design compatible with private
Tailscale-first deployment.

## Candidate normalization

All sensors emit a provider-neutral candidate contract. Domain services never
care whether a candidate came from RSS, GDELT, Brave, an API, or a page watch.

## Exit gate

- each required Monitor type can become due and create a bounded job;
- RSS/direct source monitoring works with no paid services;
- unchanged documents stop before AI processing;
- acquisition channel failures do not corrupt Monitor state;
- all paid-capable calls can be disabled globally;
- useful $0-mode monitoring demonstrated for representative Topics.

# PHASE 4 — Durable Scheduler, Jobs, and Cost Control

## Goal

Make monitoring unattended and restart-safe.

## Jobs

Implement durable SQLite-backed jobs with:

- queued/running/succeeded/partial/failed/cancelled;
- transactional claim;
- lease owner / lease expiry;
- bounded attempts;
- idempotency key where appropriate;
- next retry time;
- structured failure cause;
- parent Monitor/Research Question attribution.

## Scheduler

One scheduler loop selects due Monitors and enqueues jobs. It does not perform
research itself.

Cadence may adapt based on:

- target type;
- priority;
- recent activity;
- Story lifecycle;
- unresolved high-value question;
- recent repeated no-change result;
- cost budget.

No adaptive behavior may violate hard min/max cadence or budget limits.

## Cost ledger

Record provider usage for every external/model operation. Support:

- global daily/monthly cap;
- per-policy cap;
- per-job cap;
- per-Research-Question cap;
- hard disable of paid providers;
- alert/report when budget is exhausted.

Budget exhaustion is a controlled outcome, not a retryable failure loop.

## Exit gate

- kill worker mid-job -> lease recovery succeeds;
- duplicate scheduler tick does not create duplicate unbounded work;
- retry caps enforced;
- paid budget hard stop verified;
- app restarts with queued/running work in truthful state;
- SQLite remains sufficient under representative concurrency.

# PHASE 5 — Event Resolution and Story Evolution

## Goal

Improve v1 Story identity without surrendering event identity to embeddings/LLMs.

## Candidate retrieval

Use multiple cheap signals:

- canonical URL/document match;
- headline/text normalization;
- time window;
- Topic overlap;
- Subject/entity overlap;
- event signature;
- local embeddings;
- optionally reranker.

Retrieve a small set of plausible Stories.

## Final decision

Apply deterministic exclusions and pairwise assessment. Use a local/model
adjudicator only for ambiguous top candidates. Confidence below merge threshold
creates a new Story.

## Update classes

Classify incoming material as:

- duplicate evidence;
- corroboration;
- contradiction;
- minor update;
- material update;
- new Event.

## Story lifecycle and resurfacing

Implement developing/stable/resolved/archived state and adaptive monitoring.
Persist StoryRevision and last-reviewed revision. Material revisions can resurface
reviewed Stories without losing saved/dismissed/not-useful state.

## Exit gate

- false-merge rate meets agreed evaluation threshold;
- corrections create versioned Claims/Story revisions rather than rewriting
  history;
- corroboration can strengthen Claim state without unnecessary Inbox duplication;
- contradictions trigger attention/research gaps;
- reviewed Story resurfacing behaves correctly.

# PHASE 6 — AI / Local Model Benchmark and Routing

## Goal

Assign model capabilities empirically and keep normal cost near zero.

## Benchmark tasks separately

- relevance;
- entity/Subject linking;
- query generation;
- event match adjudication;
- update classification;
- Claim extraction;
- Evidence-span extraction;
- entailment/contradiction;
- research-gap generation;
- Story synthesis.

Compare:

- deterministic baselines;
- local embeddings;
- local reranker/NLI/classifier where applicable;
- one local LLM runtime/model;
- one frontier escalation option.

Do not freeze model names in architecture before these results.

## Router requirements

The router records:

- task type;
- model/provider;
- confidence/decision signal;
- latency;
- token/compute/cost metadata;
- escalation reason.

Paid escalation must require both policy permission and remaining budget.

## Exit gate

- routing policy is backed by benchmark results;
- local route handles the bulk of normal monitoring economically;
- frontier escalation demonstrates measurable incremental value on difficult
  cases;
- no provider is adopted merely for completeness.

# PHASE 7 — Full Review Product / PWA

## Goal

Turn the validated research system into the complete single-user product.

## Inbox

- category/topic/subject filtering;
- Story cards rendered once under overlapping filters;
- importance / lifecycle / evidence-health indicator;
- source summary;
- review actions;
- `NEW UPDATE` indicator for reviewed Stories with material newer revision.

## Story Detail / Evidence

Signature interface:

- Story revision summary;
- Claim list/state;
- evidence count/quality/independence clues;
- exact evidence reveal;
- contradiction comparison;
- source/document/version provenance;
- Claim history and supersession;
- open Research Questions;
- Story revision timeline.

## Saved / History

Port v1 review semantics and add revision-awareness.

## Topics / Subjects / Sources

Full administration of taxonomy, Subjects, source watches, monitor policies,
priority, cadence and budgets.

## Research Questions

View/filter/create/resolve/abandon questions; optionally trigger bounded manual
research.

## Runs / Jobs / Cost

Expose:

- scheduler/worker health;
- current jobs;
- run history;
- failures/retries;
- next due monitors;
- paid/free usage;
- Run Now/manual monitor trigger;
- pause/resume at global/Monitor level where safe.

## PWA/accessibility

Responsive desktop/phone/tablet, keyboard-complete core workflow, visible focus,
semantic controls, non-color-only state, installable PWA where browser permits.

## Exit gate

- complete primary workflow on desktop and phone;
- no evidence/provenance information hidden behind desktop-only affordances;
- review state persists across restarts and Story updates;
- error/loading/empty/offline states truthful;
- frontend build/typecheck/tests green.

# PHASE 8 — Security, Operations, and Private Deployment

## Goal

Make the app safe/reliable for unattended private use.

## Authentication

- one local administrator account;
- Argon2id password hash;
- HTTP-only secure session;
- CSRF defense;
- login throttling;
- session expiry/logout;
- recovery procedure documented.

## Deployment

- FastAPI serves API + static React same origin;
- Tailscale Serve for private remote access;
- no Funnel/public ingress in initial release;
- explicit Windows auto-start for web and worker;
- health/restart verification;
- no dependency on interactive desktop login if practical.

Evaluate Windows Service mechanisms during this phase; choose the simplest
supported option based on reliability tests rather than freezing NSSM/sc.exe now.

## Operations tooling

Build explicit-environment scripts for:

- install/update;
- start/stop/status;
- verify;
- backup;
- restore;
- export;
- database integrity;
- logs/diagnostics;
- uninstall retaining data by default.

Restore procedure:

1. stop writers;
2. preserve current recovery copy;
3. restore online-backup DB;
4. do not restore stale WAL/SHM;
5. migrate forward if needed;
6. integrity/schema/count checks;
7. restart worker/web;
8. resume scheduler only after verification.

## Exit gate

- reboot/restart tests pass;
- worker/web crash recovery pass;
- private phone access works;
- authentication/CSRF/session tests pass;
- online backup and isolated restore pass;
- explicit dev/prod environment targeting cannot cross-write;
- secrets absent from export/repo/logs.

# PHASE 9 — Provider/Sensor Optimization

## Goal

Add only the external services that measured gaps justify.

Run controlled comparisons for serious candidates. Measure:

- incremental important-Story recall;
- primary-source discovery;
- unique useful Story yield;
- irrelevant candidate rate;
- latency/reliability;
- extraction success;
- cost per useful Story / resolved question.

Possible candidates include GDELT, Brave Search, Exa, Tavily, SearXNG, RSSHub,
Media Cloud or others found useful at implementation time.

No provider enters the default runtime solely because it has a free tier. Pricing
and quotas are configuration/operations facts, not architecture invariants.

## Exit gate

Every enabled default provider has a written evidence-backed reason to exist.
The system remains useful when all optional paid providers are disabled.

# PHASE 10 — v1 Data Reuse / Import (Optional Before Launch)

## Goal

Decide deliberately whether any Hermes-era data is worth carrying into the first
released standalone database.

Options:

1. clean launch database;
2. taxonomy only;
3. taxonomy + selected Saved Stories;
4. full logical v1 export import.

Do not copy the v1 SQLite file directly into the new schema.

If importing legacy Stories, mark evidence provenance honestly. Existing v1
Story/Source relationships do not become retroactive Claim-level evidence simply
because v2 supports a ledger.

Optional enrichment can research selected legacy Stories later.

## Exit gate

- dry-run report;
- relationship/count validation;
- no fabricated historical Evidence;
- backup before import;
- rollback proven.

# PHASE 11 — First-Release Acceptance

## Stage A — development acceptance

Required end-to-end tests include:

1. create Topic/Subject/Source monitors;
2. receive free/direct signal;
3. discover candidate event;
4. retrieve/version Documents;
5. create/merge Story conservatively;
6. extract Claims/Evidence;
7. identify contradiction/evidence gap;
8. resolve a Research Question;
9. create evidence-bound Story revision;
10. review/save/dismiss/not-useful/tag;
11. receive material update and resurface correctly;
12. restart during queued/running work;
13. exhaust a budget safely;
14. paid provider unavailable;
15. free sensor unavailable;
16. backup/restore/export;
17. phone/PWA access;
18. authentication/session/CSRF failure cases;
19. representative scale/performance;
20. full evaluation-corpus run.

Stage A records an exact clean Git commit.

## Stage B — first-release environment

Deploy exactly the accepted commit into the explicit production runtime root.
Run controlled smoke monitoring, Evidence UI check, auth check, integrity check,
backup, worker/scheduler verification and phone/Tailscale access.

Any application code change after Stage A invalidates affected acceptance gates.

# 4. Initial API shape (subject to Phase 1 schema confirmation)

Use `/api/v1` from the beginning.

Likely resources:

```text
/auth/*
/status
/settings
/categories
/topics
/subjects
/sources
/monitors
/research-questions
/stories
/stories/{id}/revisions
/stories/{id}/claims
/claims/{id}/evidence
/documents/{id}/versions
/jobs
/runs
/provider-usage
/tags
/export
/backup/status (read-only status; backup execution may remain operator action)
```

Mutations use canonical errors and explicit nullable semantics. Long-running
research endpoints enqueue jobs and return job identity; they do not hold the
HTTP request until research completes.

# 5. Data model decisions to preserve during schema design

1. Source != Document != DocumentVersion.
2. Evidence always references DocumentVersion.
3. Claim text immutable after acceptance; corrected propositions supersede.
4. Claim state changes have history.
5. Story prose is revisioned.
6. Review status independent from Story lifecycle/revision attention.
7. Monitor target independent from acquisition channel/provider.
8. Job state persistent/restart-safe.
9. Paid usage attributable to work that caused it.
10. Subjects first-class, not just strings on Topics.
11. Research Questions persistent first-class objects.
12. Event merge conservative and auditable.

# 6. Porting strategy from Hermes v1

## Already ported

- URL normalization;
- headline similarity;
- event-signature helpers;
- conservative dedupe baseline;
- associated tests;
- adapted SQLite transaction/backup primitives.

## Port next only when receiving subsystem exists

- taxonomy invariants/tests;
- review/tag transaction semantics;
- streamed export patterns;
- backup/restore verification;
- scale fixture logic.

## Never port as dependency

- Hermes plugin loader;
- Hermes tools/skill;
- Hermes Cron/scheduler adapter;
- Hermes Dashboard SDK/auth;
- HERMES_HOME profiles;
- plugin installer/doctor scripts.

# 7. Build-now / later / defer / reject

## BUILD NOW

- evaluation corpus/replay;
- standalone schema/foundation;
- Evidence Ledger vertical slice;
- one retrieval path;
- one local AI path;
- conservative Story resolution;
- basic Research Questions;
- core evidence UI.

## BUILD AFTER EVIDENCE VALIDATION

- all monitor types;
- adaptive scheduler;
- multiple free sensors;
- full review UI;
- local model cascade optimization;
- durable deployment/security;
- provider comparison.

## DEFER

- WebSub public callbacks;
- v1 historical import until launch decision;
- sophisticated graph visualization;
- advanced automated question generation;
- cloud hosting;
- notifications beyond the app;
- formal mobile-native app;
- multi-user.

## DO NOT BUILD WITHOUT MEASURED NEED

- Redis/Celery/Kafka;
- vector DB;
- microservices;
- generic provider marketplace;
- many simultaneous search APIs;
- automatic open-ended agent loops;
- Hermes hybrid runtime;
- public Internet exposure.

# 8. Principal risks and controls

## Evidence looks precise but is wrong

Control: human-labeled citation entailment tests; exact spans; versioned documents;
post-synthesis audit; contradiction cases.

## False event merges

Control: conservative candidate pair assessment; deterministic exclusions;
ambiguity -> split; dedicated false-merge corpus.

## Monitoring becomes noisy/expensive

Control: cheap sensors first; candidate triage; Monitor policies; hard budgets;
backoff; lifecycle retirement.

## Local AI underperforms

Control: benchmark tasks independently and permit targeted paid escalation rather
than replacing the entire local-first architecture.

## Free search sources are unreliable

Control: no single best-effort provider is required for correctness; direct
sources + multiple optional sensors + reliable escalation interface.

## Source pages mutate

Control: DocumentVersion and EvidenceSpan provenance/hashes.

## SQLite queue contention

Control: short transactions, one worker initially, WAL, representative load test;
upgrade infrastructure only on measured contention.

## Windows process reliability

Control: explicit service/auto-start phase, crash/reboot tests, durable jobs,
health endpoints and private remote verification.

## Scope creep

Control: Phase-2 evidence gate before product expansion; provider additions require
metric justification; explicit non-goals.

# 9. Immediate next execution steps

The next coding session should do **Phase 0 only**, plus the minimum schema design
needed to represent evaluation labels. Specifically:

1. inspect the v1 database/export and select 30–50 representative evaluation
   cases without mutating v1;
2. define evaluation case/fixture schemas;
3. implement replay loader and metric skeleton;
4. record v1 baseline where measurable;
5. write ADR-001: Fully Standalone / Hermes Reference Only;
6. write ADR-002: Evidence-First Vertical Slice Before Broad Product Build;
7. then produce the Phase-1 schema plan for review.

Do not start building all connectors, scheduler automation, or full PWA before the
Phase-0 corpus and Phase-2 evidence gate are defined.
