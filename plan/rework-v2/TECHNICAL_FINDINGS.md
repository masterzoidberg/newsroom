# Technical findings

Audit scope: the pre-M0.1 implementation baseline plus current working files,
not only historical plans. The audit baseline was schema 39; the current branch
adds a schema-40 M0.1 foundation whose runtime integration is not yet verified.
Paths below are repository-relative. VERIFIED means read in code, or reproduced
where explicitly stated. It does not mean the whole subsystem was live-qualified.

## Evidence map

| Finding | Status | Code evidence and consequence |
|---|---|---|
| Topic setup composes Topic + policy + paused Watch atomically; request UUID gives retry identity; prose saved in Topic.description | VERIFIED | `newsroom/intelligent_monitoring.py:WatchService.create_paused_setup`, `_existing_paused_setup`; reuse composition and validation |
| Question-first setup exists in dirty working tree | VERIFIED | `newsroom/domain_api.py:_create_question_watch_setup`, `/watches/setup`; `frontend/src/views/WatchManagementView.tsx`; Astra NEXT still calls AST-41 upcoming; do not rebuild it |
| One Watch per target | VERIFIED | `newsroom/migrations.py` migration 0024 `watches UNIQUE(target_type,target_id)`; no sibling Watch hierarchy |
| Source Monitor identity includes information need | VERIFIED | migration 0024 partial `monitors_need_identity_idx`; `WatchService._need_for`, `_resolve_monitor`; `watch_sources.monitor_id UNIQUE` |
| Pause/resume changes only owned Monitor enabled state, not due time | VERIFIED + reproduced | `WatchService._set_status`; `MonitorService.create` defaults next_check_at to now + base cadence |
| New source Monitors begin an hour out under ordinary setup | VERIFIED + reproduced | setup base cadence 3600; immediate scheduler tick after two resumed fixture Watches enqueued 0 |
| No Research Check now contract | VERIFIED | `newsroom/domain_api.py` has scheduler tick, Monitor edits, job reruns and Watch resume; none supplies Research-specific idempotent expected-work/result identity |
| Durable scheduler already coalesces active Monitor work | VERIFIED; focused tests passed | `newsroom/jobs.py:SchedulerService.tick`, `_active_monitor_check_id_tx`, `JobService.rerun`; `newsroom/scheduler.py`, `worker.py`, `job_lease.py` provide runtime loop/worker/renewal |
| Only source Monitor targets acquire | VERIFIED | `newsroom/monitoring.py:MonitorExecutionService.handle`; others produce `unsupported_target`; Topic/Question Watches work through source Monitors |
| Global version-only processing collapses contexts | VERIFIED + reproduced | `newsroom/document_processing.py:enqueue_document_version_processing_tx` key `document:{version_id}`; `jobs.py:_enqueue_check_tx` active guard also version-only; payload pins one monitor/scope |
| Unchanged returns skip processing | VERIFIED + reproduced | `AcquisitionService._persist_document`, `_persist_feed_entries`, 304 paths; two fixture Monitors→one retrieved and one unchanged result→one processing job/one monitor |
| Relevance storage already has the right granular uniqueness | VERIFIED | migration 0017 `document_version_relevance UNIQUE(document_version_id,monitor_id,scope_version)`; `_evaluate_relevance` loads `scope_at_version` |
| Analysis identity is already context-sensitive | VERIFIED | `article_analysis.py:analysis_identity_hash` includes relevance_id, scope_version, provider/model/input hashes; safe reuse is per identity, not globally across different Research prompts |
| Detach deletes current ownership join | VERIFIED | `WatchService.remove_source` disables Monitor then deletes `watch_sources`; Source/documents survive but historical Research ownership is not reliably preserved |
| Source identity is primarily slug-based | VERIFIED | `domain.py:CoreService.create_source`; `_resolve_source` falls back to matching slug after conflict; same label can resolve wrong source; not a robust publisher/endpoint identity |
| Document URL identity is global, Source ownership singular | VERIFIED | migrations: documents.canonical_url_hash UNIQUE and source_id NOT NULL; feed persistence skips existing documents owned by another Source; cross-domain discovery needs separate provenance |
| Cross-domain processing conflicts with current provenance ownership checks | VERIFIED in final challenge | `document_processing.py:enqueue_document_version_processing_tx` and handler, `provenance.py:validate_analysis_provenance` require Monitor target Source = Document Source; new feed discovery authority path must be validated, not bypass the check |
| Candidate URL dedup differs from document normalization | VERIFIED | `_normalized_candidate_url` casefolds entire URL; `url_norm.py` preserves meaningful query/path structure; avoid silently merging case-sensitive paths |
| Structural and actual network safety are distinct | VERIFIED | `AcquisitionPolicy.check_url`, `_validated_addresses`, `UrllibHttpTransport`, pinned connections/peer verification/redirect checks; inspection must reuse them at every hop |
| RSS and Atom parser exists; website feed discovery does not | VERIFIED | `acquisition.py:FeedParser`; `SafeHTMLExtractor` discards anchors/link metadata; no website `rel=alternate` inspector/sitemap discovery implementation |
| Feed processing uses metadata, not article bodies | VERIFIED | `_persist_feed_entries` creates `feed_metadata` artifact and metadata DocumentVersion; no linked article fetch; `article_analysis.py:canonical_feed_analysis_view` builds exact analysis input |
| Model-only cold-start recommendations exist | VERIFIED | `WatchService.discover_sources`, `OpenAICompatibleSourceDiscoveryProvider`, managed `source_discovery` route; `provider_requests` differs from `external_requests=0` (the latter means no search/site requests, not no provider network traffic) |
| Corpus discovery is narrower than its names suggest | VERIFIED | `_discovery_proposals` uses known relevant sources, lineage parents and cross-domain origins; `feed_discovery` is not RSS autodiscovery |
| Ordinary new drafts disable discovery and have zero policy paid budget | VERIFIED | `create_paused_setup`; current UI gates recommended sources; the guided pre-Start path needs explicit bounded assistance independent of monitoring activation |
| Existing SourceProfile is operational | VERIFIED | migration 0006/source_profiles and `SourceProfileService`: activity/failure/duplication/usefulness/acquisition methods; not layered intellectual assessment with override history |
| Ask source/Monitor scope expands to all source Documents | VERIFIED | `ask.py:_scope_sets`; no Watch/Topic Ask scope; `_expand_item`, `_expand_scope`, `_load_claims`, `_load_evidence` and `_resolve_citation` can broaden through evidence/claims and must be constrained throughout |
| Ask requires database scope vocabulary migration | VERIFIED | migration 0028 ask_conversations CHECK; adding Python scope alone fails persistence |
| Local Ask is selected by ordinary UI | VERIFIED | `frontend/src/views/AskView.tsx` provider_mode local; no normal semantic provider-backed Ask route |
| Automatic Story stage creates accepted Claims and Story reports through guarded chain | VERIFIED | `report_automation.py:AutomaticReportStageExecutionService`, `_accept_claim_tx`, `_ensure_report_tx`; human override and contradiction checks; preserve |
| Watch reports target their Topic/Question/etc. | VERIFIED | `reports.py:LivingReportService.create_for_watch`, `get_for_watch`; `_story_ids` traverses broad target relations and `_accepted_claims` includes all selected Story claims |
| Scheduled Briefings read Monitor-targeted reports only | VERIFIED | `BriefingService.generate`; period/timezone/window uniqueness excludes Research scope; same-window selections can accumulate in one Briefing |
| Schedule is one workspace-level owner schedule | VERIFIED | `BriefingScheduleService.schedule_id=1`; scheduler enqueues it; current state and delivery are not equivalent concepts |
| Progress can be distorted by history | VERIFIED | `WatchService._progress_payload`: latest 100 global processing jobs then filter, old failed rows, old result links, one latest activity; successful processing without links can remain “processing” |
| No verified promotion currently can raise an error | VERIFIED | `DocumentProcessingExecutionService.handle` in `document_processing.py` raises DomainValidation when promotion outcomes exist but none is verified; planned outcome mapping must separate valid rejected proposals from broken provenance, not relabel all errors as quiet success |
| Exact evidence/promotions have strong reusable invariants | VERIFIED | `evidence_promotion.py:verify_automatic_promotion`, unique exact excerpt checks, `content_artifacts.py`, `provenance.py`, immutable versions/history; do not weaken |
| Home/review/feedback foundation already exists | VERIFIED | `InboxView.tsx`; `attention.py:changes_since`, `advance_review_cursor`, `decide`; `temporal.py`; attention decisions include not_useful, but no general Research Update reason contract |
| Source independence machinery exists | VERIFIED | `source_robustness.py` computes lineage dependency groups/counterfactuals; do not count repeated wire reports as independent confirmations |
| Local analysis is deliberately basic | VERIFIED | `ai.py:LocalArticleAnalysisProvider` sentence extraction, capitalization entities/locations, fixed confidence; local synthesis joins propositions; not equivalent to semantic understanding |
| Managed provider infrastructure should be reused | VERIFIED | `domain.py:AIConfigurationService`, OS vault, `article_analysis.py:AIConfigurationResolver`, `jobs.py:BudgetService`; current managed capabilities article_analysis/vocabulary/source_discovery; no generic search/intent/profile/Ask capability yet |
| Routing is flat hash plus storage | VERIFIED | `App.tsx:initialView`; selected Watch localStorage in WatchManagement/Reports; Story/Document navigation sessionStorage; object routes absent |
| Ordinary navigation still exposes backend workflows | VERIFIED | `AppShell.tsx:SIMPLE_NAV_ITEMS`: Home, Stories, Ask, Reports, Watches; Advanced is navigation density, not authorization |
| Settings mixes preferences/provider controls/raw keys | VERIFIED | `AdminViews.tsx:SettingsView`, `AIProviderSettings.tsx`; retain secure provider UI in advanced AI configuration |
| Visual issues exist alongside responsive/accessibility foundations | VERIFIED in CSS/components; live appearance UNKNOWN | `styles.css` title up to 4.1rem vs .65–.8rem metadata; media queries 1050/760/480, reduced motion; ViewPrimitives/EvidenceView support reuse |

## Reproduction and verification record

Initial audit ran 19 focused tests successfully: shared-source Monitor ownership, paused setup composition, model-only cold-start recommendation, Ask object-scope isolation and `tests/test_scheduler_coalescing.py`. These are existing contracts, not proof of the proposed architecture. A larger initial test invocation did not retain a complete result in the audit record; no full-suite pass is claimed.

Isolated fake-transport reproduction: migrate a temporary database; create two paused Topic Watches with approved UAP terms; attach the same page Source; resume both; tick immediately; retrieve identical HTML under both Monitor IDs. Observed: `start_due_jobs=0`, outcomes `retrieved`, `unchanged`, processing jobs=1, distinct processing monitors=1, attachments=2. No external traffic or paid calls.

The challenge pass reconfirmed version-only active guards, contextual analysis identity, deleted attachment joins, Source slug fallback, report scope/period uniqueness and explicit export allowlists. No production code was changed. No live instance/trial contacted.

## Test and migration implications

Existing relevant suites: phases 06 acquisition, 07 jobs, 08 monitors, 11 reports/briefings, 14 Ask, 18 artifacts, 19 processing, 20 relevance, 21 analysis/invocation, 22 promotion/trust, 23 Story/report/alert chain, 24 Watches, 25 Questions, 28 attention/robustness, 29 temporal; scheduler/monitor coalescing and worker lease suites. Frontend pytest checks are largely source-contract assertions. `scripts/ast32_source_smoke.py` and other Astra smoke scripts already use Python Playwright; reuse that harness rather than adding a second browser stack.

The audit baseline was schema 39; the current branch adds schema 40 for the
M0.1 foundation. New relations still require `integrity.py`, `operations.py`
explicit export/import handling and recovery tests together. Legacy CHECK
constraints for Ask/report targets require controlled SQLite table rebuilds, not
rewriting old migrations. Installed rollback must restore a verified database
backup with matching code, never launch old binaries against new writer
contracts.

INFERRED: globally scoped Story/report text could leak unrelated Research context if reused directly; scope must constrain both included IDs and rendered text. Historical ownership may sometimes be reconstructed from Monitor need + relevance records, but absence of historical attachment intervals prevents universal reconstruction.

UNKNOWN: live Source Scout provider/search availability and quality, site-specific article extraction/robots/licensing constraints, source quality usefulness, real user tolerance for local outputs, installed Windows/mobile release gates. These are explicit qualification tasks, not assumptions of success.


## Final deep M0 audit — findings and evidence

These are defects in the proposed implementation contract or existing couplings it must accommodate, not claims that unimplemented rework code has regressed. Static paths below were inspected; new acceptance cases are specifications, not passing implementation tests.

| Severity | Finding / repository evidence | Required correction |
|---|---|---|
| P1 | `story_corrections.py:945–1110` merge/split/resolve rewrites Watch target or disables collisions. `intelligent_monitoring.py` Source-target `_need_for` has no semantic need. | Preserve Watch identity while snapshotting target binding; retain advanced target capability differences. Current target alone cannot establish historic ownership. |
| P1 | `monitoring.py:_write_scope_history` reuses identical JSON; `_refresh_need_scopes_tx` rebuilds base scope. `intelligent_monitoring.py:_refresh_scopes` separately overlays Watch vocabulary; `domain.py:add_vocabulary` refreshes after its write. Question/evidence edits also call scope refresh. | Atomic orchestration across callers preserving overlays; independent Watch/Monitor version pinning, including correction and reattach. |
| P1 | `acquisition.py:poll_feed` 304 returns empty entries and event with no item version list; 200 item persistence precedes event recording. Direct unchanged paths skip normal enqueue. | Persist successful manifest and admit missing contextual obligations even unchanged. Missing cache is unavailable/recovery, not evaluated. |
| P1 | `jobs.py:_maybe_finish_run_tx` checks only jobs.run_id and can mark dispatch-only work success. Budget failure also calls it. | Sealed dependency closure is sole Watch Run finalizer, including cancellation, manual finish and lease exhaustion. |
| P1 | `operations.py:export_logical` explicit allowlist omits relevance, content artifacts, executable payloads and evidence excerpts; no explicit encompassing read transaction. `import_logical` uses INSERT OR IGNORE and returns input count. Recovery runbook explicitly says logical export is not disaster recovery. | Preserve privacy; metadata archive completeness and atomic conflict validation. Full evidence recovery gate uses verified backup, not fabricated logical rows. |
| P1 | `ask.py` retrieves globally before filtering, expands claims/tasks/evidence and correction text; `reports.py` broad Story/Claim sections can restore excluded material. | Shared exact-version projection at selection and final serialization. Integration remains M4/M5; M0 tests projector, not claimed consumer isolation. |
| P1 | `document_processing.py` version-only active guard plus key suppress second Monitor context. Existing relevance and analysis identity already include context. | Change all enqueue/retry/recovery guards together; stage-wise reconciliation and lease-fenced writes. No global semantic analysis reuse. |
| P2 | `evidence_promotion.py:_insert_claim_tx/_insert_span_tx` identity includes analysis/candidate provenance; Story resolution global, downstream keys based on prior stage. | Keep existing canonical identities. Contextual relation is not permission to clone or merge canonical Claims/spans by text. |
| P2 | Sources unique slug does not guarantee endpoint URL uniqueness. FeedParser preserves id but not consistently RSS guid/full-versus-summary fidelity. | Lossless per-Source endpoint uniqueness and unresolved conflict labels; new precise item metadata, old fidelity unknown. |
| P2 | `temporal.py:_watch_context` target branches omit Question Watches; attention uses global alerts/corrections, workbench uses global FTS/history. | Explicit qualified Watch event attribution and sanitized scoped text; keep advanced global history clearly global. |
| P2 | Current retention in operations removes backup files/expired sessions; current attachment deletion is not retained evidence deletion. | Restrict new causal-history deletion; test soft-delete/restore, do not introduce a purge or claim universal historical reconstruction. |

### End-to-end identity ledger

For A/B sharing S and article D: Source/endpoint identifies retrieval authority; acquisition event records request outcome; global Document is keyed by canonical URL hash; DocumentVersion uses existing document/hash/retrieval identity. Existing first changed fetch enqueues version processing, second unchanged result can enqueue nothing. Processing's version-only suppression loses B here. Existing relevance UNIQUE(version,Monitor,scope), analysis identity (relevance/scope/provider/model/input), promotion per analysis, Claim candidate and span provenance identities are already context-sensitive. Global Story resolution conservatively reuses event identity. Story/report/alert continuations use promotion/prior-stage job IDs, not a Watch admission ledger. Ask then expands global canonical objects. The correction is independent admission and contextual obligation, retained causal links through the existing stages, followed by strict projection—not new per-Watch Documents or Stories.

### Current attachment consumer inventory

`intelligent_monitoring.py`: setup/get/list sources/review, source health, policy/status, scope refresh, approval, corpus availability, discovery/proposals and detach. `domain_api.py`: setup source counts and list routes. `monitoring.py`: cadence. `research_questions.py:_watch_context`: active planning context. `integrity.py`: current Monitor Source/need agreement. `operations.py`: current join export. Phase24 fixtures directly insert current joins. Keep operational reads current; change historical corpus/eligibility paths to retained proof. Ask/report/temporal/attention readers that infer via target/Story need projection even if they do not directly join watch_sources. Backup includes both representations; integrity checks agreement without treating closed/unknown intervals as active.

### Security and performance gate

Existing AcquisitionPolicy, safe redirect handler and parser guards remain owners. Test every discovered URL transition: manual input, HTML alternate feed, feed link, redirect, canonical hint, Scout result and retry after DNS changes. Re-resolve public address/peer at fetch, bound redirects/bytes/time/items, reject unsafe schemes, credentials and XML entities; sanitize feed HTML. A previously verified URL is not permanent authority. Cross-domain admission still requires the complete D19 discovery path. New paths are not yet implemented or live-qualified.

For 100 Watches sharing one compatible endpoint/version, expect one transport acquisition but up to 100 contextual relevance obligations and separately authorized analysis. Use bounded transactional batches/keyset reconciliation; index observation Watch/version/relevance and membership references, job context/active key, snapshot item links and check graph parent/status. Inspect EXPLAIN QUERY PLAN on representative seeded data; prevent per-Claim evidence-query N+1 and unbounded IN lists. Record query counts, queue depth and elapsed time as baseline; no invented latency SLO or global analysis dedup to conceal real cost. Unknown URL aliases can require an initial request each.

### Test mapping and limitations

Adapt phase06 acquisition for manifest/304 and parser cases; phase07 plus worker lease/coalescing for replay; phase19–22 for identity/promotion; phase23a–e for correction and Story/report/alert compatibility; phase24/25 for membership/scope; phase14 Ask and phase11 reports for later boundary wiring; phase28/29 for Home attribution. New tests/test_research_* suites named in EXECUTION_PLAN isolate missing invariants. Existing export tests inspect selected rows; that does not prove a fully restored evidence chain. Initial audit's 19 passing tests and fake A/B reproduction remain recorded above; this final pass adds static evidence and planning gates, not a new full regression claim.
