# PHASE 28 — INTELLIGENCE QUALITY AND EXPERIENCE

## Phase 27 Reconciliation, Observation/Coverage, Source Robustness, Evidence Fragility, Attention, Simple/Advanced Experience, and Safe Analysis

---

# 0. PHASE STATUS AND AUTHORITY

Phase 27 is complete and accepted with bounded reconciliation edits.

Phase 28 is the next permitted implementation phase.

Active forward planning authority:

```text
G:\Projects\Newsroom -v2\plan\phases-v2\
```

Binding inputs:

```text
plan/phases-v2/Phase 27.md

plan/phases-v2/Strategic Architecture Review.md

plan/phases-v2/Final Architecture Reconciliation Memo.md

Phase 27 completion report

Phase 26 → Phase 27 codebase comparison/review
```

The live repository is always the implementation authority.

Do not assume a starting commit SHA.

Before implementation inspect:

```text
current branch
current HEAD
git status
migration registry
current schema
recent commits
existing Phase 27 implementation
existing tests
current frontend
current evaluation subsystem
```

The accepted Phase 27 completion reported schema version 31, but verify the live repository.

---

# 1. PHASE STRUCTURE

Phase 28 contains three mandatory internal checkpoints:

```text
PHASE 28.0
Phase 27 Reconciliation Gate

        ↓

PHASE 28A
Observation and Source Robustness

        ↓

PHASE 28B
Intelligence Experience and Safe Analysis
```

Do not begin 28A until 28.0 passes.

Do not allow 28A analytical results to influence Attention, Hypotheses, qualified absence, or user-facing intelligence until the relevant 28A acceptance gates pass.

Do not begin 28B unless the foundational Source/Coverage semantics it consumes are stable.

---

# 2. FINAL PHASE OBJECTIVE

Phase 28 should make Newsroom substantially better at answering:

```text
What actually changed?

How strong is the evidence?

How much of the apparent corroboration is genuinely distinct?

What did Newsroom actually observe?

What did Newsroom fail to observe?

What remains unknown because coverage is incomplete?

Which conclusions are fragile?

What deserves my attention?

What should Newsroom investigate next?
```

The phase should also make the product easier to operate by introducing an attention-first experience and Simple/Advanced disclosure without creating two intelligence engines.

The central transition is:

```text
Phase 27:
correct Story interpretation

Phase 28:
judge the quality, coverage, robustness,
and user significance of that interpretation
```

---

# 3. NON-NEGOTIABLE ARCHITECTURAL PRINCIPLES

Preserve:

```text
canonical evidence provenance

immutable ContentArtifacts

DocumentVersion history

verified EvidenceSpans

ClaimEvidence provenance

accepted Claim semantics

correctable Story membership

append-only Story correction history

durable JobService orchestration

shared SQL/FTS retrieval

bounded provider use

human authority over consequential mutation
```

Phase 28 analytical objects must not create an alternate factual truth path.

The hierarchy remains:

```text
canonical evidence
        ↓
Claims
        ↓
Stories / Questions
        ↓
derived intelligence
```

Coverage, dependency, fragility, blind spots, Attention, and Hypotheses are derived intelligence.

They do not become factual Evidence merely because they are persisted.

---

# 4. PHASE 28.0 — PHASE 27 RECONCILIATION GATE

Before implementing Source/Coverage Intelligence, fix the bounded Phase 27 edge cases identified in direct snapshot review.

These are not a redesign.

They are correctness repairs needed so Phase 28 does not build analytical conclusions on ambiguous operational state.

---

# 5. 28.0A — DURABLE CORRECTION RECONCILIATION FAILURE

Audit the current Story correction reconciliation Job.

The Phase 27 implementation currently permits downstream failures to be converted into deferred/result metadata while the owning Job can still appear successful.

This is unsafe.

Required invariant:

> A committed Story correction may survive downstream failure, but the downstream reconciliation obligation may not disappear.

A temporary failure in:

```text
Living Report reconciliation
Question reevaluation
Monitor reconciliation
search/projection reconciliation
other required downstream work
```

must remain durably retryable.

Use existing JobService.

Preferred solutions include:

```text
one correction reconciliation Job
with durable checkpoint/continuation state
```

or:

```text
correction reconciliation Job
        ↓
durable child Jobs for independent downstream obligations
```

Choose based on existing Job architecture.

Do not create a second orchestration framework.

---

# 6. 28.0B — NO SILENT RECONCILIATION TRUNCATION

Audit all Phase 27 correction reconciliation limits.

Known reported behavior requires inspection around limits similar to:

```text
first 50 Reports
first 100 affected Claims
```

No required downstream reconciliation may silently stop because a hard-coded batch limit was reached.

Allowed designs:

```text
cursor continuation

bounded pages with durable next checkpoint

multiple deterministic Job batches

explicit product-level operation limit
```

Not allowed:

```text
process first N
mark complete
ignore remainder
```

Every committed correction must eventually reconcile all required affected current state.

---

# 7. 28.0C — CORRECTION-AWARE REPORT CAUSALITY

Audit how Story corrections create or trigger new Living Report revisions.

A Story correction is not automatically:

```text
new world evidence
```

Moving an existing Claim between Stories must not be described as a new material evidence arrival unless new evidence actually caused the correction.

Preserve:

```text
story_correction.id
cause_class
exact caused_by reference
```

through Report reconciliation.

ReportRevision causality should be able to distinguish:

```text
new evidence

Story organizational correction

reprocessing

administrative repair
```

without weakening its current canonical Claim grounding.

---

# 8. 28.0D — CORRECTION-AWARE ALERT SEMANTICS

Alerts must continue to arise through valid Alert rules and Report causality.

A purely organizational Story correction should not accidentally produce a factual "new evidence" Alert.

If a new ReportRevision is caused primarily by a Story correction:

```text
Alert reason
must reflect correction/material organizational change
```

where existing Alert semantics support it.

Do not introduce a separate correction notification engine.

---

# 9. 28.0E — MERGE PREVIEW CURRENT-STATE FINGERPRINT

Phase 27 merge stale protection using only Story timestamps is insufficient.

A Claim can change membership without necessarily changing the Story's `updated_at`.

Implement a deterministic expected-current-state fingerprint for merge preview.

The fingerprint should cover enough current state to protect the actual decision, including at least:

```text
source current Claim membership

destination current Claim membership

current revision identity where relevant

manual metadata selected for propagation

Watch consequences if they affect the approved operation
```

The exact representation may be:

```text
stable hash

membership version

expected ID set

combined fingerprint
```

Re-read inside the mutation transaction.

If materially stale:

```text
reject
require refreshed preview
```

Do not execute Claims the user never previewed.

---

# 10. 28.0F — WATCH/MONITOR MERGE COLLISIONS

Fix canonical merge behavior when both source and destination already have Story-targeted Watches or Monitors.

Required product semantics:

If no destination collision:

```text
source Watch
→ follows canonical destination
```

If destination already has equivalent Watch intent:

```text
destination Watch remains operational

source Watch becomes historical/redundant
or otherwise explicitly non-operational

historical target preserved

no active Watch remains operationally pointed at archived Story
```

Similarly for Monitors:

```text
no redundant enabled Monitor
may continue acting on archived merged Story
```

Preserve historical Monitor scope.

Do not silently duplicate acquisition work.

---

# 11. 28.0G — SPLIT WATCH RESOLUTION WORKFLOW

Phase 27 correctly persists:

```text
needs_review
```

after a Story split.

Phase 28.0 must add a supported resolution workflow.

User must be able to choose:

```text
child A

child B

both

another valid Story target

disable Story targeting
```

as permitted by existing Watch semantics.

Provide:

```text
service operation

API

frontend workflow

history
```

Resolution must update current operational monitoring while preserving the historical split target.

---

# 12. 28.0H — COMPOSITIONAL STORY LINEAGE RESOLUTION

Story lineage must compose across multiple corrections.

Example:

```text
B merged_into A

later:

A split_into C
A split_into D
```

Current resolution of B must not stop at archived Story A.

Desired current resolution:

```text
B
→ historical A
→ current result set {C, D}
```

Likewise:

```text
split child later merged
```

must resolve through its later merge.

Implement deterministic recursive/iterative lineage resolution:

```text
active Story
→ itself

merged Story
→ resolve merge destination

split Story
→ union recursively resolved children
```

Preserve historical lineage path for explanation.

Prevent cycles.

Do not introduce a generic graph engine.

---

# 13. 28.0I — SYMMETRIC DUPLICATE IDENTITY

Duplicate suggestion identity must be independent of query direction.

For Story pair:

```text
A, B
```

the same unchanged evidence must produce one logical suggestion identity whether the user starts from A or B.

Canonicalize:

```text
Story pair

Claim-set mapping

evidence fingerprint
```

by stable Story identity rather than source/candidate orientation.

A dismissal must suppress the same unchanged pair from either direction.

Materially changed evidence may create a new reviewable suggestion.

---

# 14. 28.0J — EXPLICIT MERGE DESTINATION

Duplicate approval must not choose a canonical Story merely because one ID sorts earlier.

The user must explicitly approve:

```text
B → A
```

or:

```text
A → B
```

The preview should explain which Story becomes canonical.

Duplicate suggestion is:

```text
These appear to represent the same Story.
```

It is not:

```text
The lexicographically larger Story must win.
```

---

# 15. 28.0K — BOUNDED DUPLICATE CANDIDATE RETRIEVAL

Audit duplicate candidate discovery.

Output `limit=N` is insufficient if implementation scans every active Story and Claim set first.

Reuse existing bounded structured retrieval to obtain a candidate pool before duplicate scoring.

Candidate retrieval may consider:

```text
current Claim proposition terms

current Story Documents

Entities

event/time identity

normalized titles

Research context
```

but candidate generation itself must be bounded.

No vector database.

---

# 16. 28.0L — STORY TAG COMPATIBILITY

Phase 27 merge metadata copy must not directly update only:

```text
story_tags
```

while leaving:

```text
tag_assignments
```

inconsistent.

Route explicit Story Tag propagation through one existing or new internal transactional helper that preserves both representations until Phase 29 simplifies Tag authority.

Add regression coverage.

---

# 17. 28.0M — REAL TEMPORAL STORY EVALUATION

The Phase 27 Story-intelligence metric helpers are not sufficient alone.

Extend the existing permanent `newsroom.evals` system.

Do not create another framework.

Add real service-driven temporal correction scenarios, at minimum:

```text
wrong automatic assignment
→ human reassignment

manual unassignment
→ stale automatic replay

merge
→ later split

historical Story Document remains
→ current context changes

duplicate dismissal queried from both Story directions

merge preview
→ Claim set changes
→ stale execution rejected
```

Evaluate actual resulting repository state, not hand-authored expected=observed dictionaries.

Historical membership evaluation must preserve ordered transitions, not just set equality.

---

# 18. 28.0N — ASK HISTORY GROUNDING

Audit Ask's current correction/history retrieval.

Add exact packet-grounded context for:

```text
Claim Story transition

Story correction

Story lineage path

current lineage resolution
```

so Ask can answer:

```text
Where did this Claim belong before?

Why was it moved?

What happened after this Story merged and later split?

Which current Stories descend from this historical Story?
```

from persisted history.

Do not infer historical reason from semantic similarity.

---

# 19. 28.0O — SOURCE TERMINOLOGY CLEANUP

Before building Source Robustness, eliminate misleading terminology in touched/current user-visible areas.

Binding semantics:

```text
distinct_source_count
= unique Source records

lineage_group_count
= groups under current document-lineage model

evidence_family_count
= groups under Phase 28A dependency model
```

Avoid:

```text
independent_source_count
```

unless independence is explicitly defined by a dependency model.

Audit:

```text
StoryEvolution

Reports

Research Question criteria

Workbench

frontend

Ask

API

docs
```

Where schema migration would be unnecessarily disruptive, preserve compatibility internally but correct API/UI semantics.

---

# 20. 28.0P — LOGICAL EXPORT CLEANUP

Audit Phase 27 logical export.

Transaction-only authorization structures such as:

```text
story_transition_authorizations
```

must not be treated as canonical durable export state.

If such a table is required only as an in-transaction guard:

```text
exclude it from logical export
```

and assert it is empty outside authorized mutation boundaries.

---

# 21. 28.0Q — DOCUMENTATION STATUS

Update stale high-level documentation that still identifies obsolete schema/phase state.

Do not rewrite historical implementation plans.

At minimum ensure current README/agent-facing docs cannot mislead future agents into believing Newsroom is still at schema 23 or an old Phase 27 definition.

---

# 22. PHASE 28.0 ACCEPTANCE

28.0 passes only when:

```text
correction downstream obligations cannot disappear

no required reconciliation silently truncates

Report/Alert causes distinguish correction from new evidence

merge stale Claim-set changes are rejected

Watch merge collisions resolve operationally

split Watch review can be completed

Story lineage composes across later operations

duplicate pair identity is symmetric

merge destination is explicitly chosen

duplicate discovery is bounded

Tag propagation maintains compatibility

temporal correction evaluation uses real workflows

Ask grounds transition/lineage history

Source terminology no longer overclaims independence

transaction-only state is not exported as canonical truth
```

Run focused tests plus relevant full regressions.

Commit 28.0 as one or several coherent checkpoints before starting 28A.

---

# 23. PHASE 28A — OBSERVATION AND SOURCE ROBUSTNESS

## Objective

Phase 28A turns Newsroom from:

```text
a system that knows where evidence came from
```

into:

```text
a system that can explain how well the relevant information
environment was observed and how structurally independent
or fragile its apparent support is
```

It must answer:

```text
What did Newsroom observe?

What should it have observed?

What failed?

What was outside scope?

How many distinct Sources are represented?

How many support paths actually trace to the same evidence family?

What conclusions depend too heavily on one Source/family?

What potentially important blind spots remain?
```

---

# 24. REUSE EXISTING OBSERVATION FACTS

Do not create a second observation ledger.

Existing facts already include at least:

```text
acquisition_events

monitor_activity

Watch health

Monitor scope history

Source profiles

Research Task queries

Research Task findings

Research no-findings outcomes

Jobs/attempts

Source discovery candidates/results

document_lineage
```

Audit live repository before adding schema.

Phase 28A should compose these facts into higher-order Coverage and Source robustness analysis.

---

# 25. OBSERVATION VS COVERAGE

Keep separate:

```text
Observation facts
= what actually happened

Coverage policy
= what should have been observed

Coverage analysis
= comparison between the two
```

Do not make a derived coverage judgment indistinguishable from immutable acquisition history.

---

# 26. COVERAGE SCOPE

Coverage analysis should operate over bounded targets such as:

```text
Watch

Research Question

Story

explicit Ask/research query

possibly Source set
```

Use the smallest common abstraction supported by live code.

Do not force every domain into one giant scope table if existing relations can identify scope cleanly.

---

# 27. COVERAGE RUN / ANALYSIS IDENTITY

Introduce a bounded CoverageRun or equivalent process identity when useful.

It should identify:

```text
target type/id

target scope/version

observation window

expected channels or Source classes

included Sources

excluded Sources + reason

queries attempted

acquisition attempts

successful observations

failed acquisitions

stale inputs

known gaps

completion state

causing Job/Research Task

algorithm/policy version
```

Do not duplicate raw acquisition/monitor rows.

Reference them.

---

# 28. EXPECTED COVERAGE DENOMINATOR

The key missing concept is:

```text
What should Newsroom have observed?
```

Support explicit expected coverage such as:

```text
approved Watch Sources

required primary Source classes

official archive

regulatory filings

known publication channels

Research Task search strategies

user-declared scope

time window
```

Expected coverage should be explainable.

No provider-generated scope automatically becomes binding without approval where it changes user intent.

---

# 29. COVERAGE STATES

Formalize at least:

```text
observed

not_found

not_observed

not_searched

failed_acquisition

out_of_scope

stale
```

Definitions:

## observed

The expected channel was observed successfully.

## not_found

A defined search/observation operation completed but produced no qualifying item.

## not_observed

The expected item was absent from channels actually observed, while wider coverage may remain incomplete.

## not_searched

No relevant search/observation attempt was made.

## failed_acquisition

The channel was attempted but could not be acquired/validated.

## out_of_scope

Explicit policy excluded it.

## stale

Available observation exists but freshness is insufficient for the requested conclusion/window.

Do not collapse these states.

---

# 30. COVERAGE COMPLETENESS

Coverage completeness must be structural/explainable.

Prefer outputs like:

```text
Official archive:
observed through 2026-08-24

Three approved Sources:
3/3 successfully monitored

Primary-source class:
not configured

One Research query:
failed acquisition

Overall:
coverage incomplete
```

Do not manufacture arbitrary confidence percentages.

---

# 31. QUALIFIED NEGATIVE EVIDENCE

Negative conclusions require special care.

Qualified Negative Evidence may be derived only when all relevant conditions are explicit:

```text
expected observation channel exists

expected observation rule is known

adequate coverage threshold/rationale is satisfied

observation window is complete

absence would be meaningful
```

Examples:

```text
expected filing missing from complete official archive

scheduled release absent from fully observed official channel
```

Qualified Negative Evidence is derived analysis.

It is not an EvidenceSpan unless a positive canonical artifact explicitly states the negative fact.

---

# 32. ASK ABSENCE LANGUAGE

Ask must distinguish:

```text
Newsroom has no supporting Claim
```

from:

```text
Newsroom searched relevant scope and found no qualifying evidence
```

from:

```text
Coverage is sufficient to treat this absence as meaningful
```

from:

```text
Newsroom did not observe enough to answer
```

Do not produce:

```text
No such evidence exists.
```

when the actual state is merely incomplete observation.

---

# 33. DOCUMENT LINEAGE AS FOUNDATION

Extend the existing `document_lineage`.

Audit live supported relationships first.

Known existing relationships include:

```text
cites

syndicated_from

wire_propagation

rewritten_from

common_primary_document
```

Do not build a separate parallel Source-dependency graph if these relations can be generalized.

---

# 34. SOURCE DEPENDENCY

Keep separate concepts:

```text
Source reliability

Source dependency

Document dependency

Evidence family
```

Source reliability concerns Source quality/history/type.

Dependency concerns whether apparent support paths ultimately rely on the same underlying material.

A reliable Source may be derivative.

An unreliable Source may be independent.

Do not conflate them.

---

# 35. DEPENDENCY EDGE AUTHORITY

Dependency relationships may originate from:

```text
deterministic canonical URL identity

explicit syndication markers

document lineage

explicit citation/quotation

identical artifact identity

near-identical retained text where repository permits

publication ordering

known Source ownership metadata

user decision

bounded provider suggestion
```

Every inferred dependency should record:

```text
method

algorithm/version

reason/evidence

origin

review state where required
```

High-consequence ambiguous grouping should default to suggestion/review until measured quality justifies more automation.

---

# 36. PROVIDER ROLE

Provider classification may help classify ambiguous dependency.

It must operate behind existing AIRouter:

```text
bounded request

strict structured output

cost telemetry

fallback

no canonical mutation
```

Provider output may suggest dependency.

It does not become canonical evidence.

---

# 37. EVIDENCE FAMILIES

Introduce derived:

```text
Evidence Family
```

Meaning:

> A set of evidence paths that substantially depend on the same originating information/material.

Example:

```text
primary document A

article B quotes A

article C syndicates B

article D summarizes A
```

may form one family.

Separate firsthand confirmation E may form another.

Evidence family identity should be deterministic/rebuildable from the current dependency model where possible.

If persistence is required for performance/history:

```text
record dependency-model version
record input identity
treat current grouping as derived
```

---

# 38. DISTINCT SOURCE VS EVIDENCE FAMILY

Expose both where useful:

```text
distinct Sources: 5

evidence families: 2
```

This is more informative than pretending:

```text
five independent confirmations
```

---

# 39. CORROBORATION

Update corroboration displays/analysis to use precise counts.

Possible output:

```text
6 supporting Documents

4 distinct Source records

2 evidence families

1 direct primary Source
```

Avoid one composite confidence score unless a future evaluated use case justifies it.

---

# 40. EVIDENCE FRAGILITY

Introduce a read-only Evidence Fragility analysis.

Applicable targets may include:

```text
Claim

Research Question

Living Report statement/revision

Story

possibly Ask conclusion
```

For each target report structural dependency such as:

```text
supporting EvidenceSpans

distinct Sources

evidence families

primary-source paths

single-family dependence

unresolved dependency assumptions
```

---

# 41. FRAGILITY OUTPUT

Prefer explainable language:

```text
This Claim has four supporting Documents,
but three trace to the same evidence family.
```

or:

```text
Removing Source X leaves the Claim with one supporting
span from a separate evidence family.
```

Avoid fake numeric confidence.

---

# 42. COUNTERFACTUAL EVIDENCE LAB

Add read-only analysis allowing bounded questions such as:

```text
What if Source X is excluded?

What if Evidence Family Y is excluded?

Which Claims become unsupported?

Which Questions change assessment?

Which Report statements become unsupported?

Which Alerts would no longer have been generated?
```

This is analytical simulation.

It may not mutate canonical current state.

---

# 43. COUNTERFACTUAL NON-MUTATION INVARIANT

Counterfactual analysis must never:

```text
delete Evidence

change Claim state

change current Story membership

resolve a Question

close a Gap

rewrite Reports

retract Alerts

change Watch intent
```

Results are derived disposable or historically bounded analysis.

---

# 44. COUNTERFACTUAL INPUT IDENTITY

Persist/reconstruct enough to explain:

```text
input snapshot

dependency model version

excluded Source/Document/evidence family

target

run time

result
```

Do not retain every exploratory run forever unless product use justifies it.

Phase 29 will formalize retention.

---

# 45. BLIND-SPOT ANALYSIS

Introduce bounded Potential Blind Spot suggestions.

Inputs may include:

```text
persistent failed acquisitions

expected Source class missing

normally active Source silent

coverage gaps

new unmatched terminology

new Entity clusters

large unmatched Document clusters

Source distribution change

important Question with narrow evidence family

high-priority Watch with incomplete primary coverage
```

Blind spots are suggestions, not proof.

---

# 46. BLIND-SPOT BOUNDS

Blind-spot generation must be:

```text
bounded

explainable

deduplicated

replay-safe where persisted

dismissible

non-canonical
```

Do not create an open-ended autonomous web exploration agent.

---

# 47. RESEARCH GAP PRIORITIZATION

Extend existing Phase 25 Research architecture.

Do not create another research task system.

Rank existing Evidence Gaps using explainable factors such as:

```text
Question priority

Gap importance

coverage deficiency

evidence-family fragility

freshness

likelihood of useful result

cost/budget

user priority

known primary Source availability
```

Expose components.

Avoid a mysterious overall intelligence score.

---

# 48. DISCONFIRMING RESEARCH

Reduce confirmation-loop risk.

Research planning should be able to reserve bounded effort for:

```text
contradictory proposition search

alternative terminology

uncovered Source classes

primary-source discovery

different organization/jurisdiction wording

evidence likely to discriminate between explanations
```

Do not impose an arbitrary global percentage.

Plan decisions should be explainable.

---

# 49. RESEARCH LOOP PROTECTION

Existing Phase 25 budgets/cooldowns remain.

Add protections where needed so:

```text
Watch vocabulary
→ Research
→ more same vocabulary
→ same Sources
→ more confirming results
```

does not become an uncontrolled self-reinforcing loop.

Potential safeguards:

```text
alternative query generation

Source-class diversity requirement

duplicate query suppression

coverage-aware stopping

user-visible research rationale
```

---

# 50. SOURCE PROFILES

Extend existing Source profile/intelligence rather than introducing another Source model.

Potential derived fields:

```text
activity

acquisition reliability

duplication rate

evidence-family role

primary/secondary tendency

coverage contribution

dependency patterns

recent failures
```

Keep raw observations distinct from derived assessments.

---

# 51. 28A WORKBENCH

Extend Workbench with Source/Coverage investigation.

Support pivots such as:

```text
Story → Source dependencies

Claim → evidence families

Question → Coverage

Watch → coverage gaps

Source → dependency relationships

Report → Fragility

Evidence family → affected Claims/Stories/Questions
```

Reuse shared retrieval.

---

# 52. 28A ASK

Ask should understand:

```text
How many distinct Sources support this?

How many evidence families?

Are these reports derivative of one another?

What coverage gaps remain?

Did Newsroom actually search the official archive?

What failed acquisition?

How fragile is this conclusion?

What happens if Source X is excluded?
```

Citations must bind to canonical evidence for factual claims and to persisted analytical records for coverage/dependency/fragility explanation.

Do not cite derived analysis as if it were factual Source evidence.

---

# 53. 28A REPORTS

Living Reports should optionally surface concise intelligence robustness annotations:

```text
Evidence basis

distinct Sources

evidence families

important contradiction

important coverage gap

material fragility
```

Do not turn Reports into diagnostic dumps.

Only surface factors that change interpretation.

---

# 54. 28A API

Use existing API conventions.

Add bounded APIs for:

```text
Coverage summary/detail

dependency inspection

evidence-family inspection

Fragility

counterfactual analysis

blind-spot suggestions

research prioritization
```

Do not expose raw provider payloads.

---

# 55. 28A JOBS

Use JobService for durable:

```text
coverage computation where asynchronous

dependency inference/backfill

evidence-family rebuild

blind-spot projection

large fragility analysis

research prioritization refresh
```

Do not create new lifecycle tables that duplicate JobService unless domain history requires them.

---

# 56. 28A PROJECTION CLASSIFICATION

Explicitly classify new state.

Likely:

```text
CoverageRun
= historical process/analysis record

CoverageSummary
= derived current projection

dependency decisions
= mixed derived + human review history

Evidence Family
= derived projection

Fragility result
= derived analysis

Counterfactual result
= derived disposable/history-bounded analysis

Blind Spot
= suggestion/analysis state

Research priority
= derived projection
```

Document authority.

---

# 57. 28A MIGRATION

Create only after live audit.

Avoid speculative Phase 29 processing-provenance schema.

Use the minimum structures needed for:

```text
coverage identity/policy

dependency decision/projection

evidence families

fragility/counterfactual identity where persistence is justified

blind-spot review if persisted
```

Prefer views/projections where practical.

---

# 58. 28A EXPORT

Logical export should preserve:

```text
human coverage policy

human dependency decisions

important analysis history required to explain user decisions
```

Do not necessarily export every rebuildable derived projection.

Document what rebuilds after import.

---

# 59. 28A INTEGRITY

Structural checks should include:

```text
valid dependency references

no invalid dependency cycles where type forbids them

coverage references valid observation facts

evidence family members valid

human review decisions preserved

counterfactual results do not own canonical mutation

qualified negative evidence has required coverage basis
```

Integrity does not judge whether an inferred dependency is editorially "correct."

That belongs in evaluation.

---

# 60. PHASE 28A EVALUATION

Extend existing `newsroom.evals`.

Add/extend temporal scenarios for:

```text
wire syndication

rewritten derivative reports

common primary document

separate firsthand evidence

Source disappears/fails

official Source coverage complete

official Source coverage incomplete

Research search returns no findings

negative evidence valid

negative evidence invalid due incomplete coverage

single-family fragile conclusion

multi-family robust conclusion
```

---

# 61. PHASE 28A INTELLIGENCE METRICS

Measure where practical:

```text
dependency classification correctness

evidence-family grouping correctness

distinct Source terminology correctness

coverage-state correctness

qualified absence correctness

fragility identification correctness

blind-spot usefulness

Research prioritization usefulness
```

Avoid opaque aggregate scores.

---

# 62. PHASE 28A ACCEPTANCE

28A is complete only when Newsroom can reliably distinguish:

```text
five Source records
```

from:

```text
five genuinely distinct evidence paths
```

and:

```text
nothing was found
```

from:

```text
Newsroom did not sufficiently observe the relevant environment
```

and can expose:

```text
coverage

dependency

fragility

blind spots
```

without mutating canonical evidence.

---

# 63. PHASE 28B — INTELLIGENCE EXPERIENCE AND SAFE ANALYSIS

## Objective

Phase 28B turns the expanded intelligence engine into a product centered around user attention rather than domain-object navigation.

The top-level experience should answer:

```text
What materially changed?

What deserves attention?

What remains uncertain?

What should I investigate next?
```

without requiring the user to manually synthesize:

```text
Stories

Questions

Watches

Reports

Alerts

Sources

Coverage

Workbench

Entities

Jobs
```

---

# 64. ATTENTION ENGINE

Introduce a derived cross-domain Attention projection.

Attention candidates may arise from:

```text
material Story development

new contradiction

correction/retraction

new primary evidence

uncertainty reduction

uncertainty increase

important coverage failure

important blind spot

evidence fragility increase

Research breakthrough

high-value unresolved Gap

Watch priority

Question priority

Story materiality

new correction requiring review

split Watch awaiting resolution
```

---

# 65. ATTENTION IS NOT RELEVANCE

Keep separate:

```text
relevant
```

from:

```text
important / deserves attention
```

A Document may be relevant to a Watch but not important.

A Story correction may deserve attention even without new evidence.

A coverage failure may deserve attention despite containing no new article.

---

# 66. ATTENTION REASON CODES

Do not create one opaque LLM score.

Persist/expose reason codes such as:

```text
material_change

new_contradiction

new_primary_source

correction

retraction

coverage_gap

fragile_support

important_research_gap

research_breakthrough

watch_resolution_needed

high_priority_question

alert_followup
```

Ranking may combine factors, but the user must be able to see why something is elevated.

---

# 67. ATTENTION SCORING

Prefer explainable component scoring.

Potential components:

```text
user priority

Story materiality

Claim importance

novelty

uncertainty change

coverage risk

fragility

freshness

actionability

Research priority
```

No provider confidence alone controls ranking.

No single opaque "intelligence score."

---

# 68. ATTENTION PROJECTION

Attention should be rebuildable from authoritative state plus bounded feedback/history.

Classify it as:

```text
derived projection
```

not canonical truth.

If persisted:

```text
record algorithm/version

record reason components

record subject identity
```

---

# 69. TOP-LEVEL EXPERIENCE

Introduce an attention-first Home/Today experience.

Potential sections:

```text
Needs Attention

Material Changes

Important Uncertainty

Investigate Next

Background Activity
```

Do not simply reproduce the Inbox with new labels.

Use the cross-domain Attention projection.

---

# 70. SIMPLE MODE

Introduce Simple mode as the opinionated default experience.

Likely core navigation:

```text
Home / Today

Watches

Stories

Ask

Alerts

Reports
```

Evidence and uncertainty remain available contextually.

Simple mode hides most operational/analytical machinery unless needed.

---

# 71. ADVANCED MODE

Advanced mode exposes deeper investigative surfaces such as:

```text
Workbench

Claim/Evidence provenance

Research Questions

Evidence Gaps

Research Tasks

Source dependency

Coverage detail

Evidence Fragility

Counterfactual Evidence Lab

Entities

Story correction

Competing Hypotheses

automation controls

historical intelligence
```

Advanced is not an admin landfill.

Keep coherent navigation and task context.

---

# 72. ONE ENGINE INVARIANT

There must be exactly one canonical Newsroom engine.

Never create:

```text
Simple pipeline

Advanced pipeline
```

Instead:

```text
canonical engine
        ↓
shared domain data
        ↓
Simple visibility
Advanced visibility
```

Switching modes does not change evidence truth.

---

# 73. VISIBILITY VS AUTHORITY

Keep separate:

```text
Can the user see this feature?
```

from:

```text
Can the system execute this operation automatically?
```

Example:

```text
Competing Hypotheses visible
but generation manual
```

or:

```text
Evidence Fragility automatically calculated
but details hidden until relevant
```

UI mode must not silently escalate automation permissions.

---

# 74. SETTINGS

Use existing settings architecture where viable.

A simple configuration such as:

```text
ui.mode = simple | advanced
```

is sufficient if current settings domain supports it.

Do not introduce a second preference framework.

---

# 75. CONTEXTUAL PROGRESSIVE DISCLOSURE

Simple users should encounter advanced intelligence where relevant.

Examples:

```text
This Story depends mostly on one evidence family.
[Review evidence robustness]
```

```text
Coverage is incomplete.
[See what Newsroom could not observe]
```

```text
Two plausible explanations remain.
[Compare hypotheses]
```

Do not force users to discover these concepts through settings/navigation first.

---

# 76. CAPABILITY RISK CONTRACT

For each advanced capability define:

```text
benefit

consequence

reversibility

scope

provider use

cost

required provenance

default authority

telemetry required for more autonomy
```

Example categories:

```text
automatic

suggest

manual

disabled
```

---

# 77. PROGRESSIVE AUTONOMY

Use Phase 27/28 telemetry.

Autonomy decisions should consider:

```text
operation consequence

reversibility

measured precision

correction rate

sample size

scope stability

cost
```

Examples:

```text
exact deterministic Entity alias
→ automatic

Smart Tag projection
→ automatic

ambiguous dependency edge
→ suggest

Story merge
→ manual

Story split
→ manual

qualified negative evidence
→ suggest/manual

Hypothesis generation
→ manual/gated
```

Provider confidence alone is insufficient.

---

# 78. COMPETING HYPOTHESES

Add as Advanced-optional/experimental.

A Hypothesis is:

```text
an analytical proposed explanation
```

not a factual Claim.

Attach primarily to:

```text
Research Question
```

and optionally Story context.

Possible structure:

```text
hypothesis text

status

origin

user approval state

assumptions

supporting Claims

contradicting Claims

discriminating Claims

generated Evidence Gaps

provider/run identity
```

---

# 79. HYPOTHESIS BOUNDARY

A Hypothesis may not automatically:

```text
become ClaimEvidence

become an accepted Claim

resolve a Question

ground a factual Report statement

trigger a factual Alert
```

Only canonical Claims/Evidence can do those things.

---

# 80. HYPOTHESIS GENERATION

Provider assistance may suggest bounded candidate explanations using AIRouter.

Require:

```text
maximum hypotheses

maximum length

target Question

strict structured output

cost budget

recorded assumptions

no mutation
```

User approval makes a Hypothesis an accepted analysis object, not factual truth.

---

# 81. HYPOTHESIS COMPARISON

Expose a matrix such as:

```text
Hypothesis

Supporting Claims

Contradicting Claims

Unexplained Evidence

Discriminating Evidence Gaps

Coverage limitations
```

Use existing Claims and Research architecture.

Do not duplicate Question/Gaps/Tasks.

---

# 82. HYPOTHESIS-DRIVEN RESEARCH

Approved discriminating Gaps may feed existing Phase 25 Research planning.

They must still pass:

```text
normal budget

cooldown

Source approval

acquisition

analysis

evidence verification

Claim promotion
```

Hypothesis generation cannot create trusted factual evidence directly.

---

# 83. INVESTIGATIVE SHELL

Unify detail UX gradually around a shared pattern:

```text
Header

Current state

Why this matters

Evidence/relationships

Uncertainty

Timeline

Provenance

Actions
```

Specialized panels remain domain-specific.

Examples:

```text
Story
→ Claims / evolution / correction / fragility

Question
→ assessment / hypotheses / Gaps / Tasks / coverage

Source
→ Documents / lineage / dependency / acquisition health

Entity
→ aliases / Claims / Stories / Questions
```

Do not rewrite every frontend screen merely for visual consistency.

---

# 84. REPORTS VS ASK

Preserve:

```text
Living Report
= durable maintained brief

Ask
= ad hoc interrogation
```

Reports should increasingly summarize:

```text
what changed

why it matters

what supports it

what conflicts

what remains uncertain

coverage/fragility only when material
```

Ask handles deeper interrogation.

---

# 85. ALERT VALUE TELEMETRY

Existing exact Alert cause remains.

Add lightweight interaction telemetry such as:

```text
opened

dismissed immediately

Story viewed

evidence viewed

Ask invoked

Question action

explicit useful

explicit irrelevant

duplicate/repeat indication
```

Do not let one interaction signal automatically retrain ranking.

Phase 30 will evaluate utility.

---

# 86. ALERT ATTENTION INTEGRATION

Alerts and Attention are related but not identical.

Attention is the broader ranked workspace.

Alerts are interruptions.

An item may deserve Attention without deserving an Alert.

Preserve existing explicit Alert rules.

Do not replace them with Attention rank alone.

---

# 87. SIMPLE-MODE ALERTS

Simple mode should make Alert cause obvious:

```text
what happened

why this triggered

supporting evidence

uncertainty

what changed since prior state
```

Advanced detail remains available.

---

# 88. ATTENTION FEEDBACK

Allow bounded user feedback such as:

```text
useful

not important

already knew

needs investigation

mute this pattern
```

only if actual product need justifies it.

Feedback is user signal.

It is not canonical truth.

---

# 89. 28B WORKBENCH RELATIONSHIP

Workbench remains Advanced.

Do not duplicate all Workbench capability into Home.

Home answers:

```text
what needs attention
```

Workbench answers:

```text
let me investigate the corpus
```

---

# 90. 28B ASK

Ask should surface 28A context naturally.

Example:

```text
Two distinct Sources support this Claim,
but both currently fall into one evidence family.
```

or:

```text
Newsroom found no contradictory Claim,
but official-source coverage is incomplete.
```

or:

```text
This conclusion is fragile if Source X is excluded.
```

Avoid dumping diagnostics when not material.

---

# 91. 28B PERFORMANCE

Attention/Home must feel responsive.

Benchmark:

```text
Home load

Attention projection refresh

Simple Story list

Ask context expansion

Coverage summary retrieval
```

Do not synchronously run expensive provider analysis on Home load.

Precompute/rebuild where appropriate.

---

# 92. 28B JOBS

Use JobService for expensive derived refreshes.

Potential Jobs:

```text
attention_refresh

hypothesis_suggestion

large fragility calculation

coverage refresh
```

Do not invent a separate frontend analytics daemon.

---

# 93. 28B EXPORT

Preserve:

```text
user mode/preferences

manual capability decisions

approved Hypotheses

Hypothesis review history

important user feedback where product-significant
```

Derived Attention ranking need not be canonical export state if it can rebuild.

Document authority.

---

# 94. 28B INTEGRITY

Integrity should structurally check:

```text
Hypothesis links valid

Hypothesis never masquerades as Claim

Attention references valid objects

capability settings valid

Simple/Advanced setting valid

provider-generated analysis cannot enter ClaimEvidence

manual authority states coherent
```

Do not judge whether an Attention ranking was "good."

That belongs in evaluation.

---

# 95. PHASE 28B EVALUATION

Extend the existing evaluation system.

Do not create a second product benchmark.

Add scenarios where the system must prioritize:

```text
material correction over routine new article

primary-source confirmation over repeated syndication

important contradiction over high-volume corroboration

coverage failure over irrelevant activity

high-value Research result over minor Story update

fragile high-priority Claim over robust low-priority background change
```

---

# 96. TIME-TO-UNDERSTANDING MEASUREMENT

Create bounded evaluation tasks such as:

```text
What materially changed?

What evidence supports it?

What conflicts?

What remains uncertain?

What should be investigated next?
```

Compare the user's required steps/time between:

```text
current object-first workflow

new attention-first workflow
```

Do not require massive formal UX research.

Use reproducible task scenarios.

---

# 97. SIMPLE VS ADVANCED EVALUATION

Use the same engine/data.

Measure whether Simple users can complete core tasks without Advanced mode.

Measure whether Advanced mode materially helps difficult investigations.

Capture:

```text
navigation depth

time to answer

screens used

manual actions

errors

unnecessary complexity
```

---

# 98. PHASE 28B INTELLIGENCE VALUE

At minimum demonstrate:

```text
important developments rise above routine activity

uncertainty is not hidden

coverage gaps are visible when material

evidence-family dependence affects interpretation

blind spots can lead to useful Research

Simple mode reduces cognitive load

Advanced mode remains available without creating a second engine

Hypotheses remain safely non-canonical
```

---

# 99. PHASE 28 CHECKPOINT STRATEGY

Suggested commits/checkpoints:

## Checkpoint 28.0A

```text
durable correction reconciliation

no silent truncation

Report/Alert cause correction

merge fingerprint
```

Validate.

Commit.

---

## Checkpoint 28.0B

```text
Watch/Monitor collision resolution

split Watch resolution workflow

compositional Story lineage

duplicate symmetry

explicit canonical merge destination

bounded duplicate retrieval

Tag compatibility
```

Validate.

Commit.

---

## Checkpoint 28.0C

```text
real temporal correction evals

Ask transition/lineage grounding

Source terminology cleanup

export cleanup

current docs/status
```

Run full 28.0 acceptance.

Commit.

Do not begin 28A until this passes.

---

## Checkpoint 28A-1 — Observation/Coverage

```text
Coverage identity

expected coverage

coverage states

coverage summaries

Ask qualification
```

Validate.

Commit.

---

## Checkpoint 28A-2 — Source Dependency

```text
document lineage extension

dependency inference/review

Source terminology

Evidence Families

corroboration updates
```

Validate.

Commit.

---

## Checkpoint 28A-3 — Robustness

```text
Evidence Fragility

Counterfactual Evidence Lab

blind spots

Research prioritization

disconfirming research
```

Validate 28A Intelligence Value.

Commit.

---

## Checkpoint 28B-1 — Attention

```text
Attention projection

reason codes

Home/Today

material change/uncertainty surfaces
```

Validate.

Commit.

---

## Checkpoint 28B-2 — Simple/Advanced

```text
mode

visibility

contextual disclosure

investigative shell improvements

capability risk contract
```

Validate.

Commit.

---

## Checkpoint 28B-3 — Safe Analysis

```text
Competing Hypotheses

Hypothesis/Claim boundary

Research integration

Alert usefulness telemetry

Attention evaluation
```

Validate.

Commit.

---

## Final Phase 28 checkpoint

```text
migration matrix

export

integrity

replay

recovery

concurrency

performance

full backend suite

frontend validation

evaluation

documentation
```

Commit completion.

Checkpoint boundaries may be adapted to actual repository dependencies.

Avoid microcommit confetti.

---

# 100. CONCURRENCY

Test real SQLite concurrency around new mutable/human decision areas.

At minimum:

```text
dependency review vs automatic inference

Coverage refresh vs Watch scope change

Hypothesis approval vs Question status change

Attention refresh vs Story correction

split Watch resolution vs later Story merge
```

Derived projections may become stale temporarily but must converge.

Human decisions must not be overwritten by stale automatic Jobs.

---

# 101. REPLAY / RECOVERY

Durable Phase 28 Jobs must recover after interruption.

Prove no duplicate:

```text
Coverage summaries

dependency decisions

Evidence Families

blind-spot suggestions

Attention items

Hypotheses

Research Tasks
```

where uniqueness/idempotency applies.

Database uniqueness remains the final boundary.

---

# 102. PERFORMANCE BOUNDS

Benchmark realistic personal-intelligence workload.

At minimum inspect:

```text
Coverage computation

dependency graph traversal

Evidence Family rebuild

Fragility

counterfactual analysis

Attention refresh

Home load

Ask
```

Keep routine operations near-zero cost where practical.

Do not introduce a vector database as a reflexive optimization.

---

# 103. OUT OF SCOPE — PHASE 29

Do not implement broadly:

```text
global processing-run framework

bitemporal knowledge query system

Shadow Reprocessing

Belief Diff

projection registry

global backfill consolidation

retention/deletion architecture

logical restore/import

global event envelope

full SLO architecture
```

Tiny compatibility hooks are acceptable only when required.

---

# 104. OUT OF SCOPE — PHASE 30

Do not implement:

```text
Newsroom Lite

full Full-vs-Lite comparator

multi-week dogfood program

final feature subtraction

release certification
```

Phase 28 may collect telemetry needed by Phase 30.

---

# 105. NO PLATFORM SPRAWL

Do not add:

```text
vector database

hosted graph database

new workflow engine

new event bus

new search platform

new notification provider

new persistent analytics stack
```

without clear measured necessity.

Prefer:

```text
SQLite

existing JobService

existing SQL/FTS

existing AIRouter

existing evaluation framework
```

---

# 106. PHASE 28 ENGINEERING ACCEPTANCE

Phase 28 cannot complete unless:

```text
all Phase 28.0 reconciliation issues are fixed

Coverage states are explicit

observation facts remain distinct from coverage judgment

dependency/evidence-family semantics are explainable

distinct Source count is not called independence

Fragility is read-only

counterfactual analysis cannot mutate canonical state

blind spots are bounded suggestions

Research remains bounded

Attention is derived/explainable

Simple and Advanced use one truth model

visibility does not imply authority

Hypotheses cannot become factual evidence automatically

Jobs/replay/recovery/concurrency work

migration/export/integrity pass

full regressions pass
```

---

# 107. PHASE 28 INTELLIGENCE VALUE ACCEPTANCE

Phase 28 must also show:

```text
syndicated/derivative evidence is not overcounted

coverage gaps qualify conclusions

absence language becomes more epistemically precise

fragile conclusions can be identified

counterfactual exclusion produces useful structural insight

blind spots can improve Research planning

important changes rise above routine activity

Simple mode improves time-to-understanding

Advanced mode preserves investigative depth

Hypotheses improve analysis without contaminating Claims
```

Do not claim broad statistical certainty where evaluation sample is small.

---

# 108. REQUIRED E2E — COVERAGE

Create a Watch with:

```text
multiple approved Sources

one healthy Monitor

one failed acquisition

one explicitly out-of-scope Source class

known observation window
```

Prove Coverage distinguishes:

```text
observed

failed_acquisition

out_of_scope

not_searched
```

Ask must qualify conclusions appropriately.

---

# 109. REQUIRED E2E — SOURCE DEPENDENCY

Create:

```text
primary Document A

syndicated B

rewrite C

separate independent firsthand D
```

Prove:

```text
4 Documents

4 distinct Source records where appropriate

2 evidence families
```

or the correct equivalent under the implemented dependency model.

Explain lineage.

---

# 110. REQUIRED E2E — FRAGILITY

Create a Claim supported by several Documents from one family plus one separate family.

Run exclusion scenarios.

Prove:

```text
counterfactual result changes

canonical Claim/Evidence state does not
```

---

# 111. REQUIRED E2E — QUALIFIED ABSENCE

Use a complete expected official Source/window.

No expected item appears.

Prove qualified negative analysis is available.

Then repeat with incomplete coverage.

Prove the system refuses the stronger negative conclusion.

---

# 112. REQUIRED E2E — BLIND SPOT → RESEARCH

Create a high-priority Question with an important uncovered Source class.

Blind-spot suggestion appears.

User approves/uses it.

Existing Research planning creates bounded work.

Any discovered content goes through:

```text
normal acquisition

Document/Version

analysis

Evidence verification

Claim promotion
```

No alternate evidence path.

---

# 113. REQUIRED E2E — ATTENTION

Create simultaneous events:

```text
routine relevant article

material Story correction

major contradiction

Source acquisition failure

important Research finding
```

Prove Attention ranks/explains the important items and preserves reason codes.

---

# 114. REQUIRED E2E — SIMPLE / ADVANCED

Using identical database state:

```text
Simple mode
```

must support core monitoring/investigation.

Switch:

```text
Advanced mode
```

and verify deeper tools appear.

Canonical records remain identical.

No reprocessing occurs merely because visibility changed.

---

# 115. REQUIRED E2E — COMPETING HYPOTHESES

Create an unresolved Question.

Generate/approve two hypotheses.

Map existing Claims:

```text
supports

contradicts

discriminates
```

Create one discriminating Gap.

Prove:

```text
Hypotheses do not become Claims

Question does not resolve automatically

Research follows existing Phase 25 path

only verified promoted Claims affect factual assessment
```

---

# 116. REQUIRED VALIDATION

Before completion run all applicable:

```text
focused 28.0 tests

Phase 27 Story correction regressions

Coverage tests

dependency/evidence-family tests

Fragility/counterfactual tests

Research tests

Attention tests

Simple/Advanced tests

Hypothesis boundary tests

Ask tests

Report/Alert tests

migration fresh

migration upgrade

migration repeat

foreign keys

integrity

compileall

full backend test suite

frontend typecheck

frontend production build

evaluation corpus

new temporal scenarios

performance checks

replay/recovery/concurrency
```

Do not claim success for a test not actually run.

---

# 117. DOCUMENTATION

Update:

```text
docs/ARCHITECTURE.md

docs/API.md

docs/EVALUATION.md

README/current status

plan/phases-v2/README.md
```

where appropriate.

Clearly document:

```text
distinct Source vs evidence family

Coverage semantics

Qualified Negative Evidence

Fragility

Attention

Simple/Advanced

Hypothesis != Claim
```

Do not rewrite historical plans.

---

# 118. FINAL REPORT FORMAT

At completion provide exactly these sections.

## 1. Verdict

Choose exactly one:

```text
PHASE 28 COMPLETE AND COMMITTED — PHASE 29 READY

PHASE 28 CORRECTED AND COMMITTED — PHASE 29 READY

PHASE 28 INCOMPLETE — PHASE 29 BLOCKED
```

---

## 2. Starting Repository State

Report:

```text
branch

actual starting HEAD

starting schema

tracked/untracked state
```

Do not predict starting SHA.

---

## 3. Phase 28.0 Reconciliation

Report each bounded Phase 27 issue and exact resolution.

---

## 4. Correction Reconciliation Reliability

Report:

```text
durable retries

continuation/batching

Report/Question failure behavior

no silent truncation
```

---

## 5. Story Lineage / Watch Resolution

Report:

```text
compositional lineage

merge collisions

split resolution

history
```

---

## 6. Duplicate Story Reconciliation

Report:

```text
symmetric identity

bounded retrieval

explicit canonical target

dismissal behavior
```

---

## 7. Phase 27 Evaluation Corrections

Report real temporal correction scenarios and observed results.

---

## 8. Observation / Coverage

Report:

```text
model

states

expected denominator

Coverage runs/summaries

Ask integration
```

---

## 9. Source Dependency

Report:

```text
existing lineage reused

new dependency logic

human/provider authority

terminology
```

---

## 10. Evidence Families

Report grouping semantics and rebuild behavior.

---

## 11. Evidence Fragility

Report supported targets, calculations, explanations.

---

## 12. Counterfactual Evidence Lab

Report input identity, non-mutation, outputs.

---

## 13. Qualified Negative Evidence

Report coverage requirements and safety behavior.

---

## 14. Blind Spots

Report signals, bounds, review behavior.

---

## 15. Research Prioritization

Report Phase 25 reuse and disconfirming exploration.

---

## 16. Attention Engine

Report:

```text
reason codes

ranking factors

projection authority

Home integration
```

---

## 17. Simple / Advanced

Report:

```text
shared engine

navigation

visibility rules

settings

progressive disclosure
```

---

## 18. Capability Risk / Progressive Autonomy

Report policies and telemetry use.

---

## 19. Competing Hypotheses

Report:

```text
data model

Claim boundary

Research integration

provider bounds
```

---

## 20. Reports / Alerts

Report Coverage/Fragility/Attention integration and Alert telemetry.

---

## 21. Workbench / Ask

Report investigative and grounded analytical behavior.

---

## 22. API

List significant APIs.

---

## 23. Frontend

Report significant surfaces/workflows.

---

## 24. Migration

Report:

```text
starting schema

ending schema

fresh

upgrade

repeat

FK
```

---

## 25. Export / Integrity

Report authority and reconstruction behavior.

---

## 26. Concurrency / Idempotency / Recovery

Report real tested scenarios.

---

## 27. Evaluation / Intelligence Value

Report:

```text
existing corpus

new temporal cases

Source/dependency metrics

Coverage metrics

Fragility

Attention

Simple/Advanced outcomes
```

---

## 28. Performance

Report representative latency/cost results.

---

## 29. Tests

Report exact focused/full counts.

---

## 30. Validation

Report:

```text
compileall

backend

frontend typecheck

frontend build

migration

integrity

evaluation

performance
```

---

## 31. Files Changed

List meaningful files.

---

## 32. Commits

List actual Phase 28 commits.

---

## 33. Repository State

Report:

```text
branch

final HEAD

index

tracked worktree

preserved unrelated files

ahead/behind if inspected

push status
```

Do not push.

---

## 34. Deferred Work

List Phase 29 and Phase 30 work deliberately not implemented.

---

## 35. Phase 29 Readiness

State whether Phase 29 may begin.

---

# 119. FINAL IMPLEMENTATION PRINCIPLE

Phase 28 should leave Newsroom able to distinguish:

```text
what was observed
```

from:

```text
what should have been observed
```

and:

```text
how many Sources repeated something
```

from:

```text
how many genuinely separate evidence paths support it
```

and:

```text
no evidence was found
```

from:

```text
coverage was sufficient for meaningful absence
```

while helping the user see:

```text
what changed

what matters

what remains uncertain

what deserves investigation
```

without creating a second truth system or an overwhelming interface.

The end state should be:

```text
canonical evidence
        ↓
Claims / Stories / Questions
        ↓
Coverage + Source robustness
        ↓
Fragility + blind spots + Research
        ↓
Attention
        ↓
Simple / Advanced experience
```

with:

```text
Hypotheses
Counterfactuals
Attention
Coverage
Fragility
```

remaining analytical layers rather than factual evidence.

Proceed codebase-first, fix Phase 27 reconciliation before building Phase 28A, preserve bounded provider use, reuse existing domain and Job infrastructure, validate Intelligence Value separately from Engineering Acceptance, and do not pull Phase 29 or Phase 30 architecture forward.