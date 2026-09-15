# ExecPlan: Research rework

## Purpose / Big Picture

A first-time user describes an interest, confirms scope and sources, starts a real check, understands the outcome, and explores exact evidence in an addressable Research. Manual/basic and AI-assisted modes share the same durable architecture. Correctness precedes visual cleanup. This file is the canonical implementation sequence; the architecture document supplies binding contracts, not optional suggestions.

## Progress

- [x] Initial code audit and isolated reproduction of delayed Start/shared-source processing collapse.
- [x] Owner decisions: honest no-credential mode; linked article retrieval in MVP; retain historical knowledge after detach.
- [x] Architecture challenge, invariant pass, schema necessity and final adversarial review.
- [x] Planning documents and acceptance matrix drafted and cross-checked.
- [x] Managed migration-authority prerequisite implemented; focused authority tests pass.
- [ ] Owner authorizes implementation.
- [ ] M0.1 Scope and membership history — schema-40 foundation landed; service integration and acceptance evidence remain.
- [ ] M0.2 Observations and unchanged manifests.
- [ ] M0.3 Contextual processing and recovery.
- [ ] M0.4 Evidence projection.
- [ ] M0.5 Shared-Source integration.
- [ ] M0.6 Integrated migration/recovery/retention gate.
- [ ] M1 Explicit checks and shared acquisition/linked articles.
- [ ] M2 Source setup, inspection, interpretation and assessments.
- [ ] M3 Addressable workspace and staged setup.
- [ ] M4 Research-scoped Updates, Ask and Evidence.
- [ ] M5 Automatic Research Briefing and scoped delivery.
- [ ] M6 Interpretability, feedback, visual and Settings cleanup.
- [ ] M7 Integrated qualification and migration/recovery rehearsal.

Unchecked milestones are not acceptance-complete. M0.1 contains partially
landed migration scaffolding, but its runtime integration and acceptance gate
remain open; no later milestone is implemented or verified here.

## Surprises & Discoveries

1. Source Monitor sharing is supported; semantic processing sharing is not. The duplicate guard is wrong as well as the job key.
2. Existing Question-first setup and model-only Source recommendation supersede parts of the older roadmap.
3. Feed metadata currently occupies a publication's canonical Document; simply adding article fetch can cause feed/article representation churn unless comparison is fidelity-aware.
4. Story reports, Watch target reports and Monitor digests cannot be relabeled interchangeably.
5. Existing Runs are reusable, but need expected-source and many-to-many work links. Job timestamps/run_id alone cannot support truthful progress.
6. A correct initial Ask filter is insufficient: expansions, snippets, Claims, Story prose and citations can widen scope again.
7. Exact historical source intervals cannot always be reconstructed. Migration must preserve partial evidence of ownership and label unknowns.
8. Final challenge found direct Source-equality guards in processing and the provenance verifier. Cross-domain feed articles need an explicit membership→discovery→article proof branch; merely changing acquisition would fail verification.

## Decision Log

Binding decisions D01–D31 are in [DECISIONS.md](DECISIONS.md). Any change here must reference a new/superseding entry. Key choices: Watch identity; contextual processing tuple; interval/observation history; shared existing acquisition; Runs plus causal joins; Watch target in existing LivingReport; strict common read boundary; no equivalent no-credential AI promise; managed migration authority; per-hop acquisition safety.

## Outcomes & Retrospective

Planning outcome: an executable staged design with migration/backfill and adversarial acceptance requirements. Current implementation outcome: managed migration authority and schema-40 additive M0.1 scaffolding landed through `9d8077c`, but M0.1 is not closed. The focused authority tests pass; the full suite currently has 1,016 passed, 2 failed, and 1 skipped. No live-provider or release qualification claim is made. Append actual milestone outcomes here during implementation, including unexpected compatibility problems and remaining owner gates.

Planning validation on 2026-09-14: nine expected Markdown documents present; local document links resolve; code fences balanced; 114 distinct acceptance case IDs; every explicit milestone acceptance reference/range resolves. Final code challenge added the cross-domain provenance proof and corrected endpoint migration ordering. These checks validate the plan's structure, not implementation behavior. Only `plan/rework-v2` files were authored in this continuation.

## Context / Orientation

Backend is Python/FastAPI/SQLite with direct SQL services. Frontend is React 18/TypeScript/Vite, no router dependency. Current branch schema authority is version 40; the schema-40 M0.1 foundation is present, while contextual runtime work remains incomplete. See TECHNICAL_FINDINGS for exact symbols. Preserve `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md` evidence/private/runtime invariants and frozen trial boundaries. `plan/astra` is historical execution evidence for reused work, not this rework's task queue.

### Execution method

Execute one bounded milestone slice at a time. Within an authorized slice,
continue through all of its numbered deliverables until the stated stop/exit
gate; an individual file, test, or subtask is not a handoff boundary. Split
commits by the numbered steps without weakening the exit gate. Do not launch a
monolithic Phase 0 refactor. New files listed below are **proposed**, existing
paths are verified. Keep old APIs working through explicit compatibility
adapters; do not let adapters become competing authorities. Do not add
framework/dependency/environment choices without a proven requirement.

All migration slices include integrity checks, explicit export/import handling, upgrade tests and a writer cutover. Never allocate a migration number from this document. Inspect latest migrations first. Backups and test DBs stay outside repository. Quiesce workers for upgrades; no old/new mixed writer process. Backfill is offline, deterministic, bounded and zero-paid. Missing legacy history is reported, not guessed.

Each milestone follows the acceptance protocol in ACCEPTANCE_TESTS. Focused tests first, appropriate backend checks and frontend lint/typecheck/build when touched; broaden once for integration, not repeatedly without cause. Live external calls require separate explicit authorization. Existing fake-provider/browser fixtures are sufficient for routine implementation.

## M0 — Foundational sequence and review stops

Implement M0.1 through M0.6 in order. Stop for review after **each** gate; a green gate permits review, not automatic commencement of the next foundational slice. This planning task authorizes none of them. Existing AC-I01–I12, AC-H01–H05, AC-S01–S06 and AC-R01–R04 remain binding alongside the new AC-M cases below.

**Migration version strategy for every slice:** schema39 is the inspected baseline, not a reservation. At implementation inspect latest migrations and allocate the next unused monotonically increasing version only if schema changes are required; record its actual number in this log. Never edit an applied migration. Each slice ships its own deterministic upgrade, safe metadata export handling, backup restore fixture and integrity checks. Later M0.6 is an integrated rehearsal, not postponed data safety. No forward FK to a table planned for a later slice.

**Common rollback:** quiesce producers/workers and take a verified pre-slice backup; preserve current dirty work. Before writer cutover, additive rows can remain with producers disabled. After cutover, use compatible code or restore the matching pre-upgrade backup/code in an isolated rehearsal; do not delete history or run old processing guards on new data. Real-data rollback is an operational action requiring separate authorization. Each slice's stop condition includes no unexplained row loss, no paid/network backfill, and recorded exact commands/results.

### M0.1 — Research scope and Source membership history

**Purpose / outcome:** Preserve Watch identity, approved target/scope history and attachment intervals before changing processing.

**Invariants:** Watch ID survives Story correction; current projection and intervals agree atomically. Unknown dates are not active intervals. Identical semantic scope may serve multiple Watch revisions; overlays survive every target-edit path.

**Schema / migration version:** Next available migration: Watch scope revisions/current pointer/intent, lifecycle events, membership intervals and minimal source_endpoints. No observation/job changes. Reuse Monitor scope history without forcing a Watch-revision FK onto reused snapshots.

**Backfill:** Inventory current links, correction history, target types and duplicate endpoints. EXACT attachment timestamp is not first monitoring time. Label reconstructed current scope and inferred ownership; retain unresolved historical records globally without new eligibility.

**Exact files/services:** newsroom/migrations.py, intelligent_monitoring.py, monitoring.py, domain.py, research_questions.py, evidence.py, story_corrections.py, domain_api.py, integrity.py, operations.py; proposed newsroom/research_membership.py. Check Source URL edit authority in existing domain service.

**Unique constraints:** Watch+revision number; explicitly open Watch+Source; Source+normalized endpoint URL+kind. Preserve existing target uniqueness and conflict resolution; no Source merge.

**Jobs / retries:** No contextual enqueue change. Atomic approval/attach/detach retries reuse committed result. Existing queued scope remains pinned; correction must not rewrite it.

**Compatibility:** Current setup, health, source list, cadence, policy, proposals and Question task planning retain current attachments. Subject/Story/Source-target advanced behavior remains reachable; Source-only scope cannot imply semantic eligibility.

**Automated tests:** AC-M01–M04, M16; adapt phase24 Watch, phase23a Story correction/resolution, phase25 Question and phase08 scope suites; add tests/test_research_membership.py with transaction failure injection.

**Manual reproduction:** Disposable DB: attach, edit target terms and Watch exclusions, pause, detach, edit scope, reattach; merge/split Story target. Inspect preserved IDs/revisions and current projection; processing queue unchanged.

**Export / integrity:** Export nonsecret interval/revision/endpoint facts with confidence labels. Validate target snapshots and open projection agreement. Backup restore preserves every ID; partial logical archive never invents omitted scope basis.

**Rollback:** Common rollback; before cutover disable new writers. Preserve closed intervals even if frontend compatibility changes are reverted.

**Stop / dependency / deferred:** STOP after migration/transaction/legacy tests and review of inventory classifications. Depends on explicit implementation authorization and baseline recheck. Defer observations, processing, UI redesign, destructive cleanup and general retarget UI.

### M0.2 — Research observations and unchanged-result manifests

**Purpose / outcome:** Record that each eligible Research saw an exact version, including unchanged content, before contextual execution is enabled.

**Invariants:** Admission pins membership and both scope identities. 304 reuses a specific successful item set; no Source-wide historical scan. Withdrawn subscriber cannot be newly admitted after in-flight response.

**Schema / migration version:** Next available migration: observations plus pending execution state/result links, endpoint snapshot item-version edges using acquisition event header. No future publication-discovery FK yet; M1 adds it. Snapshot completion/result persistence atomic.

**Backfill:** No invented legacy feed manifests. Existing relevance may link only with unambiguous historical ownership and explicit confidence; otherwise unresolved. Missing cached version/snapshot causes bounded recovery or unavailable.

**Exact files/services:** newsroom/acquisition.py, intelligent_monitoring.py, monitoring.py, migrations.py, integrity.py, operations.py; proposed newsroom/research_observations.py; tests/test_research_observations.py.

**Unique constraints:** Membership+version+Monitor scope+Watch revision admission; snapshot event+endpoint+representation; snapshot+item key edges. One pending obligation per observation; semantic reuse remains separate.

**Jobs / retries:** New contextual execution deliberately disabled. Persist pending obligations for M0.3 reconciliation. Existing legacy processing behavior remains; replay cannot lose/duplicate pending admissions.

**Compatibility:** Page/feed consumers keep existing result fields; add explicit exact-version manifest. Preserve legacy fidelity unknown. Do not claim linked articles were fetched.

**Automated tests:** AC-M05–M07, M17; adapt phase06 acquisition fixtures for 200 same hash, feed/page 304, missing cache, changed feed item sets, GUID/id and full-content basis, crash between persistence stages.

**Manual reproduction:** Fake one acquired page/feed result delivered to A/B admissions; repeat 304 after adding B. Assert independent observations/pending obligations, one supplied acquisition, no extra download during admission. This is not yet scheduler-level network coalescing proof.

**Export / integrity:** Validate observation membership/revision/version consistency and complete manifests; metadata archive describes omitted evidence and cannot be imported as live evidence. Verified backup round-trip includes exact manifests.

**Rollback:** Common rollback; stop observation producers and retain pending records. Do not replay all Source history to reconstruct them.

**Stop / dependency / deferred:** STOP after independent A/B pending admissions and unchanged fixtures pass with no admission-triggered duplicate acquisition. Depends M0.1. Defer contextual job producers to M0.3, concurrent network coalescing to M0.5 and linked article discovery to M1.

### M0.3 — Contextual processing identity and recovery

**Purpose / outcome:** One recoverable semantic obligation per version/Monitor/scope, independently serving Research contexts and all admission subscribers.

**Invariants:** Active guards, enqueue, rerun, direct API, recovery and reconciliation agree. Old scope never rebinds. Lease-stale workers cannot publish side effects. Partial completed pipelines reconcile missing stages.

**Schema / migration version:** Next available migration adds nullable canonical job context fields, active partial unique index and durable observation-to-job/result joins. Preserve existing relevance/analysis/promotion schemas and identities except necessary nullable provenance links.

**Backfill:** Validate old payload tuples; preserve IDs/keys/results. Inventory conflicting queued/running rows before index creation; do not silently cancel ambiguous paid work. Quarantine unresolved cases, stop migration if safe preservation cannot be established.

**Exact files/services:** newsroom/document_processing.py, jobs.py, article_analysis.py, evidence_promotion.py, provenance.py, automatic_story_resolution.py, story_automation.py, report_automation.py, runtime.py, domain_api.py, migrations.py, integrity.py, operations.py; research_observations.py.

**Unique constraints:** One active contextual processing job per version+processing Monitor+scope; legacy acquisition-only key separate. Subscriber joins unique observation+stage/job. Existing relevance tuple and analysis/promotion identities retained.

**Jobs / retries:** Quiesce old writers before switching all guards. Reconciliation consumes M0.2 pending obligations in bounded pages. Persist job/result attachment atomically. Retry reuses completed stages; check lease/attempt authority in every result transaction. Keep invocation reservations and unknown paid outcome rules.

**Compatibility:** Legacy acquisition-only jobs and old hashes remain valid; new contextual work cannot be suppressed by their version-only identity. No cross-domain verifier weakening; M1 introduces the narrow new proof branch.

**Automated tests:** AC-M08–M10; adapt phase19 processing, phase20 relevance, phase21 analysis, phase22 promotion, phase07 jobs and worker lease suites. Add tests/test_research_processing.py for crash-after-promotion and stale-worker overlap.

**Manual reproduction:** A/B different scope, one version; interrupt after result commit before job success, expire lease and replay. Verify two correct contextual decisions, stable canonical promotion IDs and no extra acquisition.

**Export / integrity:** Check payload/canonical columns, scope history, subscriber ownership and stage links. Export execution metadata only; backup restore proves pending reconciliation without changing keys or duplicating work.

**Rollback:** Common rollback; never restart version-only old writers against contextual jobs. Preserve ambiguous invocation records; rollback cannot authorize a second paid call.

**Stop / dependency / deferred:** STOP after exact tuple uniqueness, retry/lease/crash tests and old-worker cutover review. Depends M0.2. Defer output consumer migration and shared network dispatch.

### M0.4 — Research evidence projection

**Purpose / outcome:** One bounded authoritative answer to what canonical material is eligible for this Watch and why.

**Invariants:** Exact-version support closure throughout packets; global Claim acceptance is necessary but not sufficient. Historical admissions survive detach. Shared Story identity never imports unrelated evidence/prose.

**Schema / migration version:** Prefer no migration. Add only measured projection indexes in next available migration if query plans require them; no second truth store or Story membership table.

**Backfill:** None beyond prior admitted legacy records; unresolved material remains advanced-only. Never broaden eligibility to make old reports appear scoped.

**Exact files/services:** Proposed newsroom/research_context.py; existing evidence.py, provenance.py and read contracts in ask.py, reports.py, temporal.py, attention.py, workbench.py, research_questions.py; tests/test_research_context.py. Change consumer production behavior only in later named milestones.

**Unique constraints:** Derived DISTINCT canonical IDs, stable paginated ordering; no new canonical Claim/span identity.

**Jobs / retries:** Read-only deterministic projection, no enqueue/provider call. Canonical equivalent analyses are not independent corroboration; retain existing promotion IDs.

**Compatibility:** Legacy object-scoped Ask/reports stay unchanged. New projector unavailable for unsupported Source-only semantic scope; no global fallback. Acceptance remains existing global state.

**Automated tests:** AC-M11–M12, M18; core service adversarial fixtures for shared Claim/Story, outside support/contradiction/correction, soft-deleted target, old scope and detached membership. Existing Ask/report suites protect legacy reads.

**Manual reproduction:** Seed a shared Story with A-only and B-only evidence plus mixed global summary. Inspect A/B serialized projector packets: only qualified exact spans and safe text. Repeat after detach and backup restore.

**Export / integrity:** Projection is not exported as authoritative state; validate its retained input graph and fail closed if archive is incomplete. Backup restoration reproduces eligible ID sets.

**Rollback:** Disable new projection entry points if isolation fails; retain lineage and existing advanced reads. Never replace failure with broad Topic filtering.

**Stop / dependency / deferred:** STOP after packet-level isolation and query-plan review. Depends M0.3. Ask/Updates wiring M4, Briefing M5, Home M6; no UI claim of scoped output before those gates.

### M0.5 — Shared-Source correctness integration

**Purpose / outcome:** Prove one compatible endpoint fetch fans out into independent Research processing without replacing scheduler or worker.

**Invariants:** Concurrent identical endpoint/policy/representation work coalesces; subscriber freshness and authorization checked independently. Pause/detach/reattach and scope changes cannot erase or invent obligations.

**Schema / migration version:** Next available migration if needed: canonical acquisition job key and durable subscribers/result links. Introduce minimal check_sources/check_work source-item identity here for scheduler coalescing: request_identity is the Monitor dispatch job ID, run_id nullable for compatibility dispatch, unique request_identity+membership; existing Monitor job retains authority; Watch Run request fields/UI orchestration remain M1. No duplicate temporary subscriber schema.

**Backfill:** Legacy jobs/runs remain unscoped. No manufactured expected sets. Duplicate Source endpoints remain separate source bindings; share transport result only when compatible, never infer publisher authority from URL alone.

**Exact files/services:** newsroom/acquisition.py, jobs.py, monitoring.py, runtime.py, intelligent_monitoring.py, migrations.py, integrity.py, operations.py, research_observations.py; proposed newsroom/research_checks.py limited to queue subscription/closure. tests/test_research_shared_source.py and scheduler/monitor coalescing suites.

**Unique constraints:** One active compatible acquisition key; source-item and typed work edge uniqueness; durable result fanout. Known aliases share only after verified equivalence; unknown aliases may require initial separate fetches.

**Jobs / retries:** Dispatch releases sole worker; durable result consumption finalizes Monitor activity once. Active source-item guard spans dispatch completion. Atomic child links/sealing prevents premature finish. Subscriber cancellation cannot cancel remaining eligible work.

**Compatibility:** Use existing AcquisitionService/JobService, cadence and budget owners. Existing global Runs retain finalization semantics; Watch-specific Runs later use sealed closure. No new network capabilities in M0.

**Automated tests:** AC-M13–M15, M19; full A/B page and existing feed acquisition under fake transport, fail/retry, detach in-flight, reattach new scope, 304 new subscriber, duplicate endpoints and concurrent requests. 1 Source/100 Watches/1 version fixture verifies fetch and bounded evaluation counts.

**Manual reproduction:** Run fake scheduler/worker loop with A/B sharing endpoint; count actual transport calls=1 for concurrent compatible check, two contextual results with opposite relevance, no leaked evidence. Resume B against unchanged version; B learns without duplicate article body acquisition. A fresh explicit later check may perform one conditional request.

**Export / integrity:** Backup restore between fetch persistence and subscriber completion; missing fanout repaired once. Validate every causal link and terminal sealed state. Metadata archive remains non-runnable.

**Rollback:** Common rollback; stop dispatch, preserve durable subscribers, drain/cancel only according to each subscriber authority. Do not delete shared results.

**Stop / dependency / deferred:** STOP after full integration and fanout/performance gate. Depends M0.4. M1 adds Watch Run requests/counters, Check now/Start, linked-article continuations, cross-domain proof and full feed fidelity UI; does not reimplement shared endpoint coordination.

### M0.6 — Integrated migration, recovery and retention qualification

**Purpose / outcome:** Prove all prior slices preserve existing data and recover together; close audit gaps before M1.

**Invariants:** No guessed history, silent discarded conflicts, private export expansion or omitted-evidence certification. Retained evidence/revisions keep causal records. No automatic history purge.

**Schema / migration version:** Prefer no migration; only next available corrective additive migration justified by failed rehearsal. Never consolidate/rewrite applied M0 migrations.

**Backfill:** Rehearse schema39→each slice→latest on disposable fixtures/copy; compare pre/post IDs, counts, checksums and EXACT/INFERRED/UNKNOWN inventories. Ambiguous detached ownership and old feed content remain unresolved explicitly.

**Exact files/services:** newsroom/migrations.py, operations.py, integrity.py, storage.py and actual deletion/soft-delete owners; existing recovery runbooks; tests/test_research_recovery.py plus phase23e/phase24 compatibility/export suites. No production data mutation during qualification.

**Unique constraints:** Exercise every new unique/FK constraint against conflicts and repeated imports; never use row dropping to make a migration pass.

**Jobs / retries:** Restore queued/running/expired/partially completed work under matching new code; preserve idempotency and invocation status. Logical metadata import cannot enqueue executable or paid work.

**Compatibility:** Keep safe metadata export privacy contract and supported legacy formats. New incomplete archive is explicitly not runtime recovery; reject unsupported restore before mutation. Full recovery uses verified backup and artifact closure.

**Automated tests:** AC-M16–M20 and AC-R01–R04; complete backend regression once after focused gates, with migration interruption, duplicate conflict, missing parent, snapshot consistency, soft-delete retention and restored projection equivalence.

**Manual reproduction:** Restore full verified backup to isolated root, compare A/B eligible IDs and job outcomes, then export metadata and demonstrate omitted-content status/unsupported import rejection. No live trial, port 8127, paid calls or production restore.

**Export / integrity:** Single read-snapshot metadata export; accurate actual imported/conflict counts. FK plus semantic authority verification. Verify retained artifact references and no cascading deletion of causal history; inventory existing backup/session retention separately.

**Rollback:** Demonstrate matching pre-upgrade backup/code restoration in disposable root and document interruption recovery; owner decides real-data action only if rehearsal exposes unavoidable destructive migration.

**Stop / dependency / deferred:** STOP after all six gates, regression and recovery evidence reviewed. Depends M0.1–M0.5. Defer M1 and all implementation until separately authorized; unresolved historical facts are reported, not repaired by invention.

## M1 — This check, shared acquisition and feeds as sensors

**User outcome / why now:** Start checks now; Check now is repeatable; articles discovered through feeds are retrieved once and attributed correctly. User can trust the result of this check. I01/I05/I10/I11/I12/I13.

**Steps:** (1) extend Runs/source items/work joins and idempotent request contract; (2) integrate scheduler and source-item active coalescing; (3) route compatible acquisition through shared durable continuations calling existing AcquisitionService; (4) add endpoint/discovery/fidelity records and linked-article continuation; (5) aggregate final outcomes and recover crashes at each edge.

**Exact files:** `newsroom/jobs.py`, `scheduler.py`, `monitoring.py`, `acquisition.py`, `document_processing.py`, `article_analysis.py`, `provenance.py`, `evidence_promotion.py` verification integration, `runtime.py`, `worker.py` only for required handler integration, `domain.py`, `domain_api.py`, `intelligent_monitoring.py`, `migrations.py`, `integrity.py`, `operations.py`; proposed `newsroom/research_checks.py`. Frontend existing WatchManagement and `lib/types.ts`, `lib/api.ts` for Check now/progress compatibility controls.

**Backend delta / necessity:** due-time toggle alone cannot group check descendants or dedup fetches. Reuse Runs/JobService with expected-source snapshots, many-to-many subscribers, active acquisition keys and results. Existing feed parser/transport/byte and redirect bounds stay authoritative. Persist feed→article edge and origin separately; representation-aware unchanged tests prevent metadata/body churn. Monitor dispatch must not block the worker awaiting a child job. Finalize activity once per source item.

**Schema/backfill:** runs nullable Watch/request fields; extend check_sources/check_work and acquisition identity from M0.5; publication_discoveries and result links; DocumentVersion fidelity/discovery reference; nullable contextual job/ArticleAnalysis observation provenance reference. Extend/use the endpoint identity introduced in M0 without merging by slug/domain. Old feed versions retain truthful legacy metadata; no claim that old articles were fetched. Legacy Runs remain unscoped. Validate the new cross-domain authority proof without weakening legacy source-equality/exact-evidence checks.

**Compatibility risks:** independent cadence, policy ceilings, old manual monitor jobs, retries after orchestration completion, normalization aliases, singular Document.source_id. Keep existing monitor activity semantics and source-specific budgets; use active source-item guard beyond job completion. Test old direct acquisition callers and feeds with no monitored Watch.

**Security/privacy/cost:** cross-domain links are limited to directly discovered public publications approved in endpoint policy; every redirect revalidated; no JS/paywall/login bypass. Shared fetch work charges one request while each semantic analysis has separate admission. Bounds and deferred counts explicit. No paid fixtures.

**Automated gate:** AC-C01–C14, AC-F01–F12 plus AC-I matrix under shared acquisition. Reuse phases 06/07/08/18/19, scheduler/monitor coalescing, lease suites; proposed `tests/test_research_checks.py`, `tests/test_feed_article_acquisition.py`.

**Manual acceptance:** new Watch with two fixture feeds and one failing page; press Start twice, inspect one check, verify partial outcome and full-article citation, retry only failed source, restart worker mid-chain. Scheduler stopped→due-not-running display.

**Rollback:** stop producers, drain/cancel known work, snapshot. Roll back code only to compatible reader/writer; otherwise matching restore. Never delete shared evidence to undo a check. **Dependencies:** M0. **Non-goals:** broad crawling, PDF/JS engine, multiple independently scheduled endpoints per Source, new scheduler/worker service.

## M2 — Honest setup capabilities, Source inspection and assessments

**User outcome / why now:** user can supply one URL or ask for starter Sources, review intent/profile proposals and approve exactly what will run. I03/I04/I08/I09/I10. Needs M0/M1 provenance and safe endpoint contracts.

**Steps:** (1) one-field deterministic inspector/manual preview; (2) persist intent/Focus proposal and approval; (3) layer Source assertions/overrides; (4) extend existing recommendation lane with one bounded external search adapter and coverage plan; (5) connect one-off setup authorization without enabling monitoring.

**Exact files:** `newsroom/acquisition.py`, `ai.py`, `article_analysis.py`, `domain.py`, `domain_api.py`, `intelligent_monitoring.py`, `jobs.py`, `migrations.py`, `integrity.py`, `operations.py`; proposed `newsroom/source_setup.py`. Frontend `WatchManagementView.tsx`, `AIProviderSettings.tsx`, `lib/types.ts`, `lib/api.ts` until M3 extracts the staged flow.

**Backend delta / necessity:** current local recommendation is empty, model URLs unverified, HTML alternate detection absent, intellectual profile history absent, and assistance is coupled to saved Watch routing/budget. Add preview/proposal contracts, reuse resolver/vault/reservations and model-only candidate validation. Search adapter selection uses documented API, fake contract fixture and bounded results; adapter credentials live in existing vault metadata infrastructure. No new credential store or search platform.

**Schema/backfill:** source_assessments, persisted setup proposals/operation authorization metadata where existing invocation rows cannot express one-off grants. Existing operational source_profiles unchanged. Proposals refer to stable draft/Watch and scope revision; stale approval conflicts. Do not backfill invented AI profile judgments.

**Compatibility risks:** existing vocabulary approvals, rejected candidate identity, question-first setup retry semantics, provider config generations and disabled routes. Preserve all. Manual completion must not require profile AI success.

**Security/privacy/cost:** inspection may contact only the pasted/reviewed endpoint and bounded declared discovery links; never becomes monitoring. Search receives approved scope, not accumulated private corpus. Explicit call maximum/expiry/capability; global paid setting unchanged. Cancel before call incurs no call; ambiguous paid completion is not automatically retried.

**Automated gate:** AC-N01–N09, AC-P01–P09, AC-A01–A08; phase24 recommendation/vocabulary, phase06 security and provider budget suites; proposed `tests/test_source_setup.py`, `tests/test_source_assessments.py`, `tests/test_research_setup.py`. Preserve existing `tests/test_phase29_frontend.py`, `test_phase32_frontend.py` contracts or replace obsolete wording assertions with behavior tests.

**Manual acceptance:** no credentials→manual scope + URL→approved paused draft; configured fake services→coverage/candidates/profile→override→approve; failures retain draft and never activate Source.

**Rollback:** disable optional proposal routes; manual mode still works; preserve assertions/approvals as history. Schema restore only matched to code. **Dependencies:** M0/M1. **Non-goals:** local model installation, autonomous discovery, scraped search results, universal adapter catalog, numeric trust scores.

## M3 — Addressable workspace and staged creation

**User outcome / why now:** Research is a recognizable workspace; links/reload/Back/new tab work; setup no longer exposes the admin page. I16 and prior input/authority invariants.

**Steps:** typed hash parsing/serialization and legacy routes; Research list/workspace layout; staged creation using M2 APIs; direct-link evidence route shell; normal vs advanced navigation. Preserve draft uncertain-save recovery separately from navigation.

**Exact files:** `frontend/src/App.tsx`, `components/AppShell.tsx`, `components/ViewPrimitives.tsx`, `views/WatchManagementView.tsx`, `views/ReportsView.tsx`, `views/StoryEvidenceView.tsx`, `views/DocumentView.tsx`, `views/AlertsView.tsx`, `views/InboxView.tsx`, `lib/types.ts`, `lib/api.ts`; proposed `lib/routes.ts`, `views/ResearchListView.tsx`, `views/ResearchWorkspace.tsx`, `views/ResearchSetupView.tsx`. Backend `domain_api.py` only for bounded summary/read composition over M0/M1 services.

**Backend delta / necessity:** if list summaries require N+1 health calls, expose one bounded paginated projection; no new persistent dashboard model. **Frontend:** UX document is binding for screen/action/state behavior; tabs must not render unfiltered legacy output while M4/M5 are pending—show truthful unavailable/under-construction fixture gate in development, not a released mixed scope product.

**Schema/backfill:** none beyond prior milestones. **Compatibility:** legacy hash links map safely; auth redirects preserve routes; storage selection no longer mandatory. **Security/privacy/cost:** route IDs validated on server, no network/provider calls from navigation, no prompt storage in URL. **Automated:** AC-U01–U10, AC-N setup browser cases; existing frontend checks; reuse Python Playwright scripts in proposed `scripts/rework_browser_smoke.py` with fixture backend.

**Manual:** create/open two Researches in separate tabs, navigate Update/Evidence, reload and Back, authenticate into deep link, inspect mobile tab navigation. **Rollback:** revert frontend route entry while preserving backend data; maintain old hash adapters. **Dependencies:** M0–M2. **Non-goals:** React Router, framework/component-library migration, broad visual redesign.

## M4 — Scoped Updates, Ask and exact Evidence

**User outcome / why now:** all research content reflects this Research, and citations expose exact evidence. I04/I06/I07/I10/I15/I16.

**Steps:** Watch Ask scope persistence; constrain every retrieval expansion/final packet; scoped Update projection/why-match basis; contextual Ask and evidence drawer routes; shared-Source adversarial browser and API tests.

**Exact files:** `newsroom/ask.py`, `domain_api.py`, `research_context.py` (from M0), `story_evolution.py`/`temporal.py` read adapters only, `migrations.py`, `integrity.py`, `operations.py`; frontend `views/AskView.tsx`, `StoryEvidenceView.tsx`, `DocumentView.tsx`, `InboxView.tsx`, `components/EvidenceView.tsx`, `ResearchWorkspace.tsx`, `lib/types.ts`, `lib/routes.ts`.

**Backend delta / necessity:** existing scope vocabulary has no Watch and broad source/story expansion leaks. Add CHECK vocabulary via safe migration; retain legacy advanced scopes. No change to global Claim support state merely to render a scoped answer. Include correction/question/note/fallback/historical packets in final boundary checks.

**Schema/backfill:** Ask scope CHECK rebuild with old IDs/history preserved; no reclassification. **Compatibility:** shared global Stories can contain mixed Research claims; do not copy their raw summary. Missing artifacts fail explicitly. **Security/privacy/cost:** no global evidence in Research prompts/snippets; ordinary Ask remains labeled basic local; richer paid Ask is deferred, not quietly enabled by Article Analysis settings.

**Automated:** AC-S01–S10, AC-E01–E06, AC-U citation cases; phases14/22/28/29 plus `tests/test_research_ask.py` (proposed). **Manual:** shared Reuters fixture, contradictory B-only evidence, old version and detached Source; ask A and verify every visible statement/citation is in A; direct B citation URL in A rejected.

**Rollback:** disable Watch Ask entry if qualification fails; never substitute global Ask. Preserve conversation history. **Dependencies:** M0/M3 (M1/M2 already prerequisites for integrated UI). **Non-goals:** global synthesis, semantic chat upgrade, new evidence ledger.

## M5 — Automatic Research Briefing and delivery separation

**User outcome / why now:** every Research has current evidence-backed synthesis without manual report creation; delivery settings control notification timing. I06/I07/I11/I15.

**Steps:** add Watch target to existing LivingReport; build scoped input; ensure one report per Research; enqueue refresh from scoped evidence/state/correction changes and check closure; separate scoped delivery identity/preferences; expose current/previous revisions.

**Exact files:** `newsroom/reports.py`, `report_automation.py`, `alert_automation.py`, `story_corrections.py`, `jobs.py`, `runtime.py`, `domain_api.py`, `research_context.py`, `migrations.py`, `integrity.py`, `operations.py`; frontend `ReportsView.tsx`, `ResearchWorkspace.tsx`, `InboxView.tsx`, `lib/types.ts`, `lib/api.ts`.

**Backend delta / necessity:** old Watch targets and Monitor-only digest query cannot represent isolated Research synthesis/delivery. Extend existing report/digest models, hooks, input hashes and scope keys; do not add a competing Briefing table. Bound affected-Watch fanout and unique refresh work. Deferred no-evidence is a usable state; exhausted refresh failure closes check with stale synthesis detail.

**Schema/backfill:** LivingReport target CHECK includes Watch; existing unique target identity reused. Briefing/schedule scope fields and scope-aware uniqueness require compatible SQLite rebuilds. Preserve old revisions/digests as legacy; create new empty Watch report shells, no paid backfill or altered prior input hashes. `get_for_watch` old target mapping remains advanced compatibility, not a false isolated report.

**Compatibility risks:** corrections/alert causes, period identity, existing singleton schedule, concurrent refresh, duplicated delivery, no-claim semantics. **Security/privacy/cost:** all narrative/citations use scoped service; synthesis initially uses existing deterministic evidence-bound rendering, no implicit new paid route; notifications use existing opt-in channels.

**Automated:** AC-B01–B10, AC-C completion, AC-R migration; phases11/23c/23d/29; proposed `tests/test_research_briefings.py`. **Manual:** check yields evidence→Briefing auto-updates; delivery off→current Briefing still exists; two Researches same day remain isolated; correction updates current revision without rewriting previous one.

**Rollback:** pause new refresh/delivery producers; keep immutable Watch revisions accessible; restore matched schema only if necessary. Do not deliver old global digest as a Research fallback. **Dependencies:** M0/M1/M4. **Non-goals:** second report model, newsletter infrastructure, rich generative synthesis route.

## M6 — Interpretability, feedback, visual hierarchy and Settings

**User outcome / why now:** user understands relevance/coverage, can record poor results, and reads comfortably without operator clutter. I03/I04/I06/I16.

**Steps:** expose pinned match explanation; Focus-source coverage with health separation; Research Update feedback reasons; simplify Home/Settings and typography/cards/actions; keyboard/mobile checks. These are mechanical changes against settled architecture.

**Exact files:** `newsroom/attention.py`, `research_context.py`, `domain_api.py`, `migrations.py`, `operations.py`, `integrity.py`; frontend `InboxView.tsx`, `AdminViews.tsx`, `AIProviderSettings.tsx`, `ResearchWorkspace.tsx`, `components/ViewPrimitives.tsx`, `components/AppShell.tsx`, `styles.css`, `lib/types.ts`.

**Backend delta / necessity:** existing Attention not_useful does not encode every Research Update/reason; add small append-only Research feedback record instead of adaptive ranking. Coverage and explanation are read projections; no new coverage ontology or ML. **Schema/backfill:** feedback Watch/event/reason/time relation; prior Attention decisions retained, not invented as Research-specific feedback.

**Compatibility:** mark-reviewed uses existing cursor/high-water behavior; advanced tools remain reachable. **Security/privacy/cost:** feedback stays local; no automatic AI learning/source changes; no provider configuration during normal rendering. **Automated:** AC-X01–X05, AC-U accessibility/Settings, AC-P override; proposed `tests/test_research_feedback.py` and browser scenarios. **Manual:** explain why an Update matched, Not useful→reload, small-screen evidence, 200% zoom, keyboard settings; raw key dump hidden in ordinary mode.

**Rollback:** UI revert preserves feedback/history; no evidence deletion. **Dependencies:** M3–M5. **Non-goals:** design-system rewrite, new ranking models, full source track-record analytics.

## M7 — Integrated first-value and recovery qualification

**User outcome / why now:** first-value contract is demonstrated end to end, not inferred from isolated services. Protects all invariants.

**Exact files:** proposed `tests/test_rework_acceptance.py`, `scripts/rework_browser_smoke.py` (reuse M3 harness); extend relevant existing regression tests and update `plan/rework-v2` evidence. Production files change only for demonstrated bounded defects.

**Backend/frontend/schema:** no planned new feature or schema. Rehearse clean install and upgrade from schema39 with legacy jobs, attached/detached inferred history, reports/digests, credentials configured but fake providers. Verify export/import and full backup recovery. Repeat after actual final migration set; never assume schema39→latest succeeds because individual migrations do.

**Compatibility/security/cost:** demonstrate old APIs/advanced provenance, zero-paid no network-provider calls, SSRF redirects and prompt-injection resistance, bounded shared acquisition/analysis attribution. Real service tests are optional separately authorized and budgeted; installed qualification remains separate.

**Automated:** all AC cases; full `python -m pytest -q`, applicable Ruff/backend checks; frontend `npm run lint`, `npm run typecheck`, `npm run build`; browser first-value/no-credential and A/B isolation. Record counts, hashes, commands and failures. No dependency install solely to claim a test pass; use established workspace/runtime instructions.

**Manual:** replay AC-North-Star and AC-Manual; owner evaluates source usefulness, local analysis honesty, Briefing quality, phone behavior and failure recovery. A successful quiet check is acceptable engineering behavior but cannot alone prove useful intelligence. **Rollback:** verify restore in disposable environment with matching prior code; no automatic production restore. **Dependencies:** M0–M6. **Non-goals:** promotion/deployment/value verdict by assertion.

## Conditional later work — not authorized MVP tasks

Focus-area independence only after observed need for separate sources/cadence/budget/state; Claim Diff, Belief History and Evidence Time Machine use preserved observation/scope/Claim/report times and causes. Deeper lineage UI reuses SourceRobustnessService. Any later milestone requires its own bounded outcome, evidence and owner scope decision. No preparatory platform beyond the MVP history already required.

## Stop / recovery rules

Stop a milestone on demonstrated loss of provenance, unexplained legacy ownership, unbounded fanout, unexpected paid invocation or cross-Research content leak. Preserve diagnostic IDs and fixture evidence; fix within the current contract if possible. Ask the owner only if the remedy changes product identity/history/privacy/cost/MVP scope or needs material destructive migration. Routine typed routes, CSS choices and service composition do not reopen architecture.

## Final pre-implementation audit record

D20–D26 refine this plan after code inspection: Story correction target mutation; semantic/Watch revision separation; absent 304 feed manifests; privacy-limited logical export; Run auto-finalization based only on jobs.run_id; canonical promotion identity; duplicate endpoint migration conflicts. See TECHNICAL_FINDINGS final audit for evidence and architecture section K for binding contracts. M0.5 now owns minimal shared endpoint coordination; M1 extends it. No production implementation or new live validation was performed.

Final audit structural validation: nine documents; 134 unique acceptance definitions (20 new AC-M cases); six M0 sub-milestones; relative document links resolve; code fences balanced. No production code or test fixtures authored in this audit. No new implementation regression run claimed.
