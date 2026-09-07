# Newsroom v2 Strategic Architecture Review

Date: 2026-08-24  
Repository checkpoint reviewed: `main` at `5cff639bb054098f384913b1b6ea529760ccbe6a`  
Schema reviewed: migration 0028 / schema version 28  
Scope: codebase-first audit and Phase 27–30 integration plan; no feature implementation

> **Final Phase 27 refinement:** The repository-grounded decisions in
> [Final Architecture Reconciliation Memo.md](./Final%20Architecture%20Reconciliation%20Memo.md)
> are binding where they narrow or amend this strategic baseline. The active execution
> authority remains `plan/phases-v2/`; `plan/phases-old/` is historical, and the two
> top-level overview plans remain non-authoritative until reconciled.

## 1. Executive Verdict

**Verdict: the architecture remains coherent but requires targeted simplification and a focused update to the active `plan/phases-v2` roadmap before Phase 27.**

The provenance-first core is earning its keep. Immutable content artifacts, versioned ArticleAnalysis identity, verified EvidenceSpan promotion, ClaimEvidence, deterministic Story resolution, exact-cause report/alert automation, bounded Jobs, and citation-checked Ask form a consistent trust path. The repository also already has a 30-case evaluation corpus and meaningful Story, Claim, Evidence, contradiction, primary-source, cost, and latency metrics. A rewrite or generic graph/event architecture would destroy useful semantic boundaries without solving the identified product risks.

The next risk is not weak mechanical correctness. It is that materialized derived state, automation, and user-facing objects are accumulating faster than Newsroom can prove intelligence value. `story_entities` is the clearest immediate synchronization hazard: automatic Claim-to-Entity linking copies the relationship into Story state, but Claim reassignment does not reconcile that copy. Automatic Tag assignments have the same conceptual-authority problem. Observation coverage, Source independence, historical belief reconstruction, and correction-burden telemetry remain incomplete.

Phase 27 should proceed only after a small plan reconciliation. It should remain focused on reversible Story correction and quality telemetry. Coverage/Source work belongs in Phase 28; processing provenance and temporal reliability belong in Phase 29; comparison, dogfood, and subtraction belong in Phase 30.

### Planning authority and repository-state caveat

The intended planning hierarchy is now clear:

- `plan/phases-old/` is the historical/original build plan. It remains useful implementation history but is not the forward roadmap.
- `plan/phases-v2/` is the active planning authority created after the strategic re-examination.
- `plan/MASTER_PLAN.md` and `plan/newsroom-v2-dev-plan.md` have not yet been reconciled with that newer direction and should be treated as stale overview documents where they conflict with `plan/phases-v2/`.

The working tree reflects the move from the formerly tracked `plan/phases/` path to `plan/phases-old/`; Git currently represents that uncommitted filesystem change as deletions under `plan/phases/` plus an untracked `plan/phases-old/` directory. This review does not treat that as two competing roadmaps.

The working tree was already dirty before this review:

- untracked `.kilo/`;
- untracked `Newsroom -v2.zip`;
- the in-progress `plan/phases/` to `plan/phases-old/` relocation;
- untracked `plan/phases-v2/Phase 23 Summary.md`;
- untracked `plan/phases-v2/Phase 26.md`.

The historical `plan/phases-old/README.md` calls Phase 27 “Complete Product Workflow UX” and Phase 28 final browser acceptance. That sequence is superseded for forward planning by `plan/phases-v2/`, whose documents reserve Phase 27 for advanced Story correction and discuss Phases 28–30. However, there is not yet a Phase 27–30 file or roadmap index in `plan/phases-v2/`. This is an incomplete active roadmap, not a conflict between equal authorities. It should be completed before implementation begins, then propagated into the stale top-level overview plans.

## 2. Existing Architecture Findings

| Concern | Status | Codebase evidence and consequence |
|---|---|---|
| Provenance-first canonical path | Already solved | Content artifacts are immutable; ArticleAnalysis stores artifact/hash, schema, prompt, provider, model, and an identity hash; promotion verifies exact spans before Claims/Evidence. See `migrations.py` migrations 0016–0023, `article_analysis.py`, `provenance.py`, and `evidence_promotion.py`. |
| Full-vs-Lite complexity proof | Partially solved | `newsroom.evals` already supplies 30 labeled cases and granular metrics; Phase 26 adds an 11-query retrieval benchmark. There is no same-corpus full-pipeline Newsroom Lite runner or time-to-understanding/manual-work comparison. |
| Engineering vs intelligence acceptance | Not solved as a roadmap rule | Phase plans have extensive engineering gates, but Intelligence Value Acceptance is not a separate required gate. Existing eval metrics are foundations, not phase exit criteria. |
| Canonical/human/derived distinction | Partially solved | Search is explicitly a rebuilt projection. ArticleAnalysis proposals are not canonical Claims. Ask history is audit metadata, not Evidence. Entity/Tag relationship tables mix manual and automatic origins under one durable authority model. |
| Projection rebuild principle | Partially solved | `SearchService` deletes and rebuilds `search_records`/FTS when dirty. Knowledge backfills are bounded and cursor-based. Entity mentions, automatic Tag assignments, and Story-Entity materialization lack a documented delete/rebuild contract. |
| Automatic Tag simplification | Not solved | `tag_assignments` stores `user`, `deterministic`, `provider`, `import`, and `backfill` rows under one unique identity. A later deterministic run cannot coexist with or cleanly yield to a manual decision without explicit precedence/history semantics. |
| Story-Entity authority | Partially solved, currently unsafe for Phase 27 | Claim-Entity linking inserts `story_entities` opportunistically (`knowledge.py` lines 327–350 and 707–711). Retrieval reads the materialization. No corresponding reconciliation is present for Claim reassignment/split/unassignment. |
| Common Job/backfill contract | Partially solved | `JobService` already owns durable queue state, attempts, leases, retries, idempotency, recovery, completion hooks, rerun factories, and budgets. `knowledge_backfills` separately owns cursor/batch/count state and runs synchronously. Consolidation should extend JobService rather than create a new orchestrator. |
| Common domain event envelope | Partially solved by domain histories | Story evolution, Claim state history, Question history, gap history, report revision causes, alert causes, entity merge lineage, feedback, Jobs, and provider usage already answer parts of the audit question. A new envelope is not justified in Phase 27; evaluate a thin read model in Phase 29 after correction events exist. |
| Observation provenance/coverage | Partially solved | Watch health reports approved/pending Sources, Monitor state, last result, next check, and discovery error. Acquisition events and Research Task queries/findings persist. There is no explicit observation scope/window/source-class denominator or exclusion state. |
| Absence vs negative evidence | Not solved | Research can truthfully complete with no findings, and Ask refuses when evidence is insufficient, but neither result is qualified by a coverage contract. Ask’s wording “does not have enough” is safe; future “none exists” answers need coverage qualification. |
| Confirmation-loop safeguards | Partially solved | Research is bounded, corpus-first, budgeted, and can use approved Watch vocabulary. There is no required alternative-terminology/disconfirmation/source-class exploration or framing-diversity telemetry. |
| Competing hypotheses | Partially supported, not implemented | User notes already support `hypothesis` semantics and Ask labels them unverified. Questions, Gaps, Tasks, and Claim links can host the workflow, but there is no structured multi-hypothesis comparison object. |
| Evidence fragility/counterfactual lab | Planned but not implemented | ClaimEvidence and document lineage provide graph edges, but Source dependency/evidence-family semantics are incomplete. Raw Source counts are explicitly not called independent confirmation. |
| Source dependency intelligence | Partially solved | `document_lineage` supports `cites`, `syndicated_from`, `wire_propagation`, and `rewritten_from`; Phase 24 discovery uses these. There is no durable/inferred evidence-family model or correction workflow. |
| Processing provenance | Substantially solved at analyzer boundary | ArticleAnalysis identity changes when artifact/input view/schema/prompt/provider/model changes and old rows remain immutable. Missing: active interpretation selection, downstream derivation identity, reason-for-change classification, and belief diff. |
| Bitemporal knowledge | Partially solved | Publication, first-seen/acquisition, artifact, analysis, promotion, revision, history, and correction timestamps exist. Current state is often mutable in-place, and no uniform knowledge-valid interval or “as known at” query contract exists. |
| Shadow reprocessing/belief diff | Not solved | Existing replay/rerun/backfill mechanics can execute it, but there is no isolated proposed interpretation set or structured diff/review/promotion contract. |
| Human review scaling | Partially solved | Candidate/review states exist in multiple domains and deterministic matching is conservative. There is no operation-level autonomy policy based on consequence, reversibility, measured precision, and correction rate. |
| Simple/Advanced experience | Not solved | The frontend exposes many separate navigation surfaces. There is one engine and shared APIs, but no visibility mode, contextual disclosure, or capability risk contract. |
| Attention intelligence | Partially solved | Watch priority, Research Question priority, Story materiality, Alert rules, and Inbox exist. There is no cross-domain “what deserves attention” projection or explanation. |
| Alert value | Partially solved | Alerts have exact cause, acknowledgement, delivery state, and deduplication. No open/evidence-follow/action/usefulness telemetry exists. |
| Intelligence evaluation corpus | Already has strong foundation | The corpus already targets 30 realistic cases across corrections, contradictions, syndication, source primacy, and temporal changes. It is case/fixture based rather than a full temporal ingestion stream through every current subsystem. |
| Story quality telemetry | Not solved | Evaluation measures gold Story grouping, but production does not count automatic assignments, manual reassignments, splits, merge reviews, or correction rates. |
| Blind-spot detection | Partially supported | Acquisition failure, Watch health, vocabulary, discovery, new entities, and unmatched clusters are available signals. No bounded blind-spot projection combines them. |
| Research prioritization | Partially solved | Questions have priority and due-time ordering; Tasks have budgets and cooldowns. Expected evidence value, coverage deficiency, cost, and user priority are not combined into an explainable rank. |
| Unified investigative shell | Not solved | Workbench and detail views share primitives but navigation still treats domains as separate screens. This is a Phase 28 UX composition issue, not a reason to rewrite backend domains. |
| Reports vs Ask | Mostly solved conceptually | Living Reports are durable revisioned briefs grounded in Claims; Ask is ad hoc scoped retrieval with minimal audit history. Later UI copy and evaluation should preserve this boundary. |
| Scale targets/SLOs | Partially solved | Bounded pages, queues, context, provider budgets, Phase 15 performance tests, and Phase 26 latency benchmark exist. No declared baseline/stress/stretch workload or product SLO table exists. |
| Retention/deletion/reprocessing | Partially solved | Backups and sessions have retention. Logical export is allow-listed. Canonical intelligence/content/provider-output retention and provenance-preserving deletion policy are not defined. |
| Disaster recovery | Partially solved | Verified SQLite backup/restore and upgrade rehearsal exist. The logical export is explicitly not a complete restore mechanism; no fresh-db logical import plus projection rebuild drill exists. |

## 3. Highest-Risk Problems

### Epistemic risks

1. **Unknown observation denominator.** Newsroom can prove where evidence came from but cannot yet prove the relevant Source classes/time windows it searched or failed to observe.
2. **Source records can masquerade as independence.** Current language is cautious, but future scoring/attention/Ask can still overcount derivative Sources without evidence-family semantics.
3. **Reinterpretation is not propagated as a first-class cause.** ArticleAnalysis versions are strong, but downstream changes cannot yet uniformly distinguish new world evidence from reprocessing old evidence.
4. **Closed-loop framing.** Watch vocabulary and existing Questions influence further retrieval without required bounded disconfirmation or alternative framing.

### Architecture risks

1. **`story_entities` synchronization before correction work.** This is the immediate blocker to a clean Phase 27 design.
2. **Mixed-authority Tag assignments.** Manual decisions and disposable classifiers share identity and export semantics.
3. **Parallel backfill lifecycle.** `knowledge_backfills` duplicates a subset of JobService state and will encourage each projection to invent another runner.
4. **Active-roadmap incompleteness and stale overview documents.** `phases-v2` is authoritative but lacks executable Phase 27–30 files; the historical and top-level plans still describe older sequencing.

### Product/UX risks

1. **Object-first navigation instead of attention-first workflow.** The user must traverse Stories, Questions, Watches, Workbench, Reports, Alerts, and Jobs to synthesize “what changed and what matters.”
2. **Human curation burden is unmeasured.** Phase 27 could add powerful correction tools while silently increasing janitorial work.
3. **Advanced concepts lack progressive disclosure.** Coverage, fragility, hypotheses, and source dependency are useful only when surfaced contextually and explained.

### Operational risks

1. **No workload contract or SLOs.** Performance tests cannot prove suitability without an explicit personal-intelligence workload envelope.
2. **Logical export is not disaster recovery.** Some canonical/historical state is exportable, but import/reconstruction and projection rebuild are unproven.
3. **Retention semantics are incomplete.** Content disappearance, historical versions, provider outputs, and deletions with inbound provenance lack policy.

## 4. Simplification Opportunities

| Current complexity | Proposed simplification | Preserved capability | Migration cost / risk | Phase |
|---|---|---|---|---|
| `story_entities` stores both manual and automatically copied Claim-derived links | Define effective Story Entities as `manual overrides UNION entities of currently assigned Claims`; materialize only as a rebuildable projection if query benchmarks require it | Story/Entity pivots and filters | Medium. Must preserve truly manual links separately or add authority/origin semantics before rebuild. High risk if deferred into merge/split implementation. | 27 |
| All Tag origins share one durable unique assignment | Keep manual/import assignments authoritative; treat deterministic/provider/backfill assignments as replaceable classifier output with classifier/version/run identity and manual suppress/override | Smart Tags, filters, user Tags | Medium migration; low conceptual risk. Do not delete current rows until rebuild parity and export policy exist. | 29 design; hooks in 27/28 only if touched |
| Knowledge backfills run via their own state machine | Make a projection-run contract executed by JobService: scope, cursor, batch limit, counts, algorithm version, terminal result | Restartability and bounded processing | Medium; migrating an active run is risky. Adopt for new backfills, then fold old runner only after parity. | 29 |
| Many audit histories require bespoke timeline queries | Build a read-only union/view/service over strict domain histories first; add a minimal envelope table only for future events that lack a durable domain record | Audit/timeline without genericizing schemas | Low if read model; medium if dual-written table. | 29 |
| Separate frontend “admin apps” per domain | Shared investigative shell with contextual panels and mode-aware disclosure | Existing APIs/domain distinctions | Medium UI work, low backend risk | 28 |
| Phase acceptance is mostly implementation checklists | Add paired Engineering Acceptance and Intelligence Value Acceptance sections with metric, corpus, comparison, threshold/decision rule, and subtraction fallback | Existing gates | Low | Before 27 |
| Full-system evaluation and Phase 26 retrieval benchmark are disconnected | Extend the existing eval Prediction/metrics contract; add a Lite prediction adapter and temporal runner rather than a second benchmark framework | Existing 30 cases and baselines | Medium; low architecture risk | 27 instrumentation, 30 decision gate |

Objects that should remain unchanged include immutable ContentArtifacts, DocumentVersions, verified EvidenceSpans, Claims and ClaimEvidence, ArticleAnalysis versions, Story revision/evolution history, Question assessment/history, manual corrections, entity merge lineage, Jobs/attempts, and report/alert cause records.

## 5. Canonical / Human Decision / Derived Classification

Classification is by semantic authority, not whether a row is stored.

| Object | Recommended class | Notes |
|---|---|---|
| Source | Canonical reference state + human curation | Identity/profile is durable; reliability and dependency assessments are separate decisions/derived analysis. |
| Document | Canonical reference state | Stable publication identity; metadata corrections require history policy. |
| DocumentVersion | Canonical evidence state | Immutable observation of changing content; do not collapse versions. |
| ContentArtifact | Canonical evidence state | Hash-verifiable input bytes/view. Retention policy may archive, but provenance must not silently break. |
| AcquisitionEvent | Historical process observation | Durable operational/observation provenance; not factual Evidence. |
| ArticleAnalysis / invocation | Historical derived interpretation | Rebuildable in principle but must remain durable to explain historical conclusions and paid calls. Never canonical fact. |
| EvidenceSpan | Canonical evidence state | Verified locator into a DocumentVersion; manual and automatic verification provenance matters. |
| Claim | Canonical asserted knowledge state | Accepted Claim remains a domain assertion with state history; analyzer proposals are not Claims. |
| ClaimEvidence | Canonical epistemic relationship | Defines why a Claim is supported/contradicted. |
| Story | Mixed: durable identity + derived grouping + human decisions | Story identity and revision/correction history are durable; automatic membership is correctable and should expose its origin. |
| StoryRevision / StoryEvolution | Historical decision/interpretation | Preserve append-only history even if generated automatically. |
| Claim Story assignment | Mixed | Current automatic assignment is mutable grouping; manual correction and assignment history are irreplaceable decisions. |
| Entity | Canonical knowledge reference + human curation | Canonical name/type/merge decisions are durable; automatic candidates are suggestions. |
| EntityAlias | Mixed | User/import/curated alias is durable; analyzer-derived aliases may be rebuilt but historical use may need versioned provenance. |
| EntityMention | Derived projection with historical analyzer provenance | Rebuildable from ArticleAnalysis when source/version remains; retain run/version identity if materialized. |
| ClaimEntity | Mixed | Manual relationship is a decision; analyzer/backfill relationship is a projection derived from mention/Claim. |
| StoryEntity | Mixed today; should split | Manual link/override is durable. Claim-derived effective relationship is a projection. |
| ResearchQuestion | Human intent | Lifecycle, criteria, priority, and corrections are user/historical decisions. |
| Question assessment | Historical derived interpretation | Current snapshot is derived; append-only assessment history is required for “what was believed.” |
| EvidenceGap | Mixed analysis + decisions | Automatic suggestion may be rebuilt; approval/status/history and Tasks created from it are durable. |
| ResearchTask / query / finding | Historical decision/process state | Task intent, bounds, queries, attempts, and results explain what was searched. Findings are candidates, not Claims. |
| Watch / approved vocabulary / Source membership | Human intent | Durable; provider/deterministic suggestions remain inert projections until approved. |
| Monitor / scope history | Operational state + historical decision | Scheduler state is operational; pinned scope history is required processing provenance. |
| Tag definition | Mixed | Manual namespace/tag is durable. Auto-created classifier labels need controlled lifecycle/versioning. |
| TagAssignment | Split by origin | User/import is durable decision; deterministic/provider/backfill is rebuildable projection plus optional historical run record. |
| Search records / FTS | Derived projection | Already safely deleted/rebuilt from authoritative SQLite state. Keep this model. |
| LivingReport / revisions | Durable derived intelligence | Rebuildable from Claims in principle, but revision history and user edits are historically meaningful. |
| AlertRule / acknowledgement | Human intent/decision | Durable. |
| Alert / delivery | Historical derived event | Exact cause, dedupe, interruption, and user response must remain auditable. |
| Ask conversation/run | Audit metadata | Not Evidence; retention can be shorter if product policy permits. |
| FeedbackEvent / future quality telemetry | Historical user signal | Preserve as inputs to autonomy evaluation, not canonical truth. |

## 6. Phase 27 Changes

Phase 27 should be **Advanced Story Intelligence and Correction**, following the active `phases-v2` direction rather than the historical `phases-old` “Complete Product Workflow UX” phase. Before implementation, create the authoritative Phase 27 file and an active roadmap index in `plan/phases-v2/`.

### Add

1. Story merge, split, Claim reassignment, unassignment, lineage, correction, and reversible/manual decision history.
2. An explicit `cause_class` for Story mutations: `new_evidence`, `reprocessing`, `human_correction`, `administrative`, with a reference to the causing Claim/promotion/analysis/job/decision where available. This is a hook, not full Phase 29 processing provenance.
3. Story-quality telemetry captured from domain events, not inferred later:
   - automatic assignment count;
   - manual reassignment/unassignment count;
   - merge/split count;
   - duplicate suggestion approval/dismissal;
   - correction rate per 100 automatic assignments and per 100 Claims;
   - time from automatic assignment to correction;
   - actor/origin, algorithm identity, and reversible operation identity.
4. Engineering Acceptance and Intelligence Value Acceptance as separate gates. Intelligence Value Acceptance should use existing eval cases plus correction-burden fixtures; it need not claim statistical certainty.
5. A Story-Entity invariant: effective automatic Story Entities must be derivable from currently assigned ClaimEntities; Claim moves cannot leave stale StoryEntity rows.
6. Hooks for future event read models: every Story mutation must have stable event/decision identity, occurred-at time, origin, subject, cause, and reversal relation.

### Change

- Treat automatic Story-Entity rows as materialized projection state. Preserve manual Story-Entity decisions separately or by explicit origin/override semantics.
- Require merge/split/reassignment APIs to be transactional with Claim assignment history, Story revision/evolution history, search dirtiness, and projection reconciliation.
- Define “same Story vs related Story” as an acceptance decision before implementing merge. Default recommendation: same underlying event/development with compatible temporal identity; common Entity/topic alone is insufficient. Related Stories remain distinct with an explicit relation rather than a merge.

### Remove/defer

- Do not add Source dependency, coverage, hypotheses, attention scoring, bitemporality, or a generic domain-event table to Phase 27.
- Do not rewrite the frontend into a unified shell in Phase 27; expose only the correction workflow needed to validate the domain operations.
- Do not add a second Job system.

## 7. Phase 28 Plan

The proposed Phase 28 list is too large for one implementation/acceptance gate. Preserve the phase number but split it into two coherent internal checkpoints rather than inventing extra top-level phases.

### Phase 28A — Observation and Source Robustness

- Observation/Coverage runs and summaries.
- Source dependency and evidence-family edges with deterministic-first inference.
- Evidence Fragility and read-only counterfactual removal analysis.
- Bounded blind-spot signals from failures, source-class gaps, vocabulary drift, silence, and unmatched clusters.
- Explainable Research Gap prioritization.
- Ask/Report qualification hooks so absence claims carry coverage state.

### Phase 28B — Intelligence Experience and Safe Analysis

- Cross-domain Attention projection: changed, important, uncertain, investigate-next, with reason codes.
- Shared investigative frontend shell and contextual Simple/Advanced disclosure.
- Capability-level risk/authority contract and progressive-autonomy visibility.
- Competing Hypotheses as experimental/Advanced-optional analysis over existing Questions/Gaps/Tasks.
- Alert interaction instrumentation and attention-value evaluation.

Phase 28A must complete before fragility or hypotheses are allowed to influence attention. Counterfactual results and Hypotheses remain derived analysis; they cannot mutate Claims, delete Evidence, or automatically resolve Questions.

## 8. Phase 29 Plan

Phase 29 should be **Epistemic Reliability, Rebuildability, and Production Hardening** in this order:

1. Declare baseline/stress/stretch workload envelopes and product SLOs before optimization.
2. Introduce a processing-run identity usable beyond ArticleAnalysis: algorithm/component, code/config/schema/model identity, input snapshot identity, parent run, shadow/current status.
3. Define minimum temporal semantics:
   - `world_time`: asserted event/effective time when a domain supports it;
   - `published_time`;
   - `observed/acquired_time`;
   - `knowledge_time`: when Newsroom accepted/derived the record;
   - `superseded/corrected_time` through histories, not columns on every table.
4. Implement Shadow Reprocessing using existing Jobs/backfills against a controlled corpus and isolated proposed output set.
5. Produce a structured Belief Diff across Claims, assignments, contradictions, Stories, Question assessments, Reports, and Alerts. Review before activation; never overwrite historical output.
6. Formalize projection registry/rebuild tests for search, automatic Tags, Entity mentions/relationships, Story Entities, coverage, dependency, fragility, and attention.
7. Consolidate new projection runs on JobService. Retire the standalone knowledge backfill runner only after active-run compatibility and replay tests.
8. Build a unified event timeline read model. Add a thin event envelope only for changes that cannot be projected reliably from existing histories; do not dual-write all domains speculatively.
9. Define content/provider-output/Ask/Job/version retention, reprocessing, and provenance-aware deletion policies.
10. Run backup restore plus a separate fresh-database logical import/rebuild drill. Document what logical export intentionally cannot reconstruct.
11. Execute failure injection, backlog recovery, migration, integrity, cost, and SLO tests.
12. End with an architecture complexity audit that may remove projections/features proven redundant.

## 9. Phase 30 Plan

Phase 30 is a product-decision phase, not a final feature sprint.

1. Expand the current 30 cases toward 30–50 high-quality temporal scenarios only where coverage is weak; do not inflate case count for its own sake.
2. Run identical scenario streams through Full Newsroom and Newsroom Lite.
3. Dogfood multi-week Watches in Simple and Advanced visibility modes with the same engine/data.
4. Capture semantic outcomes, manual corrections, alert actions, time-to-understanding, coverage blind spots, dependency accuracy, cost, latency, and UX friction.
5. Conduct structured error review by scenario, not just aggregate scores.
6. Require a per-capability decision: keep always-on, keep Advanced, gate experimental, simplify/make derived, merge into another surface, or remove.
7. Release only if provenance/citation gates remain perfect on critical fixtures, no high-consequence automation exceeds its correction threshold, restore/rebuild succeeds, and the full system shows material value over Lite on predeclared measures.

Phase 30 is explicitly permitted to delete features or durable projections that do not improve outcomes enough to justify their cognitive, operational, and synchronization cost.

## 10. Simple / Advanced Architecture

### Shared engine invariant

There is one canonical evidence pipeline, one scheduler/JobService, one permission model, one retrieval substrate, and one set of domain records. Simple/Advanced changes presentation and authorization for optional actions; it never creates two pipelines or two truth sets.

| Capability | Visibility | Default operation |
|---|---|---|
| Watches, important changes, Story summary, evidence, uncertainty, Ask, Alerts, Reports | Simple-visible | Safe deterministic processing automatic; user intent manual |
| Claim/Evidence provenance, Question status, open Gaps, Source coverage warning | Simple-visible contextually | Automatic calculation; manual decisions explicit |
| Workbench pivots, Story correction, Source dependency, fragility, coverage detail, research prioritization | Advanced-visible | Suggest/manual for consequential mutations |
| Competing Hypotheses, Counterfactual Evidence Lab, Shadow/Belief Diff controls | Advanced-optional | Manual start; no canonical mutation |
| New provider classifiers, blind-spot exploration, learned autonomy policy | Experimental/gated | Disabled or suggest-only until evaluated |

### Capability risk contract

Each operation declares consequence, reversibility, scope, provider use/cost, required provenance, default authority (`automatic`, `suggest`, `manual`, `disabled`), and the observed telemetry needed to earn more autonomy. Visibility is independent: an always-on safe engine feature may be hidden in Simple mode, while a visible advanced analysis may remain manual.

Progressive disclosure should occur where the user encounters a decision: dependency on a Story/Claim, coverage on an Ask answer, hypothesis comparison on a Question, fragility on a Report statement, and correction history on a Story. Avoid a separate administration screen for every concept.

## 11. Evaluation Strategy

### Newsroom Lite baseline

Implement Lite as an evaluation adapter, not a second product stack:

```text
same temporal candidate stream
→ Sources/Documents/versions
→ basic URL/title/text dedupe or clustering
→ one bounded synthesis step with citations
→ existing Prediction schema
```

Pin prompt/model/config, capture provider usage, and run Lite and Full on the same frozen inputs. Lite must receive comparable source metadata and content; it must not receive Full’s Claims, dependency labels, or Story decisions.

### Corpus evolution

Reuse `evals/corpus`, `fixtures`, replay hashes, Prediction, and metrics. Add a temporal scenario runner with checkpoints and expected current/historical outputs. Extend metrics only where decisions require them:

- correction detection and correction latency;
- derivative-source/evidence-family handling;
- Question/Gap usefulness;
- Ask correctness at each time and citation/provenance correctness;
- Alert utility;
- manual intervention count;
- observation qualification correctness.

### Phase adoption

| Phase | Engineering Acceptance | Intelligence Value Acceptance |
|---|---|---|
| 27 | Transactionality, replay, lineage, projection coherence, API/UI tests | Story grouping deltas, correction burden, merge/split decision quality on targeted fixtures |
| 28 | Coverage/dependency invariants, bounded analysis, no canonical mutation | Better source-independence judgment, useful coverage warnings, attention/Alert usefulness, hypothesis discrimination |
| 29 | Historical reconstruction, shadow isolation, rebuild/restore, SLO tests | Belief Diff identifies meaningful interpretation changes without false “new evidence”; acceptable latency/cost at declared scale |
| 30 | Release/recovery gates | Full vs Lite, Simple vs Advanced, dogfood workload, subtraction decisions |

### User-outcome measurements

- **Time to understanding:** timed scenario tasks: identify development, supporting/contradicting evidence, uncertainty, and next action.
- **Alert usefulness:** opened, evidence followed, Ask/Story/Question action, immediate dismissal, duplicate/repeat, explicit useful/irrelevant. No single signal controls optimization.
- **Correction burden:** manual correction operations per 100 automatic operations, severity-weighted separately from raw count.
- **Cost/latency:** existing provider usage, Job timestamps, Ask runs, and benchmark timing; add end-to-end wall time and operator time.

No opaque composite intelligence score is recommended. Use a scorecard with hard safety floors and comparative outcome measures.

## 12. Observation / Coverage Architecture

Model coverage as a bounded **CoverageRun** or equivalent process record, not as a Claim:

- subject/scope: Watch, Question, Story, or explicit query;
- scope/version and time window;
- intended channels and Source classes;
- included/excluded Sources and reason;
- attempted queries and acquisition targets;
- observed successes, failures, stale inputs, and exclusions;
- completeness state and known gaps;
- causing Job/ResearchTask and processing identity.

Derive per-target CoverageSummary projections for Workbench/Ask/Attention. Reuse Monitor scope history, Monitor activity, Watch Sources/vocabulary, acquisition events, ResearchTask queries/findings, Source candidates, and Job failures. Do not duplicate those rows into a generic observation ledger.

Required semantics:

| State | Meaning |
|---|---|
| `not_found` | A defined search/observation attempt completed and returned no qualifying result. |
| `not_observed` | The expected item was not present in channels actually observed. Coverage may still be incomplete. |
| `not_searched` | No relevant attempt was made. |
| `failed_acquisition` | The channel/target was attempted but content could not be acquired or validated. |
| `out_of_scope` | Explicit scope policy excluded the channel/target; not a failure. |
| `qualified_negative_evidence` | A derived analytical conclusion available only when an expected channel, adequate coverage threshold/rationale, complete window, and expected-observation rule are all recorded. |

Qualified Negative Evidence should reference the CoverageRun and expectation rule. It may support an analysis or Question assessment, but it is not an EvidenceSpan unless Newsroom has a positive canonical artifact that explicitly states the negative fact.

## 13. Source / Evidence Robustness Architecture

Keep four separate concepts:

1. **Source reliability:** a property/assessment of a Source’s track record or type.
2. **Source dependency:** a directed, typed relationship such as syndication, quotation, rewrite, shared primary artifact, or ownership dependency.
3. **Evidence family:** a derived connected group whose support paths ultimately depend on the same originating material.
4. **Evidence fragility:** a read-only analysis of how conclusions change when a Source, artifact, or evidence family is excluded.

Deterministic inputs should include canonical URL identity, document lineage, explicit citations/quotation metadata when retained, identical/near-identical artifact signals, publication ordering, and known Source metadata. Provider classification may suggest ambiguous dependency edges under existing AIRouter budgets, but must record method/version/evidence and default to review for high-consequence grouping.

Fragility output should state structural facts rather than fake confidence:

- number of direct supporting spans;
- number of distinct Source records;
- number of independent evidence families under the current dependency model;
- support paths removed by the counterfactual;
- Claims/Question assessments/Report statements/Alerts that would become unsupported or change state;
- unresolved dependency assumptions.

Counterfactual runs never delete Claims/Evidence or update canonical current state. They are disposable projections keyed by input snapshot and dependency-model version.

## 14. Competing Hypotheses Architecture

Introduce Hypothesis only as an experimental analysis object attached to one Question and optionally one Story:

- proposition/explanation text;
- status such as proposed, active, rejected, retired;
- origin and provider/run identity;
- user approval state;
- mappings to existing Claims as supports, contradicts, or discriminates;
- explicit assumptions;
- generated discriminating Evidence Gaps.

`Hypothesis != Claim`. A provider-generated Hypothesis is inert analysis. It cannot enter ClaimEvidence, ground a Report fact, resolve a Question, or trigger a factual Alert. Existing Claims remain the only factual assertions; existing Questions/Gaps/ResearchTasks remain the research engine.

Provider use belongs behind a new AIRouter capability with deterministic bounds: maximum hypotheses, length, allowed target, cost, and strict output validation. Simple mode may show “alternative explanation exists” only when approved/relevant; detailed matrices and counterfactual prompts are Advanced-optional. Research Tasks created from discriminating Gaps remain subject to Phase 25 budgets, cooldowns, acquisition, verification, and canonical promotion.

## 15. Temporal / Processing Provenance Plan

The repository already has the most important seed: immutable ArticleAnalysis versions keyed by exact artifact/input/schema/prompt/provider/model identity. Phase 29 should extend that principle downstream rather than add timestamps indiscriminately.

Minimum plan:

- create a processing-run identity for each important derived subsystem;
- link derived output to exact input snapshot and parent processing run;
- record whether a current change was caused by a new DocumentVersion, reprocessing of an old version, human correction, or administrative repair;
- preserve append-only output/history and an explicit current-selection decision where multiple interpretations exist;
- provide `as_of_knowledge_time` retrieval using created/accepted/superseded histories;
- keep `world_time` domain-specific and nullable where the Claim cannot establish it.

Shadow Reprocessing runs a candidate processing version through existing Job/backfill mechanics into isolated proposal tables or a shadow namespace. Belief Diff compares old/current and proposed graphs. Promotion is an explicit reviewed decision; historical Ask must select only records available and accepted by the requested knowledge time. “What Newsroom believed then” and “what Newsroom now believes about then” therefore become different queries.

## 16. Progressive Autonomy Plan

Automation policy should be per operation, not per provider or UI mode.

| Operation example | Initial authority | Reason |
|---|---|---|
| Exact normalized alias to one active Entity | Automatic | Low consequence, reversible projection, deterministic identity. |
| Ambiguous Entity candidate | Suggest | Wrong merge contaminates many pivots. |
| Automatic Story assignment on strong deterministic identity | Automatic with telemetry | Existing bounded path; reversible once Phase 27 lands. |
| Story merge/split | Suggest/manual | High consequence and broad downstream effects. |
| Smart Tag assignment | Automatic projection | Low consequence if rebuildable and suppressible. |
| Source dependency edge | Suggest until precision measured | Can alter corroboration/fragility conclusions. |
| Hypothesis generation | Manual start or gated | Analytical framing risk and provider cost. |
| Qualified negative evidence | Suggest/manual acceptance | High epistemic consequence; depends on coverage assumptions. |

Required telemetry precedes autonomy escalation: eligible operation count, automatic/suggest/manual decision, algorithm/provider version, consequence class, scope, reversal/correction, time-to-correction, review outcome, and downstream impact. Promotion criteria should use observed precision/correction rate within a comparable scope and minimum sample, plus reversibility and consequence. Provider confidence alone is never sufficient.

## 17. Outstanding Questions

| Priority | Question | Current answer | Remaining uncertainty | Phase | Blocks now? |
|---|---|---|---|---|---|
| Critical | What defines same Story vs related Story? | Current resolver requires strong identity signals; common subject alone is insufficient. | Formal event/time boundary and related-Story relation. | 27 | Yes, merge/split design |
| Critical | Which Story-Entity rows are authoritative? | Origin is stored, but automatic Claim links copy into Story rows. | Manual override vs derived projection and reconciliation. | 27 | Yes |
| High | What is the observation denominator? | Watch approved Sources/Monitors and Research queries are known. | Expected Source classes/channels/windows and completeness. | 28A | No for 27 |
| High | What counts as separate evidence? | Distinct Source records are explicitly not independent confirmation. | Dependency edge/evidence-family rules. | 28A | No |
| High | What makes something important? | Claim importance, Story materiality, Watch/Question priority, and Alert rules exist. | Cross-domain attention policy and user feedback. | 28B | No |
| High | How does absence become qualified negative evidence? | No-findings is an operational success, not proof. | Coverage threshold and expected-observation rule. | 28A | No |
| High | How is disconfirming research reserved? | Research is bounded and deterministic-first. | Alternative terminology/source-class/interpretation policy. | 28A/B | No |
| Medium | How are competing hypotheses bounded? | User hypotheses are already non-evidence notes. | Structured object, caps, approval, retirement. | 28B experimental | No |
| High | When do corrections change automation policy? | No production correction-rate policy. | Samples, consequence weighting, thresholds. | 27 telemetry; 28B policy | Telemetry blocks future autonomy, not 27 |
| High | What happens when analyzers/models change? | New ArticleAnalysis identity/version is created. | Downstream current selection, shadow diff, activation. | 29 | No for 27; preserve cause hook |
| High | What temporal semantics are required? | Many domain timestamps/histories exist. | Uniform knowledge-time query and domain world-time rules. | 29 | No |
| High | Which tables are canonical/historical/derived? | Search is explicit projection; evidence chain is explicit. | Mixed Entity/Tag/Story relationship authority. | 27 and 29 | StoryEntity blocks 27 |
| Medium | What is the target workload? | Personal/local-first, bounded operations, representative tests. | Concrete baseline/stress/stretch counts. | 29 | No |
| Medium | What are acceptable SLOs? | Individual performance tests and caps exist. | Product latency/throughput/recovery objectives. | 29 | No |
| High | What is retention/reprocessing policy? | Backup/session retention only; immutable histories persist. | Artifact, version, provider output, Ask, Job policies. | 29 | No |
| High | What does deletion mean? | Soft deletion is common; immutable provenance restricts destructive changes. | User-facing erase vs tombstone/archive and inbound references. | 29 | No |
| High | How is disaster recovery proven? | Verified binary backup restore exists. | Logical import plus projection rebuild and loss accounting. | 29 | No |
| Medium | What is Alert success? | Exact cause, acknowledgement, delivery, dedupe. | Attention/action/usefulness measures. | 28B/30 | No |
| Medium | How is uncertainty surfaced in Simple mode? | Ask labels uncertainty/contradiction; detail views expose evidence. | Contextual summaries without object overload. | 28B | No |
| Medium | Reports vs Ask boundary? | Durable maintained brief vs ad hoc interrogation. | UI duplication and shared change/uncertainty presentation. | 28B/30 | No |
| Medium | Which advanced features deserve persistence? | Historical decisions/provenance persist; search projection rebuilds. | Hypothesis, fragility, attention, coverage retention windows. | 29/30 | No |
| Medium | Which features should be removed? | No subtraction gate exists. | Full-vs-Lite and dogfood evidence. | 30 | No |

## 18. Recommended Plan Edits

No existing plan file was modified by this audit. With `plan/phases-v2/` confirmed as the forward authority, make these exact edits before implementation:

1. **Create `plan/phases-v2/README.md`**
   - declare `plan/phases-v2/` the active execution sequence and `plan/phases-old/` historical;
   - record the current checkpoint and schema through Phase 26;
   - index the accepted Phase 27–30 sequence;
   - add paired Engineering and Intelligence Value acceptance requirements.
2. **Create `plan/phases-v2/Phase 27.md`**
   - add the focused scope from Section 6;
   - define same-vs-related Story;
   - define Story-Entity projection/manual invariant;
   - add correction telemetry and cause hooks;
   - explicitly exclude Phase 28/29 concerns.
3. **Create `plan/phases-v2/Phase 28.md`**
   - structure it as 28A Observation/Source Robustness and 28B Intelligence Experience/Safe Analysis;
   - add authority boundaries for coverage, dependency, fragility, hypotheses, and blind spots.
4. **Create `plan/phases-v2/Phase 29.md`**
   - add processing-run identity, temporal semantics, shadow/belief diff, projection registry, Job consolidation, SLOs, retention, restore/import drill, and simplification audit.
5. **Create `plan/phases-v2/Phase 30.md`**
   - add Full-vs-Lite protocol, temporal corpus expansion, dogfood, Simple/Advanced comparison, feature subtraction, and release scorecard.
6. **`plan/phases-v2/Phase 26.md` and `Phase 26 Completion Report.md`**
   - no implementation rewrite;
   - add only a short handoff note stating that Story-Entity automatic rows are materialized derived state requiring Phase 27 reconciliation and that automatic Tags remain mixed-authority pending Phase 29 classification.
7. **`plan/MASTER_PLAN.md`**
   - mark `plan/phases-v2/README.md` and its phase files as the forward execution authority;
   - replace the obsolete post-Phase-26 direction with the reconciled Phase 27–30 sequence;
   - retain only durable product principles and dependency context that still apply.
8. **`plan/newsroom-v2-dev-plan.md`**
   - update current status, active phase location, and next permitted phase;
   - remove or label superseded implementation sequencing;
   - link to `plan/phases-old/` only as historical build evidence.
9. **`plan/phases-old/README.md`**
   - preserve the original plan content;
   - add only a short historical/superseded banner pointing forward to `plan/phases-v2/README.md`.

Do not rewrite historical Phase 01–26 implementation records for stylistic consistency.

## 19. Immediate Action List

### DO BEFORE PHASE 27

- Create the active `plan/phases-v2/README.md` and explicitly record `plan/phases-old/` as historical.
- Reconcile the stale `plan/MASTER_PLAN.md` and `plan/newsroom-v2-dev-plan.md` summaries with the new authority and sequence.
- Create an executable Phase 27 plan with separate engineering/intelligence gates.
- Decide and document same Story vs related Story.
- Decide manual vs derived Story-Entity semantics and the reassignment/split reconciliation invariant.
- Add a small set of Story correction/merge/split fixtures to the existing evaluation corpus; do not build the Lite runner yet.

### INTEGRATE INTO PHASE 27

- Implement reversible merge/split/reassign/unassign with append-only decision history.
- Record `new_evidence` vs `reprocessing` vs `human_correction` cause class.
- Capture correction-burden and Story-quality telemetry cheaply at mutation time.
- Rebuild/reconcile automatic Story-Entity projection transactionally.
- Expose a bounded correction UI without a full frontend rewrite.

### DEFER WITH EXPLICIT PLAN

- Phase 28A: Coverage, Source dependency/evidence family, fragility/counterfactuals, blind spots, research prioritization.
- Phase 28B: Attention, investigative shell, Simple/Advanced visibility, risk gating, progressive autonomy controls, experimental hypotheses, Alert value instrumentation.
- Phase 29: processing provenance, bitemporal queries, shadow/belief diff, projection registry, Job consolidation, SLOs, retention, logical import/rebuild, failure injection, simplification audit.
- Phase 30: Newsroom Lite, full temporal scorecard, dogfood, feature subtraction, release decision.

## 20. Final Recommendation

**PROCEED WITH PHASE 27 AFTER PLAN RECONCILIATION.**

Do not pause for a broad architectural correction. The evidence/provenance core is coherent, tested, and unusually disciplined. Do not proceed under the current planning state either: the active `phases-v2` roadmap is incomplete, the top-level overview plans are stale, the intended Phase 27 file is absent, and Story-Entity materialization would create stale derived relationships under the planned correction operations.

The smallest safe next step is to reconcile the roadmap, define the Story identity and Story-Entity invariants, add correction/value telemetry to the Phase 27 acceptance gate, and then implement the focused Story work. Everything else should remain explicitly deferred to the phase where its dependencies and evaluation contract exist.

## Validation Record

- Branch/HEAD/status/recent commits inspected; no starting SHA assumed.
- Migration registry and Phase 26 completion report inspected; current schema is version 28.
- Required backend domains, automation services, Job/worker path, logical export/integrity, frontend surfaces, tests, benchmarks, Phase 23–28 plans, and Phase 26 completion evidence inspected.
- Full backend suite passed: `python -m pytest -q` — all collected tests passed (deprecation warnings only).
- Frontend production build passed: `npm run build` — TypeScript check and Vite build completed successfully.
- This review added only this planning report. No runtime code, schema, history, commits, or unrelated files were changed.
