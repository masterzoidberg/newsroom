# Full-codebase adversarial review integration — 2026-09-14

Status: **binding plan delta; implementation still requires owner authorization.**

This document explains the latest full-codebase review to Codex and records the smallest changes that most improve the probability Newsroom succeeds. It is not a new architecture proposal. Where this review conflicts with earlier implementation assumptions, the append-only decisions in `DECISIONS.md` control.

## Executive conclusion

Newsroom is solving a worthwhile problem, and the strongest parts of the implementation should remain: SQLite/local-first operation, immutable DocumentVersions, deterministic evidence verification, exact provenance, durable jobs, bounded retries, explicit paid budgets, correction history, and conservative Story merging.

The most important defect is narrower than a rewrite:

> **Acquisition is correctly global, but downstream semantic work is incorrectly treated as globally complete once a DocumentVersion has been processed once. Relevance is Research-contextual, so the durable unit of downstream work must be a Research-specific observation/context, not the DocumentVersion alone.**

Everything in M0 should be evaluated against that statement.

A second major risk is product, not infrastructure: engineering proof is substantially ahead of proof that the resulting workflow saves enough human effort to justify its complexity. After the Research boundary and first-value loop are corrected, further major intelligence subsystems must be earned by observed usefulness.

## What the review verified

The review inspected the current branch at `2b367356d56a02acff9138792a772b938e087a68`, including the backend domain/services, acquisition, jobs/scheduler/worker, relevance, ArticleAnalysis, provenance/evidence promotion, Story correction, reports, Ask, integrity/recovery/runtime, frontend shell and Watch workflow, migrations, representative tests, deployment/security docs, evaluation docs, and the current rework plan.

Important verified facts:

1. `document_version_process` is currently deduplicated around a DocumentVersion-level identity, while persisted relevance is already unique by `(document_version_id, monitor_id, scope_version)` and ArticleAnalysis identity is also contextual.
2. Existing Phase 19 tests intentionally prove the old invariant: one changed DocumentVersion creates one downstream processing job and an unchanged/304 result creates no new processing obligation.
3. That invariant becomes incorrect as soon as one canonical Source/DocumentVersion can serve multiple Researches with different scope.
4. Provenance/evidence promotion is unusually strong and should not be weakened to solve the shared-Research problem.
5. `create_app()` currently invokes `apply_migrations(...)`, while the runtime supervisor documentation/code says managed migrations should occur only under the supervisor/upgrade boundary with managed writers stopped. The safety property is therefore not mechanically single-sourced.
6. Only `source` Monitor targets perform real acquisition. Other Monitor target types remain schema/API compatibility states rather than functioning acquisition modes.
7. RSS/feed processing currently persists feed metadata; linked article retrieval is still needed for the intended evidence experience.
8. Phase 29 engineering/eval infrastructure is broad, but real longitudinal user-value proof is still pending.

## The question the architecture must now answer correctly

The most important question that was not asked early enough was:

> **What is the durable unit of work Newsroom owes the user: a DocumentVersion, or a Research-specific observation of that DocumentVersion?**

The answer is the latter.

Canonical bytes and acquisition remain global. Research relevance, eligibility, and semantic processing are contextual.

The intended shape is:

```text
canonical Source / endpoint
        ↓
one bounded acquisition
        ↓
canonical DocumentVersion
        ↓
Research observation A ── pinned Research/Monitor/scope context
        ↓
contextual relevance / analysis / eligibility

Research observation B ── independently pinned context
        ↓
contextual relevance / analysis / eligibility
```

Do **not** duplicate Documents, DocumentVersions, EvidenceSpans, Claims, Stories, transports, schedulers, or worker systems to achieve this.

## Mandatory plan changes

### 1. Pre-M0.1: make managed migration authority mechanically single-sourced

Before introducing the M0 migration series, reconcile the current contradiction between API startup and supervisor-controlled upgrades.

Required contract:

- In the managed production/runtime path, the supervisor or explicit upgrade command is the migration authority.
- Managed API startup verifies schema readiness and fails clearly if migration is required. It must not independently mutate schema while another writer can be active.
- Disposable dev/test helpers may still initialize fresh test databases explicitly, but that behavior must not undermine the managed runtime rule.
- Add an integration test proving an API child restart cannot independently advance schema while worker/scheduler ownership is active.

This is a bounded operational correction, not a migration framework rewrite.

### 2. M0.2/M0.3: explicitly supersede the old Phase 19 processing invariant

The old invariant:

```text
one DocumentVersion = one downstream processing obligation
```

must be replaced by:

```text
one canonical acquisition/version
+ independently durable Research-context obligations
```

Consequences for implementation and tests:

- Existing one-job-per-version tests must be deliberately revised, not worked around.
- A 304/unchanged response may still create a **missing Research obligation** when a newly eligible Research has not observed/processed the cached exact version under its own pinned context.
- No new network fetch is required merely because a new Research obligation exists.
- Job/enqueue/retry/recovery guards must agree on the contextual identity. Fixing only the idempotency key is insufficient.
- Scope must remain pinned. A retry must never silently rebind old work to current scope.
- Shared canonical Claim/Evidence identity should remain global where already correct. Research context controls eligibility and provenance, not textual cloning.

### 3. M0.6/M1: check completion must represent causal descendants, not timestamps

A Research check may report completion only when its sealed expected work is terminal, including contextual descendants created by acquisition and processing.

Do not infer completion from:

- global recent job timestamps,
- `jobs.run_id` alone,
- source activity counters,
- acquisition finishing before semantic descendants finish.

A quiet result is valid only after the work set is actually closed.

### 4. M1: preserve the acquisition security boundary at every newly discovered URL hop

Linked article retrieval and Source setup introduce new URL transitions. Every hop must re-enter the same deterministic network-safety boundary.

At minimum validate independently:

- pasted/manual URL,
- HTML feed autodiscovery URL,
- feed entry/article URL,
- redirects,
- canonical hints used for fetch identity,
- Source Scout candidate URLs,
- retries after DNS changes.

A safe parent URL does not confer safety on a child URL.

### 5. Do not expand generic non-Source Monitor runtime behavior

The current product has one real acquisition target: Source.

During the rework:

- do not add new runtime acquisition behavior for Topic/Subject/Story/Research Question Monitor targets;
- preserve compatibility with historical/API rows until a measured migration/deprecation path exists;
- prefer the conceptual model `Source Monitor + information need/Research context` for new code;
- do not perform destructive cleanup during M0.

This is a simplification direction, not an immediate schema purge.

### 6. M7 becomes a real value gate, not only an engineering qualification gate

In addition to correctness/recovery acceptance, record at least:

- time from Research creation to first useful evidence-backed Update;
- human minutes spent per useful development surfaced;
- useful-update yield versus noisy/irrelevant/empty checks;
- how often Ask/Briefing provides something meaningfully better than the user's simpler feed/search workflow;
- Full-vs-Lite comparison when the frozen evaluation contract is ready.

Green mocks prove correctness. They do not prove that the product earns its complexity.

Until this gate has real evidence, do not begin major new intelligence subsystems such as Claim Diff UI, Evidence Time Machine UI, new autonomous research systems, new ranking models, or a second synthesis architecture.

## Production failure modes Codex must design against

The highest-priority silent failures are:

1. **Missing Research obligation:** Research B never processes a cached DocumentVersion because Research A processed it first.
2. **False completion:** the UI says a check completed while contextual descendants are still queued/running or never linked to the check.
3. **Historical amnesia:** detaching a Source destroys the proof that earlier evidence legitimately belonged to the Research at the time.
4. **Scope rebinding:** retry/recovery processes old work under a newer Research/Monitor scope.
5. **Cross-Research leakage:** shared Story/Claim/global prose causes Ask or Briefing A to include B-only material.
6. **Unsafe discovered URL:** feed/article/Scout continuation bypasses the acquisition URL-security boundary.
7. **Live migration ambiguity:** API startup performs a schema write outside the declared quiesced-writer upgrade path.

Prefer tests that make these failures impossible over additional defensive status fields.

## Highest-value integration tests

Codex should make sure the existing acceptance matrix covers these behaviors explicitly. If an equivalent case already exists, strengthen that case rather than creating duplicate test taxonomy.

1. Same Source, two Researches, one DocumentVersion, relevant to both.
2. Same Source, two Researches, same DocumentVersion, relevant to only one.
3. Research B attaches after A processed the exact version; a later 304 creates B's missing contextual obligation without another body fetch.
4. Detach A while B remains active; A historical evidence remains readable but receives no new work.
5. Queue contextual work, change scope, retry after lease expiry; work uses the pinned old scope.
6. Ask/Briefing A cannot retrieve or serialize B-only evidence through a shared Source, Claim, or Story.
7. Worker crash after promotion/result commit does not create duplicate canonical evidence or a second paid call.
8. Managed API restart cannot independently run migrations while other managed writer ownership is active.
9. Feed autodiscovery/article/cross-domain redirect is URL-policy checked at each hop.
10. A Research check does not become successful until its sealed expected contextual descendants are terminal.

## Simplification guidance

Do not reward the existing architecture with more architecture.

Continue:

- SQLite;
- one scheduler/worker/job system;
- one acquisition service;
- immutable canonical Documents/Versions;
- exact evidence/provenance verification;
- Watch ID as durable Research identity;
- LivingReport as the backend synthesis model;
- derived Source robustness rather than redundant canonical scoring state.

Stop or defer:

- new root Research table;
- new report/Briefing storage model;
- new distributed queue/cache/database;
- React/router/framework rewrite;
- new non-Source Monitor acquisition semantics;
- generic autonomous research loops;
- trust scores;
- broad visual redesign before first-value correctness;
- architecture built only for hypothetical multi-user scale.

## Codex execution instruction

When implementation is authorized, treat this document as a binding delta to the existing rework plan:

1. Recheck current branch/schema before editing.
2. Incorporate the migration-authority prerequisite before the first M0 schema change.
3. Implement M0 review-gated slices in order.
4. When adapting old tests, explicitly document which old invariant is being superseded and why. Do not preserve the one-job-per-version behavior merely because prior tests encode it.
5. Preserve unrelated work and frozen Phase 29 trial boundaries.
6. Use existing scheduler/worker/acquisition/provenance machinery unless a failing acceptance case proves it cannot satisfy the contract.
7. Stop after each mandatory M0 review gate. Do not continue automatically into the next slice.
8. Record exact commands, test results, migration identity, surprises, and outcomes in `EXECUTION_PLAN.md` as implementation proceeds.

## Strategic stop rule

After the corrected Research boundary and first-value loop are implemented, further optimization is unlikely to materially improve Newsroom until real use answers this question:

> **After following a complicated subject for 30–60 days, does Newsroom let a knowledgeable user understand what changed, what remains uncertain, and why their understanding changed materially faster or more reliably than their existing workflow?**

If the answer is not clearly yes, simplify the product before adding more intelligence machinery.
