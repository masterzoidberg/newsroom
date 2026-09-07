# NEWSROOM V2 — ADVERSARIAL PRODUCT AND ARCHITECTURE REVIEW
## Independent codebase-first second opinion before Phase 29 is frozen

**Review date:** 2026-08-24
**Repository:** `G:\Projects\Newsroom -v2`
**Branch:** `main`
**HEAD (verified live):** `68f73ca84097728880736deb354dd4226c4c7018` — "Phase 28: rank attention candidates before limiting"
**Schema:** migration 0032 / schema version 32 (132 `CREATE TABLE` statements in `newsroom/migrations.py`)
**Working tree:** dirty — `plan/phases/` deleted (unstaged), `plan/phases-v2/*.md` and `plan/phases-old/` untracked, a `Newsroom -v2 - Phase 28.zip` build artifact and `.kilo/` untracked. Planning authority is currently *uncommitted*.
**Tests:** `python -m pytest -q` → **779 tests, 0 failures**, full suite green.
**Backend size:** 36,217 lines across 54 modules. **Eval corpus:** 30 cases, **unchanged since commit `d7b1524` (Phase 0)**.

This review ran deterministic probes against throwaway temporary databases. The live project database was not touched. No runtime code, schema, migration, test, or frontend file was modified.

---

# 1. EXECUTIVE VERDICT

### Product continuation verdict — **CONTINUE, BUT SIMPLIFY AGGRESSIVELY**

There is a real, differentiated product here, and its differentiation is not imaginary: correctable Story identity with append-only correction history, exact-cause Report/Alert causality, and an evidence ledger where Claims cannot outrun their spans are things a "RSS + LLM with citations" baseline genuinely cannot do. That core has earned its complexity.

But the last two phases have been adding *product surfaces* faster than they have been adding *proven intelligence*, and Phase 28 in particular shipped a layer that is architecturally shaped but functionally hollow — and, in one case, actively dangerous. The correct move is not more Newsroom. It is less Newsroom with the proven parts hardened.

### Architecture verdict — **SOUND CORE, UNSAFE DERIVED LAYER**

The canonical layer (documents → versions → artifacts → spans → claims → stories, with corrections) is well-modelled and well-tested. The Phase 28 derived layer (Coverage, Evidence Families, Fragility, Attention, Blind Spots, Hypotheses) has no invalidation discipline, no producers, no user surface, and in two places produces materially false output. It currently *overstates its own authority* in the database, in the logical export, and in Ask's natural language.

### Surface-area verdict — **REDUCTION IS REQUIRED, NOT OPTIONAL**

16 primary navigation items, 4 overlapping taxonomies (Topic/Subject/Tag/Entity), 2 unrelated concepts both named "Coverage", 3 systems competing to tell the user "look here" (Attention queue, Alerts, Inbox), and 2 parallel Evidence-Gap lifecycles. A user cannot hold this model.

### Phase 29 plan verdict — **ACCEPTED WITH TARGETED EDITS**

This is the finding I did not expect. `Phase 29.md` §5–§52 (stage 29.0) independently diagnoses **almost every P0 I found**, and prescribes largely the right fixes. It is a better document than Phase 28 was an implementation. My edits are:

1. **Add the Ask global-scope coverage leak** (§13 of the plan does not cover it; it is the single worst live defect).
2. **Move Full-vs-Lite validation OUT of Phase 30 and INTO Phase 29.** The plan explicitly defers it (§127). That deferral makes Phase 30 an existential test, which is exactly the failure mode the review brief names.
3. **Defer 29B (Shadow Reprocessing / Belief Diff) entirely.** It is the least-earned, most expensive stage in the plan.
4. **Add a minimum tooling/CI standard** — the plan has zero mentions of lint, format, or CI.

Phase 29 as written is roughly 4,443 lines specifying five stages. That is too much for one phase given that stage 29.0 alone is a full phase of real work.

---

# 2. WHAT NEWSROOM ACTUALLY IS

### Target user

Derived from the implemented workflows — not from the marketing in the README — Newsroom is for the **longitudinal single-domain investigator**: someone tracking one contested, slow-moving, evidence-poor subject over months to years, where the important events are *corrections, contradictions, and confirmations*, not volume.

Concretely, the strongest fits, in order:

1. **Independent/obsessive domain researchers** (the UAP-disclosure archetype in the brief is exactly right) — contested claims, unreliable sources, heavy syndication, long timelines, and a genuine need to know "who actually reported this first, and did anyone independently confirm it?"
2. **Policy / regulatory analysts** tracking a narrow docket — the `official_archive` / `regulatory` channel vocabulary in `coverage.py` and the primary-vs-secondary eval cases point straight here.
3. **Investigative journalists on a single beat** — the correction ledger and Story merge/split machinery is journalist-shaped.
4. **Industry analysts tracking a handful of companies.** Weaker fit: they mostly want speed and summarization, which is Lite territory.

It is **not** for general news consumption, and the code shows no attempt to serve that.

### Core job

> *"Over months, tell me what actually changed about the thing I care about, show me why I should believe it, and remember what I already decided — without me re-reading everything."*

Three verbs: **remember, corroborate, correct.**

### Strongest differentiated capability

**Correctable Story identity with durable, append-only correction history** (`newsroom/story_corrections.py`, 1,207 lines; `story_target_resolution_history`). The system's automatic grouping can be wrong, the user can fix it, the fix is permanent, the fix is causally attributed, and downstream Reports/Alerts respect it. That is the moat. Everything else is either table stakes or unproven.

### Does the present UX match that user?

**Partially, and worse than it was two phases ago.** The user above wants a small number of high-signal surfaces. They get 16 nav items, most of which are the object model exposed directly ("Topics", "Subjects", "Documents", "Runs & jobs"). Phase 28's entire backend — Coverage, Attention, Fragility, Hypotheses, Blind Spots — is reachable from the UI through **one card in InboxView**, and the promised "Advanced" mode that would reveal the rest **does not exist** (see §12).

---

# 3. WHAT IS GENUINELY STRONG

These should not be casually simplified away. Removing any of them destroys a real advantage.

| Subsystem | Why it is strong | Evidence |
|---|---|---|
| **Evidence ledger** (Document → DocumentVersion → ContentArtifact → EvidenceSpan → Claim) | Claims cannot exist without spans; spans cannot exist without versioned, hashed content. This is the trust substrate and it is enforced, not documented. | `newsroom/evidence.py`, `content_artifacts.py`, FK chain in migrations |
| **Story corrections** | Append-only history, cause classification, reconciliation job, merge/split with preview. Genuinely hard to reproduce. | `story_corrections.py:32`, `:353`, `:1035`; `story_target_resolution_history` |
| **Exact-cause Report/Alert causality** | `report_revision_causes` ties every revision to the specific claim/span/document that caused it. Alerts fire on *material causes*, not keyword volume. | `reports.py`, `alert_automation.py`, `report_revision_causes` schema |
| **Document lineage + `lineage_group`** | The connected-component computation in `_lineage_group_tx` is correct and always current (computed on demand, never cached). It is the *honest* independence signal in the system. | `source_robustness.py:56` |
| **Deterministic local fallback throughout** | The product works with zero provider credentials. Rare and commercially valuable. | `ai.py` AIRouter, `provider_route="local_deterministic"` defaults |
| **Provenance/integrity checking** | `integrity.py` (1,184 lines) actively hunts orphans and authority violations. | `integrity.py:957`, `:1069`, `:1133` |
| **Ask's `insufficient_evidence` refusal** | A RAG system that refuses is worth more than one that doesn't. (Currently undermined — see P0-1.) | `ask.py:921` |
| **779 green tests / SQLite / no platform sprawl** | Real engineering discipline. Do not trade this away. | verified |

---

# 4. WHAT IS OVERBUILT

Complexity exceeding current value:

1. **Coverage** — 400 lines + 3 tables + 3 API routes + logical export + Ask integration, for a hand-maintained checklist. See §8.
2. **Evidence Families** — 2 tables and a content-addressed identity scheme that produces *stale, self-contradictory* output, layered on top of `lineage_group` which already answers the same question correctly and for free. See §9.
3. **Fragility** — a persisted table with no writer, a score that leaves its range and inverts its own meaning. See §10.
4. **Counterfactual lab** — `counterfactual()` is 20 lines of set arithmetic over `analyze_fragility`. It does not deserve, and does not have, a subsystem. It should stay a function; the plan's instinct to keep it non-mutating is right.
5. **Hypotheses** — 4 tables, 5 API routes, 141 lines of CRUD, **zero UI, zero generation, zero research integration**. See §13.
6. **Topic + Subject + Tag + Entity** — 4 taxonomies. See §14.
7. **Attention as durable state** — persisted `attention_items` + `attention_feedback` that never converge, when the same ranking could be computed on demand with a small durable *suppression* table.

---

# 5. WHAT IS UNDERBUILT

Exists mainly as scaffolding:

1. **Competing Hypotheses** — schema + CRUD only. `origin` accepts `'provider'`; nothing generates. `hypothesis_gaps` connects to nothing. No frontend reference to "hypoth" exists outside the Ask statement-classification enum.
2. **Blind Spot → Research** — `review_blind_spot(status='approved')` writes a status column that **no code reads**. Approving a blind spot has no effect on anything. Verified: the only reader of `blind_spot_suggestions` is `attention.py`'s `status = 'pending'` query and `integrity.py`.
3. **Simple / Advanced experience** — a persisted string. See §12.
4. **All four Phase 28 Jobs** — handlers with no producers. See §17.
5. **Entity merge** — `entity_merges` table exists, is exported, is integrity-checked, and has **zero `INSERT` sites**. A half-visible destructive capability.
6. **Onboarding** — there is none. See §21.
7. **External notification** — deliberately absent; see §21.

---

# 6. WHAT IS ACTUALLY BROKEN

Every item here was reproduced with a deterministic probe against a temporary database.

### BROKEN-1 — Ask fabricates a search claim, for the wrong target, on an unrelated question, and does not refuse

Probe (temp DB, empty except one coverage run):

```
c.create_run('watch','w1', ...)   # 'w1' does not exist as a Watch
c.record_item(r,'o','not_found')  # observation_refs = []  -> accepted
c.complete(r)                     # qualified_negative = True
ask('Was there any regulatory filing about widgets?')  # scope: global
```

Result:

```
status: qualified   refusal_code: None
answer: "Uncertainty: Coverage supports a qualified negative: the expected
         channels were searched, but no observation was recorded for at
         least one required channel. [cite_1]"
citations: [{object_type: "coverage_run", target_type:"watch", target_id:"w1"}]
```

Three independent defects compose here:

- **(a) Unqualified negative.** `record_item` only validates `observation_refs` *if supplied* (`coverage.py:167-183`). An empty list passes. So a hand-asserted `not_found` becomes `qualified_negative = True` (`_summary_rows`, `coverage.py:216`). The project's own test `test_complete_expected_window_qualifies_negative_absence` codifies this.
- **(b) Scope leak.** `AskService._coverage_context` maps `scope_type == "global"` to `target_type = None`, then calls `list_runs(target_type=None, target_id=None, limit=5)` — **the 5 most recent coverage runs of any target, injected into any global question** (`ask.py`, added in `c254596`).
- **(c) Refusal bypass.** The retrieval was empty and should have produced `insufficient_evidence` (`ask.py:921`). The coverage statement supplies the only statement and the run returns `qualified` instead.

Newsroom told the user it searched, when nothing was searched, about something it was not asked, and declined to admit it had no evidence. **This is the single most damaging line of code in the repository.**

### BROKEN-2 — Evidence Families go stale and contradict themselves in the same response

Probe: documents A (source A) and B (source B) support one claim; families rebuilt → 2 families. Then `link_lineage(B, A, 'syndicated_from')` is added. Then `evidence_summary` is called with no explicit rebuild:

```
before link:  families=2
AFTER link:   families=2   lineage_groups=1     <-- same dict, contradictory
fragility:    0.0   (correct value would be 0.5)
after explicit rebuild: families=1
```

`evidence_summary` only rebuilds when a document has **no** family row at all (`source_robustness.py:203-206`). Existing-but-wrong membership survives indefinitely. `reports.py:380` consumes `evidence_family_members` directly, so **Reports overstate independence too**. There is no lineage-write hook, and the `evidence_family_rebuild` job has no producer.

Aggravating: `family_key = sha256(document_id_list)`, so family *identity* changes whenever membership changes. Any persisted `family_id` (Attention explanations, counterfactual exclusions) can dangle.

### BROKEN-3 — Fragility leaves its range and inverts its own meaning

`score = 1.0 - (len(family_ids) / max(1, len(source_ids)))` (`source_robustness.py:300`).

```
PROBE A: 2 docs, ONE source, no lineage      -> sources=1 families=2 -> score = -1.0
PROBE B: 1 doc, 1 source (maximally fragile) -> score = 0.0 ("least fragile")
```

The documented interpretation is *"higher means more support traces to fewer evidence families"*. Probe B returns the minimum score while simultaneously listing the claim in `explanation.fragile_claim_ids` — **the score contradicts its own explanation in the same object.** Probe A returns a negative number from a metric presented as a bounded score.

### BROKEN-4 — Attention never converges

Probe: incomplete coverage run → `refresh()` → 1 open item. Complete the run → `refresh()` again:

```
refresh#2 open items: 1  [('coverage_run','coverage_gap','open')]
```

`refresh()` is insert-only (`INSERT OR IGNORE`, `attention.py:139`). Nothing ever resolves an item whose underlying condition is gone. The same applies to dismissed blind spots and acknowledged alerts. Attention is an append-only pile, not a projection.

### BROKEN-5 — "Keep open" makes the item disappear

`InboxView.tsx:48`: the button labelled **"Keep open"** calls `giveFeedback(id, "needs_investigation")` → backend sets `state = 'seen'` (`attention.py:172`) → and the frontend then does `setAttention(items => items.filter(item => item.id !== id))`. The button labelled "keep this" removes it from the queue. The label is the opposite of the behaviour.

### BROKEN-6 — Coverage accepts nonexistent targets

`create_run` validates `target_type ∈ {watch, research_question, story, ask, source}` and that `target_id` is a non-empty string — nothing more (`coverage.py:76-78`). Probe D created a run for `watch-does-not-exist` successfully. `target_version` is `str(target_version or "")` — arbitrary free text, defaulting to empty. Invalid Coverage then flows into Ask (BROKEN-1), Attention, Blind Spots, and `ResearchPrioritizationService.coverage_deficiency`.

### BROKEN-7 — `source_summary` has a latent crash path

`source_robustness.py:256-260`: when `evidence_family_members` is absent the query becomes `"SELECT NULL WHERE 0"` but `(source_id,)` is still bound → `sqlite3.ProgrammingError`. Dead path today; it will not stay dead.

---

# 7. WHAT IS MISLEADING

Names, docs, UI, and scores that overstate actual behaviour. This category matters more than usual for a product whose entire pitch is trustworthiness.

| # | Where | The overstatement | Reality |
|---|---|---|---|
| M1 | `ask.py` coverage statement | "the expected channels **were searched**" | Nothing was searched. A human set a state. |
| M2 | `docs/EVALUATION.md` (added in `c254596`) | "These scenarios **extend the existing evaluation corpus**" | `evals/corpus/cases/` has been **byte-identical since Phase 0** (`git log --name-status -- evals/corpus` shows exactly one commit, `d7b1524`). Phase 28 added pytest cases, not corpus cases. **A documentation claim contradicted by git.** |
| M3 | `docs/ARCHITECTURE.md:728` | "The durable derived handlers `coverage_refresh`, `evidence_family_rebuild`, `fragility_analysis`, `attention_refresh` **use the existing JobService**" | Nothing enqueues any of them. Verified by exhaustive grep: the only non-definition references are one test and this doc line. |
| M4 | `tests/test_research_question_worker.py:95` `test_production_handler_coverage` | Named as if it verifies "enqueue producers without a production handler" | `produced` is a hand-maintained literal set. It proves handlers were registered. It **entrenches** the four ceremonial jobs and would pass forever with zero producers. |
| M5 | `AdminViews.tsx:47` | "Advanced reveals source robustness, hypotheses, and counterfactual review." | No such views exist. `experience.mode` is read in exactly one place — the settings card that sets it. |
| M6 | `research_prioritization.py` rationale string | "...and **current budget availability**" | `cost_budget: 1.0` is a hardcoded constant. `freshness` is not freshness — it is `open` vs `pursuing`. 2 of 5 components are fiction. |
| M7 | `evidence_families.authority = 'derived'` column | Implies a manual/derived authority split like `story_entities` has | No service can ever write `'manual'`. The column is aspirational. |
| M8 | `evidence_fragility_analyses` table | A canonical-looking persisted analysis table, present in migrations *and* in the logical export | **Zero writers, zero readers.** `analyze_fragility` mints `new_id("fragility")` and never inserts it. |
| M9 | "Coverage" | One word, two unrelated concepts | `coverage_runs` (Phase 28 evidence coverage) vs `/diagnostics/coverage` (monitor run health, shown in Workbench as "Monitor coverage"). Guaranteed user and agent confusion. |
| M10 | `blind_spot_suggestions.status='approved'` | Implies approval does something | No reader. Approval is a no-op. |
| M11 | `attention.FEEDBACK` includes `mute_pattern` | Implies a pattern is muted | Sets one row to `dismissed`. No pattern is stored anywhere. Also `useful`, `already_knew`, `mute_pattern` are unreachable from the UI. |
| M12 | README §"Phase 28 adds ... explicit Coverage" | Reads as shipped capability | Shipped as an API with no producers, no UI, and unsafe semantics. |

---

# 8. COVERAGE / OBSERVATION

**Concern:** Coverage may be a manual ledger rather than intelligence.
**Verdict: AGREE — fully.**

**Evidence.** `CoverageService.create_run(expected_channels=...)` takes the entire expected denominator from the caller. `record_item(state=...)` takes each observation state from the caller. There is not one query in `coverage.py` against `acquisition_events`, `monitor_activity`, `watch_sources`, `research_question_attempts`, or `source_profiles` — those tables appear **only** in the optional `observation_refs` existence check. The sole derivation is arithmetic in `_summary_rows`.

**Defense (fairest reading).** A *bounded, explicit, human-auditable* denominator is defensible. Auto-derived coverage that silently expands its denominator is worse than a checklist, because completeness would then swing on acquisition noise. The `not_searched` / `not_found` / `not_observed` / `failed_acquisition` / `out_of_scope` state vocabulary is genuinely well-designed — it is the right *ontology*. And `COMPLETE_STATES` correctly refuses to qualify a negative while any required item is blocking.

**Weakness.** A denominator the user must construct by hand, through an API with no UI, will never be constructed. The feature is therefore either unused (dead weight) or used by an automated caller that will be as arbitrary as the current tests are (`"watch-1"`, `"rq-1"`). And an unused-but-writable ledger is *worse than absent* because Ask reads it (BROKEN-1).

**Decision: FIX as an actual projection, and shrink.**
**Timing: 29.0.** This matches `Phase 29.md` §6 "29.0A — OPERATIONALIZE COVERAGE" and §7 "COVERAGE AUTHORITY". The plan is right.

**Specific action:**
1. Derive `expected_channels` from **Watch-approved Sources + Monitor configuration** at run creation. The caller supplies the target and window, never the denominator.
2. Derive each item state from `acquisition_events` / `monitor_activity` within the window. Human override allowed only for `out_of_scope`, and recorded as a decision.
3. Validate `target_type`/`target_id` against the real table; make `target_version` the Watch scope version / Monitor revision (plan §10 says this).
4. Delete `target_type = 'ask'` — an Ask run is not a coverage target.
5. Rename the Phase 28 concept or the diagnostics one. Two "Coverages" is unacceptable (M9).

**Should Coverage be on-demand?** The *summary* should be derived on read; the **run** should stay persisted, because a coverage run is a historical observation record with a window — that is Class B/A, not a projection. `coverage_summaries` is a projection and should be rebuildable, not exported (see §17).

---

# 9. SOURCE DEPENDENCY / EVIDENCE FAMILIES

### Staleness — **AGREE** (BROKEN-2, reproduced)

Covered above. The plan's §14/§15/§16 (connected-component invalidation) is exactly the right *diagnosis*; see the revised remedy below.

### Projection invalidation is inconsistent — **AGREE, and it is broader than Families**

| Projection | Truth owner | Invalidated by | Marked dirty by | Rebuilt by | Auto? | Stale state survives? |
|---|---|---|---|---|---|---|
| `evidence_family_members` | `document_lineage` | new/changed lineage edge | **nobody** | `rebuild_evidence_families` | **No** | **Yes, indefinitely** |
| `coverage_summaries` | `coverage_items` | `record_item` | nobody | `complete()` | Only on complete | Yes (items can change pre-completion) |
| `attention_items` | alerts/coverage/corrections/blind spots | underlying resolution | **nobody** | `refresh()` (insert-only) | **No** | **Yes, indefinitely** |
| derived `story_entities` | claims/entity mentions | claim change | nobody | `knowledge.py:345,711` on write | Partly | Yes on deletion |
| automatic `tag_assignments` | classifier | classifier/model change | nobody | backfill | No | Yes |
| entity mentions/relationships | documents | reprocessing | `knowledge_backfills` | backfill | Manual | Yes |
| Search / FTS | documents | writes | SQLite triggers | triggers | **Yes** | No — **this one is done right** |
| `evidence_fragility_analyses` | n/a | n/a | n/a | n/a | n/a | Table is empty by construction |
| blind spots | coverage items | coverage completion | nobody | `generate_blind_spots` | No | Yes |
| research priority | computed on read | n/a | n/a | n/a | **Yes — computed** | No |

The pattern is clear: **the projections computed on demand (`lineage_group`, research priority) are always correct. Every projection persisted without an invalidation owner is wrong.** That is the most useful architectural lesson available from Phase 28, and it should drive the Phase 29C projection registry — the plan's §84–§89 already says this.

### Source independence is weakly modelled — **AGREE, but the honest answer is better than feared**

`DEPENDENCY_RELATIONSHIPS = {syndicated_from, wire_propagation, rewritten_from, common_primary_document}` is a *good* vocabulary — it distinguishes syndication, wire propagation, rewrites, and shared primary sourcing. What is missing:

- **Detection.** The vocabulary exists; automatic population is thin. Lineage edges come from `StoryEvolutionService.link_lineage` — largely a manual/dedupe-driven path.
- **Citation** and **organizational dependency** (same owner, same parent company, same stringer) are not modelled at all.
- Nothing distinguishes "genuinely separate observation" from "we found no edge", which is the crucial asymmetry: **absence of a lineage edge is not evidence of independence.**

**What Newsroom can honestly claim today:** *"These N documents come from N distinct Source records, and we have found no dependency edge between them."* It may **not** claim independent confirmation. `reports.py` reporting `distinct_source_count` alongside `evidence_family_count` currently invites exactly that misreading — and with stale families, it actively produces it.

**Decision: KEEP the lineage vocabulary. REMOVE `evidence_families` as a persisted table; MERGE it into on-demand `lineage_group`.** `_lineage_group_tx` already computes the identical connected component, always correctly, with no lifecycle. The families table adds a stale cache, an unstable content-addressed identity, an orphan-cleanup DELETE, and two bugs — in exchange for nothing the function does not already provide. This is the cheapest large simplification available in the codebase.
**Timing: 29.0.**

> This is a *revision* of the plan: `Phase 29.md` §14–§16 proposes to fix family invalidation. I recommend deleting the projection instead. If measurement later shows the connected-component walk is a hot path at declared workload, reintroduce it as a registered projection with a real invalidation owner — not before.

### Review authority over lineage — **PARTIALLY AGREE**

`evidence_families.authority` exists and can only ever be `'derived'` (M7). But the *underlying* `document_lineage` edges are user-correctable through the story-evolution path, which is the layer that actually matters. So the gap is in the redundant projection, not in the canonical data. Deleting the families table resolves the concern rather than requiring a manual-override service.

**One real gap remains:** if automatic dependency detection wrongly asserts `syndicated_from`, the user needs a way to dismiss that edge, and dismissal must be durable against re-detection. A small `dismissed` flag on `document_lineage` with a human decision record. **Timing: 29.0 or Phase 30.**

---

# 10. FRAGILITY / COUNTERFACTUALS

### Fragility — **AGREE, worse than the concern states**

The concern says the metric "can leave its intended range". It also **inverts** (BROKEN-3). And the table meant to hold it has never held a row (M8).

**Defense.** In the regime it was designed for — many sources, one syndication family — it behaves correctly (3 sources / 1 family → 0.67). The `fragile_claim_ids` explanation list is genuinely useful and is *correct* in every probe I ran.

**Weakness.** A single score that returns −1.0, and that rates a single-source single-document claim as minimally fragile, cannot be shown to a user in a product whose value proposition is calibrated trust. Users lose more confidence from one visibly wrong score than they gain from a hundred right ones.

**Decision: REMOVE the score. KEEP the components.** Ship what the concern proposes and what plan §17 hints at:

```
supporting spans · distinct sources · dependency groups ·
largest group's share of support · claims supported by only one group ·
primary evidence paths present? · zero-support state
```

Explainable, individually verifiable, none can be out of range, none can invert. Attention ranking can use `single_group_dependence` (a boolean) far more defensibly than a float. **Also drop `evidence_fragility_analyses`** — a table with no writer in the schema *and in the logical export* is pure misdirection.

**Timing: 29.0.** One migration and ~40 lines net *deleted*.

### Counterfactual lab — **AGREE it is too much product, DISAGREE that it is a subsystem**

It already is what the concern recommends: `counterfactual()` is a 20-line pure function over `analyze_fragility`, persists nothing, and is explicitly documented as non-mutating. `test_fragility_counterfactual_is_non_mutating_and_explains_family_dependence` verifies canonical claim state is unchanged. **This one survives the review intact.**

**Decision: KEEP, as an Advanced on-demand action** ("What if I exclude this source group?"). No table, no lifecycle, no nav item. Retarget from `family_ids` to `lineage_group` when families are deleted.

---

# 11. ATTENTION / INBOX / ALERTS

### Attention is not a true current projection — **AGREE** (BROKEN-4)

**Defense.** Durability has a real purpose: an item the user has seen should not resurface, and feedback must outlive a refresh. `INSERT OR IGNORE` on a fingerprint achieves that cheaply.

**Weakness.** It achieves it by never closing anything. The queue only grows. In a system whose pitch is "tell me what deserves attention *now*", a queue full of resolved items is product-killing — worse than no queue, because the user learns to distrust it.

**Decision: SIMPLIFY to "compute the ranking, persist only the suppression."**

```
ranking          -> computed on demand from alerts / coverage / corrections / blind spots
attention_state  -> small durable table keyed by (object_type, object_id):
                    seen_at, dismissed_at, snoozed_until, feedback
```

An item is shown iff it is a current candidate AND not suppressed. Resolution becomes automatic and free — a resolved condition simply stops being a candidate. This deletes `attention_items`, the fingerprint problem, and the convergence problem, and removes ~60 lines. The plan's §20–§22 proposes reconciliation logic instead; **the simpler shape satisfies §89 "PROJECTION CONVERGENCE" by construction rather than by test.**

**Timing: 29.0.**

Secondary defect: `InboxView` issues `POST /attention/refresh` on every page load. A read-shaped user action performing a durable write is a concurrency and idempotency hazard under SQLite's single-writer model.

### Feedback semantics — **AGREE** (BROKEN-5, M11)

**Decision: SIMPLIFY to three real actions** with labels that match behaviour:

```
Seen         -> hide until it changes materially
Snooze 7d    -> hide until a date (what users actually want)
Not useful   -> dismiss, and record the reason_code for ranking feedback
```

Delete `mute_pattern` unless a pattern is actually stored (`reason_code` + `object_type` + optional target would be a real pattern). Delete `useful` and `already_knew` — unreachable and indistinguishable in effect. Fix the "Keep open" label. Plan §25/§26 covers this correctly.

### Candidate selection bias — **PARTIALLY AGREE / mostly ALREADY FIXED**

HEAD commit `68f73ca` moved the global sort before `[:limit]` — the important half. What remains: the four pools are still pre-limited by *different* orderings (alerts by importance — fine; coverage runs and corrections by recency — not fine, since they are scored by blocking-state and a constant respectively). A 101st older coverage run with blocking states cannot reach the ranking.

**Decision: FIX, minimally.** Retrieve each pool ordered by *its own scoring key*, not recency, and keep the bounded limits. Do not propose unbounded scans. **Timing: 29.0** (plan §27 agrees).

### Attention / Inbox / Alerts overlap — **AGREE. The proposed simplification is correct; adopt it.**

Today `InboxView` renders an "Attention queue" card and a "Needs your attention" (alerts) card **stacked in the same view**, and a separate Alerts nav item shows the same alerts again. Three surfaces, one job.

**Adopt exactly:**

```
Attention  = internal ranking layer, no nav item, no user-facing name
Home       = THE user-facing surface, rendering the ranking
Alert      = high-threshold interruption + the (future) external notification carrier
```

One refinement: **Alerts should not have their own nav item either.** An alert worth interrupting for is worth being #1 on Home; one that is not is just a Home row. Keep "Alert rules" under Advanced/Settings. That removes the user's need to decide which of three inboxes to check.

---

# 12. SIMPLE / ADVANCED / NAVIGATION

### Simple/Advanced does not exist — **AGREE, plainly**

`experience.mode` and `capabilities` are referenced in the frontend in exactly one file: `AdminViews.tsx` (the SettingsView that reads and writes them). `AppShell.tsx` imports nothing from experience; `NAV_ITEMS` is a module-level constant array; `App.tsx`'s `initialView()` hardcodes all 16 view keys. **Mode changes nothing.** The settings copy promising that Advanced "reveals source robustness, hypotheses, and counterfactual review" describes views that do not exist (M5).

**Is it worth keeping?** Yes — but only if it is ~30 lines. `NAV_ITEMS` gains a `mode: "simple" | "advanced"` field; `AppShell` filters on it; `App.tsx` redirects an advanced-only deep link to Home when in simple mode with a one-line affordance. That is the entire feature. `capabilities` as a per-flag override dictionary is over-designed for a single-user local product — **collapse it to the mode alone**. Plan §28–§33 is right in intent; it should explicitly cap the implementation size.

### Too many primary navigation items — **AGREE**

Current: 16, in three groups. **Topics, Subjects, Documents, Runs & jobs** are the object model exposed directly, and **Saved** and **History** are review-state surfaces that belong on the objects they describe. `ReviewViews.tsx` "Saved" literally asks the user to paste a `st_…` Story ID into a text input. That is a database console, not a product.

**Recommended Simple-mode navigation — 5 items:**

```
Home       what deserves my attention now      (Attention ranking + alerts)
Stories    what is happening                   (Story + evidence + lineage + corrections)
Ask        what does the evidence say?
Reports    the maintained briefs
Watches    what I care about                   (sources, scope, vocabulary, coverage config)
```

**Advanced adds 4:**

```
Research     questions, gaps, hypotheses, blind spots, tasks — one workflow
Documents    raw document/version/artifact inspection
Workbench    cross-object retrieval and comparison
Diagnostics  runs, jobs, monitor health, source health, integrity
```

**Contextual panels (no nav item):** Coverage (on a Watch/Question), Evidence quality (on a Claim/Story), Entities (on a Story/Document), Tags, Saved/History (on a Story), Alert rules (in Settings), Counterfactual (an action in Evidence quality).

**Internal/admin-only:** Jobs, runs, backfills, provider telemetry, algorithm/schema metadata, integrity reports.

**Removed as nav concepts:** Topics and Subjects (see §14).

---

# 13. RESEARCH / BLIND SPOTS / HYPOTHESES

### Two competing Evidence Gap systems — **AGREE**

`hypothesis_gaps(id, hypothesis_id, description, status, ...)` and `research_question_gaps(id, question_id, gap_type, description, status, rationale, ...)`. They share a purpose and share nothing else — no FK, no promotion path, no shared status vocabulary. `ResearchPrioritizationService` reads **only** `research_question_gaps`. So hypothesis gaps are inert: they can be created and can never be worked.

**Which should own research work?** `research_question_gaps`, unambiguously. It has `gap_type` (which drives prioritization), a rationale, and a Research Task executor behind it.

**The proposed conceptual model in the brief is correct and I endorse it without modification:**

```
Research Question
    ├── current assessment
    ├── competing hypotheses      (framing — what would distinguish these?)
    ├── canonical Evidence Gaps   (the ONLY researchable unit)
    └── Research Tasks            (the ONLY executor)
```

**Decision: MERGE.** Delete `hypothesis_gaps`. A hypothesis proposes a *discriminating gap* by creating a row in `research_question_gaps` with `gap_type='discriminating'` and a `hypothesis_id` reference. One gap table, one executor, one status vocabulary. Plan §36/§37 proposes exactly this migration. **Timing: 29.0.**

### Hypotheses are scaffolding — **AGREE**

| Question | Answer |
|---|---|
| Can users use competing hypotheses? | **No.** Zero frontend. API-only. |
| Is provider generation implemented? | **No.** `origin` accepts `'provider'`; nothing generates. `provider_route` is stored, never used. |
| Is it bounded? | Yes — statement ≤10k chars, list limit ≤500. Bounding is the one thing done. |
| Does it have UI? | **No.** |
| Does it feed canonical Research? | **No.** `hypothesis_gaps` is a dead end. |
| Does it improve difficult investigations? | **Unproven — it cannot, because it is unreachable.** |

**Defense.** The *discipline* is right and rare: `hypothesis_claim_links` with `supports`/`contradicts`/`discriminates`, an append-only `hypothesis_history`, an explicit approval gate, and a module docstring stating hypotheses are "never substituted for Claims". Ask correctly classifies `user_hypothesis` separately from `fact` and surfaces "Notes remain hypotheses and never become facts" (`AskView.tsx:106`). Competing-hypothesis reasoning is genuinely what separates investigation from summarization, and it is the most intellectually valuable *unbuilt* idea in the system.

**Weakness.** None of that is reachable by a user, and half-built epistemics are worse than none: they consume schema, export surface, integrity checks, and reviewer attention while producing zero value.

**Decision: FINISH — scoped to the minimum that makes it real, gated on the merge above.**

1. Delete `hypothesis_gaps`; hypotheses create `research_question_gaps` rows.
2. One frontend panel inside Research: list hypotheses on a question, create, link a claim as supports/contradicts/discriminates, approve/reject.
3. **Deterministic** discriminating-gap suggestion: claims linked `discriminates` to one hypothesis and not another. No provider needed for v1.
4. Provider generation via the existing AIRouter — **DEFER to Phase 30**, behind Advanced.

If 1–3 cannot be funded in 29.0, then **REMOVE** the tables and re-add when the research workflow is proven. Do not ship a third phase with this unreachable.
**Timing: 29.0 for 1–3.**

### Blind Spots as a separate lifecycle — **AGREE, should be simplified**

`approve blind spot` creates nothing and links to nothing. Verified: no reader of `status='approved'` exists anywhere in `newsroom/`.

**Decision: MERGE into Research Gaps.** A blind spot is precisely "a coverage gap that suggests a research direction" — i.e. a *suggested* `research_question_gaps` row. Keep the suggestion table only as a pending inbox with `pending`/`dismissed`/`promoted`, where `promoted` **creates a real gap row and records its id**. A small FK and ~20 lines collapse a whole lifecycle. Plan §41/§42 agrees. **Timing: 29.0.**

### Research prioritization uses fake inputs — **AGREE**

`cost_budget: 1.0` is a literal constant contributing 20% of every score, and the rationale string sold to the user cites "current budget availability" (M6). `freshness` is mislabelled. A five-component average where two are fiction is not explainable prioritization — it is a number with a paragraph attached.

**Decision: FIX by deletion.** Three real components: `question_priority`, `gap_importance`, `coverage_deficiency`. If a real budget/cooldown signal exists (`provider_usage`, budget limits, task cooldowns), wire it; otherwise do not name it. Never average in a constant. **Timing: 29.0** (plan §43 agrees).

### Confirmation loop risk — **AGREE; the mitigations are planning concepts, not code**

What exists in `research_questions.py` / `intelligent_monitoring.py` is query construction from Watch vocabulary, with bounded attempts and `research_question_attempts` recording. What does **not** exist as implemented, tested strategy: alternative terminology, contradictory-proposition search, primary-source-first ordering, deliberate targeting of uncovered source classes, cross-attempt duplicate-query suppression, or a source-diversity constraint.

This is a real epistemic hazard for exactly the target user: a UAP researcher's Watch vocabulary retrieves the UAP-adjacent corpus, which confirms the UAP-adjacent vocabulary, forever. The product would be *confidently* wrong — the worst outcome for a trust product.

**Bounded fix (do not build a framework):**
1. **Duplicate-query suppression** — hash the normalized query; skip if attempted within a cooldown. Uses `research_question_attempts`, already present. ~15 lines.
2. **One disconfirming query per gap** — for a proposition, also search its negation/contradiction terms. Deterministic, no provider.
3. **Source-class diversity floor** — when a gap's supporting evidence concentrates in one `source_class`, prefer queries targeting a different class. Coverage already carries `source_class`.

Three bounded rules, ~100 lines, converting a stated principle into a tested behaviour. Plan §44/§45 proposes this. **Timing: 29.0.**

---

# 14. ENTITIES / TAGS / TOPICS / SUBJECTS

### Can a normal user distinguish Topic, Subject, Tag, and Entity? **No.**

Two of them (Topic, Subject) are *primary nav items*, forcing the user to learn the distinction before doing anything. Nothing in the UI explains it. Best reconstruction from the code: Topic ≈ configuration grouping, Subject ≈ what a Watch is about, Tag ≈ classification (manual or automatic), Entity ≈ a canonical real-world thing with aliases and relationships. Only **Entity** carries investigative weight the others cannot express.

| Concept | Classification | Rationale |
|---|---|---|
| **Entity** | **CORE**, contextual surface (no nav item) | Aliases + mentions + relationships is the real investigative primitive: "everything about this person/org across time". |
| **Tag** | **SUPPORTING**, contextual | Manual = durable user intent (Class B). Automatic = classifier output (Class C, rebuildable). |
| **Topic** | **MERGE into Watch/Tag** | Remove from nav. |
| **Subject** | **MERGE into Watch scope** | A Watch already is "what I care about". Remove from nav. |

### Entity complexity — **PARTIALLY AGREE**

Aliases, mentions, and relationships earn their place — they make "show me everything about X" possible across syndication and renaming, and `story_context.py` and `ask.py:512` genuinely consume them. Two problems:

- **Entity merge is dormant and destructive.** `entity_merges` has zero INSERT sites but is exported and integrity-checked. **Decision: HIDE.** Remove from logical export and integrity surface, leave the table, do not build the workflow until entity precision is measured. A half-visible destructive capability is the worst of both worlds. Plan does not cover this — **add it**.
- **Mention/relationship rebuild is manual** (`knowledge_backfills`), so it drifts after any model change. A projection-registry item.

### Story Entities — **PARTIALLY AGREE**

Phase 27's manual/derived authority split (`story_entities.authority`) is correct and load-bearing: `ask.py:512` and `knowledge.py:748` both query `authority = 'manual'` specifically to protect user decisions from derived churn. **That must not be removed.**

Whether *derived* rows should remain materialized is a performance question, not a correctness one. `story_context.py` and Ask both join it in hot paths. **Decision: BENCHMARK FIRST.** Do not remove on principle. If derived rows stay materialized, they must be registered projections with an invalidation owner (they currently have none — deleting a claim can strand a derived row). Plan §96 agrees.

### Smart Tags — **AGREE**

Automatic tags are classifier output — **rebuildable Class C**, not intelligence truth. Manual tags are Class B and durable. The dual structure (`story_tags` legacy + `tag_assignments` general) is real duplication: two writable authorities for the same fact.

**Decision: MERGE `story_tags` into `tag_assignments`** with `object_type='story'`, keep a compatibility view if needed, and stamp automatic assignments with the classifier version so they can be invalidated wholesale. Plan §95 agrees. **Timing: 29C.**

---

# 15. STORIES / STORY AUTOMATION

### Story granularity — **PARTIALLY AGREE**

**Defense.** Better specified than most of the system. `AutomaticStoryResolutionService` is deterministic; `evals/corpus/cases/` contains directly relevant gold cases — `ambiguous-merge-same-subject`, `ambiguous-merge-similar-date`, `similar-distinct-hermes-events`, `cross-topic-ai-energy`, `developing-story-*`, `material-update-*`. Merge/split corrections exist with preview. A real operational definition backed by evaluation.

**Weakness.** Those 30 cases are **synthetic and frozen since Phase 0**. They encode the definition the team wrote down; they do not measure whether it survives contact with a real Watch over months. And there is **no correction-rate telemetry**: the system records corrections but nothing reports "automatic assignment required correction N% of the time". Without that number, nobody can say whether manual correction burden is acceptable.

**Decision: FIX by measurement, not re-specification.** Add a correction-rate metric over `story_target_resolution_history` + `story_corrections` (a query, not a subsystem). Then run a real Watch. **Timing: 29.0 for the metric; the validation stage for the real-Watch measurement.**

### Duplicate legacy resolution paths — **PARTIALLY AGREE / INSUFFICIENT EVIDENCE for consolidation**

Two identity-resolution paths coexist: `AutomaticStoryResolutionService` (`automatic_story_resolution.py:314`) and `StoryEvolutionService` (`story_evolution.py:415`), with `StoryCorrectionService`/`StoryCorrectionReconciliationService` as the correction authority above both. Phase 27's `story_target_resolution_history` exists precisely to make correction authority win.

I did **not** find evidence that either path bypasses corrections — but I also did not prove they cannot diverge, and no adversarial test for that exists.

**Decision: DO NOT consolidate yet — ADD THE TEST FIRST.** One test that applies a correction and drives *both* paths at the same document, asserting identical resolution. If they diverge, that is a P0 and consolidation is forced. If they agree, consolidation is a Phase 30 cleanup, not a Phase 29 risk. Consolidating two live identity resolvers without that test is how you lose Story history.
**Timing: 29.0 for the test.**

---

# 16. ASK / REPORTS / WORKBENCH

### Ask quality

| Dimension | Assessment |
|---|---|
| Retrieval | SQL/FTS with a documented deterministic ranking (`exact_match_then_bm25_then_entity_type_then_entity_id`). Solid, explainable, no black box. |
| Citation grounding | **Strong.** Every statement carries citations to resolvable canonical objects. |
| Insufficient-evidence refusal | **Strong in design, currently bypassed** (BROKEN-1c). |
| Contradiction presentation | **Real advantage.** Claim states (`disputed`) and `contradicts` relationships are first-class; generic RAG has no such concept. |
| Coverage qualification | **Actively harmful today** (BROKEN-1). Correct in intent. |
| Historical questions | **Not supported.** Phase 29A's premise. |
| Story lineage questions | Partial — Story evolution exists but is weakly exposed through Ask. |
| Source-family reasoning | Present but **reading stale families** (BROKEN-2). |

**Where Ask beats generic RAG today:** it refuses; it cites resolvable canonical objects rather than text chunks; it distinguishes fact / inference / uncertainty / contradiction / user_hypothesis; it knows a claim is *disputed*; it respects manual Story-Entity decisions.

**Where it does not yet:** absence reasoning (currently negative value), temporal reasoning, independence reasoning (currently overstated).

### Is Ask the product, with everything else supporting it? — **PARTIALLY AGREE. The most useful reframe available.**

I endorse the thesis with one amendment. Newsroom is best understood as:

> **a monitoring + evidence engine whose user experience is Home (what changed), Stories (what is happening), and Ask (what does the evidence say) — with everything else contextual to those three.**

Ask alone is not enough, because Ask is *pull*. The differentiated job — "tell me what changed while I wasn't looking" — is *push*, and that is Home/Alerts. But the reframe is right about the important thing: **Coverage, Families, Fragility, Hypotheses, Gaps, and Entities should be inputs to and context within those three surfaces, never destinations.** Adopt it as the organizing principle for §20.

### Reports vs Ask — **PARTIALLY AGREE; they ARE differentiated in implementation, but not in UX**

The implementation distinction is real and strong: a Living Report has revisions, a `claim_set_hash`, a `material_change` flag, and `report_revision_causes` tying each revision to its exact cause. Ask is a stateless run. *That* is the distinction: **a Report is a durable brief that tells you why it changed; Ask is a question.**

But the UX does not communicate it. `ReportsView` presents reports as documents, not as *maintained things with a changelog*.

**Decision: KEEP both, differentiate in UX.** A Report's primary presentation should be its **diff since you last read it**, not its full text. That single change makes the role obvious and makes Reports the daily-utility surface. **Timing: Phase 30.**

### Workbench — **Advanced tool; defensible but must be demoted**

For the user mid-investigation who needs cross-object retrieval a single question cannot express. Enables pending-claim triage, monitor health, cross-type comparison — genuinely useful for the power user. Its problem is exposing the object model directly and hosting the *other* "Coverage" (M9).

**Decision: KEEP as ADVANCED.** Move "Monitor coverage" into Diagnostics and rename it "Monitor health" to kill the collision.

---

# 17. JOBS / PROJECTIONS / PERSISTENCE

### Registered Jobs are ceremonial — **AGREE, fully verified**

| Job type | Who creates it? | What obligation? | Can it fail/retry? | Necessary? |
|---|---|---|---|---|
| `coverage_refresh` | **Nobody** | None | Handler would, but never runs | Yes *if* coverage becomes derived |
| `evidence_family_rebuild` | **Nobody** | None | " | **No** if families are deleted (§9) |
| `fragility_analysis` | **Nobody** | None — result is discarded, nothing persists it | " | **No** |
| `attention_refresh` | **Nobody** (frontend calls the HTTP route synchronously) | None | " | **No** if Attention becomes on-demand (§11) |

Exhaustive grep confirms the only references outside the defining modules are `tests/test_research_question_worker.py` and `docs/ARCHITECTURE.md:728` (M3). The test that appears to guard this (`test_production_handler_coverage`) compares handlers to a hand-written literal (M4) — architecture-shaped decoration guarded by a decoration-shaped test.

**Decision: REMOVE three, WIRE one.** Keep `coverage_refresh` and give it a real producer (Watch/Monitor schedule) once Coverage is derived. Delete `evidence_family_rebuild` and `fragility_analysis` with their projections. Delete `attention_refresh` when Attention becomes on-demand. **Rewrite `test_production_handler_coverage`** to derive the producer set from actual enqueue call sites, or delete it — a test that cannot fail is worse than no test. Plan §46/§47 agrees on the decision rule. **Timing: 29.0.**

### Derived tables that look too canonical — **AGREE**

| Table | Presented as | Actually is | Action |
|---|---|---|---|
| `evidence_fragility_analyses` | canonical analysis record | **empty by construction** | **DROP** |
| `coverage_summaries` | canonical summary | Class C projection of `coverage_items` | Keep, mark rebuildable, drop from export |
| `evidence_families` / `_members` | canonical grouping with `authority` | stale Class C cache of `document_lineage` | **DROP** (§9) |
| `attention_items` | durable queue | non-converging Class C projection | **DROP**, keep suppression only (§11) |
| `blind_spot_suggestions` | independent lifecycle | suggestions for Research Gaps | Keep as suggestion inbox only (§13) |
| `hypothesis_gaps` | parallel gap authority | duplicate of `research_question_gaps` | **DROP** (§13) |
| `coverage_runs` / `coverage_items` | — | correctly Class A/B (historical observation with a window) | Keep |
| `story_corrections`, `*_history` | — | correctly Class B (human decisions) | Keep, never rebuild |

The plan's §85 three-class model (A canonical / B human intent / C derived) is exactly right. Amendment: **apply it as a deletion instrument first and a registry second.** Five tables disappear under classification; a registry is only needed for what survives.

### Logical export includes too much derived state — **AGREE**

`operations.py` `_EXPORT_COLUMNS` exports `coverage_summaries`, `evidence_families`, `evidence_family_members`, `evidence_fragility_analyses` (always empty), and `attention_items`. Exporting a projection as reconstruction truth means a restore can resurrect *stale* families and *resolved* attention items — restoring the bugs along with the data.

**Correct authority boundary:**

```
EXPORT (reconstruction truth):
  Class A  canonical evidence + reference:
           sources, documents, versions, artifacts, spans, claims, claim_evidence,
           stories, entities, document_lineage, coverage_runs, coverage_items,
           acquisition_events, monitor_activity
  Class B  human intent + audit history:
           watches/monitors config, manual tags, manual story_entities,
           story_corrections + history, research questions/gaps/tasks,
           hypotheses + history, alert rules, attention suppression/feedback,
           blind-spot review decisions, settings

DO NOT EXPORT (rebuild after restore):
  coverage_summaries, evidence family membership, fragility, attention ranking,
  derived story_entities, automatic tag_assignments, entity mentions/relationships,
  FTS indexes
```

Also remove `entity_merges` from the export until the workflow exists (§14). Plan §51 and §116 agree. **Timing: 29.0 for the trim; 29D for the rebuild-order test.**

### Backfill / job lifecycle duplication — **AGREE**

`JobService` (`jobs.py`, 1,820 lines) and `knowledge_backfills` are two orchestration mechanisms with two status vocabularies, two retry stories, and two recovery stories. **Decision: MERGE** `knowledge_backfills` into JobService as a cursor-carrying job type. Plan §90/§91 agrees. **Timing: 29C.**

---

# 18. EVALUATION

### Do evaluation claims exceed implementation? — **AGREE. Say it plainly:**

> **`docs/EVALUATION.md` claims Phase 28 scenarios "extend the existing evaluation corpus". They do not. `evals/corpus/cases/` contains 30 files, all added in commit `d7b1524` ("Phase 0: establish evaluation and replay foundation"), and has not been modified since. Phase 28 added pytest cases in `tests/test_phase28_*.py`. Those are engineering tests, not corpus cases.**

The clearest instance of a completion report overstating implementation, and it matters more than the others because it is a claim *about the mechanism that is supposed to catch overstatement*.

### Does current evaluation test plumbing more than intelligence? — **AGREE, with a caveat in its favour**

The caveat: `evals/corpus/` is genuinely a *semantic* corpus. The 30 cases target story grouping, corrections, corroboration, contradictions, rumor→confirmation, syndication, primary-vs-secondary, and stale content. That is real intelligence evaluation, and more than most projects have.

The problem is that it is 30 synthetic cases, frozen for 28 phases, while the system grew 36,000 lines.

| Capability | Covered by corpus? |
|---|---|
| Story grouping | **Yes** (ambiguous-merge, similar-distinct, cross-topic) |
| Correction handling | **Yes** (correction-earnings, correction-health-case-count) |
| Source dependency | **Partially** (duplicate-syndication, multi-outlet, primary-vs-secondary) |
| Coverage qualification | **No** |
| Contradiction detection | **Yes** (conflicting-attribution, conflicting-casualty-figures) |
| Attention quality | **No** |
| Research usefulness | **No** |
| Ask superiority | **No** |
| Historical reasoning | **No** |

**Missing temporal scenarios** — the most important gap, and the one Phase 29A's premise depends on:

1. Belief-at-T1 vs belief-at-T2 for the same underlying event.
2. A correction arriving *after* a report was issued — does the cause chain reflect it?
3. Evidence retracted by its source.
4. A document silently edited to contradict the claim it supported (`mutating-document-content` covers part).
5. **Late syndication discovery** — a source believed independent later revealed as derivative. **This is BROKEN-2's exact scenario, and the absence of this case is why the bug shipped.**
6. A rumor confirmed and then *un*-confirmed.
7. A story split months after formation, with downstream reports already issued.

**Decision: FIX.** Phase 29.0 must add corpus cases for the Phase 28/29 semantics — at minimum #5, coverage qualification, and one historical-belief case. And `docs/EVALUATION.md` must be corrected. Plan §48/§49/§50 agrees. **Timing: 29.0.**

### Test count vs product proof — **AGREE**

779 passing tests, all green, is genuine engineering strength — and it is disguising weak product validation.

```
unit correctness              STRONG   (~779 tests, deterministic, fast)
integration correctness       STRONG   (API + worker + migration coverage)
temporal intelligence         WEAK     (no corpus case exercises knowledge-time)
user outcome quality          ABSENT   (zero real-Watch data, zero dogfood)
```

Tests can also *entrench* defects: `test_complete_expected_window_qualifies_negative_absence` asserts the unsafe qualified-negative behaviour, and `test_production_handler_coverage` locks in four producerless jobs. **When fixing the P0s, the tests must be corrected, not merely extended.**

**Recommended balance before release:** do not add unit tests. Add ~10 corpus cases, one real-Watch dogfood, and one Full-vs-Lite comparison. The marginal value of test #780 is near zero; the marginal value of the first real Watch is enormous.

---

# 19. FULL NEWSROOM VS LITE

Baseline **Newsroom Lite**: sources/RSS → normalized Documents → good full-text search → basic clustering → strong LLM synthesis → citations.

| Subsystem | Beats Lite? | Verdict |
|---|---|---|
| **Sources / acquisition** | No | Table stakes. |
| **Documents / Versions / Artifacts** | **Yes** | Lite re-fetches and loses history. Version + content hash detects silent edits — structurally beyond Lite. **EARNED.** |
| **EvidenceSpans / Claims** | **Yes** | Lite cites a document; Newsroom cites a *span* grounding a *proposition* with a state. This is what makes refusal and contradiction possible. **EARNED.** |
| **Stories + corrections** | **Yes, strongest** | Lite re-clusters every run and forgets your corrections. **EARNED.** |
| **Reports (living, caused)** | **Yes** | Lite re-summarizes; it cannot say *what changed and why*. **EARNED.** |
| **Alerts (exact-cause)** | **Yes** | Lite alerts on keywords/volume. **EARNED**, but utility unmeasured. |
| **Ask** | **Marginally** | Refusal + typed statements + disputed-claim awareness beat generic RAG. **PARTIALLY EARNED.** |
| **Entities** | Probably | Longitudinal alias resolution is beyond Lite, but **unproven** in outcome terms. |
| **Monitors / intelligent monitoring** | **Yes** | Persistent monitoring memory with meaningful-change detection. **EARNED.** |
| **Research Questions / Gaps / Tasks** | Plausibly | Structurally beyond Lite. **UNPROVEN.** |
| **Coverage** | Not yet | Currently negative value (BROKEN-1). **UNEARNED.** |
| **Evidence Families** | No | `lineage_group` already does it better. **UNEARNED.** |
| **Fragility** | No | Broken metric. **UNEARNED.** |
| **Attention** | Not yet | Non-converging. Concept is right. **UNEARNED as built.** |
| **Hypotheses** | Unknown | Unreachable. **UNEARNED.** |
| **Blind spots** | No | No-op. **UNEARNED.** |
| **Workbench** | Marginally | Advanced convenience. |
| **Jobs / provenance** | N/A | Infrastructure — necessary, not differentiating. |

**Summary:** the Phase 22–27 core has clearly earned its complexity. **Essentially the entire Phase 28 layer has not.** That is the review's central quantitative finding.

**Tests that should happen before further expansion:**
1. One real Watch on a genuinely contested domain, ≥4 weeks.
2. Same corpus, same 20 questions: Full Ask vs Lite (FTS + LLM + citations). Score grounding, refusal correctness, hallucination rate.
3. Correction burden: what fraction of automatic Story assignments needed correction?
4. Alert utility: of N alerts emitted, how many did the user act on?

None require Phase 29's provenance architecture. All are blocked on nothing.

---

# 20. PRODUCT SURFACE REDUCTION PROPOSAL

**Verdict on the compressed mental model in §8 of the brief: DEFEND IT. It is correct.** "Complex engine, small cockpit" is exactly right for this product, and it maps cleanly onto what is actually strong.

```
WATCH      what I care about              first-class, user-created
STORY      what is happening              first-class, correctable
ASK        what does the evidence say     first-class, stateless
REPORT     what materially changed        first-class, durable, diff-first
ALERT      what interrupts me             a Home row + optional external push
RESEARCH   what remains unresolved        first-class in ADVANCED only
EVIDENCE   why should I trust this        CONTEXTUAL — always attached, never a destination
```

Everything else is machinery:

- **Contextual detail only:** Coverage, Evidence quality (dependency groups + components), Entities, Tags, Claims, Spans, Documents, Saved/History, Counterfactual.
- **Internal supporting machinery:** Monitors, Jobs, Runs, Backfills, ContentArtifacts, DocumentVersions, processing provenance, projections.
- **Advanced-only:** Research (questions + gaps + hypotheses + blind spots + tasks), Workbench, Documents inspector, Diagnostics.
- **Merged away:** Topics → Watch/Tag; Subjects → Watch scope; Evidence Families → lineage groups; Hypothesis Gaps → Research Gaps; Blind Spots → Research Gap suggestions; Attention → Home; Alerts nav → Home + Settings.
- **Removed:** Fragility score, `evidence_fragility_analyses`, `attention_items`, three ceremonial jobs.

**The brief's four candidate compressions:**

- **Evidence Quality** (combine Coverage + dependency + Families + Fragility into one contextual surface) — **DEFEND, adopt.** With Families deleted and Fragility reduced to components, this becomes a single panel: *"3 supporting spans · 2 dependency groups · 1 group carries 67% · no primary source yet · coverage of this Watch's official channel is incomplete."* One panel, plain language, no scores.
- **Research** (one investigative workflow) — **DEFEND, adopt.** With `hypothesis_gaps` deleted and blind spots demoted to suggestions, this is genuinely one workflow.
- **Attention** (ranking engine / Home surface / Alert interruption) — **DEFEND, adopt**, with the amendment that Alerts should also lose their nav item.
- **Evidence contextual to Stories/Ask/Research unless Advanced** — **DEFEND, adopt.**

Net: 16 nav items → **5 (Simple) / 9 (Advanced)**.

---

# 21. COMMERCIAL PRODUCT ASSESSMENT

### The positioning sentence, derived from the implementation

> **Newsroom is for the independent researcher tracking one contested subject over months, who needs to know what actually changed and whether to believe it — and unlike an RSS reader with an LLM on top, it remembers every source, correction, and decision, and tells you when its own earlier answer turned out to be wrong.**

The last clause is the only genuinely defensible one, and it is the one the architecture actually delivers. That the sentence resolves cleanly is a good sign: the architecture *does* have a coherent product thesis. The problem is that the UI does not express it.

### Time to first value — **the most serious commercial problem after the P0s**

The actual setup path: install Python + Node → run migrations → start the API → start a worker → create an account → create a Source → create a Watch → configure scope/vocabulary → wait for acquisition → wait for analysis → wait for claim promotion → wait for a Story → wait for a Report revision.

**Estimated time to a useful Watch: hours. To a meaningful Story: days. To a useful Report: days-to-weeks. To a trustworthy Ask result: days**, because Ask is grounded in Claims, and Claims require the full pipeline to have run and (for anything non-deterministic) a provider.

**Nothing shortens this.** No seed Sources, no starter Watch templates, no sample dataset, no import path.

**Fixable and cheap:** ship 20–50 curated seed Sources by domain, 3–5 Watch templates, and — most valuable — **backfill-on-create** that acquires the last 30–90 days when a Watch is created, so the first Story appears in minutes rather than days. That single change probably matters more commercially than all of Phase 29A.

### Empty state / onboarding — **AGREE, none exists**

Frontend empty states are informational, not directive: *"No monitors yet — Create a Monitor to make coverage and health visible here."* That tells the user what is missing, not what to do. Nothing takes "I want to monitor UAP disclosure" and produces active monitoring. `ReviewViews` requiring a pasted `st_…` ID is the low point.

**Missing:** a first-run wizard (subject → suggested sources → suggested vocabulary → confirm → backfill), per-surface "what this is for" copy, and a visible pipeline-progress indicator so the wait is legible instead of feeling broken.

### Daily utility

Currently **weak**, because Home is three competing cards, one of which never converges. After the §11/§12 fixes plus diff-first Reports: **strong** — "what changed since yesterday, ranked, with why" is a genuinely good daily surface.

### Local-first operational burden — **AGREE it will severely limit adoption**

A buyer who is a *researcher*, not an engineer, currently needs: Python 3.11+, Node, migrations, a uvicorn process, a separate worker process, SQLite care, provider credentials, backup discipline, and (for remote access) Tailscale Serve. The Windows deploy script and Task Scheduler registration (`scripts/phase16_windows_deploy.ps1`) help, but the mental model is still "I am running a server".

**How much should disappear behind packaging in Phase 30:** effectively all of it. One installer, one process (worker in-process or auto-supervised), a tray icon or desktop shortcut, automatic scheduled backup, zero-credential first run. The local-first choice is *correct* — a privacy and cost advantage for exactly this user — but it must be invisible.

### Provider configuration and cost — **PARTIALLY AGREE; better than feared**

Genuinely good architecture: AIRouter with local deterministic fallback means the product **works with no credentials at all**, budgets are enforced server-side, and `provider_usage` records actual cost. More honest than most commercial products.

What the user cannot currently see: *what costs money*, *when AI is used*, and *what they lose without a provider*. `SettingsView` renders budget limits as `<code>{JSON.stringify(budget)}</code>` — a developer surface.

**Decision:** one plain-language panel — "Newsroom works fully offline. Adding a provider key improves X, Y, Z. You have spent $N this month; your cap is $M." **Timing: Phase 30.**

### Notifications — **VALUABLE, trending toward ESSENTIAL**

In-app-only is defensible for a local-first tool and correctly scoped for now. But the core job is *"tell me what changed while I wasn't looking"* — a monitoring product whose notifications exist only inside the app the user isn't looking at has an unresolved tension at the centre of its value proposition. For the target user (checks in weekly, not hourly), a weekly email digest is probably the single highest-leverage delivery feature.

```
email digest       VALUABLE (approaching essential)  <- highest leverage
push / PWA         VALUABLE (browser push partly exists)
Slack / webhook    OPTIONAL (only if a team buyer emerges)
mobile native      UNNECESSARY
```

Do not build now. Do not let the architecture preclude it: keep `alert_deliveries` channel-generic (it already is).

### Acquisition breadth — **DEFEND the current strategy, with one addition**

The concern is real: sophisticated downstream reasoning is worthless if Newsroom misses the material. But "approved Sources + bounded discovery + no arbitrary crawler" is the **right** default — an arbitrary crawler would flood the evidence ledger with low-quality material, and the entire trust model depends on knowing where things came from. The bounded `watch_source_discovery` job is the correct escape valve.

**The addition that matters:** the target user's most important material is often **primary and non-syndicated** — regulatory dockets, FOIA releases, court filings, agency archives, PDFs. Coverage's vocabulary (`official_archive`, `regulatory`, `primary`) shows the team knows this. Breadth of *source class* matters more here than breadth of *crawl*. Prioritize primary-source connectors over crawler breadth.

### Commercial moat

| Capability | Moat or table stakes? |
|---|---|
| **Correctable Story identity + correction history** | **MOAT.** Hard to retrofit; requires the whole ledger beneath it. |
| **Historical evidence provenance** | **MOAT**, once real. |
| **Persistent monitoring memory** | **MOAT.** Stateless competitors structurally cannot. |
| **Exact-cause Report/Alert causality** | **MOAT.** |
| **Knowledge-time reconstruction** | **Potential moat — unproven demand.** |
| **Evidence-grounded Ask** | **Table stakes by 2027.** Everyone will cite. |
| **Longitudinal Research** | **Potential moat — unproven.** |
| **Source dependency** | **Table stakes if shallow; moat if deep.** Currently shallow. |
| Local-first / privacy | **Positioning advantage**, not a moat. |
| Code volume | **Not a moat.** 36k lines is a liability until proven otherwise. |

### Top-selling product standard — ranked gaps

1. **Trust** — never says something it cannot support. *(Currently violated: BROKEN-1.)*
2. **Time-to-value** — useful within minutes. *(Currently days.)*
3. **Signal-to-noise** — Home is short, right, converges. *(Currently violated: BROKEN-4.)*
4. **Daily utility** — a reason to open it daily. *(Weak; diff-first Reports fix most of it.)*
5. **Ease of use** — 5 surfaces, not 16. *(Currently violated.)*
6. **Onboarding** — subject → active monitoring, no DB knowledge. *(Absent.)*
7. **Packaging** — one installer, no terminal. *(Absent.)*
8. **Differentiation** — demonstrably better than Lite. *(Unproven.)*
9. **Notifications** — reaches the user outside the app. *(Absent by design.)*
10. **Data acquisition** — primary-source breadth. *(Adequate, improvable.)*
11. **Reliability** — recovery, backup, integrity. *(Good foundation.)*
12. **Cost** — predictable, comprehensible. *(Good architecture, bad surface.)*
13. **Performance** — undeclared but no evidence of a problem.

**1, 3, and 5 are all Phase 29.0 items. 2, 4, 6, 7 are Phase 30 items that nobody has scoped.**

---

# 22. PHASE 29 FEATURE CHALLENGE

| Proposed capability | Verdict | Justification |
|---|---|---|
| **29.0 closure (all of it)** | **KEEP — the whole phase's justification** | Independently confirms nearly every P0 in this review. It is a hard gate; treat it as one. |
| **ProcessingRun** | **KEEP, SIMPLIFIED** | The real need is narrow: distinguish "new evidence changed belief" from "the model changed belief". Implement as `(algorithm_version, prompt_version, model, input_content_hash)` stamped on derived outputs plus a `change_cause` enum. `article_analyses` **already carries most of these columns** (`schema_version`, `prompt_version`, `provider`, `model`, `input_content_hash`, `analyzed_content_hash`, `invocation_id`). Largely generalizing an existing pattern, not a new subsystem. |
| **Knowledge-time semantics** | **SIMPLIFY** | Four time axes is the correct *ontology*, but full bitemporality across all derived state is enormous. Implement knowledge-time only where a durable history already exists: claims, claim states, story assignments, corrections, report revisions. Those already have append-only history — knowledge-time is largely a *query* over them. |
| **Historical Ask** | **KEEP, scoped narrowly** | Genuinely differentiating for the longitudinal researcher, and the natural read model over the above. Scope to Claims/Stories/Reports; do not attempt as-of reconstruction of every projection. Plan §69's "HISTORICAL ASK LIMITATION" suggests the author already knows this. |
| **Shadow Reprocessing** | **DEFER to Phase 31+** | The most expensive stage with the least demonstrated need. It solves "reprocess without contaminating current state" — a problem that matters at scale, after the intelligence is proven. Newsroom currently has **zero real-Watch data to reprocess**. Building a shadow lane before there is a subject worth shadowing is exactly the inversion this review exists to catch. |
| **Belief Diff** | **DEFER with Shadow** | A cheap subset is worth keeping *inside* 29A: when a claim's state changes, record whether the cause was new evidence or reprocessing. One enum column, ~80% of the user value for ~2% of the cost. |
| **Projection registry** | **KEEP, SIMPLIFIED** | The three-class model is the most valuable idea in the plan. Apply it as a **deletion instrument first**: five tables disappear under classification. Register what survives (coverage summaries, derived story entities, automatic tags, entity mentions, FTS) with an explicit invalidation owner. Do not build a generic framework. |
| **Job / backfill consolidation** | **KEEP** | Two orchestration mechanisms is a real failure-mode multiplier. Straightforward, high value. |
| **Retention / deletion architecture** | **SIMPLIFY** | Real need — `content_artifacts.retention_eligible` already anticipates it, and indefinite retention of raw content and provider outputs is a storage, privacy, and legal exposure. v1 is: a retention setting per class, a purge job, correct handling of inbound references (never orphan a span). Not an architecture. |
| **Logical reconstruction** | **KEEP** | The actual disaster-recovery story. Must be proven by an executed test, not documented. Depends on the export authority trim (§17). |
| **Failure injection** | **KEEP, minimal** | 3–5 targeted scenarios (SQLite busy, provider failure mid-job, worker kill mid-transaction, migration interrupted). Not a chaos framework. |
| **Workload SLOs** | **KEEP** | Cheap and clarifying — see §34. |

---

# 23. PHASE 29 CHANGES REQUIRED

Recommended edits to `plan/phases-v2/Phase 29.md`. **Not applied** — this review does not modify the plan.

1. **§13 (Qualified Negative Ask Language) — expand to cover the scope leak.** Add: *"`AskService._coverage_context` must never return coverage runs whose target is not in the question's scope. Global-scope Ask must not attach coverage runs at all. A coverage statement must never be the only statement in a run that would otherwise refuse with `insufficient_evidence`."* The worst live defect, and the plan currently addresses only the wording, not the retrieval.

2. **§14–§16 (Evidence Family Invalidation) — change the remedy from "invalidate" to "delete the projection".** `_lineage_group_tx` already computes the identical connected component on demand and is always correct. Replace family membership with lineage groups everywhere (`reports.py:380`, `evidence_summary`, counterfactual). Reintroduce a cached projection only if measurement at declared workload demands it.

3. **§17/§18 (Fragility) — commit to removal of the score, not a redesign option.** The plan leaves "keep score" open. Probe evidence (−1.0; single-source claim scored least fragile while simultaneously listed as fragile) closes the question. Ship the components; drop `evidence_fragility_analyses`.

4. **§20–§22 (Attention) — replace "reconciliation" with "compute on demand, persist suppression only".** Satisfies §89's convergence requirement by construction rather than by test, and deletes a table.

5. **NEW §29.0N — Minimum development tooling.** The plan has **zero** mentions of lint, format, or CI. Add: `ruff` (format + lint, default config), `mypy` on `newsroom/` only (non-blocking initially), the existing `tsc --noEmit`, ESLint for the frontend, and one GitHub Actions workflow running `ruff check && pytest && npm run typecheck`. There is currently no `.github/` directory and no lint or format script anywhere. Four config files, one workflow. Nothing more.

6. **NEW §29.0O — Correction and utility telemetry.** Before increasing automation, Newsroom must answer: story-correction rate, entity-decision correction rate, dependency-family correction rate, research-task yield, alert action rate, attention dismissal rate by `reason_code`. All are queries over existing tables. Prerequisite for §69's progressive autonomy.

7. **NEW §29.0P — Entity merge and export hygiene.** `entity_merges` has zero writers; remove it from `_EXPORT_COLUMNS` and from integrity surfacing, and note that the merge workflow is deferred. Do not leave a half-visible destructive capability.

8. **NEW §29.0Q — Naming collision.** Rename either the Phase 28 evidence Coverage or the `/diagnostics/coverage` monitor coverage. Suggested: monitor coverage → **"Monitor health"**.

9. **§48/§49 (Evaluation) — make corpus extension a numeric acceptance criterion.** "Phase 29 adds ≥10 corpus cases, including ≥1 late-syndication-discovery case, ≥1 coverage-qualification case, and ≥3 knowledge-time cases." And correct the false claim in `docs/EVALUATION.md` explicitly.

10. **§71–§83 (Phase 29B Shadow / Belief Diff) — MOVE OUT of Phase 29.** Retain only the `change_cause` enum inside 29A.

11. **§127 (Out of Scope) — MOVE Full-vs-Lite validation INTO Phase 29.** See §24. The most important structural edit.

12. **Restructure the phase.** As written, Phase 29 is five stages and 4,443 lines. With 29B deferred, split the remainder:

```
PHASE 29  = 29.0 (closure) + 29V (intelligence validation)   <- ship this
PHASE 29B = 29A (provenance) + 29C (projection registry) + 29D (hardening)
PHASE 30  = release: packaging, onboarding, UX compression, tuning, dogfood
```

29.0 alone is a full phase of real work. Landing it alongside provenance, shadow reprocessing, a projection registry, and production hardening is how 29.0's fixes end up as thin as Phase 28's features were.

---

# 24. PHASE 30 BOUNDARY

**The proposed boundary is right in principle and wrong in placement.**

> *"Phase 29 = prove the intelligence. Phase 30 = ship the product."*

**DEFEND this framing.** But `Phase 29.md` §127 explicitly defers **Full Newsroom vs Newsroom Lite**, **multi-week dogfood**, and **Simple vs Advanced product outcome comparison** to Phase 30. Those *are* proving the intelligence. As written, Phase 29 proves *reliability* — beliefs are reconstructable, projections rebuild, the system recovers — while leaving *usefulness* entirely to Phase 30.

**Should intelligence validation move into Phase 29? YES. Strongly agree with the concern.**

Discovering in Phase 30 that Full Newsroom does not beat Lite would invalidate an enormous amount of Phase 29 work — you would have built knowledge-time reconstruction for beliefs nobody wants reconstructed. And the validations are cheap and blocked on nothing: a real Watch, 20 questions, two systems, a scorecard. They need neither ProcessingRun, nor Shadow Reprocessing, nor a projection registry.

**Phase 30 should not be an existential test. Agree — adopt this boundary. Must be proven before Phase 30 starts:**

1. Newsroom never asserts a search it did not perform *(BROKEN-1 fixed and corpus-tested)*.
2. Derived projections converge *(BROKEN-2/-4 fixed; no stale state survives a rebuild)*.
3. No shown score or label contradicts its own explanation *(BROKEN-3 fixed)*.
4. Attention/Home is short, correct, and self-resolving.
5. Simple mode is a real product surface with ≤5–6 items.
6. One coherent Research workflow; no parallel gap lifecycle.
7. **Full beats Lite on a measured comparison** — or the delta is understood and the roadmap corrected.
8. **≥4 weeks of real-Watch dogfood** with correction-burden and alert-utility numbers.
9. Corpus extended with temporal/coverage/dependency cases.
10. Backup and logical restore executed end-to-end at least once.

Then Phase 30 is genuinely: release candidate, UX compression, onboarding, packaging, ranking/alert tuning, bug fixing, release validation — *not* "is this useful?"

---

# 25. P0 FINDINGS — must fix before Phase 29 core work

| # | Finding | Why P0 |
|---|---|---|
| **P0-1** | **Ask asserts "the expected channels were searched" from a hand-asserted `not_found` with zero observation refs — for a target that need not exist, on a global question it does not scope-match, and it suppresses the `insufficient_evidence` refusal.** (BROKEN-1a/b/c) | Materially false intelligence, in natural language, in the product's most trusted surface. One occurrence destroys the trust proposition. |
| **P0-2** | **Evidence Families never invalidate; stale membership overstates source independence in `evidence_summary`, fragility, and Reports — and contradicts `lineage_group_count` in the same response.** (BROKEN-2) | Overstated independent corroboration is the most dangerous possible error for an evidence product. Reproduced. |
| **P0-3** | **Fragility returns values outside [0,1] and rates a single-source single-document claim as least fragile while listing it as fragile.** (BROKEN-3) | A displayed trust score that contradicts itself. Will contaminate any Attention ranking or evaluation built on it. |
| **P0-4** | **Attention never converges — resolved conditions stay `open` forever.** (BROKEN-4) | The "what needs attention now" surface lies by construction. Contaminates any attention-quality evaluation. |
| **P0-5** | **Coverage accepts nonexistent targets and arbitrary `target_version`, and that invalid coverage flows into Ask, Attention, Blind Spots, and Research prioritization.** (BROKEN-6) | Unvalidated identity propagating into user-facing conclusions. |
| **P0-6** | **Tests entrench the defects:** `test_complete_expected_window_qualifies_negative_absence` asserts unsafe qualified-negative behaviour; `test_production_handler_coverage` locks in four producerless jobs behind a hand-written literal. | Fixing P0-1/P0-5 requires changing green tests. If not called out, a future agent will "preserve" the bugs to keep the suite green. |

---

# 26. P1 FINDINGS — must fix before Phase 30

| # | Finding | Why P1 |
|---|---|---|
| **P1-1** | Full-vs-Lite validation and real-Watch dogfood deferred to Phase 30. | Makes Phase 30 an existential test. Move into Phase 29. |
| **P1-2** | Coverage is a manual ledger with no derivation from `acquisition_events`/`monitor_activity` and no UI. | Either becomes a real projection or it is dead weight that Ask reads. |
| **P1-3** | Simple/Advanced does not exist; UI copy promises views that do not exist. | Blocks the surface reduction the product needs, and is a live false statement to the user. |
| **P1-4** | 16 primary nav items exposing the object model; Attention/Alerts/Inbox overlap. | Primary usability barrier for the target user. |
| **P1-5** | Two parallel Evidence Gap systems (`hypothesis_gaps` vs `research_question_gaps`). | Duplicate major architecture; guarantees divergence. |
| **P1-6** | Hypotheses, blind-spot approval, and Entity merge are unreachable or no-ops. | Broken workflows; half-built epistemics are worse than absent. |
| **P1-7** | Four registered Jobs with zero producers; `evidence_fragility_analyses` has zero writers. | Architecture-shaped decoration, documented as working (M3). |
| **P1-8** | Logical export includes derived state as reconstruction truth. | A restore would resurrect stale families and resolved attention items. Prevents a trustworthy recovery story. |
| **P1-9** | `docs/EVALUATION.md` claims a corpus extension that git disproves. | Undermines the mechanism meant to catch overstatement. |
| **P1-10** | Research prioritization averages in a hardcoded `cost_budget: 1.0` and calls it "current budget availability". | Fake input in a user-facing explanation. |
| **P1-11** | No correction-burden or alert-utility telemetry. | Cannot justify increasing automation. Prerequisite for progressive autonomy. |
| **P1-12** | Research confirmation-loop mitigations are planning concepts, not code. | Systematic epistemic bias for exactly the target user. |
| **P1-13** | Time-to-first-value is days; no onboarding, no seed sources, no backfill-on-create. | Probably the largest commercial barrier after trust. |
| **P1-14** | No adversarial test that the two Story identity-resolution paths cannot diverge. | Unbounded risk to the system's single strongest capability. |
| **P1-15** | "Keep open" removes the item; 3 of 5 feedback values unreachable; `mute_pattern` mutes nothing. | Directly teaches the user the UI is untrustworthy. |

---

# 27. P2 FINDINGS — should improve before release

1. No lint, no format, no CI, no `.github/` — 36k lines with `pytest` as the only gate.
2. Topic/Subject/Tag/Entity — four taxonomies, no user-facing distinction.
3. Two unrelated concepts named "Coverage" (M9).
4. `story_tags` and `tag_assignments` are dual tag authorities.
5. `evidence_families.authority` can never be `'manual'` (M7).
6. Reports presented as documents rather than diffs — the main daily-utility miss.
7. `InboxView` performs a durable write (`POST /attention/refresh`) on page load.
8. No declared workload envelope anywhere in the repo or docs.
9. No retention policy for raw content, provider outputs, Ask history, Jobs, or Coverage.
10. `knowledge_backfills` duplicates JobService orchestration.
11. `SettingsView` renders budgets as raw `JSON.stringify` output.
12. "Saved" requires pasting a `st_…` ID.
13. `source_summary` latent crash path (BROKEN-7).
14. `CoverageService.list_runs` is N+1 (`get_run` per row), bounded at 200.
15. Planning documents are uncommitted; a build zip and `.kilo/` are untracked in the working tree.
16. `evidence_families.family_key` is content-addressed, so family identity is unstable across membership changes.

---

# 28. P3 FINDINGS — optional / future

1. External notifications (email digest highest leverage) — do not build now; do not preclude.
2. Vector search — **explicitly defend staying simple.** SQL/FTS with a documented deterministic ranking is *more* explainable, has zero infrastructure, and no benchmark in this repo shows retrieval as the bottleneck. Ask's weaknesses are absence reasoning, temporal reasoning, and independence — **none of which vectors fix.** Revisit only if a measured recall failure on real-Watch data traces to lexical mismatch.
3. **SQLite remains correct.** Single user, single machine, local-first, sub-million rows, one writer. Revisit only on measured evidence: sustained write contention with `busy_timeout` exhaustion, a working set exceeding RAM with poor locality, or genuine multi-user concurrency. None are near. Do not switch to PostgreSQL reflexively.
4. Provider generation for hypotheses.
5. Entity merge workflow (after precision is measured).
6. Multi-user / team features.
7. Migration consolidation — 132 tables across 32 migrations is large but the history is sound. Do not rewrite history; drop the dead tables identified here and stop adding projection tables without invalidation owners.

---

# 29. FEATURES TO KEEP

```
Evidence ledger (Document / DocumentVersion / ContentArtifact / EvidenceSpan / Claim)
Story + StoryEvolution + Story corrections + correction history
report_revision_causes (exact-cause causality)
Living Reports with revisions and material_change
Alerts on material causes
Ask with insufficient_evidence refusal and typed statements
Entities with aliases / mentions / relationships
Manual StoryEntity authority ('manual' vs 'derived')  <- load-bearing, do not remove
document_lineage + the connected-component lineage_group computation
Monitors / intelligent monitoring / meaningful-change detection
JobService
AIRouter with local deterministic fallback
SQLite + SQL/FTS
integrity.py
The evals corpus + replay framework (extend it, do not replace it)
Counterfactual as a non-mutating on-demand function
Coverage's state vocabulary (observed / not_found / not_observed / not_searched /
                             failed_acquisition / out_of_scope / stale)
779 passing tests
```

---

# 30. FEATURES TO MERGE

| From | Into | Note |
|---|---|---|
| `hypothesis_gaps` | `research_question_gaps` (`gap_type='discriminating'`) | One gap authority, one executor |
| `blind_spot_suggestions` (as lifecycle) | Research Gap *suggestions*; `promoted` creates a real gap | Keep the suggestion inbox only |
| Evidence Families | on-demand `lineage_group` | Deletes 2 tables and 2 bugs |
| Attention as durable queue | Home surface + small suppression table | Convergence by construction |
| Alerts nav item | Home (+ Alert rules in Settings) | Three inboxes → one |
| Topics | Watch / Tag | Remove from nav |
| Subjects | Watch scope | Remove from nav |
| `story_tags` | `tag_assignments` | Single tag authority |
| `knowledge_backfills` | JobService | Single orchestration |
| Coverage + dependency + fragility components | one "Evidence quality" contextual panel | Four areas → one panel |
| Saved / History | contextual on Story | Remove from nav |
| Workbench "Monitor coverage" | Diagnostics, renamed "Monitor health" | Kills the naming collision |

---

# 31. FEATURES TO MAKE DERIVED / ON-DEMAND

```
Evidence family grouping        -> lineage_group (already on-demand and correct)
Attention ranking               -> computed; persist suppression only
Coverage summary                -> computed on read from coverage_items
Fragility components            -> computed on read; no persistence
Counterfactual                  -> already on-demand; keep
Research priority               -> already on-demand; keep (remove fake components)
Derived StoryEntity             -> benchmark before deciding; register if kept
Automatic tag assignments       -> classifier-versioned, rebuildable
Entity mentions / relationships -> registered projection with an invalidation owner
```

---

# 32. FEATURES TO HIDE IN ADVANCED MODE

```
Research (questions, gaps, hypotheses, blind spots, tasks)
Workbench
Documents / versions / artifacts inspector
Diagnostics (runs, jobs, monitor health, source health, integrity)
Counterfactual analysis
Evidence quality detail (summary line stays visible in Simple)
Alert rule configuration
Budgets / provider telemetry / cost detail
Export / backup operations
Entity merge (if ever built)
```

---

# 33. FEATURES TO REMOVE OR SERIOUSLY CONSIDER REMOVING

**Remove now (verified: no readers, no writers, or actively wrong):**

```
evidence_fragility_analyses table            zero writers, zero readers, in export
the single fragility score                   out of range; contradicts its own explanation
evidence_families + evidence_family_members  stale cache of lineage_group
attention_items table                        non-converging; replace with suppression
hypothesis_gaps table                        duplicate gap authority
Job types: evidence_family_rebuild, fragility_analysis, attention_refresh   no producers
attention feedback values: useful, already_knew, mute_pattern   unreachable / not real
coverage target_type 'ask'                   an Ask run is not a coverage target
entity_merges from logical export + integrity surface   dormant, destructive
experience 'capabilities' override dict      over-designed; keep mode only
Topics and Subjects as primary nav items
Saved and History as primary nav items
```

**Seriously consider removing:**

```
Coverage entirely  -- if 29.0A cannot make it genuinely derived from observation facts,
                      delete it rather than ship a hand-maintained ledger that Ask reads.
                      A checklist nobody fills in is not a feature; it is a liability.
Hypotheses         -- if the merge + one UI panel + deterministic suggestion cannot land
                      in 29.0, delete the tables and revisit when Research is proven.
Workbench          -- if dogfood shows it is unused, it is 958 lines of Advanced surface.
```

---

# 34. MISSING CAPABILITIES

1. **Onboarding / first-run wizard.** Subject → suggested sources → suggested vocabulary → confirm → backfill. Not in Phase 29; not scoped in Phase 30.
2. **Backfill-on-Watch-creation.** Acquire the last 30–90 days at creation. Probably the single highest-leverage change for time-to-value in the entire backlog.
3. **Seed source catalog + Watch templates.** By domain. Cheap, high impact.
4. **Diff-first Reports.** "What changed since you last read this" as the primary presentation.
5. **Correction/utility telemetry.** Prerequisite for any autonomy increase.
6. **Packaging.** One installer, one process, no terminal, automatic backup.
7. **Cost transparency in plain language.**
8. **Dependency-edge dismissal.** Correct a wrong `syndicated_from`, durably.
9. **Primary-source connectors** (dockets, FOIA, court filings, agency archives, PDFs) — matters more than crawler breadth for this user.
10. **Retention policy + purge.**
11. **Declared workload envelope.** Concretely proposed, to be validated in 29D:

```
Sources          100 – 500
Documents        100k – 500k
DocumentVersions 300k – 1.5M
Claims           50k – 200k
Stories          1k – 10k
Entities         10k – 50k
Jobs/day         1k – 10k
Database size    5 – 50 GB
Concurrent users 1 (occasionally 2 devices)
```

With SLOs: Ask p95 < 5s; Home load < 1s; Story view < 1s; acquisition→Story < 15 min; full projection rebuild < 30 min. Declaring these makes "is SQLite still right?" answerable instead of rhetorical.

12. **Minimum tooling/CI** (§23 item 5).

---

# 35. ADDITIONAL FINDINGS NOT RAISED IN THIS PROMPT

**A35-1 — Ask's coverage injection can *replace* a refusal.** Not merely additive: in my probe the coverage statement was the *only* statement, turning what should have been `insufficient_evidence` into `status: qualified`. Any derived-context injection into Ask must be forbidden from satisfying the evidence-sufficiency threshold on its own. Generalize this rule beyond Coverage — it will recur with every future context source.

**A35-2 — `evidence_summary` returns two contradictory independence measures in one object.** `lineage_group_count: 1` and `evidence_family_count: 2` simultaneously (Probe C). Any two fields answering the same question must be computed from one source. This is the specific mechanism by which the staleness bug becomes visible to users.

**A35-3 — The fragility score contradicts its own explanation in the same object.** Probe B: `fragility_score: 0.0` alongside `fragile_claim_ids: [that same claim]`. Worse than either being wrong alone: it proves the score and the explanation were derived independently and neither was validated against the other.

**A35-4 — `family_key` content-addressing makes family identity unstable.** Membership change ⇒ new key ⇒ new row ⇒ old row orphan-deleted. Any persisted `family_id` (attention explanations, counterfactual exclusion lists, user bookmarks) dangles silently. Resolved by deleting the projection.

**A35-5 — Phase 28 shipped ~2,600 insertions across 42 files in a single commit** (`c254596`), including 5 new modules, 208 lines of migration, and 6 new test files. The follow-ups (`1dbb3ed`, `68f73ca`) fixed two of the bugs I probed for. A phase of that surface area landing in one commit is a process finding: it is why family invalidation, job producers, and the frontend were all missed at once. **Recommend: Phase 29.0 lands as one checkpoint commit per lettered sub-stage** — the plan's §123 already proposes checkpoints; enforce them.

**A35-6 — Planning authority is uncommitted.** Every `plan/phases-v2/*.md` file — including Phase 29 itself — is untracked, while `plan/phases/` is deleted-but-unstaged. The document that governs the next phase is not in version control. Also untracked: a redundant `Newsroom -v2 - Phase 28.zip` build artifact in the repo root. Commit the plan; gitignore or delete the zip.

**A35-7 — No `.github/`, no CI, no lint, no format, no Python type check.** Only `pytest` and frontend `tsc --noEmit`. For a 36k-line codebase primarily edited by coding agents, the absence of a mechanical style/type gate is a real maintainability risk — review attention gets spent on what a linter should catch.

**A35-8 — `pydantic` is used directly in `domain_api.py` but is not a declared dependency** (it arrives transitively via `fastapi`). A FastAPI major-version change could break the build confusingly. One-line fix.

**A35-9 — Security/privacy.** `THREAT_MODEL.md` exists and the auth path uses argon2 with session purging — good. Two notes: `record_item` accepts a 4,000-char free-text `reason` rendered in Attention explanations and Ask citations (React escapes by default, but the Ask answer-string path deserves an explicit test); and Ask conversation history is retained indefinitely with no purge, a privacy exposure for a tool whose users research sensitive topics.

**A35-10 — Concurrency.** `storage.write_tx` discipline is consistent and correct across the modules I read, and SQLite single-writer is manageable at declared workload. Two brittleness patterns: `evidence_summary` opens a connection, closes it, calls `rebuild_evidence_families` (which opens another), then **recurses** — a read path that performs a write and can reopen connections three deep; and `CoverageService.list_runs` opens one connection per returned run. Neither is a live bug at current scale; both are the shape of things that break under load.

**A35-11 — Nothing measures whether Alerts are useful.** `alerts.status` and `acknowledged_at` exist, so the data is there — no code reports on it. "Correctness of emission" is thoroughly tested; "value of interruption" is entirely unmeasured. That distinction generalizes: **the system measures whether it is right far more than whether it is useful.** That is the single sentence that best summarizes this codebase.

**A35-12 — Intelligence vs attention: AGREE, and it is the strategic finding.** Newsroom has invested extraordinarily in *epistemic correctness* — spans, families, coverage, fragility, qualified negatives, provenance — and comparatively little in *"what changed, why should I care, what deserves attention now"*. The evidence is quantitative: Phase 28 added ~1,400 lines of epistemic backend and **one card** to the Inbox. The risk is real and currently materializing: Newsroom is becoming excellent at proving why an answer is justified while remaining cumbersome at delivering answers.

The correct rebalance does **not** weaken trust, because the trust machinery is mostly *engine*, not *cockpit*. Keep every canonical invariant. Move the epistemic surfaces into context. Spend the next two phases' UI budget on Home, Stories, Reports-as-diffs, and onboarding. **Complex engine, small cockpit.**

---

# 36. RECOMMENDED FINAL PHASE 29 SHAPE

```
PHASE 29 — TRUSTWORTHY AND USEFUL
"Nothing Newsroom says is unsupported, nothing it shows is stale,
 and we know it beats the simple alternative."

29.0  CORRECTNESS CLOSURE  (hard gate)
  A  Qualified negative safety     P0-1  canonical observation refs required;
                                         scope-matched coverage only; never
                                         satisfies the sufficiency threshold alone
  B  Coverage as projection        P0-5  derived denominator + states; validated
                                         target/version; or DELETE the subsystem
  C  Independence honesty          P0-2  delete evidence_families; lineage_group
                                         everywhere (incl. reports.py:380)
  D  Fragility components          P0-3  drop score, drop table, ship components
  E  Attention convergence         P0-4  on-demand ranking + suppression table;
                                         fix "Keep open"; 3 real feedback actions
  F  Test de-entrenchment          P0-6  correct the tests that assert the bugs
  G  Job lifecycle                 P1-7  delete 3 ceremonial jobs; wire coverage_refresh
                                         or delete it; rewrite the producer test
  H  Export authority              P1-8  Class A/B only; drop derived + entity_merges

29.1  PRODUCT COMPRESSION
  I  Simple/Advanced for real      P1-3  ~30 lines; nav filtering; honest copy
  J  Nav 16 -> 5 / 9               P1-4  Home / Stories / Ask / Reports / Watches
  K  One Research workflow         P1-5/6 merge hypothesis_gaps + blind spots;
                                         one hypotheses panel; deterministic
                                         discriminating-gap suggestion
  L  Real prioritization           P1-10 delete fake components
  M  Loop protection               P1-12 duplicate-query suppression, one
                                         disconfirming query, source-class diversity

29.2  VALIDATION  (the stage that must not be deferred)
  N  Corpus extension              P1-9  >=10 cases: late syndication discovery,
                                         coverage qualification, knowledge-time;
                                         correct docs/EVALUATION.md
  O  Telemetry                     P1-11 correction rate, alert action rate,
                                         research yield, dismissal by reason_code
  P  Real Watch dogfood            P1-1  >=4 weeks, one contested domain
  Q  Full vs Lite                  P1-1  same corpus, 20 questions, scored
  R  Story resolver divergence     P1-14 one adversarial test

29.3  ENGINEERING BASELINE
  S  ruff + mypy + eslint + one CI workflow
  T  Commit the plan; remove the build zip
  U  Rename one of the two "Coverage"s

DEFERRED OUT OF PHASE 29
  Shadow Reprocessing / Belief Diff         -> Phase 31+ (keep only a change_cause enum)
  ProcessingRun / knowledge-time / hist Ask -> next phase, simplified
  Projection registry                       -> next phase, as a deletion instrument first
  Retention / recovery / failure injection  -> next phase
  Packaging / onboarding / notifications    -> Phase 30
```

**Five of the eight 29.0 items are net code deletions.** This phase should end with fewer tables, fewer jobs, fewer nav items, and fewer persistent authorities than Phase 28 — and with the first real evidence that the product works.

---

# 37. FINAL DECISION

### Is Newsroom worth continuing?

**Yes — CONTINUE, BUT SIMPLIFY AGGRESSIVELY.** The Phase 22–27 core is a genuinely differentiated intelligence product with a real moat in correctable Story identity and exact-cause causality. Judged without sunk cost, that core would be worth building from scratch today. The Phase 28 layer would not.

### Should surface area be reduced now?

**Yes, in Phase 29 — not Phase 30.** 16 nav items, 4 taxonomies, 2 gap systems, 3 attention surfaces, and 2 things named "Coverage" is past the point where a new user can form a mental model. Delaying compression means Phase 29's correctness work gets built on top of surfaces that should not exist.

### Should Phase 29 be rewritten?

**No — ACCEPTED WITH TARGETED EDITS.** Stage 29.0 independently reached nearly the same diagnosis this review reached from the code, which is strong evidence the document is trustworthy. It needs 12 specific edits (§23), of which three are structural: add the Ask scope leak, move Full-vs-Lite validation in, and move Shadow Reprocessing out.

### Should Full-vs-Lite validation happen before Phase 30?

**Yes, unequivocally.** It is cheap, blocked on nothing, and it is the only measurement that can tell you whether the remaining roadmap is worth executing. Deferring it to Phase 30 converts Phase 30 into an existential test after another phase of investment — precisely the failure this review was commissioned to prevent.

### The five most important things to do next

1. **Fix the Ask qualified-negative path (P0-1).** Require canonical observation references for `not_found`/`not_observed`; forbid cross-scope coverage injection; forbid derived context from satisfying the evidence-sufficiency threshold alone. *Newsroom must never claim it searched when it did not.*
2. **Delete `evidence_families` and the fragility score; use `lineage_group` and explainable components (P0-2, P0-3).** Two bugs, two tables, and one dead table disappear; the honest signal is the one that was already correct.
3. **Make Attention converge by making it on-demand, persisting only suppression (P0-4)** — and fix the "Keep open" button that removes items.
4. **Compress navigation to 5 Simple / 9 Advanced surfaces and actually implement Simple mode (P1-3, P1-4).** ~30 lines of frontend for the largest usability gain available.
5. **Run one real Watch for four weeks and score Full vs Lite (P1-1).** Nothing in Phase 29's architecture is blocked on it, and everything after Phase 29 depends on the answer.

---

*Prepared as an adversarial peer review. Every "AGREE" verdict is backed by a file path, a line number, a git observation, or a reproduced probe against a temporary database. Every "KEEP" and "DEFEND" verdict names the code or invariant that earns it. The live project database was not modified, and no runtime code, schema, migration, test, or frontend file was changed.*
