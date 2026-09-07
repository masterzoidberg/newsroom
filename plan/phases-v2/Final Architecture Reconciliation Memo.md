# Final Architecture Reconciliation Memo

Date: 2026-08-24  
Repository reviewed: `G:\Projects\Newsroom -v2`  
Baseline: `plan/phases-v2/Strategic Architecture Review.md`  
Scope: narrow Phase 27–30 reconciliation; no runtime/schema implementation

## 1. Final Verdict

**PHASE 27 PLAN NEEDS SPECIFIC ARCHITECTURE CHANGES**

The repository does not need an architectural repair before Phase 27, but the Phase 27 plan must bind several repository-specific decisions before implementation:

1. preserve `claims.story_id` as the current membership pointer;
2. replace one-time assignment history with append-only transitions;
3. preserve `story_documents` as historical provenance and stop using unfiltered historical rows as current Story context;
4. split manual Story-Entity authority from Claim-derived projection state;
5. make one Story correction aggregate the stable cause for membership and lineage changes;
6. enqueue bounded durable reconciliation for reports, Questions, search, and other projections.

These are contained extensions of existing conventions. No separate current-membership table, generic event system, Phase 29 processing-provenance framework, or Simple/Advanced runtime branch is warranted.

## 2. Binding Phase 27 Decisions

### Claim current Story membership

Keep:

```text
claims.story_id = nullable current Story membership pointer
```

This is the smallest correct change. Current readers throughout `EvidenceService`, Ask, reports, Research Questions, Workbench, and the resolver already treat `claims.story_id` as current state. Replacing it with a separate membership table would require rewriting many correct joins without adding information that the current pointer plus history cannot represent.

The live schema already permits an automatic Claim to have `story_id = NULL` and migration 0023 deliberately removed `story_id` from `claims_automatic_provenance_immutable` (`newsroom/migrations.py:1964`). There is no remaining provenance reason to replace the pointer.

### Claim Story history

Generalize `claim_story_assignment_history` from one row per Claim to an append-only transition log supporting:

```text
NULL → Story A
Story A → Story B
Story A → NULL
Story B → Story C
```

Required fields:

```text
id
claim_id
from_story_id nullable
to_story_id nullable
correction_id
origin                  human | automatic | import | repair
reason_code
reason
occurred_at
```

Require `from_story_id IS NOT to_story_id` and at least one endpoint non-null. Remove the current `UNIQUE(claim_id)` and `to_story_id NOT NULL`. Keep immutable update/delete triggers. Index `(claim_id, occurred_at, id)`, `from_story_id`, `to_story_id`, and `correction_id`.

The correction service, not an uncontextualized trigger-generated random event, should insert the transition with its exact correction identity, origin, actor/reason, and time. A defensive trigger may reject a `claims.story_id` update without a transaction-local authorized correction mechanism, but the service-owned history insert is the semantic record.

### Triggers, constraints, and Claim invariants

Change:

- drop/replace `claims_story_association_immutable` (`migrations.py:1972`), which currently blocks any non-null transition;
- rebuild `claim_story_assignment_history` (`migrations.py:1981`) without `UNIQUE(claim_id)` and with nullable `to_story_id` plus correction metadata;
- replace the initial-assignment-only history trigger (`migrations.py:1992`) with controlled service writes or a guarded all-transition trigger;
- update `EvidenceService.assign_claim_to_story()` and `_assign_claim_to_story_tx()` (`evidence.py:374`) into a controlled transition API that accepts `story_id | None`, correction identity, origin, and reason;
- update `AutomaticStoryStageExecutionService` so it uses the transition API only for a never-decided automatic Claim.

Keep untouched:

- accepted Claim proposition/hash immutability;
- automatic `article_analysis_id`, candidate index, proposition, and proposition-hash immutability;
- accepted-at immutability;
- Claim delete immutability;
- unique automatic Claim identity `(article_analysis_id, candidate_claim_index)`;
- ClaimEvidence and EvidenceSpan provenance/immutability.

Recommended migration: additive correction/lineage tables first; rebuild only `claim_story_assignment_history`; backfill existing rows with `origin='automatic'` when the Claim has ArticleAnalysis provenance, otherwise `origin='human'`, `reason_code='initial_assignment'`, and a deterministic legacy correction identity or nullable legacy cause explicitly allowed by migration. Do not fabricate reassignments. Recreate immutable-history triggers and add integrity checks that the ordered transition chain terminates at `claims.story_id`.

### `story_documents`

`story_documents` means **append-only historical Story/Document observation provenance today**. This is proven by immutable update/delete triggers (`migrations.py:844`) and by every writer using `INSERT OR IGNORE`:

- Story observation/evolution (`story_evolution.py:493`, `589`);
- automatic Story stage (`story_automation.py:510`);
- Story revision provenance (`evidence.py:691`);
- manual vertical-slice fixture/run (`evidence.py:1061`).

Its current uses are:

| Use | Current classification |
|---|---|
| Story timeline/evolution provenance | Historical |
| `StoryEvolutionService.corroboration(story_id)` | Currently treated as current; unsafe after correction |
| legacy `StoryEvolutionService` candidate construction and update classification | Automatic matching/evolution input; unsafe after correction |
| Phase 23 automatic candidate retrieval, entities/locations/source/event/time summaries | Automatic matching signal; unsafe after correction |
| Source-targeted report Story discovery | Reporting input; unsafe after correction |
| Workbench monitor/source diagnostics | Navigation/diagnostic input; unsafe after correction |
| Story revision document links | Separate immutable historical provenance; safe |

Phase 27 invariant:

```text
story_documents
= append-only historical Story/Document observation association

current_story_documents
= documents reachable from currently assigned Claims
   → ClaimEvidence
   → EvidenceSpan
   → DocumentVersion
   → Document
```

An explicit view is optional. The minimal safe implementation is one shared SQL helper/CTE for effective current documents. Where historical `story_documents` carries event/entity/location snapshot metadata, join that metadata only for document IDs present in the current ClaimEvidence-derived set.

Without this fix, moving Claim C from A to B leaves `(A,D)` in `story_documents`, and D can still:

- retrieve/rank Story A in `AutomaticStoryResolutionService._retrieve_candidates()` (`automatic_story_resolution.py:543`, `575`, `619`);
- influence legacy `StoryEvolutionService.resolve/process()` via current candidate entities, locations, event key, URL, time, same-Source and lineage tests (`story_evolution.py:891`, `982`, `992`);
- count as Story A corroboration (`story_evolution.py:736`);
- make a Source-targeted Living Report include Story A (`reports.py:257`);
- appear in Workbench Story-monitor Source context (`workbench.py:877`).

Ask Story scope already follows current `claims.story_id`, not `story_documents`, and is safe. Story timelines and prior revisions should continue showing D historically.

### `story_entities`

Current authority is mixed and insufficiently distinguishable:

- explicit API/service calls can insert `origin='user'`, which is a manual decision;
- `KnowledgeService.link_claim_entity()` and `_link_claim_entity_tx()` copy Claim Entities into `story_entities` with the Claim relation origin (`knowledge.py:327`, `707`), producing automatic Claim-derived projection rows;
- `origin='import'` and `origin='backfill'` are allowed;
- primary key `(story_id, entity_id)` permits only one row, so the first origin wins and a later manual decision cannot be represented independently from an automatic row.

Readers treat the table as authoritative: Entity detail uses it (`knowledge.py:744`) and Ask Entity scope expands Stories from it (`ask.py:463`). Search is dirtied by it, although Story search text currently does not directly include `story_entities`.

Binding authority model:

```text
effective current Story Entities
= manual Story-Entity relationships
   UNION
   Entities on currently assigned Claims
```

Phase 27 must distinguish manual rows from the materialized automatic projection. Preferred minimal schema is separate storage:

- preserve `story_entities` for explicit/manual/import decisions, or add an authority key that permits a manual row and derived row to coexist;
- create/rebuild a clearly named Claim-derived projection table/view if materialization is needed.

Do not rely on the current single `origin` column with `(story_id, entity_id)` uniqueness; it cannot safely preserve manual authority during rebuild.

Reconciliation contract:

- Claim reassignment/unassignment: recompute derived Entity pairs for both old and new Stories from current Claims; never delete manual rows.
- Story merge: retain source historical/manual rows; copy manual rows to the destination only as an explicit merge decision, then rebuild destination derived rows from moved Claims.
- Story split: the split command explicitly assigns/copies manual Story metadata; derived rows come only from Claims placed in each Story.
- Entity merge: resolve effective reads through `entities.merged_into_id`/merge lineage and rebuild derived pairs to the canonical Entity. The current repository has merge schema/history but no complete merge service, so Phase 27 should make its reconciliation callable without implementing broad Entity merge UX.

### Story Tags

Both tables are currently treated as authoritative and can drift:

- `CoreService.get_story()` and Workbench Story text read `story_tags` (`domain.py:942`, `workbench.py:171`);
- tag filtering and Tag detail read `tag_assignments` (`workbench.py:360`, `knowledge.py:441`);
- `CoreService.tag_story()` writes `story_tags` then compatibility-writes a user `tag_assignments` row (`domain.py:1081`);
- `KnowledgeService.assign_tag(..., object_type='story')` writes `tag_assignments` then compatibility-writes `story_tags` (`knowledge.py:399`);
- there is no symmetric removal path or database constraint proving parity;
- logical export includes both tables.

Long-term authority should be `tag_assignments`; `story_tags` is a legacy compatibility projection. Phase 29 should complete that consolidation.

Minimum Phase 27 rule: do not infer, copy, delete, or merge Story Tags from Claim moves. Merge/split must treat Story Tags as explicit Story-level decisions:

- merge: source tags remain historical; any destination tag copy must be explicit and dual-written through one existing service;
- split: default to no inherited tags unless the user explicitly selects tags for the new Story;
- reassignment/unassignment: no Story Tag mutation;
- add a parity integrity check for Story assignments touched by a correction, but do not perform the large authority migration in Phase 27.

### Same Story, related Story, and follow-on development

Binding editorial rule:

- **Same Story:** records describe the same underlying event, decision, release, incident, proceeding, or continuously developing outcome, such that the defining Claims can coexist on one chronological evidence ledger without changing the subject of the event. Corrections, contradictions, updated quantities, and later confirmation of that same event remain the same Story.
- **Related but separate Story:** records share context or consequences but have distinct defining events/decisions. Each can be understood and corrected independently. Store no lineage merely because they are related; cross-domain Entity/Topic/Question links already express discoverability.
- **Follow-on/parent-child:** a later event is causally or procedurally dependent on an earlier Story but has its own defining event and lifecycle—for example announcement → investigation → ruling. Keep separate Stories; add parent/child only when the product must navigate or summarize that causal sequence.

Strong/necessary automatic matching evidence remains repository-aligned:

- identical Document/canonical URL or a unique compatible exact defining Claim;
- strong proposition/text identity with compatible time and no event/location/exclusion conflict;
- entity-backed strong proposition/headline identity with compatible time;
- a named event/event key as corroborating evidence, never alone;
- continuity of defining Claims and event time, not merely surrounding context.

Weak signals insufficient alone:

```text
same Topic
same Entity
same Tag
same Source
same Research Question
generic vocabulary overlap
event key alone
historical Story Document alone
```

Duplicate suggestions use the same rule but may surface a unique near-threshold candidate for review. Merge approval asserts “same Story.” Split suggestions require evidence of at least two incompatible defining events, mutually incompatible time/location/event keys, or separable defining Claim clusters—not merely diverse Entities.

### Story lineage

Use a dedicated `story_lineage` table because Story lifecycle relations are not document lineage and cannot be reconstructed reliably from Claim transitions alone.

Required relationships only:

```text
merged_into   source Story → canonical destination Story
split_into    historical/original Story → each resulting Story
```

`split_from` is the inverse read of `split_into`; do not store both. Defer `duplicate_of`, `superseded_by`, `related_to`, and parent/child until concrete product behavior requires them. Duplicate approval becomes `merged_into`; duplicate dismissal is a decision/exclusion, not lineage.

Each lineage row references the exact Story correction. Correction records therefore cause lineage, rather than Story revisions owning lineage.

Rules:

- no self-edge;
- append-only;
- `merged_into` out-degree at most one per source;
- follow `merged_into` transitively to one active canonical Story, with cycle prevention in the write transaction and integrity checks;
- a merged Story is non-active/non-matchable and resolves to its canonical destination for ordinary navigation, while historical views retain its own timeline;
- `split_into` may have one-to-many edges and must never resolve the historical source to one arbitrary child;
- a split historical Story resolves to a choice/list of active children plus its own historical view;
- active Stories resolve to themselves unless later merged.

### Story correction record

Use one coherent domain-specific aggregate, not three unrelated top-level record types and not a generic event table:

```text
story_corrections
  id
  operation_type        reassign | unassign | merge | split | duplicate_dismissal
  origin                human | automatic | import | repair
  actor
  reason_code
  reason
  cause_class
  caused_by_type/id nullable
  occurred_at

claim_story_assignment_history
  ... correction_id

story_lineage
  ... correction_id
```

One correction may own many Claim transitions and lineage rows, which is required for merge/split atomicity. Domain-specific child rows remain strict; this is not a generic event schema.

The correction ID is the stable cause supplied to Story reconciliation Jobs, new corrective Story revisions/evolution entries where applicable, report regeneration, Question reevaluation, Workbench timelines, Ask, logical export, and integrity checks.

### Correction cause classification

`cause_class` belongs on `story_corrections`, not on every StoryRevision and not in a shared Phase 29 structure:

```text
new_evidence
reprocessing
human_correction
administrative
```

Exact `caused_by_type/id` identifies the triggering promotion, analysis, Job, prior decision, or user action. Exact IDs answer “what caused this”; `cause_class` answers the narrow semantic distinction “new world evidence or changed interpretation.” Derived revisions/jobs copy/reference `correction_id`; they need not duplicate the classification.

Normal Phase 23 automatic initial assignment is not a Story correction and remains explained by its Job/promotion/evolution exact causes. Phase 27 correction operations default to `human_correction`; repair/import tooling must choose explicitly. `new_evidence` should be used only when a newly acquired canonical evidence item caused the regrouping, not merely because old evidence was reconsidered.

### Manual authority and automatic resolver behavior

The latest controlled current-membership decision is authoritative.

- Manual reassignment: resolver and stale automatic Jobs may not move the Claim again.
- Manual unassignment: `story_id=NULL` is an intentional hold, not “never assigned.” Automatic resolver must defer rather than reassign.
- Story merge: merged source is excluded from active candidate retrieval; navigation resolves to the canonical destination.
- Story split: historical source is excluded from active matching if retired; children are independent active candidates. No arbitrary canonical child.
- Duplicate dismissal: persist a pair/Claim-to-Story exclusion decision tied to the correction/decision ID; candidate retrieval may remain broad, but matching must apply the exclusion before proposing/assigning the same pair again.

The resolver can distinguish a new unassigned automatic Claim from a manually unassigned Claim by assignment history: no history means eligible initial assignment; latest transition to NULL with human authority means locked/deferred. Do not add a redundant boolean unless query/performance evidence requires it.

Candidate inputs must use:

- latest active Story revision as descriptive context, but never as membership authority;
- current Claims from `claims.story_id`;
- current Documents from current Claims, with historical snapshot metadata only for those Documents;
- effective current Entities from manual relations plus current ClaimEntities;
- Story Tags only as explanatory/weak context, never sufficient matching authority;
- duplicate-dismissal exclusions.

### Transaction boundary

Atomic in one SQLite transaction:

| Operation | Atomic state |
|---|---|
| Claim reassignment | correction header; `claims.story_id`; one transition row; manual authority/exclusion state; projection-dirty markers; durable reconciliation Job enqueue |
| Claim unassignment | same, with `to_story_id=NULL`; explicit manual hold semantics; Job enqueue |
| Story merge | correction header; all selected Claim transitions; `merged_into` lineage; source lifecycle retirement; duplicate decision resolution; manual metadata decisions; dirty markers; Job enqueue |
| Story split | correction header; new Story creation; selected Claim transitions; one-to-many `split_into` lineage; source lifecycle decision; explicit manual metadata choices; dirty markers; Job enqueue |

The transaction must not synthesize reports, run Question evaluation, call providers, or rebuild broad projections.

Durable reconciliation outside the transaction:

1. validate correction/transition chain and current membership;
2. rebuild current Story-Document and Story-Entity projections for affected Stories;
3. create corrective current Story revisions for affected active Stories while preserving old revisions/evolution as history;
4. refresh Story Monitor scopes and reconcile Story-targeted Watches/Monitors without rewriting pinned historical scope;
5. regenerate affected Living Reports using correction ID as an exact non-evidence cause supported by the changed Claim set;
6. evaluate Alerts only from the new ReportRevision; correction itself does not bypass Report causality;
7. reevaluate Questions linked to moved Claims, then allow existing Gap/Task reconciliation to follow;
8. mark/rebuild search projection;
9. run bounded integrity checks and complete the Job with counts.

Use `JobService` with correction-ID idempotency, attempts, lease recovery, completion outcome, and rerun factory. Phase 23’s report/alert chain is currently keyed specifically to automatic Story-stage Jobs, so Phase 27 needs a dedicated correction reconciliation Job rather than pretending a correction is a new automatic promotion.

## 3. Derived-State Reconciliation Matrix

| State | Current meaning | Desired meaning | Current or historical? | Canonical/human/derived? | What Phase 27 must do |
|---|---|---|---|---|---|
| `claims.story_id` | One-time current Story pointer | Mutable only through controlled corrections; nullable current pointer | Current | Current domain state | Update atomically; keep pointer |
| `claim_story_assignment_history` | One immutable initial assignment row | Full append-only transition chain | Historical | Human/automatic decision history | Rebuild schema; link correction; validate chain |
| `story_documents` | Append-only observation links, also misused as current | Historical Story/Document provenance only | Historical | Historical | Never delete/move; replace current-context reads |
| effective current Story Documents | Implicit/mixed | Current ClaimEvidence-derived document set | Current | Derived projection | Add shared query/view; rebuild/dirty affected Stories |
| `story_revisions` | Immutable evidence-bound Story snapshots | Same; correction reconciliation adds new current snapshots | Historical sequence | Historical derived intelligence | Preserve old rows; append corrective revisions |
| `stories.current_revision_id` | Present but Story getters usually select latest revision; not consistently maintained | Either make it a valid current pointer or formally retire in Phase 29 | Current/mixed | Cache/pointer | Do not rely on it; Phase 27 plan must state latest revision rule |
| `story_revision_claims` | Claim set cited by one revision | Same | Historical | Historical provenance | Never rewrite when Claim moves |
| `story_revision_documents` | Documents cited/triggering one revision | Same | Historical | Historical provenance | Never rewrite |
| `story_evolution_events` | Immutable observations/classifications | Same; optional correction-linked event only when it truthfully represents Story evolution | Historical | Historical derived/provenance | Never move/delete; timelines remain truthful |
| `story_entities` | Mixed manual and copied Claim-derived rows | Explicit/manual authority separated from derived projection | Mixed | Human + derived | Split authority; rebuild derived rows; preserve manual |
| `claim_entities` | Claim-level Entity relationships | Same | Current relationship with provenance | Mixed human/derived at Claim level | No move needed; current Story aggregation follows Claim |
| `story_tags` | Legacy Story tag relation and active reader | Compatibility projection of authoritative assignments | Current | Human/derived compatibility | No inferred movement; maintain parity for touched tags |
| `tag_assignments` for Story | Smart/manual assignment authority for modern filtering | Long-term authority | Current | Mixed human/derived | Use as decision source; avoid broad migration |
| `story_topics` | Story-level metadata and resolver signal | Explicit Story metadata, never Claim-derived membership proof | Current | Human/import/legacy decision | Merge/split choices explicit; no automatic union |
| `story_subjects` | Story-level metadata, scopes, Workbench/Ask signal | Same | Current | Human/import/legacy decision | Merge/split choices explicit; no automatic union |
| `story_review` | Current review state and last reviewed revision | Per-Story human decision | Current | Human decision | Merge/split policy explicit; do not copy silently |
| `feedback_events` | Schema exists but live review path does not write it | Optional historical user signal | Historical | Human telemetry | Do not depend on it; correction history supplies Phase 27 metrics |
| Story duplicate exclusions | Not persisted | Durable manual negative decision | Current + history | Human decision | Add so resolver cannot repeat dismissed match |
| `story_lineage` | Absent | Append-only merge/split lineage | Historical/current resolution | Human decision history | Add dedicated table and resolver rules |
| Living Report target | Durable target Story | Same; merged target resolves or archives by explicit policy | Current | Human intent | Reconcile source/destination reports via Job |
| `report_revisions` / claims / causes | Immutable report snapshots with exact evidence/evolution causes | Same; new correction-driven revision must cite correction plus current Claim set | Historical | Historical derived | Preserve; generate new revision durably |
| Alerts/deliveries | Immutable interruption tied to ReportRevision causes | Same | Historical | Historical derived | Never rewrite/retract; evaluate new Alert only after new ReportRevision |
| `research_question_claims` | Explicit Question-to-Claim relation independent of Story | Same | Current + history/overrides | Human/derived relationship | Do not move; enqueue reevaluation for linked Questions |
| Question assessments/history | Current assessment plus append-only snapshots | Same | Current + historical | Derived + historical | Reevaluate durably; preserve prior assessments |
| Evidence Gaps/history | Current analysis state plus history | Same | Current + historical | Derived + human decisions | Let Question reevaluation reconcile; preserve dismissals/history |
| Research Tasks/attempts/findings | Bounded historical research work | Same | Historical/current process | Human intent/process | Do not move; current Question results may update through existing rules |
| Story-targeted Watches/Monitors | User intent plus operational scope pinned from latest Story revision | Same, with explicit merge/split reassignment policy | Current + historical scopes | Human intent/operational | Reconcile targets explicitly; preserve scope history |
| Workbench `search_records`/FTS | Rebuilt cache, dirty-triggered | Same | Current | Cache/index | Mark dirty in atomic transaction; rebuild outside |
| Ask runs | Historical answer audit; Story scope expands current Claims | Same | Historical | Audit metadata | Do not rewrite; future Ask sees current pointer; timelines expose correction |
| logical export | Exports both authoritative and mixed projection tables | Export correction/history/lineage; label or later omit rebuildable projections | Historical snapshot | Mixed | Add new records; retain compatibility rows for now |
| integrity checks | Validate automatic Story→Report→Alert chains against current Claim membership | Validate historical chain at event time plus current transition consistency | Current validation | Operational | Amend checks so later valid correction does not falsely invalidate old automatic checkpoints |

Critical integrity implication: current Phase 23 checks join old automatic Job results to the Claim’s **current** `story_id` (`integrity.py:504`). After legitimate reassignment, that becomes a false failure. Phase 27 must validate the original automatic assignment through the matching history/evolution/revision/correction chronology, not require permanent current membership.

## 4. Phase 27 Plan Amendments

### BLOCKING

1. Preserve `claims.story_id`; specify the transition-capable history schema and migration.
2. Define the domain-specific `story_corrections` aggregate and exact correction-ID causality.
3. Add `story_lineage` with only `merged_into` and one-to-many `split_into`; define cycle/canonical resolution.
4. Bind `story_documents` as historical and replace all current-context reads identified in Section 2 with the ClaimEvidence-derived effective set.
5. Separate manual Story-Entity authority from Claim-derived projection state and define rebuild rules.
6. Define manual unassignment/duplicate dismissal as durable negative authority so stale automation cannot reverse it.
7. Define SQLite atomic state and a dedicated JobService-backed correction reconciliation workflow.
8. Amend integrity logic so historical Phase 23 checkpoints remain valid after a legitimate later correction.
9. Add failure/replay/concurrency tests proving transition history, correction idempotency, lineage cycles, split one-to-many semantics, stale Job resistance, and projection convergence.

### IMPORTANT

1. State that Story revisions/evolution, Report revisions, Alerts, prior Ask runs, Question histories, and Research Tasks remain historical and are never rewritten.
2. Add explicit merge/split policies for Story Topics, Subjects, Tags, review state, Reports, and Story-targeted Watches; default to no silent copying of human intent.
3. Add production Story-quality telemetry derived from correction/history/resolver records.
4. Persist duplicate suggestions and approval/dismissal decisions if Phase 27 exposes that workflow; the current resolver only returns ambiguity/candidates and has no review history.
5. Add exact correction cause propagation to reconciliation Job result, new Story revision metadata/timeline, ReportRevision cause, Workbench, Ask, export, and integrity.
6. Rename or qualify misleading Source-independence fields if touched.

### OPTIONAL

1. Materialize `current_story_documents` only if query benchmarks require it; a shared CTE/view is sufficient initially.
2. Add parent/child Story lineage only if a concrete Phase 27 UI/workflow needs it; otherwise defer.
3. Add a compact Story correction timeline panel. Do not build the full Phase 28 investigative shell.
4. Add `ui.mode` documentation only; no Phase 27 schema/runtime mode hook is needed.

## 5. Phase 28A / 28B Confirmation

Keep two checkpoints under one Phase 28. Repository reality reinforces the proposed dependency order.

### Phase 28A — Observation and Source Robustness

1. Extend existing immutable `document_lineage` rather than create a parallel Source-dependency architecture. Current relationships are `cites`, `syndicated_from`, `wire_propagation`, `rewritten_from`, and `common_primary_document` (`story_evolution.py:37`). Consumers already include lineage inspection, cycle prevention, corroboration grouping, update classification, Phase 24 Source discovery, and tests.
2. Add Source/document dependency inference and review over those edges.
3. Derive evidence families as connected lineage/dependency groups.
4. Build Evidence Fragility/counterfactual analysis from ClaimEvidence plus evidence families.
5. Build Coverage as a projection/analysis over existing facts, not a duplicate observation ledger.
6. Add qualified absence and bounded blind-spot signals only after the denominator is explicit.

Existing observation facts already cover:

- `acquisition_events`: Source/channel/request/final URL, outcome/status/content metadata, bytes, hashes, error, observed time, resulting Document/Version;
- `monitor_activity`: Monitor outcome, new/changed/relevant counts, error code, observed time, cadence/error history;
- Watch health: active Sources, pending Source/vocabulary candidates, last/next attempts, monitor errors, Job failures, discovery state/error;
- `source_profiles`: acquisition methods, observed activity, stored coverage metadata, duplication/usefulness summaries, failure counts/codes/times;
- Research Tasks: exact bounded plan, limits, queries/hash/strategy/order, findings and acquisition/result identities, attempts/outcomes/no-findings;
- Jobs/attempts: status, retries, errors, timing, result and recovery identity;
- Source discovery: candidate method, rationale, authority context, limitations, provenance, review outcome.

Missing denominator only:

```text
what should have been observed
expected Source classes/channels
intentional exclusions and reason
what was not searched
expected and completed observation window
coverage completeness/known gaps
```

### Phase 28B — Intelligence Experience and Safe Analysis

Consume 28A outputs for:

```text
dependency/evidence families → fragility explanations
coverage → qualified absence and blind spots
28A outputs → Attention ranking/explanation
28A outputs → Competing Hypotheses context and discriminating Gaps
28A outputs → Simple/Advanced contextual warnings
```

Then implement Attention, shared investigative shell, contextual Simple/Advanced visibility, capability authority controls, progressive autonomy UI, Alert-value instrumentation, and experimental Competing Hypotheses.

No compelling repository reason exists to create separate top-level phases. Two acceptance checkpoints preserve dependency order while avoiding roadmap churn.

## 6. Phase 29 / 30 Confirmation

The strategic direction remains correct.

Phase 29 should explicitly reconsider:

- automatic Tag persistence and `story_tags`/`tag_assignments` consolidation;
- whether current StoryEntity materialization remains worthwhile after Phase 27 establishes correct authority;
- EntityMention persistence/retention and analyzer-run identity;
- migration of `knowledge_backfills` onto JobService;
- per-query FTS rebuild cost and a clearer projection rebuild contract;
- cross-domain timeline/read model after Story corrections add another event-producing domain;
- processing provenance, shadow reprocessing, and Belief Diff;
- projection registry/rebuild guarantees;
- retention and provenance-aware deletion;
- logical import/restore plus projection rebuild;
- `stories.current_revision_id`, which exists but is not consistently maintained/read as authoritative;
- unused `feedback_events`, which is currently schema-only and should either gain a real contract or be removed;
- legacy `story_evolution.py` resolver versus Phase 23 `automatic_story_resolution.py`, which currently duplicate candidate/matching paths and both consume historical Story Documents;
- dormant Entity merge schema without a complete service contract.

Phase 30 remains the Full-vs-Lite, temporal corpus, dogfood, Simple/Advanced, feature-subtraction, and release-decision phase. Material correction: Story correction burden and historical-membership correctness must be part of the Phase 30 scorecard, using Phase 27 telemetry rather than retrospective inference.

## 7. Terminology Corrections

Adopt immediately:

```text
distinct_source_count
= count of different Source records

lineage_group_count / evidence_family_count
= dependency-aware grouping count

independent_source_count
= forbidden unless the calculation and UI explicitly define
   the dependency model used
```

Current precise usage:

- Ask says “distinct Source records” and warns that multiple Documents from one Source are not independent (`ask.py:806`); keep it.
- Phase 25/26 planning text already warns that distinct Source IDs are not independence; keep it.

Current overstatement:

- `StoryEvolutionService.corroboration()` returns `independent_source_count` (`story_evolution.py:775`). It is lineage-aware for the five current Document relationships, but its key construction can count one single-Source lineage group by Source ID and lacks broader dependency/ownership/shared-evidence semantics. Rename to `lineage_adjusted_source_group_count` or expose `lineage_group_count` plus `distinct_source_count` until Phase 28.
- Research Question criteria use `min_independent_sources` and a gap `independent_support`, but implementation is `len(source_ids)`—distinct Source records only (`research_questions.py:616`, `648`). This is materially misleading. Before/during Phase 27 if the schema is touched, present it as `min_distinct_sources` / `distinct_source_support`; otherwise record a Phase 28 migration and change user-facing text now.
- `classify_update(... source_independent=not same_source)` in legacy Story evolution means only “different Source record,” not independence (`story_evolution.py:1004`). Rename on the next touched change or stop using the independence label.

Story terminology:

- use **assignment/reassignment/unassignment** for Claim current membership;
- use **merge** only for asserting same Story;
- use **split** only for separating incompatible defining events/Claim clusters;
- use **related** without lineage unless a product behavior depends on the relation;
- use **historical Story Document** versus **current Story Document context** explicitly.

## 8. Evaluation / Telemetry Integration

### Fixture/evaluation metrics

Extend existing `newsroom.evals`; do not create another framework.

The current 30-case corpus already labels candidate Documents into gold event groups and the Prediction schema already carries Story groups and Claims. Existing pairwise false-merge/false-split/duplicate metrics cover final grouping quality.

Smallest Phase 27 extension:

1. add optional ordered correction checkpoints to selected cases rather than a new case format/framework;
2. add Prediction membership snapshots/transitions keyed by Claim and checkpoint;
3. score:
   - Claim reassignment correctness: expected Claim → Story at checkpoint;
   - merge correctness: resulting candidate/Claim partition equals gold same-event group;
   - split correctness: incompatible gold groups remain separate;
   - historical membership correctness: transition sequence and prior snapshot remain queryable;
   - stale-context correctness: moved Document/Entity cannot affect the old Story’s current resolver/report/Ask context;
4. reuse current event false-merge/false-split metrics for final state; add transition metrics separately rather than altering their meaning.

Phase 26’s retrieval benchmark remains a search regression benchmark; add Story correction search cases to it only to prove old/new Story navigation and current filtering, not to measure editorial accuracy.

### Production telemetry

Calculate later quality rates from durable domain records, not eval fixtures and not a new metrics service:

- automatic assignments: initial transition history rows tied to automatic Story-stage Job/promotion identity;
- manual reassignments/unassignments: correction type/origin plus transition rows;
- merge approvals/splits: correction operation type;
- merge suggestions: persist suggestion/decision record when produced;
- merge dismissals: duplicate-dismissal correction/decision;
- time-to-correction: correction `occurred_at` minus initial automatic transition time;
- origin/algorithm identity: existing automatic Job result contains reason/signals/candidate IDs; add a resolver algorithm/version constant to the persisted decision/result;
- manual interventions per 100 automatic assignments: aggregate correction transitions over automatic initial transitions, segmented by operation and consequence.

Do not use `feedback_events` for this unless it is first given a real writer and immutable contract; currently the table has no live writes.

### Simple/Advanced timing

Phase 27 needs no mode schema/runtime hook. The generic `settings` table and authenticated settings API can later store `ui.mode = simple|advanced`; current component/API composition is sufficient for UI visibility. Capability authority settings should be designed in Phase 28B, independent of visibility. Phase 27 should expose stable capability/operation names and avoid mode-specific branching.

## 9. Outstanding Questions

| Question | Why unresolved | Phase | Blocking now |
|---|---|---|---|
| On merge, should a Story-targeted Watch/Monitor retarget automatically to the canonical Story or require confirmation? | This is a product-intent decision; both are technically supportable, and Watch intent should not be silently changed without a declared policy. | 27 plan | Yes |
| On split, does the original Story remain a historical container only, or can it remain active alongside children? | The answer changes resolver eligibility, Report/Watch handling, and UI resolution. Recommendation is historical/retired source with active children, but product confirmation is required. | 27 plan | Yes |
| Which explicit Story Topics, Subjects, Tags, and review state should copy during merge/split? | These are human Story-level decisions, not derivable from Claim membership. Default is no silent copy except explicitly selected merge destination metadata. | 27 UX contract | Yes |
| Should Phase 27 materialize effective current Story Documents/Entities or use views/queries initially? | Correctness contract is resolved; only benchmarked performance can choose materialization. | 27 implementation | No |
| Should parent/child Story lineage enter Phase 27? | No current required workflow consumes it. Keep deferred unless Phase 27 product design adds a concrete follow-on navigation requirement. | 27/28 | No |

All other requested architecture questions are resolved by this memo.

## 10. Immediate Next Step

**REWRITE PHASE 27 PLAN, REVIEW ONCE, THEN IMPLEMENT**

The one review should verify that the rewritten plan contains every BLOCKING item in Section 4, chooses the three remaining product policies in Section 9, and does not pull Phase 28/29 systems into Phase 27.

Planning hierarchy to encode at the same time:

```text
plan/phases-v2/
= active forward execution authority

plan/phases-old/
= historical implementation plan

plan/MASTER_PLAN.md
= high-level overview only after reconciliation

plan/newsroom-v2-dev-plan.md
= high-level development overview only after reconciliation
```

Minimal documentation guardrails:

1. create `plan/phases-v2/README.md` with an explicit authority banner, current checkpoint, phase index, and “next permitted phase”;
2. add a historical/superseded banner to `plan/phases-old/README.md` without rewriting Phase 01–26 records;
3. update both top-level overview plans to point to `phases-v2/README.md` for executable phase definitions and remove obsolete Phase 27/28 summaries;
4. ensure repository README/agent instructions link to the active index;
5. use unambiguous filenames `Phase 27.md` through `Phase 30.md` only under `phases-v2`.

No runtime/schema changes, commits, pushes, or unrelated-file changes were made during this reconciliation.
