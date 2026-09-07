# PHASE 28.5 — CORRECTNESS, HONESTY, AND SURFACE REDUCTION

## Phase 28 Remediation: Truth Safety, Projection Deletion, Lifecycle Consolidation, Cockpit Compression, and Validation Readiness

---

# 0. PHASE STATUS AND AUTHORITY

Phase 28 is complete and committed. It is **not accepted**.

Phase 28.5 is the next permitted implementation phase. **Phase 29 is blocked until Phase 28.5 is accepted.**

Active forward planning authority:

```text
G:\Projects\Newsroom -v2\plan\phases-v2\
```

Binding inputs:

```text
plan/phases-v2/Phase 27.md
plan/phases-v2/Phase 28.md
plan/phases-v2/Phase 29.md
plan/phases-v2/Strategic Architecture Review.md
plan/phases-v2/Final Architecture Reconciliation Memo.md
docs/reviews/PHASE_29_PRE_IMPLEMENTATION_ADVERSARIAL_REVIEW.md
```

This phase also incorporates the subsequent Codex/Claude adversarial reconciliation of the Phase 28.5 plan.

The **live repository is always implementation authority**. Do not assume a future starting HEAD, schema number, table count, route count, or test count. Before implementation, inspect:

```text
current branch
current HEAD
git status
current migration/schema version
live base-table count
logical-export table count
registered Job types
API route count
primary navigation count
recent commits
existing tests
frontend
evaluation corpus/framework
documentation
```

The latest reviewed baseline was:

```text
branch:                 main
HEAD:                   68f73ca84097728880736deb354dd4226c4c7018
schema:                 32
backend tests:          779 passing
base tables:            120
logical-export tables:   94
```

**Re-verify all of it before editing.**

Preserve unrelated tracked and untracked work. Do not reset, rewrite history, delete unrelated files, or push.

---

# 1. WHY THIS PHASE EXISTS

Phase 28 added useful concepts but also shipped a derived layer whose lifecycle and product claims outran the code.

Verified problems included:

```text
Ask could state that Newsroom searched when no search occurred
Coverage accepted nonexistent targets and arbitrary versions
Coverage was a caller-assembled ledger with no trustworthy observation denominator
Evidence Family persistence could stay stale after lineage changed
Fragility returned invalid or self-contradictory results
Attention was insert-only and therefore non-convergent
"Keep open" hid the item
Simple/Advanced existed as a stored setting but not a product mode
Blind Spot approval had no downstream effect
Hypothesis Gaps duplicated canonical Research Gaps
Phase 28 Jobs were registered but had no production producers
dead persisted analysis/state was exported as if authoritative
documentation overstated what Phase 28 actually implemented
```

Phase 29 must not be built on top of knowingly false or stale derived state.

Phase 28.5 therefore exists as a **remediation and subtraction phase**.

Its job is not to make Phase 28 larger. Its job is to make Newsroom:

```text
smaller
more truthful
more convergent
easier to understand
easier to evaluate
```

---

# 2. FINAL PHASE OBJECTIVE

> **Newsroom must not state anything it cannot support, must not show stale derived state, and must not present more product surface than it has earned.**

Phase 28.5 is complete only when:

```text
Ask cannot turn absence of evidence into evidence of absence
Phase 28 epistemic Coverage no longer exists in runtime
known source dependency is represented by one current computation
no Fragility scalar remains
Attention ranking is current by construction and only human decisions persist
one canonical Research Gap authority exists
Simple mode materially reduces primary navigation without hiding provenance
documentation describes only behavior that exists
Phase 28 semantic evaluation coverage is materially expanded
utility/correction telemetry exists
a frozen Newsroom Lite comparison harness exists
the real-Watch dogfood clock has started
```

---

# 3. DEFINING CONSTRAINT — SUBTRACTION IS PART OF CORRECTNESS

This phase must reduce **architectural surface**.

Preference order for every fix:

```text
1. delete
2. reuse existing architecture
3. make derived/on-demand
4. merge concepts
5. add a small invariant
6. add bounded persistence
7. only then add a new subsystem
```

Do not introduce:

```text
new database
new workflow engine
event bus
graph store
vector infrastructure
generic projection framework
generic policy engine
generic event envelope
```

The plan specifies **required outcomes and invariants**. Where an example names a column, API field, line count, or migration number, the live repository may justify a smaller repository-native mechanism.

The deletion inventory is binding in intent. The live code decides exact mechanics.

---

# 4. WHAT PHASE 28.5 MUST NOT DO

Do not begin:

```text
general ProcessingRun / processing provenance
knowledge-time / bitemporal architecture
historical Ask
shadow reprocessing
general Belief Diff
projection registry/framework
knowledge_backfills consolidation
retention/deletion architecture
Class C rebuild-order reconstruction proof
failure-injection framework
workload envelope/SLO program
packaging / installer
onboarding wizard
backfill-on-Watch-creation
external notifications
provider-generated hypotheses
Entity merge workflow
vector search
PostgreSQL migration
progressive-autonomy framework
```

Narrow exceptions:

```text
logical export authority must be trimmed because tables are being removed

minimum development tooling is allowed because the current codebase lacks a
basic mechanical quality gate

dogfood and the Lite harness are started here because Phase 30 must not become
the first existential product test
```

---

# 5. PHASE STRUCTURE

Six checkpoint stages:

```text
28.5.0  TRUTH SAFETY
        remove false observation/absence claims

28.5.1  PROJECTION DELETION
        remove persisted derived state that can become stale

28.5.2  LIFECYCLE CONSOLIDATION
        one authority per concept; no ceremonial lifecycle

28.5.3  COCKPIT COMPRESSION
        small primary product surface; provenance always reachable

28.5.4  HONEST DOCUMENTATION AND TOOLING
        repository claims and quality gates match reality

28.5.5  VALIDATION READINESS
        semantic corpus, utility telemetry, Lite harness, dogfood clock
```

Each stage should end in a coherent checkpoint commit after focused validation.

**28.5.0 and 28.5.1 are a hard gate. Do not begin 28.5.2 while a P0 remains open.**


---

# 6. STAGE 28.5.0 — TRUTH SAFETY

## Objective

Newsroom must never assert an observation it did not make.

---

# 7. 28.5.0A — BINDING DECISION: DELETE PHASE 28 EPISTEMIC COVERAGE

The Coverage decision is no longer open.

**Coverage Path B is binding. Delete Phase 28 epistemic Coverage.**

The ontology was thoughtful. The substrate required to make its strongest claims is absent.

Current canonical facts prove:

```text
a Source was fetched
bytes changed or did not change
a Monitor ran
a Monitor recorded no_change / relevant_change / partial / error
an acquisition retrieved / failed / blocked / was unchanged
```

They do **not** prove:

```text
a proposition was exhaustively searched
an observation channel was complete for a requested window
absence in that channel is meaningful evidence of absence
a Source-level acquisition belongs uniquely to one Watch expectation
```

In particular:

```text
acquisition_events are Source-level, not Watch/Monitor expectation-level
monitor_activity describes monitor execution/change outcomes, not exhaustive proposition search
Watch scope version semantics required by Coverage do not exist as a first-class Watch identity
Research Question and Source version identities proposed by the old plan do not exist in the required form
```

Trying to derive Coverage now would manufacture epistemic meaning from operational fetch facts.

That is worse than deleting it.

## Required deletion

Remove Phase 28 epistemic Coverage runtime completely:

```text
Coverage service/runtime usage
coverage_runs
coverage_items
coverage_summaries
Coverage API models/routes
Ask Coverage retrieval/context
Coverage statements/citations
Coverage Attention candidate source
Coverage-derived Research priority component
coverage_refresh Job type and handler
Coverage logical-export entries
Coverage integrity rules
Coverage frontend/admin copy/types
Coverage tests that only exercise the deleted subsystem
blind_spot_suggestions, because Coverage is its only producer
```

Do not leave dormant Coverage DTOs, enums, service stubs, Job names, frontend types, or UI copy merely "for later."

## Preserve design thinking, not ghost runtime

Create or update an ADR documenting the useful ontology and the reason for deletion:

```text
not_searched
not_found
not_observed
failed_acquisition
out_of_scope
stale
```

The ADR must state that a future Coverage system, if dogfood proves its value, requires an explicit model of:

```text
Expectation
Observation
Completeness rule
Window
```

A future implementation must not infer meaningful absence from generic acquisition success.

## Conservative runtime invariant after deletion

```text
"No evidence found in Newsroom's observed material"
is not
"Evidence proves absence"
```

Ask must express corpus limitation honestly.

---

# 8. 28.5.0B — DERIVED/QUALIFYING CONTEXT MAY NOT SATISFY ASK SUFFICIENCY

The reproduced Ask defect was broader than Coverage.

Derived context was able to become the only statement in an answer and prevent `insufficient_evidence`.

The durable rule is:

> **Qualifying context can qualify a grounded answer. It can never constitute the grounded answer by itself.**

Implement a single, general sufficiency rule.

Conceptually:

```text
GROUNDING
    canonical evidence-bearing material that can support the answer

QUALIFYING
    analytical/structural context that modifies interpretation
    e.g. known dependency structure, evidence-quality components,
    future noncanonical analytical context

QUALIFYING material never satisfies evidence sufficiency by itself.
```

If an Ask run produces zero grounding statements, it must refuse with:

```text
insufficient_evidence
```

regardless of qualifying context.

Do not implement this as a deleted-Coverage special case.

## Acceptance

```text
an Ask with no grounding evidence refuses
adding dependency/evidence-quality context cannot convert the refusal into a substantive answer
an Ask with grounding evidence may include qualifying context
a future qualifying-context source would inherit the same rule automatically
```

---

# 9. 28.5.0C — CONSERVATIVE ABSENCE LANGUAGE

Delete all user-facing language that claims Newsroom "searched the expected channels" or equivalent Phase 28 Coverage language.

When evidence is absent, allowed language must remain conservative, e.g.:

```text
Newsroom did not find evidence of that in the material currently available to it.
That does not establish that the event did not occur or that all relevant sources
were checked.
```

Exact wording may vary by UI context.

Binding rule:

```text
corpus absence is never existential absence
```

Add a regression test that makes reverting to the old semantic claim fail.

---

# 10. 28.5.0D — PRESERVE HONEST MONITOR/ACQUISITION HEALTH

Deleting Phase 28 Coverage must **not** delete the older, honest operational observation surfaces.

Preserve:

```text
Monitor health
Watch/Monitor execution history
monitor_activity
acquisition_events
Source acquisition health
normal Monitor/Watch configuration
```

These answer:

```text
Did this monitor run?
Did acquisition fail?
Was content unchanged?
Was relevant change detected?
```

They do not claim:

```text
The proposition was exhaustively searched
or
absence is meaningful evidence
```

That distinction is binding.

---

# 11. 28.5.0E — FIX VERIFIED MONITOR-HEALTH FALSE/DEAD PREDICATES

Because Monitor health becomes the honest observation surface after Coverage deletion, clean the verified dead predicates in the same stage.

Audit live CHECK constraints and queries.

Previously verified issues included:

```text
monitor_activity outcome predicates checking values not allowed by schema
such as content_changed

acquisition_events predicates checking impossible values such as error/timeout
when the schema allows retrieved/not_modified/unchanged/failed/blocked

source_summary using the same stale outcome vocabulary
```

Do not preserve impossible predicates for compatibility.

Align queries and UI language to the actual persisted outcome vocabulary.

## Acceptance

```text
no Monitor-health metric is permanently zero because it queries an impossible enum
failure metrics include actual failure/blocked states supported by schema
source summaries use the same canonical outcome vocabulary
```

---

# 12. 28.5.0F — BOUND MONITOR-HEALTH AGGREGATION

The existing Diagnostics/Monitor-health aggregate may perform an unbounded N+1 over every Monitor.

Keep retrieval bounded and explicit.

Do not introduce a new analytics store.

Use the smallest repository-native query/batching mechanism.

## Acceptance

```text
Monitor-health list/aggregate has an explicit bound/pagination contract
the implementation does not open an unbounded per-Monitor query loop
results remain deterministic and explainable
```


---

# 13. STAGE 28.5.1 — PROJECTION DELETION

## Objective

Where current truth is already cheaply computable, remove persisted projections that can become stale.

---

# 14. 28.5.1A — DELETE PERSISTED EVIDENCE FAMILIES

Delete:

```text
evidence_families
evidence_family_members
rebuild_evidence_families
evidence_family_rebuild Job type/handler
family-key lifecycle/invalidation machinery
logical-export entries for family tables
family-table integrity rules
```

The canonical truth is:

```text
document_lineage
```

and the current connected component is computed on demand by the existing lineage/dependency-group logic.

Replace family consumers with the current dependency-group computation, including:

```text
source robustness/evidence quality
Reports
counterfactual analysis
API fields
tests
```

Do not create a replacement persisted cache.

If real measurement later proves this computation a hot path, Phase 29 may classify and cache it with an explicit invalidation owner.

---

# 15. 28.5.1B — TERMINOLOGY: KNOWN DEPENDENCY IS NOT INDEPENDENCE

A dependency group means:

```text
these documents are connected by known dependency edges
```

Different groups mean:

```text
Newsroom has not found a dependency edge connecting them
```

They do **not** mean:

```text
independently observed
editorially independent
independent confirmation
```

Standardize runtime/API/UI language around:

```text
dependency group
known dependency group
lineage group
```

Avoid system-generated assertions such as:

```text
independent source
independent family
independent confirmation
```

unless future canonical facts explicitly support them.

Useful explanatory form:

```text
3 documents · 2 known dependency groups.
No dependency edge is known between the groups; this does not prove independent observation.
```

## Acceptance

```text
one dependency-group count exists where the old family/lineage pair disagreed
adding a lineage edge changes the next read immediately, no rebuild call required
Reports use dependency-group language
no current user-facing output infers independence from absence of a lineage edge
```

---

# 16. 28.5.1C — DELETE FRAGILITY AS A SCALAR

Delete:

```text
fragility_score
evidence_fragility_analyses
fragility_analysis Job type/handler
export entries for the dead persisted analysis
```

Do not clamp or redesign the scalar.

Replace it with individually explainable evidence-quality components derived on read.

The exact component set should follow live readers/UI, but must be:

```text
verifiable
non-contradictory
bounded where represented as a share
named according to what it actually measures
```

Likely useful components include:

```text
supporting span count
distinct Source count
known dependency-group count
largest dependency group's share of support
Claims supported by only one dependency group
presence of primary evidence
zero-support state
```

Do not call the aggregate "Fragility."

Rename service/API concepts toward:

```text
Evidence Quality
Source Dependence
```

as appropriate.

---

# 17. 28.5.1D — KEEP COUNTERFACTUAL AS AN ON-DEMAND ACTION

Preserve the existing non-mutation invariant.

Counterfactual analysis remains:

```text
pure/on-demand
noncanonical
non-mutating
Advanced/contextual
```

Do not create a table, Job, lifecycle, or navigation item.

After family deletion, do not invent an ephemeral `group_id` merely to preserve the old API.

Use canonical anchors:

```text
exclude_document_ids
exclude_source_ids
```

At evaluation time, resolve the current dependency component containing each anchor.

Return the resolved current membership so the user can see what was excluded.

Binding invariant:

```text
canonical IDs identify the user's choice
current lineage determines the group at execution time
```

---

# 18. 28.5.1E — ATTENTION IS COMPUTED; HUMAN DECISIONS PERSIST

Delete the mutable current Attention projection.

Remove:

```text
attention_items
attention_feedback
attention_refresh Job type/handler
POST /attention/refresh write-on-read workflow
attention_items export authority
```

Replace with:

```text
current Attention candidates
    computed on demand from current canonical/operational state

human Attention decisions
    append-only Class B history
```

A minimal durable decision record must encode enough identity to support:

```text
Seen
Snooze
Not useful
```

without suppressing future materially different events.

Binding Attention identity:

```text
(object_type, object_id, reason_code, basis_fingerprint)
```

The **basis fingerprint must hash canonical material cause**, not explanation prose, ranking scores, cosmetic metadata, timestamps, or merely a broad reason category.

Rule:

```text
same object/reason + same canonical material cause
    -> prior Seen/Dismiss may suppress it

same object/reason + a new canonical material cause
    -> candidate must be eligible to appear again
```

Examples of canonical material cause may include:

```text
Alert cause ID / material Alert event identity
Report revision/cause ID
Claim ID + state transition
Story correction ID
Research Gap/Task identity
canonical cause-set hash
```

Use the smallest existing domain-native identity for each candidate type.

Do not recreate `attention_items` under another name.

---

# 19. 28.5.1F — ATTENTION VISIBILITY AND SEMANTICS

Current ranking is shown iff:

```text
candidate condition is currently true
AND
no matching active suppression decision exists
```

A resolved condition disappears because it is no longer a candidate.

No reconciliation job exists.

No refresh mutation exists.

Required user actions:

```text
Seen
    suppress this material instance

Snooze
    suppress until snoozed_until

Not useful
    dismiss this material instance and record reason_code for telemetry
```

Remove fake/unreachable semantics:

```text
Keep open
useful
already_knew
mute_pattern
needs_investigation-as-seen
```

If future pattern muting exists, it must store a real reversible pattern and be a separate feature.

## Acceptance

```text
resolved conditions disappear on the next read without a refresh write
a Seen decision on one material cause does not suppress a later different cause
with the same object/reason
loading Home performs no Attention write
every UI label matches resulting visibility
reason_code telemetry is derivable from the decision log
```

---

# 20. 28.5.1G — ALERT / HOME CONSISTENCY

The same Alert must not have contradictory visibility between Home and any Alert-oriented control surface.

Define one relationship between Alert acknowledgement and Attention decisions.

Preferred invariant:

```text
an acknowledged Alert is not a current Home Attention candidate
```

Implement using the smallest existing authority boundary.

Do not create another Alert-vs-Attention state machine.

Alert rules/settings remain durable. Current Attention ranking remains derived.

---

# 21. 28.5.1H — BOUNDED ATTENTION RETRIEVAL

Keep candidate pools bounded.

Order each bounded pool by the same material factor used by its candidate scoring so important older items are not excluded solely by recency.

Do not use unbounded scans for theoretical purity.

After Coverage/Blind Spot deletion, simplify the candidate sources accordingly.


---

# 22. STAGE 28.5.2 — LIFECYCLE CONSOLIDATION

## Objective

One authority per concept.

No active product-state table, status, Job, or feedback value introduced or maintained by the current architecture may exist without a real reader and writer.

Historical/deferred schema may remain only if:

```text
it is not presented as a shipped capability
it is absent from logical-export authority
it is absent from active integrity surfacing
it is documented as deferred
```

---

# 23. 28.5.2A — ONE RESEARCH GAP AUTHORITY

Canonical model:

```text
Research Question
    ├── current assessment
    ├── competing hypotheses
    ├── canonical Research Gaps
    └── Research Tasks
```

Only `research_question_gaps` may represent researchable gaps.

Only Research Tasks execute research work.

Delete `hypothesis_gaps`.

Migrate existing rows into canonical Research Gaps if any exist.

A Gap may record provenance that it originated during review of a Hypothesis.

Do not encode false ownership.

Use outcome-level semantics equivalent to:

```text
origin_hypothesis_id
```

meaning only:

```text
this Hypothesis review originated the Gap
```

Do not add a many-to-many Gap↔Hypothesis table until a live reader requires it.

---

# 24. 28.5.2B — HYPOTHESES MUST BECOME MINIMALLY REAL OR BE REMOVED

This remains an either/or acceptance gate.

## Minimum viable branch

Within the Research surface:

```text
list Hypotheses for a Research Question
create Hypothesis
approve/reject Hypothesis
compare Hypotheses
link canonical Claims as:
    supports
    contradicts
    discriminates
explicitly create a canonical discriminating Research Gap from the comparison
```

Hypotheses remain analysis/framing objects, not Claims and not research executors.

No provider-generated Hypotheses in 28.5.

No automatic Gap inference from existing `discriminates` Claim links.

## Remove branch

If the minimum workflow cannot be made genuinely usable end-to-end in this phase:

```text
drop hypotheses
drop hypothesis_claim_links
drop hypothesis_history
remove related routes/export/integrity/frontend claims
```

Do not ship a third phase with unreachable Hypothesis scaffolding.

Record the chosen branch and rationale in the completion report.

---

# 25. 28.5.2C — BLIND SPOTS ARE REMOVED WITH COVERAGE

Because Phase 28 epistemic Coverage is deleted, its only produced Blind Spot subsystem is also deleted.

Remove:

```text
blind_spot_suggestions
Blind Spot API/runtime
Blind Spot Attention candidates
Blind Spot export/integrity/UI
Blind Spot statuses
```

## Preserve human decisions honestly

Before dropping the table, inspect live persisted Blind Spot review data.

If **no reviewed human decisions exist**, state that in the migration/completion report and drop normally.

If reviewed decisions do exist:

```text
do not silently discard them
```

Preserve them using the smallest appropriate existing backup/export/history mechanism before removal.

**Do not make the schema migration write arbitrary filesystem sidecar files.**

Binding invariants:

```text
no human decision is silently lost
schema migrations do not create external ad hoc artifacts
```

---

# 26. 28.5.2D — RESEARCH PRIORITIZATION USES ONLY REAL SIGNALS

Remove:

```text
cost_budget = 1.0
freshness mislabeled from open/pursuing state
coverage_deficiency, because epistemic Coverage is deleted
```

Keep only real, explainable components currently supported by canonical state.

At minimum:

```text
Question priority
Gap importance
```

If a real budget/cooldown signal already exists and can be used without adding new semantics, it may be added under its actual name.

Never average in a constant merely to preserve a score shape.

The rationale text must mention only factors actually used.

---

# 27. 28.5.2E — RESEARCH LOOP PROTECTION WITHOUT TOY NATURAL-LANGUAGE LOGIC

Keep:

```text
duplicate-query suppression
source-class diversification
```

Implement them using existing Research attempt/source-class facts.

Do **not** automatically negate arbitrary natural-language propositions.

Contrary-evidence pursuit is allowed only where Newsroom has a safe existing transformation, such as:

```text
a canonical contradicting Claim
a disputed Claim state with a known contradictory side
human-approved alternative/exclude vocabulary
explicit contradiction terms already present in canonical metadata
```

Where no safe transformation exists, record:

```text
no safe contrary-evidence query strategy available
```

Do not silently pretend a disconfirming search happened.

---

# 28. 28.5.2F — JOBS MUST REPRESENT REAL PRODUCTION OBLIGATIONS

All four Phase 28 analytical Job types are removed under the binding design:

```text
coverage_refresh
evidence_family_rebuild
fragility_analysis
attention_refresh
```

Delete their handlers, registration, docs, and tests that exist only to justify their presence.

Do not replace the bad literal-based producer test with a static-analysis framework.

For surviving Jobs generally:

```text
production-domain actions that enqueue Jobs should have behavioral tests
asserting the expected Job was enqueued

actually enqueued Job types must have registered handlers
```

Delete `test_production_handler_coverage` if it cannot be converted into a meaningful behavioral guarantee.

---

# 29. 28.5.2G — LOGICAL EXPORT AUTHORITY

Logical export must stop presenting rebuildable/current derived state as reconstruction truth.

28.5 export contains:

```text
Class A
    canonical evidence/reference state

Class B
    human intent, decisions, corrections, history, settings
```

28.5 export excludes:

```text
current derived projections
search indexes
automatic classifier output
current Attention ranking
deleted Phase 28 projections
```

Specific removals include, where present:

```text
coverage_runs
coverage_items
coverage_summaries
blind_spot_suggestions
evidence_families
evidence_family_members
evidence_fragility_analyses
attention_items
hypothesis_gaps
entity_merges
```

Add `attention_decisions` because it is human intent/history.

Derived StoryEntity and automatic Tag export treatment should follow the existing Class A/B/C classification and this phase's scope; do not invent Class C reconstruction here.

## 28.5 logical round-trip definition

Acceptance means:

```text
export Class A/B
import into a fresh database
foreign keys pass
integrity passes for imported authority
human decisions/history are preserved
no Class C rows are imported as reconstruction truth
```

It does **not** require Phase 29's future Class C rebuild ordering or semantic-equivalence proof.

---

# 30. 28.5.2H — ENTITY MERGE HYGIENE

`entity_merges` has no active writer.

Do not build the workflow.

Remove it from:

```text
logical-export authority
active integrity surfacing
documentation implying shipped behavior
```

Keeping the empty historical/deferred table is allowed under the narrowed reader/writer invariant.

Document Entity merge as deferred.


---

# 31. STAGE 28.5.3 — COCKPIT COMPRESSION

## Objective

Complex engine, small cockpit.

Simple mode reduces primary destinations.

It never reduces evidence/provenance reachability.

---

# 32. 28.5.3A — SIMPLE / ADVANCED MUST BE REAL

Bind frontend navigation to the persisted Experience mode.

Required outcome:

```text
switching Simple/Advanced changes primary navigation
```

Collapse unused per-capability override machinery unless a live reader proves it necessary.

Do not use mode as an authorization boundary.

---

# 33. 28.5.3B — SIMPLE PRIMARY NAVIGATION

Target Simple primary navigation:

```text
Home
Stories
Ask
Reports
Watches
```

Simple should have **no more than 6** primary items.

Settings does not count as a primary product destination.

It is a persistent header/profile/gear utility and must remain reachable in both modes.

---

# 34. 28.5.3C — ADVANCED NAVIGATION

Advanced adds power-user destinations such as:

```text
Research
Documents
Workbench
Diagnostics
```

Exact labels should follow the current frontend if a smaller implementation preserves meaning.

Advanced is a discoverability/presentation mode, not evidence authorization.

---

# 35. 28.5.3D — PROVENANCE DEEP LINKS ALWAYS WORK

A Simple-mode user who follows a citation or contextual link must be able to inspect provenance.

Always reachable from a valid contextual/citation link in either mode:

```text
EvidenceSpan
Document
DocumentVersion
ContentArtifact where product policy permits
Claim
Story
Story correction/history
Entity
known dependency detail
Report revision
Ask citation target
```

Mode-gated destinations may include:

```text
Diagnostics
Jobs/runs
bulk/admin/configuration surfaces
Workbench authoring/bulk inspection
```

Do not redirect evidence deep links to Home merely because the user is in Simple mode.

Binding principle:

> **Simple hides primary navigation complexity. It never hides why Newsroom believes something.**

---

# 36. 28.5.3E — HOME IS THE ONLY "LOOK HERE" SURFACE

Relationship:

```text
Attention
    internal ranking logic only

Home
    the primary current-priority surface

Alert
    high-threshold interruption object / future external-delivery carrier
```

Remove Alerts as a competing Simple-mode daily inbox destination.

Alert rules/configuration live in Settings/Advanced as appropriate.

A user must not choose among Home, Attention, and Alerts to know what deserves attention.

---

# 37. 28.5.3F — TAXONOMY REDUCTION

Presentation model:

```text
Entity
    core investigative identity, contextual

Tag
    supporting classification, contextual

Topic
    remove from primary navigation; contextualize under Watch/Tag where needed

Subject
    remove from primary navigation; contextualize under Watch scope where needed
```

Do not change Topic/Subject schema merely for presentation cleanup.

The `story_tags` / `tag_assignments` authority merge remains Phase 29 work unless live implementation forces a tiny compatibility adjustment.

---

# 38. 28.5.3G — MONITOR HEALTH NAMING

After Coverage deletion, the ambiguous Phase 28 "Coverage" product concept is gone.

Use **Monitor health** consistently for the operational diagnostics surface.

Move it under Diagnostics rather than Workbench if that matches the live frontend architecture.

Do not rename unrelated canonical fields solely for cosmetic consistency if it causes avoidable churn.


---

# 39. STAGE 28.5.4 — HONEST DOCUMENTATION AND TOOLING

## Objective

A user, developer, or coding agent reading the repository must not be told a capability exists when it does not.

---

# 40. 28.5.4A — CORRECT DOCUMENTATION CLAIMS

Correct all documentation and UI copy affected by deletions and consolidation.

At minimum audit:

```text
docs/EVALUATION.md
docs/ARCHITECTURE.md
docs/API.md
README.md
frontend Settings/Experience copy
Phase 28 capability descriptions
```

Specific corrections:

```text
do not claim Phase 28 extended the permanent eval corpus when it only added pytest
do not claim removed Phase 28 Jobs "use JobService" operationally
remove Coverage feature claims after runtime deletion
remove Evidence Family / Fragility feature claims
describe Attention as current ranking + human decisions
describe Advanced mode only in terms of surfaces that actually exist
```

Preserve useful historical context where appropriate, clearly marked as historical.

---

# 41. 28.5.4B — MINIMUM DEVELOPMENT TOOLING

Add the smallest useful mechanical baseline.

Hard gates:

```text
ruff check / format configuration
existing backend pytest suite
existing frontend typecheck
frontend lint if the repository can adopt it without disproportionate churn
one CI workflow running the supported hard gates
```

Add `pydantic` as a direct dependency if it is imported directly and currently arrives only transitively.

## Mypy staging

Configure mypy for `newsroom/`.

Run it and record the baseline.

It is blocking only if the existing baseline is already tractable.

Regardless:

```text
28.5 touched code must not introduce new mypy errors
```

Do not let retrofitting 36k lines of type-cleanliness consume the remediation phase.

---

# 42. 28.5.4C — REPOSITORY HYGIENE

Before completion:

```text
the active phase plans are tracked in version control
obsolete plan/phases deletions are handled intentionally
repository-root build ZIP artifacts are removed or ignored
.kilo/ is explicitly tracked or ignored
the final 28.5 plan and README sequencing are committed with the phase
```

Do not delete unrelated user artifacts without verifying intent.


---

# 43. STAGE 28.5.5 — VALIDATION READINESS

## Objective

Phase 29 should reason about a product that can already measure whether its intelligence is useful.

---

# 44. 28.5.5A — EXTEND THE PERMANENT EVALUATION CORPUS

The permanent semantic corpus must finally evolve beyond the Phase 0 set.

Add **at least 8** substantive cases that exercise semantics owned by Phase 28.5/current architecture.

Mandatory themes:

```text
1. LATE DEPENDENCY DISCOVERY
   Documents initially appear unrelated; a later lineage edge reveals known dependence.
   Current reads must immediately reflect one dependency group.

2. CONSERVATIVE ABSENCE
   Corpus absence must not be presented as proof of absence.

3. ASK REFUSAL INVARIANT
   Qualifying/derived context cannot satisfy evidence sufficiency by itself.

4. LATE STORY CORRECTION
   A correction arriving after earlier Story/Report state preserves causal history.

5. LATE STORY SPLIT
   A later split preserves history and correct current membership.

6. SINGLE-GROUP SUPPORT
   Multiple documents in one known dependency group must not be presented as
   independent corroboration.

7. RETRACTED EVIDENCE
   Existing canonical behavior around source retraction/correction is exercised
   without inventing historical Ask.

8. SILENT DOCUMENT EDIT
   Versioned content changes materially and provenance remains exact.
```

Do **not** require in Phase 28.5:

```text
belief at T1 vs T2
as-of knowledge queries
historical Ask
un-confirmation as a knowledge-time question
```

Those belong to Phase 29A and should be recorded in the Phase 29 handoff.

Update `docs/EVALUATION.md` with the true corpus count and taxonomy.

---

# 45. 28.5.5B — CORRECTION AND UTILITY TELEMETRY

Add read-only reporting over existing durable data.

No new telemetry lifecycle table unless the live code proves one is unavoidable.

At minimum Newsroom should be able to answer where source data exists:

```text
Story automatic-assignment correction rate
Alert acknowledgement/action rate
Research attempt yield
Attention dismissal rate by reason_code
```

Entity/dependency correction rates may be reported as unavailable if the canonical correction authority does not yet exist.

Do not fabricate metrics from proxy fields.

Expose this under Diagnostics/Advanced, not as a new primary product surface.

---

# 46. 28.5.5C — NEWSROOM LITE HARNESS

Build the comparison harness but do not claim a final verdict yet.

Lite definition:

```text
same database
same Documents
same corpus cutoff
FTS document retrieval only
no Claims
no Stories
no Phase 28 Coverage
no dependency-group reasoning
strong LLM synthesis
document citations
```

Reuse:

```text
newsroom.evals
existing replay/evaluation infrastructure
```

Do not create a second benchmark framework.

---

# 47. 28.5.5D — FREEZE THE LITE BENCHMARK CONTRACT BEFORE RESULTS

Freeze before either system is run to conclusion:

```text
corpus cutoff timestamp
20-question set
provider
model
temperature/deterministic settings
prompt version(s)
context budget
retrieval limit
FTS configuration/ranking
citation limit
scoring rubric
blinding procedure
falsification/acceptance criterion
```

Suggested question mix:

```text
6 factual retrieval
4 conservative-absence
4 corroboration/dependency
3 temporal "what changed" questions supported by current non-historical semantics
3 intentionally unanswerable/refusal cases
```

Both systems use the same provider/model and comparable budgets where applicable.

Answers should be stripped of system identity and shuffled for scoring where practical.

Pre-register what outcome would count as:

```text
Full clearly better
mixed / feature-specific advantage
Lite effectively equivalent
```

Do not redefine success after seeing results.

---

# 48. 28.5.5E — START THE DOGFOOD CLOCK

At Phase 28.5 acceptance, start one real Watch.

Phase 29 may proceed immediately.

Phase 30 waits for the dogfood window/Full-vs-Lite report.

## Dogfood environment contract

Before starting, explicitly define:

```text
dedicated dogfood DB/profile/path
Watch subject
approved Source set
owner responsible for API/worker uptime
start date
provider enabled/disabled
provider/model if enabled
budget cap
backup policy
telemetry collected
```

Rules:

```text
never use the developer default DB implicitly
never use the dogfood DB as a test target
freeze subject/source set/provider/model/budget at start
record later Source additions as explicit events
reliable automated backup
minimum 4-week window
extend the window rather than restarting it
```

Recommended first Watch:

```text
one contested/messy longitudinal topic
8-15 Sources spanning primary/official, mainstream, specialist, and aggregator classes
```

Use a provider for the dogfood if the intended product normally benefits from one. Freeze the provider/model for the window.

Collect:

```text
correction burden
Alert action/acknowledgement rate
Research yield
Attention dismissal by reason_code
brief human usefulness notes
```

The human usefulness log is not replaced by an inferred database metric.


---

# 49. TESTS THAT MUST CHANGE, NOT MERELY BE ADDED

The current green suite contains tests that encode deleted or incorrect behavior.

Do not preserve bugs merely to keep historical tests green.

Delete or rewrite tests for:

```text
Phase 28 Coverage
qualified-negative assertions
Coverage target/version behavior
Coverage Ask language/context
Evidence Families
Fragility scalar
Attention refresh/persisted-item lifecycle
Experience capabilities dict
literal producer coverage test
Hypothesis Gap lifecycle
Blind Spot approval lifecycle
```

Preserve valid invariants while changing their implementation, especially:

```text
counterfactual non-mutation
Story correction authority
exact evidence provenance
Ask insufficient_evidence refusal
```

Add regression tests so reverting each reproduced defect fails.

At minimum:

```text
Ask conservative absence
qualifying context cannot satisfy sufficiency
dependency-group read updates immediately after lineage change
only one dependency measure is returned
no Fragility scalar exists
Attention converges because current candidates are computed
Seen does not suppress a later materially different cause
every UI action label matches visibility
Simple mode still resolves every provenance/citation deep link
Research has one Gap authority
surviving production Job workflows enqueue handled Job types
Monitor-health predicates match real schema enums
```

---

# 50. MIGRATION INTENT

Forward-only.

Do not hard-code migration numbers in the plan as future truth. Use the next available numbers in the live registry.

Migration outcome must:

```text
preserve every Class A record
preserve every Class B human decision/history
migrate Attention human decisions before dropping their source tables
migrate Hypothesis Gap content into canonical Research Gaps before dropping it
drop only deleted/rebuildable/empty Phase 28 derived state
pass foreign_key_check
support fresh install
support upgrade from current Phase 28 schema
be idempotent under normal migration runner semantics
```

Expected binding deletion under Coverage Path B:

```text
DROP evidence_families
DROP evidence_family_members
DROP evidence_fragility_analyses
DROP attention_items
DROP attention_feedback
DROP hypothesis_gaps
DROP coverage_runs
DROP coverage_items
DROP coverage_summaries
DROP blind_spot_suggestions
```

Add:

```text
attention_decisions
```

Potential Hypothesis-table deletion depends on the 28.5.2B finish/remove gate.

Do not add expectation/Coverage tables.

Do not add a new projection registry.

---

# 51. MEASURED SUBTRACTION BASELINE AND TARGETS

The latest measured fresh-DB baseline was:

```text
120 base tables
126 tables including FTS shadow tables
94 logical-export tables
```

Re-verify before implementation and use the live count as the acceptance baseline.

Under the binding Coverage deletion and minimum Hypothesis-preservation branch, expected table delta:

```text
drop 10 base tables
add 1 attention_decisions table

120 -> 111 base tables
net -9
```

Expected export delta:

```text
remove the 10 dropped tables from export where present
remove entity_merges from export
add attention_decisions

latest measured expectation:
94 -> 84
net -10
```

Expected Phase 28 Job-type delta:

```text
-4
coverage_refresh
evidence_family_rebuild
fragility_analysis
attention_refresh
```

If Hypotheses are removed, report the additional table/route reductions separately.

Do not use migration-source `CREATE TABLE` statement count as the live table baseline.

---

# 52. DELETION INVENTORY

## Runtime/table deletion

```text
coverage_runs
coverage_items
coverage_summaries
blind_spot_suggestions
evidence_families
evidence_family_members
evidence_fragility_analyses
attention_items
attention_feedback
hypothesis_gaps
```

## New persisted table

```text
attention_decisions
```

## Phase 28 Job deletion

```text
coverage_refresh
evidence_family_rebuild
fragility_analysis
attention_refresh
```

## Runtime concept deletion

```text
Phase 28 epistemic Coverage service/API/UI/Ask integration
Evidence Family cache/IDs
Fragility scalar
mutable Attention current-item lifecycle
Blind Spot lifecycle
Hypothesis Gap lifecycle
fake Attention feedback values
fake Research priority components
```

## Navigation deletion/re-parenting

```text
Topics        no Simple top-level nav
Subjects      no Simple top-level nav
Saved         contextual
History       contextual
Documents     Advanced
Runs/Jobs     Diagnostics/Advanced
Workbench     Advanced
Alerts        Home + Settings rather than a competing Simple inbox
```


---

# 53. WHAT MUST NOT BE SIMPLIFIED AWAY

Protect:

```text
Document -> DocumentVersion -> ContentArtifact -> EvidenceSpan -> Claim
accepted Claim/evidence provenance
Story corrections and append-only correction history
story_target_resolution_history
story_entities.authority = 'manual'
report_revision_causes
document_lineage
Ask insufficient_evidence refusal
Ask statement classification:
fact / inference / uncertainty / contradiction / user_hypothesis
counterfactual non-mutation
AIRouter local deterministic fallback
SQLite
SQL/FTS
JobService
integrity framework
existing eval/replay framework
```

No simplification target may weaken those invariants.

---

# 54. STAGE ACCEPTANCE GATES

## 28.5.0 — Truth Safety

```text
Phase 28 epistemic Coverage runtime is gone
Ask contains no Coverage context/citations/statements
Ask with zero grounding evidence refuses even if qualifying context exists
no user-facing language implies an exhaustive search merely from corpus absence
Monitor health uses only schema-valid outcome values
Monitor-health aggregate is bounded
```

## 28.5.1 — Projection Deletion

```text
Evidence Family runtime references are gone except historical migration/ADR text
adding a document_lineage edge changes dependency grouping on the next read
only one dependency-group measure is returned
no Fragility scalar is returned by runtime/API
evidence_fragility_analyses is gone
Counterfactual remains non-mutating and uses canonical anchors
Attention current ranking is computed on read
Attention human decisions persist
no Attention refresh write exists
Seen/Dismiss of one material cause does not suppress a later different cause
Home and Alert acknowledgement semantics agree
```

## 28.5.2 — Lifecycle Consolidation

```text
exactly one canonical Research Gap authority exists
Hypotheses are usable end-to-end or removed
Blind Spot runtime is gone
Research priority contains no constant/fake component
research loop protection includes duplicate suppression and source-class diversity
no naive arbitrary-proposition negation exists
the four Phase 28 Job types are gone
logical export contains reconstruction authority, not deleted/current projections
entity_merges is not presented as a shipped active capability
```

## 28.5.3 — Cockpit Compression

```text
Simple shows <= 6 primary items, target 5
switching mode changes navigation
Settings remains reachable in both modes
all citation/provenance deep links resolve in Simple mode
Home is the only normal "look here" surface
Topics/Subjects are not primary Simple destinations
Monitor health is under the appropriate Diagnostics context
```

## 28.5.4 — Documentation/Tooling

```text
docs/EVALUATION.md reports the true corpus history/count
docs/API/ARCHITECTURE/README match runtime deletions
ruff/backend pytest/frontend typecheck/CI baseline pass
mypy baseline is recorded; touched code adds no new mypy errors
pydantic is direct if required
active plan authority is tracked
```

## 28.5.5 — Validation Readiness

```text
>= 8 substantive permanent semantic cases added
required utility/correction metrics are answerable where canonical data exists
Lite harness runs against the same DB/corpus contract
benchmark contract is frozen before scoring
dogfood environment is explicitly defined
one real Watch is started at acceptance
```

---

# 55. PHASE ACCEPTANCE

## Engineering

```text
all stage gates pass
full backend suite green
frontend typecheck/build according to supported environment
fresh migration succeeds
upgrade migration succeeds
repeat migration is a no-op under the migration runner
PRAGMA foreign_key_check passes
binary backup succeeds
logical Class A/B export -> fresh import succeeds
imported authority passes integrity
no Class C projection is imported as reconstruction truth
```

## Architectural subtraction — HARD PASS/FAIL

Use live pre-phase baseline.

Hard gates:

```text
base persisted tables decrease
expected latest baseline: 120 -> 111 before optional Hypothesis deletion

logical-export tables decrease
expected latest baseline: 94 -> 84

registered Job types decrease by the four Phase 28 types

primary Simple navigation decreases from 16 to <= 6, target 5

persistent authorities per concept are singular

dead/removed routes do not survive

under the narrowed invariant:
no active product-state table/status/Job/feedback value maintained by current
architecture exists without a real reader and writer
```

## Production LOC — REPORTED TARGET, NOT SOLE FAIL GATE

Report:

```text
production Python LOC delta
frontend LOC delta
test/eval/tooling LOC delta
```

A net production-code decrease is expected.

Do not fail the phase solely because added validation/evaluation/tooling makes total raw LOC increase.

Do not game LOC by compressing validation or deleting useful comments/tests.

## Truth — HARD PASS/FAIL

```text
no user-facing assertion exceeds what canonical state supports
no two fields in one response contradict one another
no UI label contradicts behavior
no documentation claim is contradicted by the live repository
no human decision is silently discarded
```

---

# 56. DOGFOOD / BENCHMARK SEQUENCING

Phase 28.5 acceptance starts the dogfood clock.

Phase 29 may begin immediately after 28.5 acceptance.

Phase 29 does **not** wait four weeks.

Phase 30 does not begin until:

```text
the dogfood window is complete enough for a useful report
the frozen Full-vs-Lite comparison has been run
the intelligence-value findings have been incorporated into Phase 29/30 decisions
```

If dogfood is ambiguous, report ambiguity. Do not move goalposts.

---

# 57. PHASE 29 HANDOFF

After Phase 28.5 acceptance, revise Phase 29.

Expected changes:

```text
remove Phase 29.0 because 28.5 completed it
remove Phase 28 Coverage projection work entirely
remove Evidence Family/Fragility/Attention projection lifecycle work that no longer exists
defer generalized Shadow Reprocessing / Belief Diff to Phase 31+ unless dogfood
produces evidence that it is needed
retain only a narrow change-cause / processing-identity requirement where it
provides immediate explanatory value
keep the three-class persistence classification as a static authority/rebuild
discipline, not a generic framework
move true knowledge-time semantic cases into Phase 29A:
    belief at T1 vs T2
    as-of knowledge queries
    historical Ask
    un-confirmation as a knowledge-time question
keep Job/backfill consolidation, retention, recovery, workload envelope,
and other production-hardening work only at the scale justified by the smaller
post-28.5 architecture
```

Full-vs-Lite intelligence validation must report before Phase 30.

---

# 58. DELIBERATE DEFERRALS

Explicitly deferred:

```text
seed Source catalog
Watch templates
backfill-on-Watch-create
intent-first onboarding wizard
diff-first Reports
installer/packaging
external notification delivery
primary-source connector expansion
tag-authority merge
Story-resolver consolidation unless divergence test finds a correctness bug
Entity merge workflow
retention/purge architecture
broad knowledge-time model
shadow reprocessing
vector search
```

These are deferred, not forgotten.

Do not use Coverage deletion to pull any of them forward.

**Freed scope makes 28.5 smaller and finishes the dogfood-start gate sooner.**

---

# 59. REQUIRED IMPLEMENTATION DISCIPLINE

Before editing each checkpoint:

```text
inspect live readers/writers
inspect schema constraints
inspect tests that encode old behavior
inspect export/integrity/API/frontend references
```

Before dropping a table:

```text
count rows
identify Class A/B vs Class C data
identify human decisions
identify every reader/writer
identify foreign-key/migration ordering
identify frontend/API compatibility
```

Do not silently lose human decisions.

Do not preserve dead runtime merely because tests currently reference it.

Do not create a new subsystem to replace a subsystem whose safest replacement is deletion.

After every 2–3 coherent capabilities, checkpoint after focused validation rather than accumulating another Phase 28-sized single commit.

---

# 60. COMPLETION REPORT

Report:

```text
starting branch / HEAD / schema / worktree state
final HEAD / schema / worktree state
checkpoint commits
exact tables removed/added
exact Job types removed
exact routes removed
exact navigation before/after
production/test/frontend LOC deltas
Coverage deletion confirmation
ADR preserving Coverage ontology/rationale
Attention final identity/fingerprint semantics
Attention decision migration counts
Evidence Family deletion confirmation
dependency-group terminology/API changes
Fragility scalar/table deletion confirmation
Counterfactual anchor API
Research Gap migration counts
Hypotheses finish/remove decision and rationale
Blind Spot row counts before deletion
reviewed human-decision preservation result
Monitor-health predicate/bound fixes
tests deleted/rewritten and what incorrect behavior they previously asserted
new permanent eval cases
tooling/CI results
mypy baseline
Class A/B export/import results
dogfood contract:
    DB/profile
    Watch subject
    Sources
    provider/model/budget
    start date
    owner
    backup policy
Lite frozen benchmark contract
remaining known limitations
```

Do not report a capability as complete because a schema/table/handler exists.

For user-facing capabilities, distinguish:

```text
data model
service
API
frontend
end-to-end workflow
measured product value
```

Those are different completion levels.

---

# 61. FINAL ACCEPTANCE QUESTION

Phase 28.5 is successful if it leaves Newsroom:

```text
more truthful
less stale
smaller
clearer
more testable
more honest about uncertainty
```

It is not successful merely because the suite is green.

The intended result is:

> **Less Newsroom, with the proven parts stronger.**
