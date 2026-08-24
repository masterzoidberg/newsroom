# PHASE 24 — INTELLIGENT MONITORING

## Unified Watches, Vocabulary Intelligence, and Source Discovery

---

# 0. RECONCILIATION ADDENDUM — post-Phase-23 repository audit

> This section was written **after** inspecting the repository at the accepted
> Phase 23 checkpoint (`52ab0ad`). It resolves the open architecture questions
> that §4, §5, §73, and §89 delegate to implementation. Where it conflicts with
> the generic guidance below, **this section wins**.

## 0.1 Phase 23 verification result

Phase 23 was independently re-verified before Phase 24 work continued:

```text
[PASS] Phase 22.3 + 23A-E suites          23 passed
[PASS] scripts/live_test_c.py             status=passed, integrity=ok
[PASS] Live Test C replay                 exact_logical_identities_unchanged
[PASS] external network / provider calls  0 / 0
```

No Phase 23 defects were found. The Phase 23 Summary's claims are backed by the
committed implementation (`automatic_story_resolution.py`, `story_automation.py`,
`report_automation.py`, `alert_automation.py`, and the checkpoint-ownership
integrity checks in `integrity.py`). **Phase 24 is unblocked.**

## 0.2 Architecture decision — Watch is a new durable object over Monitor

Of the three options in §5, the repository supports **option C**:

```text
Watch  = durable user monitoring intent (new table)
Monitor = existing durable acquisition/scheduling unit (unchanged role)

one Watch --< watch_sources >-- one source Monitor per approved Source
```

Rationale:

* `Monitor` is already load-bearing for Phases 8, 19, 20, 21, and 23 (scope
  pinning, job ownership, cadence, relevance provenance). Overloading it with
  user-facing intent would have put product naming on a trust-critical record.
* A Watch needs vocabulary, Source candidates, and discovery policy, none of
  which belong on a scheduling row.
* Acquisition therefore still flows through exactly one path. **No new
  acquisition, relevance, analysis, or evidence path is introduced.**

## 0.3 Monitor identity changed — per-need Monitors (migration 0024)

This is the one material schema deviation from the plan as written.

The plan requires (§16, §94, acceptance gate) that **multiple Watches share a
Source**. That was impossible under the pre-existing constraint:

```text
monitors UNIQUE(target_type, target_id)   -- one Monitor per Source, globally
```

Migration 0024 rebuilds `monitors` and replaces that table constraint with two
partial unique indexes:

```sql
UNIQUE(target_type, target_id)                        WHERE need_type IS NULL
UNIQUE(target_type, target_id, need_type, need_id)    WHERE need_type IS NOT NULL
```

Consequences:

```text
Source X
 ├─ Watch A (need = topic:UAP)      -> monitor_1   own scope, cadence, enabled
 └─ Watch B (need = topic:Aviation) -> monitor_2   own scope, cadence, enabled
```

* Partial indexes are used deliberately. A table-level `UNIQUE` over the
  nullable need columns would treat every `NULL` as distinct and silently
  permit duplicate acquisition-only Monitors, weakening a Phase 20 invariant.
* Acquisition-only Monitors (`need_type IS NULL`) remain limited to one per
  target, exactly as the old constraint guaranteed.
* `watch_sources.monitor_id` stays `UNIQUE`: because `watches` is unique on
  `(target_type, target_id)`, every Monitor belongs to exactly one Watch. That
  is what makes per-Watch pause/resume safe on a shared Source.
* The rebuild follows the established migration-0021/0022 pattern
  (`legacy_alter_table` + rename + copy + drop), and the `search_dirty_monitors_*`
  triggers are dropped and recreated around it.

## 0.4 Deterministic vocabulary suggestions are domain-derived

§28 requires deterministic suggestions before any provider call. These are
derived from **persisted domain state only**:

```text
Watch title
+ approved scope of the Watch target (_scope_for_target)
    exact terms / vocabulary / entities / concepts / exclusions
+ structurally derived initialisms of multi-word approved terms
```

No hardcoded topic dictionary is used. Suggestions persist as
`status='suggested', enabled=0` and cannot affect monitoring until approved.

## 0.5 Corrections applied to earlier in-progress Phase 24 work

Uncommitted Phase 24 work existed before this audit and contained defects that
are now fixed:

```text
[FIX] integrity.py — the Phase 20 `invalid_monitor_need_reference` check had
      been spliced apart and silently disabled; it now detects again, and the
      new Watch checks live in their own block.
[FIX] migration-version assertions left at 23 in three test modules.
[FIX] Source sharing was impossible (see 0.3).
[FIX] pause/resume disabled Monitors reachable from the Watch without
      ownership scoping.
[FIX] candidate approval used INSERT OR IGNORE, so a link could silently fail
      while the candidate was still marked "approved".
[FIX] module rewritten to the repository's one-statement-per-line convention.
```

## 0.6 Status of the §90 required capabilities

```text
[DONE] coherent Watch/Monitor abstraction
[DONE] multiple supported monitoring target types
[DONE] persistent Watch vocabulary (aliases, acronyms, include/exclude)
[DONE] deterministic vocabulary suggestions
[DONE] persistent suggestion approval/rejection + rejected-suggestion memory
[DONE] persistent Source candidates with explanation/provenance
[DONE] candidate approval/rejection + existing Source recognition
[DONE] Watch-Source relationships incl. sharing
[DONE] logical export of Watch state
[DONE] integrity coverage (orphan target, watch-source monitor need)
[DONE] Phase 23 downstream compatibility (full suite green)

[DONE] deterministic Source discovery (see 0.7)
[DONE] JobService-backed discovery + suggestion runs (§49, §50)
[DONE] discovery audit fields (last_discovery_at / discovery_error)

[DONE] provider-assisted vocabulary via the existing AIRouter + budget controls
[DONE] bounded vocabulary query planning (§33, §84)
[DONE] Watch health / coverage summary (§60, §61)
[DONE] frontend Watch, vocabulary, Source, and candidate management surfaces
[DONE] logical export/backup reconstruction regression (§77)
[DONE] Watch->Phase 23 evidence, Story, Report, and Alert integration (§103, §104)
[DONE] concurrency, scheduler idempotency, migration, and external-input regressions
```

## 0.7 Source discovery is corpus-derived, not crawled

§36 conditions deterministic discovery on the corpus retaining link/reference
information, and forbids building a crawler for Phase 24. Repository reality:

```text
SafeHTMLExtractor keeps visible text and DISCARDS <a href>.
Content artifacts store visible_text_v1 / feed_metadata_v1 / fallback_text_v1.
=> outbound hyperlinks are NOT part of the corpus.
```

So href-scraping discovery is not implementable without either a crawler
(forbidden) or changing the immutable Phase 18 artifact contract (out of scope
and trust-critical). Discovery instead uses the three reference signals
Newsroom genuinely does persist, all gated on a confirmed Phase 20
`relevant = 1` decision for one of the Watch's own Monitors:

| method | signal | outcome |
|---|---|---|
| `existing_source` | a known Source produced relevant material for this Watch but is not attached | resolves to the existing Source (§43) |
| `document_link` | a Phase 09 `document_lineage` parent (cites / syndicated_from / wire_propagation / rewritten_from) | proposes the referenced publication |
| `feed_discovery` | a relevant Document's canonical URL is on a different domain than the Source that delivered it, and that domain has no Source record | proposes the syndicated original publisher |

Properties: zero network requests, bounded (`MAX_CANDIDATES_PER_RUN = 25`),
idempotent per `(watch_id, normalized_url)`, and a run finding nothing is a
**successful** run (§86). Candidates are inert until approved.

## 0.8 Discovery and suggestion runs are durable Jobs

`WatchMaintenanceService` registers two job types in the production worker:

```text
watch_source_discovery
watch_vocabulary_suggestion
```

Idempotency uses `{job_type}:{watch_id}:{requested_at}` so duplicate dispatch of
one requested run coalesces while a genuinely later user-triggered run is still
allowed (§50). Discovery failure raises `RetryableJobFailure`, records
`watches.discovery_error`, and leaves approved Sources monitoring normally
(§82/§83).

## 0.9 Final implementation reconciliation

The repository's completed implementation makes the following codebase-driven
adjustments to the original product plan:

* A Watch is a persistent user-intent row. It does not replace `Monitor`:
  approved Watch Sources are represented by ordinary Source Monitors, with
  `need_type`/`need_id` preserving the Watch target's relevance scope. Source
  sharing therefore creates one Monitor per Watch, preserving independent
  cadence, pause/resume state, and immutable scope history while retaining the
  Phase 23 acquisition-to-evidence path.
* Provider-assisted vocabulary is an optional `vocabulary` capability on the
  existing `AIRouter`. Inputs and outputs are bounded structured models;
  policy `paid_budget_usd`, the existing global paid-enabled control, and the
  router's call/cost limits gate paid escalation. The default application
  composition remains local-first and deterministic when no paid provider is
  configured. Provider terms are persisted only as inert `suggested` rows and
  never directly change Watch configuration.
* Query planning is deterministic and deliberately conservative: approved
  terms only, no Cartesian expansion, one term per variant, a hard cap of 12
  variants, and the existing policy query budget as the lower cap. Pending and
  rejected vocabulary cannot enter the plan.
* Source discovery is corpus-derived rather than crawled. Because the
  immutable Phase 18 artifacts retain visible content but not outbound
  anchors, the supported methods are `existing_source`, `document_link`, and
  `feed_discovery`; all are bounded and require a confirmed Phase 20 relevant
  decision. No new network or crawler abstraction was introduced.
* The frontend replaces the prior monitor-management placeholder with a
  bounded Watch workflow using the existing authenticated API: create/edit,
  pause/resume, vocabulary review, Source discovery, candidate review, and
  health/coverage inspection.
* Logical export now includes the Watch configuration, full monitoring policy
  controls, Monitor provenance/scope history, vocabulary, candidates, and
  Watch-Source relationships. Migration 0024 adds Watch state while preserving
  existing Phase 23 Monitors unchanged; repeat application is idempotent.

The completed focused suite covers these adjustments, including provider
failure and malformed output isolation, concurrent candidate/suggestion
convergence, scheduler coalescing, backup/restore, and a controlled
Watch-linked Phase 23 Alert path. Phase 25 work is not included.

---

# ROLE

Implement **Phase 24 of Newsroom v2** as the first major product-capability phase after completion of the trusted autonomous intelligence pipeline.

Phase 23 established the durable core:

```text
Source / Monitor
→ Acquisition
→ Document
→ DocumentVersion
→ ContentArtifact
→ ArticleAnalysis
→ verified Evidence
→ automatic Claim
→ Story automation
→ audited Claim acceptance
→ LivingReport
→ exact ReportRevision causes
→ exact-cause Alert
→ durable in_app delivery
```

Phase 24 expands the front of that pipeline.

The goal is to move Newsroom from:

> "Process information from Sources I have already configured."

to:

> **"Let me describe what I care about, help me define the terminology around it, help me find useful Sources, and maintain an understandable monitoring configuration over time."**

Phase 24 combines three closely related capabilities:

1. **Unified Watches**
2. **Vocabulary Intelligence**
3. **Source Discovery**

These should operate as one coherent monitoring system rather than three separate features later stitched together.

This is intentionally a larger phase.

Codex may divide implementation into several coherent internal milestones or commits when doing so improves correctness, testing, or reviewability.

The entire Phase 24 capability described here should be complete before declaring Phase 24 finished.

---

# 1. CODEBASE-FIRST INSTRUCTION

Before implementing Phase 24, inspect the actual repository and reconcile this plan with the completed Phase 23 architecture.

Review at minimum:

* Monitor models and services;
* Topics;
* Subjects;
* Sources;
* Research Questions;
* Stories;
* scheduler;
* Jobs;
* acquisition;
* relevance processing;
* ArticleAnalysis;
* provider abstractions;
* provider-budget controls;
* frontend Monitor management;
* APIs;
* Workbench/Search;
* logical export;
* database integrity;
* migration conventions;
* tests.

This document defines required **product outcomes and invariants**.

It does not require a particular table name, class hierarchy, endpoint layout, or implementation sequence.

If existing abstractions provide a simpler or stronger solution, use them.

Do not duplicate mature concepts simply to match terminology in this document.

---

# 2. STARTING REPOSITORY STATE

Assume:

```text
Phase 23 is complete and committed.
```

Do not assume a specific commit SHA.

Before editing:

* verify the current branch;
* inspect the latest commits;
* confirm tracked worktree state;
* confirm staged state;
* inspect current phase documentation;
* use the actual current HEAD;
* preserve unrelated files;
* do not reset repository history;
* do not rewrite existing commits;
* do not push.

If implementation work has already begun, inspect and preserve legitimate current changes rather than restarting automatically.

---

# 3. PHASE 24 PRODUCT OUTCOME

The desired workflow is approximately:

```text
User:
"Monitor UAP disclosure."

Newsroom:
→ creates or updates a persistent monitoring definition
→ understands its active vocabulary
→ recognizes aliases and acronym expansions
→ proposes useful additional terminology
→ identifies currently attached Sources
→ discovers additional Source candidates
→ explains why each candidate was suggested
→ lets the user approve or reject suggestions
→ schedules monitoring
→ feeds acquired material into the normal Newsroom pipeline
→ preserves an inspectable monitoring history
```

A user should be able to understand:

```text
What am I monitoring?

What does Newsroom currently consider relevant terminology?

Which Sources are currently included?

Which terminology was suggested automatically?

Which Sources were suggested automatically?

Which suggestions did I approve?

Which did I reject?

When did monitoring last run?

When will it run next?

Is monitoring currently active?

Did a discovery operation complete successfully?
```

No important Watch behavior should depend on invisible configuration drift.

---

# 4. AUDIT THE CURRENT MONITORING ARCHITECTURE

Before choosing the final model, answer from the codebase:

```text
1. What is a Monitor today?

2. Does Monitor already represent the correct durable
   abstraction for Phase 24?

3. Would "Watch" be best implemented as:
   - an enhanced Monitor,
   - a higher-level object,
   - or simply user-facing terminology?

4. How are Topics currently represented?

5. How are Subjects currently represented?

6. How are Sources attached to monitoring?

7. Can existing Stories already influence monitoring?

8. How are Research Questions currently represented?

9. What scheduling configuration already exists?

10. What search/query terms are already persisted?

11. What Source discovery capabilities already exist?

12. Which APIs are already stable frontend contracts?

13. Which frontend screens currently manage Monitors?

14. What provider/budget infrastructure already supports
    suggestion or discovery operations?

15. Which existing validators and domain services should
    be reused?
```

Document the final architecture decision.

---

# 5. WATCH TERMINOLOGY

The user-facing term for the Phase 24 monitoring abstraction may be:

```text
Watch
```

but Codex should not introduce a redundant durable `Watch` object if the existing `Monitor` already fulfills that role cleanly.

Possible architectures include:

```text
A. Monitor itself becomes the unified Watch abstraction.

B. Watch is a thin user-facing representation over Monitor.

C. Watch coordinates one or more lower-level Monitors.
```

Choose the architecture that best matches the repository.

The final user experience matters more than forcing a new noun into the schema.

---

# 6. UNIFIED WATCH MODEL

The monitoring abstraction should be capable of representing several kinds of monitoring intent.

The desired supported target classes are:

```text
Topic
Subject
Story
Source
Research Question
Entity-like target where current architecture permits
```

Not every target type must use identical acquisition mechanics.

They should, however, participate in one coherent monitoring contract.

---

# 7. TOPIC WATCH

Example:

```text
UAP disclosure
```

A Topic Watch represents broad thematic monitoring.

It may use:

* vocabulary;
* selected Sources;
* Source discovery;
* schedule;
* relevance configuration.

Reuse the existing Topic model where possible.

---

# 8. SUBJECT WATCH

Example:

```text
AARO
```

A Subject Watch follows a known subject represented by the current domain model.

Reuse Subject relationships rather than duplicating them as text-only Watch metadata.

---

# 9. STORY WATCH

Example:

```text
2026 congressional UAP hearings
```

A Story Watch means:

> Look for potential new developments related to this Story.

It does **not** mean:

> Automatically assign every retrieved Document to this Story.

The existing Story resolution system remains authoritative.

Required path:

```text
Story Watch
→ retrieval/acquisition
→ normal relevance analysis
→ ArticleAnalysis
→ evidence
→ normal Story resolution
```

---

# 10. SOURCE WATCH

Example:

```text
NASA newsroom
```

A Source Watch follows a specific Source.

Where existing Monitor semantics allow it, support both:

```text
Monitor all eligible content from this Source.
```

and:

```text
Monitor only content matching this Watch's configured scope.
```

Do not require vocabulary for a Source Watch when the user wants full-source monitoring.

---

# 11. RESEARCH QUESTION WATCH

Example:

```text
Has independent physical evidence been released?
```

A Research Question Watch should monitor configured Sources for new material potentially relevant to an existing Research Question.

Phase 24 should **not** implement autonomous research pursuit.

That belongs to Phase 25.

Phase 24 only provides continuous monitoring context.

---

# 12. ENTITY-LIKE WATCH TARGETS

Phase 26 will introduce broader canonical Entity Intelligence.

Do not prematurely implement the full Phase 26 Entity system.

If the current domain can already represent entity-like monitoring cleanly through Subjects, Topics, strings, or another existing mechanism, support the smallest compatible Phase 24 version.

Document how Phase 26 can later adopt canonical Entities without breaking existing Watches.

---

# 13. WATCH CONTRACT

A Watch should expose, directly or through established related records, enough information to represent:

```text
identifier
display name
target type
target identity
lifecycle state
priority
schedule
Source scope
vocabulary
include/exclude configuration
relevance policy
discovery policy
created timestamp
updated timestamp
last attempted run
last successful run
next scheduled run
last discovery run
operational status
```

Do not duplicate fields already owned by Scheduler, Monitor, Source, or Job records.

Prefer normalized relationships.

---

# 14. WATCH LIFECYCLE

The final system should distinguish at minimum:

```text
active
paused
inactive / archived according to repository conventions
```

Operational problems should be represented separately from lifecycle where the existing architecture supports that distinction.

The user should be able to:

* create;
* inspect;
* edit;
* pause;
* resume;
* archive or remove according to existing domain rules.

Historical monitoring results must remain historically accurate after Watch edits.

---

# 15. WATCH SCHEDULING

Reuse the existing scheduler.

Do not create a second scheduling framework.

The conceptual flow should remain:

```text
Watch / Monitor configuration
→ scheduler
→ Job
→ acquisition
```

Verify:

* schedule edits take effect predictably;
* paused Watches stop generating new scheduled work;
* resumed Watches continue correctly;
* repeated scheduler execution does not duplicate one logical obligation;
* monitoring history remains inspectable.

---

# 16. SOURCE SHARING

A Source may be useful to multiple Watches.

Prefer a relationship such as:

```text
Watch A ─┐
         ├→ Source X
Watch B ─┘
```

rather than duplicating Source records.

Removing Source X from Watch A must not delete Source X if:

* Watch B uses it;
* historical Documents use it;
* Claims or Evidence refer to it.

---

# 17. WATCH-SOURCE RELATIONSHIP

Where Watch-specific Source configuration is useful, store it on the relationship.

Potential examples:

```text
enabled
priority
scope
relationship origin
approved candidate identity
```

Add only fields justified by actual behavior.

Do not turn the relationship into another full Source configuration object unless required.

---

# 18. VOCABULARY INTELLIGENCE PRODUCT GOAL

A user should not need to manually know every relevant form of a concept.

Example Watch:

```text
UFO sightings
```

might reasonably use:

```text
UFO
UFOs
unidentified flying object
UAP
unidentified anomalous phenomena
unidentified aerial phenomena
flying saucer
flying saucers
NHI
non-human intelligence
```

Vocabulary should be explicit, inspectable, editable, and persistent.

It should not exist only inside provider prompts.

---

# 19. VOCABULARY MODEL

Design the smallest persistent vocabulary model that fits the repository.

A term should conceptually support:

```text
term text
normalized form
term category
enabled state
origin
approval state where applicable
created timestamp
```

Possible term categories include:

```text
primary
alias
acronym
acronym expansion
synonym
related phrase
include
exclude
```

Do not introduce categories with no actual behavioral difference.

---

# 20. VOCABULARY ORIGIN

Persist how terms entered the system.

Possible origins:

```text
user
system
existing Topic
existing Subject
existing Source metadata
deterministic suggestion
provider-assisted suggestion
import
```

This should allow the user and operator to understand:

> Why is this term part of the Watch?

---

# 21. ACRONYM SUPPORT

Phase 24 should explicitly support acronym relationships.

Examples:

```text
NHI
→ non-human intelligence
```

```text
UAP
→ unidentified anomalous phenomena
→ unidentified aerial phenomena
```

Preserve both acronym and expansion.

Do not rewrite historical Document text.

Vocabulary operates on retrieval and monitoring configuration.

---

# 22. SYNONYMS AND ALIASES

Support useful alternate terminology.

Examples:

```text
UFO
↔ unidentified flying object
```

```text
flying saucer
↔ flying saucers
```

Do not automatically treat broader thematic concepts as exact synonyms.

The system should preserve meaningful distinctions between:

```text
same concept
related concept
broad contextual term
```

where the current model supports them.

---

# 23. VOCABULARY NORMALIZATION

Reuse existing normalization helpers where possible.

Consider deterministic normalization for:

* Unicode;
* casing;
* whitespace;
* punctuation;
* duplicate detection.

Do not use transformations that merge genuinely different terminology.

Original source text remains unchanged.

---

# 24. INCLUDE AND EXCLUDE TERMS

Support explicit positive and negative retrieval guidance.

Example:

```text
Include:
UAP
AARO
Pentagon

Exclude:
fiction
movie review
video game
```

These rules should be persistent and testable.

They should participate in query/retrieval planning where appropriate.

They do not replace the canonical relevance pipeline.

---

# 25. TERM PRIORITY

Only add priority or weighting if the current acquisition/relevance architecture can use it meaningfully.

Potential simple representation:

```text
primary
supporting
contextual
exclude
```

or reuse existing numeric weights.

Do not add scoring complexity without a downstream consumer.

---

# 26. VOCABULARY AND RELEVANCE

This boundary is important:

```text
Vocabulary
→ helps decide what material to inspect
```

but:

```text
Vocabulary match
≠ verified relevance
```

All material must still follow the established relevance and ArticleAnalysis path.

Phase 24 should improve retrieval coverage, not redefine evidence.

---

# 27. VOCABULARY SUGGESTIONS

Provide a way to propose additional terminology.

Potential inputs:

```text
Watch target
current approved vocabulary
Topic/Subject metadata
relevant existing Claims
recent relevant Documents
known Sources
```

Potential suggestion output:

```text
candidate term
candidate category
short explanation
origin
```

Use existing provider infrastructure if semantic assistance is useful.

---

# 28. DETERMINISTIC SUGGESTIONS FIRST

Use existing structured data before using a provider.

Examples:

* existing acronym expansions;
* known aliases;
* existing Topic terminology;
* Subject names;
* recurring phrases from already verified relevant material;
* deterministic spelling/casing variants.

Provider assistance should add value rather than become a routine dependency.

---

# 29. PROVIDER-ASSISTED VOCABULARY

If provider assistance is used:

* use the current provider abstraction;
* use existing cost/budget controls;
* send bounded context;
* request structured results;
* validate returned fields;
* enforce result-count limits;
* persist suggestion origin;
* preserve the Watch if the provider is unavailable.

Provider suggestions remain proposals until accepted according to Watch policy.

---

# 30. VOCABULARY APPROVAL

Semantic suggestions should be inspectable before they modify persistent Watch behavior.

A practical lifecycle may be:

```text
suggested
→ approved
→ active
```

with:

```text
rejected
```

also persisted.

If existing application policy already treats certain deterministic normalization variants as equivalent, preserve that behavior.

Do not require manual approval for transformations that are already safely canonicalized by the domain.

---

# 31. REJECTED VOCABULARY MEMORY

Rejected suggestions should remain known to the system.

A rejected term should not reappear immediately on every suggestion run without materially new context.

Allow later reconsideration when appropriate.

---

# 32. VOCABULARY EDIT HISTORY

Changing vocabulary should affect future monitoring.

It should not silently rewrite:

* historical relevance results;
* historical Claims;
* Stories;
* Reports;
* Alerts.

If historical material is explicitly reprocessed, use the existing reprocessing mechanisms.

---

# 33. VOCABULARY QUERY PLANNING

A Watch with many terms should not create uncontrolled query growth.

Build bounded deterministic query plans.

Conceptually:

```text
primary terms
+
selected aliases
+
selected contextual terms
```

instead of combining every possible term into every query.

Provider-assisted query planning may be used only through validated structured output and hard backend limits.

---

# 34. SOURCE DISCOVERY PRODUCT GOAL

For a Watch, Newsroom should help answer:

> **Where else should I be looking?**

The system should discover candidate Sources and explain why they may improve monitoring coverage.

The user should then be able to approve or reject them.

---

# 35. SOURCE DISCOVERY INPUTS

Use discovery methods that fit the existing architecture.

Possible sources of candidates include:

* currently relevant Documents;
* links referenced by Documents;
* existing Source relationships;
* feed metadata;
* known publication metadata;
* search services already available to Newsroom;
* institutional or organizational Sources;
* provider-assisted Source suggestions;
* existing corpus references.

Do not implement every possible discovery technique merely because it is listed.

Choose the strongest practical combination based on existing infrastructure.

---

# 36. DETERMINISTIC SOURCE DISCOVERY

Prefer low-cost deterministic methods first.

Examples include:

```text
relevant Document
→ referenced publication/domain
→ not currently attached to Watch
→ Source candidate
```

or:

```text
existing Source metadata
→ related feed
→ Source candidate
```

If the existing corpus does not retain enough link/reference information for these approaches, do not create a general crawler solely for Phase 24.

---

# 37. FEED DISCOVERY

If the current acquisition system supports RSS or Atom, Source discovery may use normal feed metadata and existing feed handling.

Reuse existing network/request services.

Keep discovery bounded.

Do not build a broad web indexing system.

---

# 38. SEARCH-ASSISTED SOURCE DISCOVERY

If Newsroom already has or can cleanly support a search abstraction, use Watch vocabulary and target context to generate bounded Source-discovery queries.

Potential inputs:

```text
Watch target
approved vocabulary
desired Source class
known Sources
```

Persist enough metadata to explain how a candidate was found.

Avoid storing large search response payloads.

---

# 39. PROVIDER-ASSISTED SOURCE DISCOVERY

Provider assistance may help propose:

* likely organizations;
* likely publications;
* government or institutional Sources;
* specialist Sources;
* useful search directions.

Provider suggestions should be treated as candidate planning information.

A proposed Source should be resolved through normal application validation before becoming an approved Source.

---

# 40. SOURCE CANDIDATE MODEL

A Source candidate should conceptually include:

```text
candidate identity
Watch identity
display name
URL/domain/feed identity where available
discovery method
short explanation
candidate type
status
created timestamp
resolved existing Source ID if applicable
```

Use the smallest schema that preserves necessary provenance.

---

# 41. SOURCE CANDIDATE LIFECYCLE

A practical lifecycle may be:

```text
suggested
approved
rejected
added / linked
```

Adjust names to repository conventions.

The important distinction is:

```text
candidate
≠ active Source relationship
```

until normal validation and approval are complete.

---

# 42. SOURCE IDENTITY AND DEDUPLICATION

Inspect the existing Source model carefully.

Use its identity rules.

Potential signals include:

* normalized URL;
* feed URL;
* domain;
* canonical Source record;
* publication identity.

Avoid simplistic rules such as:

```text
all URLs on one domain are always one Source
```

or:

```text
every page URL is always a new Source
```

Respect current domain semantics.

---

# 43. EXISTING SOURCE RECOGNITION

When discovery returns a Source already known to Newsroom:

```text
do not create another Source
```

Instead:

```text
candidate
→ resolves to existing Source
→ user can attach existing Source to Watch
```

Expose this clearly in API/frontend.

---

# 44. SOURCE APPROVAL

Approval must use the existing Source/domain services.

Conceptually:

```text
candidate approved
→ validate candidate through existing application rules
→ resolve existing Source or create valid new Source
→ attach Source to Watch
```

Do not introduce a parallel Source creation pathway.

---

# 45. REJECTED SOURCE MEMORY

Rejected Source candidates should remain recorded sufficiently to prevent repeated suggestion noise.

A later materially different discovery run may allow reconsideration if product policy supports it.

---

# 46. DISCOVERY IDEMPOTENCY

Repeated discovery of the same logical Source for the same Watch should converge.

Expected:

```text
same Watch
+
same logical Source candidate
→ one logical candidate
```

Update supporting discovery metadata where useful rather than producing duplicate rows.

Use database identity constraints where appropriate.

---

# 47. DISCOVERY RUNS

Source discovery should support an explicit manual run.

If periodic discovery fits the current scheduler cleanly, it may also support periodic execution.

Potential policy:

```text
off
manual
periodic
```

Do not make provider/search discovery run on every normal Watch scan by default.

---

# 48. DISCOVERY AUDIT

The operator should be able to determine:

```text
which Watch was evaluated
when discovery ran
which methods were used
how many candidates were found
whether the run completed
whether external/provider services were used
```

Reuse Job metadata where that already provides sufficient auditability.

Do not create a separate discovery-run table solely for reporting if Jobs already satisfy the requirement.

---

# 49. JOB INFRASTRUCTURE

Use JobService for Phase 24 operations that are:

* asynchronous;
* externally dependent;
* retryable;
* scheduled;
* operationally significant.

Potential examples:

```text
Watch vocabulary suggestion
Watch Source discovery
```

Use current Job naming conventions.

Simple CRUD should remain simple CRUD.

---

# 50. JOB IDENTITY

Distinguish:

```text
duplicate dispatch of one requested run
```

from:

```text
a legitimate new discovery run requested later
```

Do not use permanent idempotency keys that prevent future intentional discovery.

---

# 51. DISCOVERY AND PROVIDER COST POLICY

Use:

```text
local / deterministic first
provider when useful
bounded discovery
existing provider abstraction
existing budget controls
explicit user or scheduled policy
```

Routine monitoring should not depend on paid suggestions.

The Watch should continue functioning when optional discovery/provider features are unavailable.

---

# 52. EXTERNAL INPUT HANDLING

Phase 24 processes external URLs, Source metadata, search results, and provider-generated candidate data.

Reuse the application's established validation boundaries.

At minimum:

* validate URLs and Source identifiers through existing application services;
* validate redirects and resolved destinations using existing network rules;
* validate provider output against bounded structured schemas;
* validate API inputs using current request models;
* keep external content separate from application configuration;
* prevent externally derived data from changing persistent configuration except through normal domain services;
* protect sensitive application data according to current repository policy.

Prefer shared validators over Phase-24-specific duplicate logic.

---

# 53. EXTERNAL CONTENT TRUST BOUNDARY

Content retrieved from Sources or returned by external services is **data**.

It must remain separate from application instructions and configuration authority.

This applies to:

* Source metadata;
* page text;
* feed metadata;
* search results;
* provider suggestions.

Add regression coverage demonstrating that malformed or invalid external input is handled safely and does not produce unauthorized persistent changes.

Keep tests focused on expected application behavior.

---

# 54. PROVIDER OUTPUT VALIDATION

Provider output should use a clearly defined schema.

Validate:

* required fields;
* field types;
* lengths;
* counts;
* normalized values;
* duplicates;
* supported categories.

Invalid output should leave existing Watch state unchanged.

---

# 55. NETWORK REQUEST POLICY

All network operations introduced by Phase 24 should reuse current request/destination controls, timeouts, redirect handling, and retry policies.

Do not create a Phase-24-specific networking layer unless required.

Do not implement broad recursive crawling.

---

# 56. FRONTEND PRODUCT GOAL

Phase 24 must include functional frontend management.

Do not postpone the entire experience to Phase 30.

A user should be able to manage the new monitoring functionality without editing database records or configuration files manually.

Visual redesign is not required.

Functional usability is.

---

# 57. WATCH MANAGEMENT UI

Adapt the current Monitor/Topic management experience.

The user should be able to:

```text
create Watch
inspect Watch
edit Watch
pause Watch
resume Watch
configure schedule
inspect Sources
attach Sources
remove Watch-Source relationships
inspect vocabulary
add vocabulary
request suggestions
approve/reject suggestions
run Source discovery
approve/reject Source candidates
inspect operational status
```

Use current application patterns.

---

# 58. VOCABULARY UI

Clearly distinguish:

```text
Active terms
Suggested terms
Excluded terms
```

Where useful, display origin such as:

```text
User
System
Existing Topic/Subject
Suggested
Observed from corpus
```

Avoid exposing internal provider metadata that does not help the user.

---

# 59. SOURCE DISCOVERY UI

For each candidate, provide enough information to make a decision:

```text
name
URL/domain
Source type if available
why it was suggested
discovery method
existing/new status
approve
reject
```

If a candidate resolves to an existing Source, make that visible.

---

# 60. WATCH HEALTH

Provide a bounded operational summary such as:

```text
lifecycle state
last attempt
last success
next scheduled run
last discovery run
active Source count
pending Source candidate count
pending vocabulary suggestion count
recent error/deferred state where applicable
```

Reuse existing Jobs/Scheduler data.

Do not invent another operational state machine.

---

# 61. WATCH COVERAGE

The user should be able to answer:

```text
How many Sources are active for this Watch?

Which Sources are still only candidates?

What vocabulary is active?

Which suggestions are awaiting review?

When did this Watch last run?

When is the next run?

Is optional Source discovery enabled?
```

Expose these efficiently.

---

# 62. MATCH EXPLANATIONS

Phase 24 should improve monitoring transparency.

Where retrieval logic can deterministically explain why a Document entered consideration, preserve that explanation.

Example:

```text
Source:
Department of Defense

Matched Watch terms:
UAP
AARO
```

This means:

```text
Why the Document was considered
```

not:

```text
Proof that the Document is relevant
```

Final relevance remains downstream.

---

# 63. SOURCE SUGGESTION EXPLANATIONS

A candidate Source should have a concise persisted reason.

Examples:

```text
Referenced by relevant Documents.
```

```text
Found during Source discovery for this Watch.
```

```text
Matches configured institutional Source criteria.
```

Do not generate explanations after the fact if the provenance needed to support them was not persisted.

---

# 64. RELEVANCE BOUNDARY

Maintain the following distinction:

```text
Watch configuration
→ retrieval candidate
```

```text
normal relevance pipeline
→ relevant Document
```

```text
canonical analysis/evidence pipeline
→ trustworthy Claim evidence
```

Vocabulary, Tags, Source suggestions, and provider recommendations do not themselves constitute evidence.

---

# 65. PHASE 23 AUTOMATION COMPATIBILITY

The trusted downstream chain must remain unchanged:

```text
Document
→ ArticleAnalysis
→ verified evidence
→ Claim
→ Story
→ Report
→ Alert
```

Phase 24 may improve how Documents enter consideration.

It must not introduce another downstream evidence path.

---

# 66. STORY WATCH CORRECTNESS

Explicitly test that a Story Watch does not directly assign resulting Claims/Documents to the watched Story.

Normal Story resolution must still decide.

---

# 67. RESEARCH QUESTION COMPATIBILITY

Phase 24 may support Research Question Watches.

Do not implement:

```text
gap generation
active research pursuit
automatic Question resolution
```

Those belong to Phase 25.

---

# 68. WORKBENCH COMPATIBILITY

Expose Watch relationships and vocabulary where naturally useful.

Do not implement Workbench v2 here.

That belongs to Phase 26.

---

# 69. SOURCE INTELLIGENCE BOUNDARY

Phase 24 may use simple Source categories needed for discovery.

Do not build:

* broad Source reliability models;
* detailed Source dependency graphs;
* universal credibility scoring.

Those belong to Phase 28.

---

# 70. API DESIGN

Use existing `/api/v1` conventions.

Do not add new endpoints where existing Monitor/Source endpoints can be cleanly extended.

The final API should support the equivalent of:

## Watch management

```text
list
detail
create
update
pause/resume
archive/delete according to domain conventions
```

## Vocabulary

```text
list
add
edit
disable/remove
request suggestions
approve suggestion
reject suggestion
```

## Watch Sources

```text
list attached Sources
attach Source
remove Watch relationship
```

## Source discovery

```text
run discovery
list candidates
candidate detail if needed
approve
reject
```

---

# 71. API BOUNDS

All collection endpoints must use established pagination/bounds.

Apply this to:

* Watches;
* vocabulary;
* suggestions;
* Sources;
* Source candidates;
* discovery history if exposed.

Use backend-owned maximum page sizes.

---

# 72. API PROVENANCE

Responses should provide stable IDs and concise origin information necessary to understand:

```text
where a vocabulary term came from
why a Source candidate exists
whether a Source is existing/new
whether a suggestion was approved
```

Do not expose raw provider payloads.

---

# 73. MIGRATION STRATEGY

Phase 24 likely requires persistence changes.

Codex must decide after repository inspection.

Possible strategies include:

```text
extend Monitor

add relationships to Monitor

introduce a thin Watch abstraction

generalize Monitor target identity
```

Use the simplest compatible approach.

Avoid overlapping abstractions such as:

```text
Watch
Monitor
MonitorDefinition
WatchDefinition
WatchConfig
```

unless each has a clear, necessary responsibility.

---

# 74. MIGRATION REQUIREMENTS

If schema changes:

* follow repository migration conventions;
* advance schema version correctly;
* support fresh database creation;
* support upgrade from the completed Phase 23 schema;
* preserve existing Monitor behavior;
* preserve existing Sources;
* preserve Topic/Subject relationships;
* preserve existing scheduler behavior;
* pass foreign-key validation;
* support migration idempotency according to project conventions;
* update relevant documentation.

Existing users should not need to recreate Monitors manually.

---

# 75. BACKWARD COMPATIBILITY

Test:

```text
existing Phase 23 Monitor
→ database upgrade
→ equivalent monitoring behavior
```

If existing Monitor APIs remain active contracts, preserve or adapt them cleanly.

Do not casually remove existing functionality because a new Watch representation exists.

---

# 76. LOGICAL EXPORT

Extend logical export to preserve Phase 24 durable state.

Depending on final schema, this may include:

```text
Watch/Monitor configuration
Watch target relationships
vocabulary
vocabulary suggestion state
Watch-Source relationships
Source candidates
discovery audit metadata
```

Use actual implemented records.

Do not export large provider/search payloads merely because they exist operationally.

---

# 77. EXPORT RECONSTRUCTION

Add a regression proving an exported Watch can reconstruct:

```text
Watch
→ target
→ active vocabulary
→ rejected vocabulary suggestion
→ attached Source
→ approved Source candidate relationship
→ rejected Source candidate
```

according to actual implemented schema.

---

# 78. BACKUP / RESTORE

Verify Phase 24 data is preserved by the existing full database backup/restore process.

Do not create a new backup mechanism.

---

# 79. DATABASE INTEGRITY

Extend `check_database()` only for important structural invariants.

Potential checks include:

```text
Watch target relationship resolves

active vocabulary belongs to a valid Watch

Watch-Source relationship resolves

approved candidate resolves coherently

candidate state is internally consistent

required target/source references exist
```

Do not attempt to determine whether a synonym is semantically "good" during database integrity checking.

Structural truth belongs in integrity.

Semantic quality belongs in application logic and tests.

---

# 80. CONCURRENCY

Use real database-backed tests where logical uniqueness matters.

Important examples:

```text
two discovery workers
→ same Watch
→ same logical Source candidate
→ one logical candidate
```

```text
two approval attempts
→ same candidate
→ one logical Watch-Source relationship
```

```text
two vocabulary suggestion workers
→ same normalized suggestion
→ one logical candidate
```

Use database constraints where appropriate.

Do not rely only on pre-insert existence checks.

---

# 81. IDEMPOTENCY

Verify replay behavior for:

* discovery jobs;
* suggestion jobs;
* Source candidate approval;
* Watch-Source relationship creation;
* scheduler obligations.

Do not prevent legitimate new user-triggered discovery runs simply because an older run exists.

---

# 82. DISCOVERY FAILURE ISOLATION

Optional discovery functionality must not break normal monitoring.

Example:

```text
Source discovery unavailable
→ existing Watch still monitors approved Sources
```

Likewise:

```text
vocabulary suggestion unavailable
→ existing active vocabulary continues functioning
```

---

# 83. PROVIDER FAILURE ISOLATION

Provider-assisted suggestions are optional enhancements.

Provider failure must leave:

```text
Watch configuration
approved vocabulary
approved Sources
normal scheduled monitoring
```

intact.

---

# 84. PERFORMANCE BOUNDS

Prevent uncontrolled combinatorial growth.

Define backend limits appropriate to the codebase for:

* active vocabulary terms considered per query plan;
* query variants per Watch cycle;
* suggestions per run;
* Source candidates per discovery run;
* provider requests per run;
* external search requests per run;
* results returned by APIs.

Choose practical values based on existing application conventions.

---

# 85. COST BOUNDS

Reuse existing provider cost controls.

Phase 24 should make it possible to identify optional costs associated with:

```text
vocabulary suggestions
Source discovery
search-assisted discovery
```

Routine source monitoring should remain as inexpensive as the existing architecture permits.

---

# 86. RETRY BEHAVIOR

Use existing Job retry conventions.

Distinguish:

```text
temporary operational failure
```

from:

```text
valid completed run with zero candidates
```

A discovery run that finds nothing is not necessarily a failed Job.

---

# 87. OBSERVABILITY

Add practical operational events consistent with existing logging conventions.

Examples:

```text
Watch created
Watch updated
Watch paused/resumed
vocabulary suggestion completed
vocabulary suggestion approved/rejected
Source discovery completed
Source candidate approved/rejected
Source linked to Watch
```

Keep logs concise.

Do not include full Document bodies or unnecessary provider payloads.

---

# 88. DOCUMENTATION

Update:

* phase planning documentation;
* current phase status;
* Monitor/Watch architecture documentation;
* relevant API documentation;
* README only where current repository conventions call for it.

Document clearly:

```text
Watch
Monitor
Source
Vocabulary
Source Candidate
```

and how they relate in the final implementation.

---

# 89. CODEBASE-DRIVEN ADJUSTMENT AUTHORITY

Codex is expected to modify this plan's implementation details based on repository reality.

Examples:

```text
If Monitor already supports target types,
extend it rather than creating Watch.

If Topic vocabulary already exists,
reuse it rather than cloning it.

If Source discovery already has reusable helpers,
reuse them.

If JobService already supports appropriate
discovery operations, extend those conventions.

If existing validation is stronger than this plan,
preserve the stronger validation.

If an existing API can be extended cleanly,
prefer that over adding a parallel endpoint family.
```

Document material deviations in the final report.

---

# 90. REQUIRED PRODUCT CAPABILITIES MUST NOT BE SILENTLY DEFERRED

Architectural flexibility does not reduce the required end state.

Phase 24 must finish with:

```text
coherent Watch/Monitor abstraction

multiple supported monitoring target types

persistent Watch vocabulary

aliases/synonyms

acronym expansions

include/exclude terminology

deterministic vocabulary suggestions

provider-assisted vocabulary suggestions where useful

persistent suggestion approval/rejection

Source discovery

persistent Source candidates

Source candidate explanations/provenance

candidate approval/rejection

existing Source recognition

Watch-Source relationships

scheduler integration

functional APIs

functional frontend management

logical export

integrity coverage

Phase 23 downstream compatibility

end-to-end monitoring integration
```

If one particular mechanism is unnecessary because the repository already solves the problem differently, explain the equivalent implementation.

---

# 91. OUT OF SCOPE

Do not implement Phase 25 capabilities:

```text
autonomous Research Question pursuit
Evidence Gap research loops
Question resolution automation
```

Do not implement Phase 26 capabilities:

```text
full canonical Entity Intelligence
smart tagging
Workbench v2
evidence-grounded Ask
```

Do not implement Phase 27 capabilities:

```text
Story merge
Story split
Claim reassignment
advanced Story correction
```

Do not implement Phase 28 capabilities:

```text
Source dependency graph
advanced Source reliability
external Alert delivery expansion
major intelligence dashboard redesign
```

Do not perform Phase 29's broad production-hardening program.

Do not begin Phase 30 release/dogfood work.

---

# 92. SUGGESTED IMPLEMENTATION ORDER

Codex may adjust this after repository review.

A reasonable sequence is:

```text
1. Audit Monitor/Topic/Subject/Source architecture

2. Decide final Watch architecture

3. Implement migration/compatibility changes

4. Implement unified Watch lifecycle

5. Implement target relationships

6. Implement Watch vocabulary persistence

7. Implement vocabulary normalization

8. Implement deterministic suggestions

9. Implement provider-assisted suggestions where useful

10. Integrate vocabulary into bounded query planning

11. Implement Source candidate persistence

12. Implement deterministic Source discovery

13. Implement search/provider-assisted discovery where useful

14. Implement candidate approval and Source linking

15. Integrate scheduler

16. Add/extend APIs

17. Build frontend Watch management

18. Add export and integrity support

19. Add concurrency/replay coverage

20. Run end-to-end Watch → Phase 23 integration

21. Run full validation
```

---

# 93. COMMIT STRATEGY

Phase 24 is intentionally larger than previous narrow slices.

Several coherent commits are acceptable.

For example:

```text
Phase 24: add unified intelligent monitoring model

Phase 24: add vocabulary intelligence

Phase 24: add Source discovery

Phase 24: integrate Watch API and frontend

Phase 24: complete monitoring integration and validation
```

Use fewer commits if the implementation remains clearly reviewable.

Do not create unnecessary microcommits.

Do not push.

---

# 94. REQUIRED WATCH TEST COVERAGE

At minimum verify:

```text
existing Monitor survives upgrade

Topic Watch creation

Subject Watch creation

Story Watch creation

Source Watch creation

Research Question Watch compatibility

supported entity-like target behavior if implemented

invalid/missing target handling

pause stops new scheduled work

resume restores monitoring

schedule changes behave correctly

multiple Watches share one Source

removing one Watch relationship preserves Source

Watch retrieval is bounded

target identity remains deterministic
```

Adjust target cases to actual domain capabilities.

---

# 95. REQUIRED VOCABULARY TEST COVERAGE

Verify:

```text
manual term creation

normalization

duplicate prevention

acronym + expansion

alias/synonym representation

include term

exclude term

disabled term omitted from query planning

suggested term inactive before approval

approved suggestion becomes active

rejected suggestion remains recorded

rejected suggestion does not immediately recur

provider suggestion schema validation

suggestion count limits

historical source text remains unchanged

vocabulary survives export/backup
```

---

# 96. REQUIRED SOURCE DISCOVERY TEST COVERAGE

Verify:

```text
manual discovery run

candidate creation

repeated discovery converges

existing Source is recognized

candidate approval links existing Source

valid new candidate creates Source through normal service

candidate rejection persists

rejected candidate is not repeatedly suggested immediately

invalid Source input is handled safely

Source identity deduplicates correctly

discovery result count is bounded

unresolved provider suggestions remain candidates only

candidate does not become monitored before normal approval

candidate explanation/provenance is preserved

discovery failure does not stop normal Watch monitoring
```

---

# 97. REQUIRED PROVIDER TEST COVERAGE

If Phase 24 uses providers:

```text
uses existing provider abstraction

uses existing budget controls

uses bounded context

uses structured result schema

invalid result leaves Watch unchanged

provider failure leaves Watch usable

provider suggestion count is bounded

raw provider response is not exposed through normal API/export

normal monitoring does not depend on provider availability
```

---

# 98. REQUIRED API TEST COVERAGE

Test final supported contracts for:

```text
Watch list

Watch detail

Watch create/edit

pause/resume

vocabulary list

vocabulary mutation

suggestion request

suggestion approval/rejection

Watch Sources

Source discovery

candidate list

candidate approval/rejection

pagination

invalid identifiers

origin/provenance

legacy Monitor compatibility
```

Test serialized responses, not only service methods.

---

# 99. REQUIRED FRONTEND COVERAGE

At minimum verify:

```text
frontend typecheck

Watch model/type support

Watch target representation

vocabulary representation

Source candidate representation

optional/null state handling

existing Monitor UI compatibility

Watch detail retrieval

vocabulary management rendering

Source candidate rendering
```

Use existing frontend test conventions.

Do not add a new frontend testing framework solely for this phase.

---

# 100. EXTERNAL INPUT REGRESSION COVERAGE

Add focused regression tests proving Phase 24 applies existing application protections to external and provider-derived inputs.

Test expected outcomes such as:

```text
invalid URL/source input
→ rejected
→ no persistent Watch change
```

```text
invalid provider suggestion
→ rejected
→ Watch remains unchanged
```

```text
external content containing application-like instructions
→ treated as content
→ configuration remains unchanged
```

```text
unapproved candidate
→ cannot become active Watch Source
```

Use repository-level shared validators.

Keep the tests outcome-focused.

---

# 101. CONCURRENCY TEST COVERAGE

Use actual database-backed concurrency where appropriate.

Verify:

```text
same candidate discovered concurrently
→ one logical candidate

same candidate approved concurrently
→ one logical Source relationship

same vocabulary suggestion produced concurrently
→ one logical suggestion

same scheduler obligation evaluated concurrently
→ no duplicate logical acquisition work
```

---

# 102. INTEGRITY / EXPORT TEST

Create a representative Watch containing:

```text
approved vocabulary
excluded vocabulary
rejected vocabulary suggestion
attached Source
approved Source candidate
rejected Source candidate
```

Export it.

Reconstruct the Watch configuration from exported records.

Run database integrity validation.

---

# 103. PHASE 23 REGRESSION TEST

Create or reuse an integration test demonstrating:

```text
Watch
→ scheduler
→ Source acquisition
→ Document
→ relevance
→ ArticleAnalysis
→ verified evidence
→ Claim
→ Story
→ Report
→ Alert
```

The downstream path must use normal runtime/domain wiring.

Do not manually insert Story, Report, or Alert results to make the test pass.

---

# 104. DISCOVERED SOURCE PIPELINE TEST

Verify:

```text
Source candidate
→ approval
→ Source relationship
→ monitoring
→ Document acquisition
→ normal relevance
→ ArticleAnalysis
→ evidence
```

Source discovery must not create Claims directly.

---

# 105. LIVE / CONTROLLED INTEGRATION TEST

Create or use a controlled production-composition test.

Target workflow:

```text
create Watch
→ add vocabulary
→ configure/approve Source
→ scheduler or supported Monitor execution
→ acquire Document
→ process through relevance
→ ArticleAnalysis
→ verified Claim
→ Story
→ Report
→ Alert
```

Where Source discovery is part of the test:

```text
run discovery
→ candidate
→ approval
→ normal Source monitoring
```

Use real services/runtime and controlled external boundaries according to repository conventions.

---

# 106. MIGRATION VALIDATION

If schema changes, run:

```text
fresh database creation

completed Phase 23 schema → Phase 24 upgrade

migration registration

migration repeat/idempotency according to project conventions

foreign key validation

legacy Monitor behavior test
```

Do not claim migration support without testing upgrade behavior.

---

# 107. VALIDATION

Run focused Phase 24 suites first.

Then relevant suites covering:

```text
Monitors
Topics
Subjects
Sources
Scheduler
Jobs
Acquisition
Relevance
ArticleAnalysis
Evidence
Phase 23 automation
Runtime
API
Workbench compatibility
Operations/export
Integrity
provider/budget infrastructure
```

Then run the complete backend suite:

```bash
python -m pytest -p no:cacheprovider -q
```

Compile:

```bash
python -m compileall -q newsroom scripts tests
```

Frontend:

```bash
npm run typecheck
```

Diff hygiene:

```bash
git diff --check
```

Before final commit:

```bash
git diff --cached --check
```

Run actual configured project lint/build commands where relevant.

Do not report any command as passed unless it was actually executed.

---

# 108. PHASE 24 ACCEPTANCE GATE

Phase 24 is complete only when every applicable requirement below is proven.

## Unified Monitoring

```text
[PASS] existing Monitor behavior remains compatible

[PASS] one coherent Watch/Monitor abstraction exists

[PASS] Watch target identity is explicit

[PASS] supported target types operate correctly

[PASS] Watch lifecycle is manageable

[PASS] scheduler integration is preserved

[PASS] paused Watches stop new scheduled work

[PASS] resume works correctly

[PASS] multiple Watches can safely share Sources

[PASS] historical monitoring state is preserved after edits
```

## Vocabulary Intelligence

```text
[PASS] Watch vocabulary is persistent

[PASS] vocabulary is inspectable

[PASS] aliases/synonyms are supported

[PASS] acronym expansions are supported

[PASS] include terms are supported

[PASS] exclude terms are supported

[PASS] normalization prevents logical duplicates

[PASS] deterministic suggestions work

[PASS] provider-assisted suggestions work where implemented

[PASS] semantic suggestions remain inactive until approved

[PASS] suggestion origin is inspectable

[PASS] rejected suggestions remain recorded

[PASS] Watch remains functional without optional provider assistance

[PASS] vocabulary changes affect future monitoring only
```

## Source Discovery

```text
[PASS] discovery can run for a Watch

[PASS] discovery is bounded

[PASS] deterministic discovery works where supported

[PASS] search/provider-assisted discovery works where implemented

[PASS] Source candidates retain explanation/provenance

[PASS] repeated discovery converges

[PASS] existing Sources are recognized

[PASS] candidate approval uses normal Source services

[PASS] candidate rejection is persistent

[PASS] candidates remain inactive until approved

[PASS] Source identity is deduplicated correctly

[PASS] discovery failure does not stop normal monitoring
```

## Application Safety

```text
[PASS] external inputs use established application validation

[PASS] network operations use established request/destination controls

[PASS] provider outputs use bounded structured validation

[PASS] externally derived content remains data

[PASS] persistent Watch changes occur through normal domain services

[PASS] sensitive application data follows existing privacy policy

[PASS] invalid external/provider inputs leave existing Watch state safe
```

## Product Surface

```text
[PASS] backend Watch APIs are bounded

[PASS] vocabulary management is available

[PASS] suggestion approval/rejection is available

[PASS] Watch Sources are manageable

[PASS] Source discovery is available

[PASS] candidate approval/rejection is available

[PASS] frontend can manage Watches

[PASS] frontend can manage vocabulary

[PASS] frontend can inspect Source candidates

[PASS] basic Watch health is visible
```

## Auditability

```text
[PASS] Watch configuration is logically exportable

[PASS] vocabulary state is exportable

[PASS] suggestion approval/rejection state is exportable

[PASS] Watch-Source relationships are exportable

[PASS] Source candidate state is exportable

[PASS] representative Watch configuration reconstructs from export

[PASS] database integrity validates critical relationships

[PASS] backup/restore preserves Phase 24 state
```

## Reliability

```text
[PASS] concurrent candidate discovery converges

[PASS] concurrent candidate approval converges

[PASS] duplicate Watch-Source relationships are prevented

[PASS] repeated suggestion execution converges appropriately

[PASS] scheduler duplication is prevented

[PASS] provider failure is isolated

[PASS] discovery failure is isolated
```

## Downstream Integration

```text
[PASS] Watch vocabulary affects retrieval rather than evidence authority

[PASS] Story Watches still use normal Story resolution

[PASS] discovered Sources use normal acquisition

[PASS] acquired Documents use normal relevance processing

[PASS] ArticleAnalysis remains authoritative

[PASS] evidence verification remains authoritative

[PASS] existing Story/Report/Alert automation remains intact

[PASS] controlled Watch → Alert integration succeeds
```

## Repository

```text
[PASS] focused Phase 24 tests pass

[PASS] relevant existing monitoring/acquisition tests pass

[PASS] Phase 23 regressions pass

[PASS] complete backend suite passes

[PASS] compileall passes

[PASS] frontend typecheck passes

[PASS] git diff --check passes

[PASS] migration/FK validation passes if applicable

[PASS] Phase 24 work is committed

[PASS] tracked worktree is clean
```

---

# 109. FINAL USER EXPERIENCE GATE

Do not declare Phase 24 complete unless the following experience works through supported application flows:

```text
User creates:

"UAP disclosure"

Newsroom creates a persistent Watch.

The Watch contains explicit vocabulary such as:

UAP
unidentified anomalous phenomena
UFO
NHI
non-human intelligence

The user can inspect this vocabulary.

Newsroom can suggest additional terminology.

The user can approve or reject those suggestions.

The Watch displays its currently attached Sources.

Newsroom can perform Source discovery.

The user sees Source candidates with explanations.

Existing Sources are identified rather than duplicated.

The user can approve or reject candidates.

Approved Sources become part of normal Watch monitoring.

The Watch runs according to the existing scheduler.

New material follows:

Source
→ Document
→ relevance
→ ArticleAnalysis
→ evidence
→ Claim

and, where material:

Claim
→ Story
→ Living Report
→ Alert

The user can inspect:

what is being monitored
what vocabulary is active
what Sources are active
what suggestions remain pending
what was rejected
when monitoring last ran
when it will run next
```

That is the Phase 24 product.

---

# 110. FINAL RESPONSE FORMAT

## 1. Verdict

Return exactly one:

```text
PHASE 24 COMPLETE AND COMMITTED — PHASE 25 READY
```

or:

```text
PHASE 24 CORRECTED AND COMMITTED — PHASE 25 READY
```

or:

```text
PHASE 24 INCOMPLETE — PHASE 25 BLOCKED
```

---

## 2. Codebase Review and Architecture Decision

Explain what existed before Phase 24.

State:

* what Monitor represented;
* how Topic/Subject/Source relationships worked;
* final Watch architecture;
* whether Watch became a persistent object, Monitor extension, or presentation abstraction;
* why this was the simplest safe architecture.

List material adjustments made to this plan based on repository structure.

---

## 3. Unified Watch Model

Describe:

* supported target types;
* target identity;
* lifecycle;
* scheduling;
* Source scope;
* sharing behavior;
* backward compatibility;
* relationship to existing Monitor.

---

## 4. Vocabulary Intelligence

Describe the final vocabulary contract.

Include:

```text
term
normalized form
category
origin
approval state
enabled state
```

Report:

* acronym support;
* synonyms/aliases;
* include/exclude behavior;
* priority/weighting if implemented;
* deterministic suggestions;
* provider-assisted suggestions;
* approval/rejection;
* rejected-suggestion memory;
* query planning.

---

## 5. Source Discovery

Describe:

* discovery methods actually implemented;
* deterministic discovery;
* search-assisted discovery;
* provider assistance;
* candidate identity;
* candidate lifecycle;
* deduplication;
* existing Source recognition;
* candidate explanations;
* approval;
* scheduling/manual execution.

---

## 6. Acquisition / Relevance Integration

Explain the actual flow:

```text
Watch
→ vocabulary
→ Source scope
→ acquisition/retrieval
→ relevance
→ ArticleAnalysis
→ evidence
```

Confirm that monitoring configuration does not replace canonical relevance/evidence processing.

---

## 7. Provider and Cost Behavior

Report:

* which Phase 24 capabilities use providers;
* which remain deterministic;
* provider abstraction;
* call/result limits;
* budget enforcement;
* behavior when provider services are unavailable.

---

## 8. External Input Handling

Summarize how Phase 24 reuses the application's existing:

* input validation;
* Source validation;
* network-request controls;
* provider-output validation;
* authorization boundaries;
* privacy protections.

Keep this section outcome-focused.

---

## 9. API

List new or changed supported APIs.

Include:

* Watch management;
* vocabulary;
* suggestions;
* Watch Sources;
* Source discovery;
* candidate approval/rejection.

Report collection bounds and pagination.

---

## 10. Frontend

Describe the completed Watch management workflow.

Include:

* create;
* edit;
* pause/resume;
* schedule;
* vocabulary;
* suggestions;
* Sources;
* discovery candidates;
* approval/rejection;
* operational status.

---

## 11. Migration

Report:

```text
migration required: yes/no
starting schema version
ending schema version
```

If migrated, include:

* legacy Monitor handling;
* fresh database result;
* upgrade result;
* migration repeat/idempotency result;
* foreign-key result.

---

## 12. Export / Backup / Integrity

Report:

* exported Watch configuration;
* vocabulary;
* suggestions;
* Source relationships;
* Source candidates;
* discovery audit records where applicable;
* reconstruction test;
* backup compatibility;
* database integrity checks.

---

## 13. Concurrency / Idempotency

Explain safeguards for:

* duplicate Source candidates;
* concurrent discovery;
* concurrent approval;
* duplicate Source relationships;
* repeated suggestion runs;
* scheduler duplication.

---

## 14. Tests

List focused Phase 24 tests actually added.

Explicitly cover:

* legacy Monitor compatibility;
* Watch lifecycle;
* scheduler behavior;
* target types;
* vocabulary normalization;
* acronym expansions;
* include/exclude terms;
* suggestion approval;
* rejected-suggestion memory;
* Source discovery;
* Source deduplication;
* concurrent candidate handling;
* Source approval;
* invalid external-input handling;
* provider failure;
* export/integrity;
* API/frontend contracts;
* Watch → Phase 23 downstream integration.

---

## 15. Validation

List every command actually executed and its result.

Do not claim unexecuted validation passed.

---

## 16. Files Changed

Group changed files by:

```text
domain/schema
monitoring
vocabulary
Source discovery
Jobs/runtime
API
frontend
operations/integrity
tests
documentation
```

---

## 17. Commits

Report:

* commit SHA(s);
* subject(s);
* scope.

Do not push.

---

## 18. Repository State

Report:

* branch;
* current HEAD;
* relationship to origin;
* schema version;
* tracked worktree;
* staged state;
* preserved unrelated files;
* whether push occurred.

Do not compare against a prompt-predicted SHA.

---

## 19. Deferred Work

List only genuine later-phase work.

### Phase 25 — Autonomous Research

* Research Question evidence-gap reasoning;
* bounded research pursuit;
* Question lifecycle automation.

### Phase 26 — Knowledge Workspace + Ask

* canonical Entity intelligence;
* smart tagging;
* Workbench v2;
* evidence-grounded Ask.

### Phase 27 — Advanced Story Intelligence

* Story merge;
* Story split;
* Claim reassignment;
* Story correction/evolution intelligence.

### Phase 28 — Intelligence Experience + Source Intelligence

* intelligence dashboards;
* advanced Source intelligence;
* Source dependency;
* external Alert delivery expansion.

### Phase 29 — Production Hardening

* broad performance;
* operations;
* security review;
* cost optimization.

### Phase 30 — Newsroom v2 Completion

* final UX;
* dogfood;
* release audit.

Do not classify incomplete Phase 24 requirements as deferred.

---

## 20. Phase 25 Readiness

State whether Newsroom now supports:

```text
Watch
→ structured vocabulary
→ approved Sources
→ Source discovery
→ scheduled monitoring
→ canonical evidence

then:

Research Question
→ Evidence Gap
→ bounded research task
→ Source/document pursuit
→ canonical evidence pipeline
→ Question reevaluation
```

Do not begin Phase 25 in this task.
