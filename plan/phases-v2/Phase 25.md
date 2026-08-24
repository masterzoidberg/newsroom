# PHASE 25 — AUTONOMOUS RESEARCH

## Research Questions, Evidence Gaps, and Bounded Research Pursuit

---

# 0. PHASE 24 RECONCILIATION

Phase 25 begins from the **actual completed Phase 24 architecture**, not from the earlier conceptual assumptions.

Before implementation, verify the current repository and current HEAD.

Do not assume a specific starting commit SHA.

The accepted Phase 24 architecture establishes the following important facts.

## 0.1 Watch and Monitor are separate concepts

Phase 24 resolved the monitoring architecture as:

```text
Watch
= durable user monitoring intent

Monitor
= durable acquisition / scheduling obligation
```

Approved Watch Sources are represented through Watch-Source relationships and ordinary per-need Source Monitors.

Conceptually:

```text
Watch
  ↓
Watch-Source relationship
  ↓
per-need Monitor
  ↓
existing scheduler/acquisition pipeline
```

A Source may be shared by multiple Watches while each Watch retains its own:

* lifecycle;
* schedule;
* relevance scope;
* vocabulary;
* operational status.

Phase 25 must preserve this architecture.

Do not make Research Questions another acquisition scheduler.

---

## 0.2 Phase 24 vocabulary is reusable infrastructure

Watch vocabulary is persistent and supports:

* primary terms;
* aliases;
* acronym forms;
* acronym expansions;
* related terms;
* include terms;
* exclude terms;
* suggestion origin;
* suggestion approval/rejection.

Provider-assisted vocabulary uses the existing `AIRouter` and existing provider-budget controls.

Provider suggestions remain inactive until approved.

Phase 25 should **reuse this vocabulary** when a Research Question belongs to or is associated with a Watch.

Do not create a second general synonym system for Research Questions.

---

## 0.3 Existing Watch query planning is bounded

Phase 24 implemented conservative deterministic Watch query planning.

The current architecture uses approved vocabulary only and avoids uncontrolled term combinations.

Research planning may build additional bounded queries for one Research Task, but it must not mutate or bypass the normal Watch query planner.

Research queries and continuous Watch queries are separate concepts.

---

## 0.4 Phase 24 Source discovery is corpus-derived

Phase 24 deliberately did not build a crawler.

Current deterministic discovery uses persisted Newsroom signals such as:

```text
existing_source
document_link
feed_discovery
```

where supported by the corpus.

The current content artifact contract does not preserve arbitrary outbound links from every page.

Therefore Phase 25 must not assume Phase 24 provides general web crawling.

---

## 0.5 Phase 25 may add bounded search capability where necessary

Autonomous Research may need a narrow way to identify candidate material beyond the existing corpus.

First inspect the repository for an existing search abstraction or provider-supported search service.

If one exists:

```text
reuse it
```

If no suitable search abstraction exists and Phase 25 cannot satisfy bounded research pursuit without one:

```text
introduce the smallest application-owned search interface
needed for Phase 25
```

That interface must:

* accept bounded structured queries;
* return bounded candidate metadata;
* integrate with existing provider/cost controls where applicable;
* remain separate from Document evidence;
* avoid recursive crawling;
* route candidate material through normal Source/acquisition services before it can influence evidence.

Do not build a general-purpose crawler or web index.

---

## 0.6 Phase 23 remains the downstream trust path

Phase 25 findings must still enter:

```text
Source
→ acquisition
→ Document
→ DocumentVersion
→ ContentArtifact
→ relevance
→ ArticleAnalysis
→ EvidenceSpan
→ Claim
→ Story
→ Report
→ Alert
```

Research planning may expand **where Newsroom looks**.

It does not create another evidence path.

---

# 1. ROLE

Implement **Phase 25 of Newsroom v2** as the bounded autonomous-research layer built on top of:

* the trusted evidence pipeline completed through Phase 23;
* the intelligent monitoring infrastructure completed in Phase 24.

Phase 24 answers:

> "What should Newsroom continuously monitor?"

Phase 25 adds:

> **"What do we still need to know, what evidence would materially change the answer, and can Newsroom pursue those gaps through a finite, auditable research attempt?"**

This is intentionally a large phase.

The entire required Phase 25 product capability must be complete before the phase is declared finished.

---

# 2. CODEBASE-FIRST INSTRUCTION

Before designing or editing Phase 25, inspect the actual repository.

Review at minimum:

* Research Question models;
* Research Question services;
* existing lifecycle/state handling;
* Research Question APIs;
* Research Question frontend;
* Claim relationships;
* Claim state semantics;
* EvidenceSpan relationships;
* Stories;
* Reports;
* Watches;
* Watch vocabulary;
* Watch-Source relationships;
* per-need Monitors;
* Phase 24 Source discovery;
* scheduler;
* Jobs;
* acquisition;
* relevance;
* ArticleAnalysis;
* provider abstractions;
* AIRouter;
* provider budgets;
* search/workbench infrastructure;
* logical export;
* database integrity;
* migrations;
* tests.

This plan defines:

* required product behavior;
* correctness invariants;
* trust boundaries;
* acceptance tests.

It does not prescribe every table, class, or endpoint.

Reuse existing abstractions wherever practical.

Do not duplicate mature systems merely to match the terminology used below.

---

# 3. REPOSITORY STARTING STATE

Assume:

```text
Phase 24 is complete and committed.
```

Do not assume a specific commit SHA.

Before editing:

* inspect current branch;
* inspect current HEAD;
* inspect recent commits;
* inspect tracked worktree state;
* inspect staged state;
* inspect Phase 24 completion documentation;
* inspect any existing Phase 25 work;
* preserve unrelated untracked files;
* do not reset repository history;
* do not rewrite existing commits;
* do not push.

If legitimate Phase 25 work already exists, reconcile and preserve it rather than restarting automatically.

---

# 4. PHASE 25 PRODUCT GOAL

At completion, a user should be able to create a persistent Research Question such as:

```text
Has recovered non-human technology
been scientifically verified by another Source?
```

Newsroom should evaluate the existing trusted corpus:

```text
Research Question
        ↓
eligible related Claims
        ↓
supporting Claims
contradictory Claims
contextual Claims
        ↓
current structured assessment
        ↓
Evidence Gaps
```

For example:

```text
Current evidence:
- Claim A reports alleged recovered material.
- Claim B reports testing occurred.

Contradictory evidence:
- Claim C disputes the reported provenance.

Open gaps:
- primary technical documentation
- additional Source record
- named laboratory result
- unresolved contradiction

Assessment:
PARTIALLY_ANSWERED
```

If pursuit is enabled:

```text
Research Question
        ↓
Evidence Gap
        ↓
bounded Research Task
        ↓
corpus-first planning
        ↓
approved Watch Sources
Phase 24 Source discovery
bounded search where required
        ↓
candidate material
        ↓
normal acquisition pipeline
        ↓
trusted Claims
        ↓
Question reevaluation
```

---

# 5. CENTRAL PHASE 25 INVARIANT

The central rule is:

> **Research planning may determine where Newsroom should look. Only canonically processed evidence may determine what Newsroom believes.**

Therefore:

```text
search result
≠ evidence

provider suggestion
≠ evidence

research plan
≠ evidence

Source candidate
≠ evidence

acquired and verified content
→ may produce evidence
```

No research execution path may create accepted factual state directly from search metadata or generated summaries.

---

# 6. FIRST IMPLEMENTATION TASK — AUDIT EXISTING RESEARCH QUESTIONS

Research Questions already exist.

Do not replace them without first understanding their current semantics.

Determine from the codebase:

```text
1. What is a Research Question today?

2. Which states currently exist?

3. What fields represent lifecycle?

4. Can Questions already relate to Claims?

5. Can support and contradiction already be represented?

6. Are Questions directly related to EvidenceSpans?

7. Are Questions related to Stories?

8. Are Questions related to Reports?

9. What existing gap-suggestion behavior exists?

10. Is there an existing research worker or research Job?

11. How are manual Question changes audited?

12. What Question history already exists?

13. Can a Question currently reference a Monitor or Watch?

14. What frontend workflow already exists?

15. Which public API contracts already exist?

16. What export/integrity coverage already exists?
```

Document the final architectural decision in the Phase 25 completion report.

---

# 7. RESEARCH QUESTION PRODUCT MEANING

A Research Question is a durable, answerable intelligence objective.

Examples:

```text
Did agency X publish document Y?

Has organization Z changed its official position?

Was person X present at event Y?

Has a named laboratory published testing results?

What accepted evidence supports program Y before 2010?
```

A Research Question is not:

* a temporary chat message;
* a search query;
* a Story title;
* a generated answer;
* a generic Topic;
* an unlimited instruction to keep searching indefinitely.

---

# 8. QUESTION LIFECYCLE

The desired lifecycle must distinguish concepts equivalent to:

```text
OPEN
PARTIALLY_ANSWERED
SUPPORTED
CONTRADICTED
RESOLVED
STALE / NEEDS_REVIEW
```

Do not blindly add these exact enum names.

Map the required distinctions to the existing Research Question model.

---

# 9. OPEN

A Question is open when there is insufficient qualifying evidence to reach a stronger assessment.

An open Question may still have:

* relevant Claims;
* partial evidence;
* research history.

Open does not mean empty.

---

# 10. PARTIALLY ANSWERED

A Question is partially answered when material evidence exists but one or more important conditions remain unresolved.

Examples:

```text
support exists
+
critical gap remains
```

or:

```text
support exists
+
material contradiction remains
```

---

# 11. SUPPORTED

A Question may be considered supported when qualifying trusted evidence satisfies the configured support criteria.

The state must derive from persisted domain evidence.

Do not derive it from a generated label.

---

# 12. CONTRADICTED

A Question may be contradicted when qualifying Claims explicitly conflict with the proposition being evaluated.

Absence of findings is not contradiction.

---

# 13. RESOLVED

A Question may be resolved when:

* its defined evidence conditions are satisfied; or
* the user explicitly closes it according to existing lifecycle rules.

Resolution should have an inspectable reason.

---

# 14. STALE / NEEDS REVIEW

Only apply staleness where the Question is time-sensitive.

Examples:

```text
Is agency X currently investigating Y?
```

may become stale.

Historical questions may never require staleness.

Do not introduce a universal timer that marks all Questions stale.

---

# 15. QUESTION STATE MUST BE EVIDENCE-GROUNDED

Question state should be calculated from persisted structured inputs such as:

```text
eligible Claims
+
support/contradiction relationships
+
resolution criteria
+
open/satisfied gaps
+
user lifecycle decision
```

Provider output may assist classification of bounded candidates.

It must not become the sole authority for Question lifecycle mutation.

---

# 16. HUMAN AUTHORITY

Explicit user decisions must remain visible and authoritative.

Automation must not silently undo a manual closure, dismissal, or classification.

If current architecture supports separate concepts such as:

```text
user lifecycle
system assessment
```

reuse them.

Otherwise use existing history/origin mechanisms.

Do not create parallel state machines unless necessary.

---

# 17. QUESTION PROPOSITION

A Question should have a stable target meaning.

Preserve the original user text.

If a normalized proposition is useful, it may be stored separately.

Example:

```text
Original:
"Has recovered material been independently tested?"

Normalized proposition:
"Recovered material has been tested by another Source."
```

If normalization is generated automatically:

* persist the result explicitly;
* preserve origin;
* allow inspection;
* do not silently replace the original Question.

Do not require a generated proposition if deterministic evaluation can operate directly from existing fields.

---

# 18. QUESTION SCOPE

A Question may be scoped using existing domain objects such as:

* Watch;
* Topic;
* Subject;
* Story;
* Source set;
* date range;
* location where modeled;
* current entity-like objects supported by the repository.

Do not implement Phase 26 canonical Entities early.

Scope helps retrieval.

Scope does not constitute evidence.

---

# 19. QUESTION ↔ CLAIM RELATIONSHIPS

Research Questions must relate to Claims through explicit persisted relationships.

At minimum the system must distinguish:

```text
supports
contradicts
contextual / relevant
```

Reuse existing relationship types if present.

Only add richer distinctions where the evidence model can support them.

---

# 20. RELATIONSHIP ORIGIN

Automatic Question-Claim relationships should retain compact provenance.

Possible origins include:

```text
user
deterministic
provider-assisted
research_task
```

Persist only structured reason information needed for auditability.

Do not persist model reasoning transcripts.

---

# 21. AUTOMATIC CLAIM LINKING

When trusted Claims enter Newsroom, Phase 25 should identify bounded Research Questions they may affect.

Preferred pattern:

```text
new eligible Claim
        ↓
Watch / Topic / Subject / Story scope
        ↓
bounded Question candidates
        ↓
deterministic relevance signals
        ↓
optional bounded semantic classification
        ↓
Question-Claim relationship
```

Do not compare every Claim with every Question.

---

# 22. CLAIM-LINKING QUALITY

Broad shared terminology must not be enough to create a strong support relationship.

Example:

```text
Question:
Did AARO recover material?

Claim:
AARO published its annual report.
```

Shared subject identity alone does not establish support.

Weak matches may remain contextual or unlinked.

Prefer conservative automatic linking.

---

# 23. MANUAL RELATIONSHIPS

Where supported by the current product, users should be able to:

* attach a Claim;
* correct relationship type;
* remove an incorrect relationship.

Manual decisions must not be silently replaced by automatic classification.

Preserve origin/history.

---

# 24. CURRENT QUESTION ASSESSMENT

A Question should expose structured current state.

Conceptually:

```text
Question:
Has X been verified?

Assessment:
PARTIALLY_ANSWERED

Supporting Claims:
C1
C2

Contradictory Claims:
C3

Open Gaps:
G1
G2

Last evaluated:
timestamp
```

This structured assessment is the source of truth.

Do not generate a full prose answer every time the detail page loads.

---

# 25. QUESTION ASSESSMENT SNAPSHOT

Question evaluation should use a deterministic evidence snapshot.

Possible inputs:

```text
sorted eligible Claim IDs
relationship types
Claim lifecycle/support state
gap state
resolution criteria
```

Use a stable identity or hash where useful.

Expected:

```text
same evidence snapshot
→ no duplicate assessment transition
```

---

# 26. ELIGIBLE CLAIMS

Inspect actual Claim lifecycle semantics.

Only trusted states should influence automatic Question assessment.

Do not allow a provisional or invalid Claim to resolve a Question merely because it exists.

Contradictory Claims should follow the same evidence-quality requirements.

---

# 27. SUPPORT / CONTRADICTION POLICY

Define deterministic state rules.

Conceptually:

```text
qualifying support
+
no material contradiction
+
required gaps satisfied
→ supported / resolved
```

```text
support
+
material contradiction
→ partially answered
+ contradiction gap
```

```text
qualifying contradiction
+
insufficient qualifying support
→ contradicted
```

Map these rules to existing Claim semantics.

Avoid a generic generated "confidence score" as the state machine.

---

# 28. RESOLUTION CRITERIA

Different Questions may need different resolution conditions.

Examples:

```text
Question:
Did agency X publish report Y?

Possible criterion:
one verified primary Source Document
```

versus:

```text
Question:
Has another Source corroborated Claim X?

Possible criterion:
qualifying support from more than one distinct Source record
```

Keep criteria simple and evaluable.

Do not build a general rule language.

---

# 29. DISTINCT SOURCE CAUTION

Phase 25 must not treat distinct Source IDs as proof of editorial independence.

Until Phase 28 Source dependency intelligence exists, use terminology such as:

```text
two distinct Source records
additional Source
second Source
```

Do not represent this automatically as:

```text
independent confirmation
```

unless the repository actually models independence.

---

# 30. QUESTION CRITERIA MODEL

If current Research Questions need richer conditions, add only structured criteria the application can evaluate.

Possible examples:

```text
required_support_count
required_source_count
require_primary_source
require_no_open_contradiction
time bound
```

Reuse existing schema where possible.

---

# 31. DEFAULT CRITERIA

Provide practical defaults based on current Newsroom semantics.

Users should not need to configure detailed epistemic criteria for every Question.

Defaults must remain conservative.

Document them.

---

# 32. QUESTION EXPLANATION

The API/frontend should explain why a Question has its current state using persisted relationships.

Example:

```text
PARTIALLY_ANSWERED

Supporting:
2 accepted Claims
from 2 distinct Source records

Contradictory:
1 accepted Claim

Open gaps:
2
```

Avoid opaque generated paragraphs as the only explanation.

---

# 33. OPTIONAL PROSE SUMMARY

A concise generated assessment summary is optional.

If implemented:

* use only the eligible closed-world Claim set;
* include exact Claim references;
* validate references against retrieved context;
* persist provider provenance;
* avoid regeneration when evidence is unchanged;
* do not permit unsupported factual additions.

Structured assessment remains authoritative.

---

# 34. EVIDENCE GAP PRODUCT MEANING

An Evidence Gap represents:

> **A specific kind of evidence or clarification that would materially improve the Research Question assessment.**

Examples:

```text
Need a primary-source document.

Need support from another Source record.

Need a named laboratory report.

Need confirmation for a specific date range.

Need clarification of conflicting Claims.
```

---

# 35. AUDIT EXISTING GAP FUNCTIONALITY FIRST

Before creating a new Gap model, inspect existing Research Question gap suggestion code.

Determine whether Phase 25 should:

```text
extend existing gap storage
```

or:

```text
introduce a new durable Evidence Gap object
```

Do not create duplicate concepts.

---

# 36. GAP TYPES

Keep the taxonomy small.

Possible types:

```text
missing_primary_source
missing_support
missing_additional_source
unresolved_contradiction
missing_document
missing_date_confirmation
missing_location_confirmation
missing_named_source
stale_evidence
other
```

Only implement types that can be evaluated using current domain data.

---

# 37. GAP CREATION

Prefer deterministic Gap generation.

Examples:

```text
Question requires another Source record
and only one qualifying Source exists
→ missing_additional_source
```

```text
qualifying support
+
qualifying contradiction
→ unresolved_contradiction
```

```text
criterion requires primary Source
but no qualifying primary Source exists
→ missing_primary_source
```

Provider assistance may suggest nuanced candidate gaps.

Generated candidate gaps must be normalized and validated against actual Question state before becoming active.

---

# 38. GAP IDENTITY

Repeated evaluation must converge.

Expected:

```text
same Question
+
same Gap type
+
same target/context
→ one logical active Gap
```

Prefer structured identity over prose-only hashing.

---

# 39. GAP LIFECYCLE

Conceptually support states equivalent to:

```text
open
pursuing
satisfied
dismissed
blocked
```

Map to repository conventions.

---

# 40. GAP SATISFACTION

A Gap becomes satisfied because qualifying evidence now meets its condition.

Not because a Research Task completed.

Therefore:

```text
Research Task completed
+
no qualifying evidence
→ Gap remains open
```

and:

```text
qualifying persisted evidence arrives
→ Gap may become satisfied
```

---

# 41. USER CONTROL OVER GAPS

Users should be able to:

* inspect a Gap;
* dismiss it;
* reopen it where supported;
* pursue it manually;
* inspect past attempts.

Automatic evaluation should respect dismissal.

Do not recreate the same dismissed Gap on every evaluation without materially changed evidence or an explicit reconsideration policy.

---

# 42. RESEARCH TASK PRODUCT MEANING

A Research Task is one finite attempt to pursue one Evidence Gap.

Example:

```text
Question:
Has recovered material been tested?

Gap:
Missing named laboratory report.

Research Task:
Look for material relevant to a named
laboratory analysis using the configured
research scope and limits.
```

---

# 43. RESEARCH TASK IS FINITE

A Research Task must have explicit bounds.

At minimum inspect/configure limits for:

* search queries;
* Source candidates;
* candidate Documents;
* acquired Documents;
* provider calls;
* runtime duration;
* retries;
* discovery depth.

The Task must terminate.

An open Gap may require another future Task.

---

# 44. RESEARCH TASK IDENTITY

Distinguish:

```text
retry/replay of one Task
```

from:

```text
new intentional attempt later
```

Reuse JobService identity patterns.

Do not use one permanent idempotency key that prevents future research attempts.

---

# 45. RESEARCH TASK STATE

Reuse JobService execution state where possible.

The domain still needs to distinguish meaningful outcomes such as:

```text
completed_with_evidence
completed_with_candidates
completed_no_findings
deferred
cancelled
failed
```

Do not create a redundant second Job state machine if structured Job results already provide the distinction.

---

# 46. NO FINDINGS IS SUCCESSFUL EXECUTION

A bounded search that completes and finds no qualifying material is not necessarily an operational failure.

Persist an outcome equivalent to:

```text
completed_no_findings
```

The Gap remains open.

The Question does not become contradicted merely because nothing was found.

---

# 47. RESEARCH PLANNING

A Research Task needs a bounded structured plan.

Potential inputs:

```text
Question
Gap
Question scope
approved Watch vocabulary
approved Watch Sources
Source classes
date range
query limits
candidate limits
```

Planning should be deterministic first.

---

# 48. DETERMINISTIC QUERY GENERATION

Prefer:

```text
Question terms
+
Gap-specific terms
+
approved Watch vocabulary
+
optional date/source scope
```

with bounded variants.

Do not generate every combination of every term.

---

# 49. PROVIDER-ASSISTED RESEARCH PLANNING

If provider assistance materially improves research planning:

* use the existing AIRouter/provider abstraction;
* use existing budget controls;
* send bounded context;
* require structured output;
* validate lengths/counts/categories;
* treat returned planning information as suggestions;
* preserve deterministic fallback behavior.

Provider availability must not be required for basic corpus-first research.

---

# 50. PROVIDER PLANNING OUTPUT

Provider planning output may include bounded fields such as:

```text
query suggestions
preferred Source classes
date constraints
short plan explanation
```

Only predefined application operations may consume this structured plan.

Provider output itself does not mutate Question state or Watch configuration.

---

# 51. RESEARCH EXECUTION ORDER

Research pursuit should prefer:

```text
1. Existing trusted corpus
2. Existing approved Watch Sources
3. Existing Phase 24 Source candidates / approved Sources
4. Bounded external search where required
5. Additional Phase 24 Source discovery
```

Do not pay for broader pursuit before checking existing Newsroom knowledge.

---

# 52. CORPUS-FIRST RESEARCH

Before any external search, inspect persisted:

* Claims;
* EvidenceSpans;
* Documents;
* Stories;
* Reports;
* existing Question relationships.

A Question may already be answerable from material Newsroom has not yet linked to it.

Use existing Search/Workbench/SQL-backed retrieval where appropriate.

---

# 53. WATCH INTEGRATION

When a Question belongs to or is associated with a Watch:

reuse:

* Watch scope;
* approved vocabulary;
* approved Sources;
* per-need Monitor context;
* Phase 24 Source candidates;
* Phase 24 discovery services.

Do not create hidden duplicate Monitors.

---

# 54. WATCH VOCABULARY REUSE

Prefer:

```text
Question terms
+
approved Watch vocabulary
+
Gap-specific temporary terms
```

Temporary Research Task query terms do not automatically become Watch vocabulary.

Persistent vocabulary changes still use Phase 24 approval/provenance behavior.

---

# 55. APPROVED WATCH SOURCES

Research Tasks should preferentially pursue approved Watch Sources when useful.

Normal Watch monitoring must remain independent.

A Research Task failure must not disable or alter Watch monitoring.

---

# 56. SOURCE DISCOVERY REUSE

Use Phase 24 Source discovery rather than creating another discovery engine.

Research may request discovery in the context of a Question/Gap.

Results remain Source candidates according to Phase 24 policy.

---

# 57. EXTERNAL SEARCH INTEGRATION

If bounded external search is required, use or add the smallest supported application abstraction.

Its responsibilities should be limited to:

```text
validated structured query
→ bounded candidate results
→ normalized candidate metadata
→ Source/Document acquisition decision
```

Search output is discovery metadata.

Do not treat result text as trusted evidence.

Do not build broad recursive traversal.

---

# 58. CANDIDATE SOURCE HANDLING

Research pursuit must distinguish:

```text
candidate Source
```

from:

```text
persistent approved Watch Source
```

A Research Task may encounter a useful candidate without automatically adding it permanently to a Watch.

Persistent Watch Source changes continue through Phase 24 domain services.

---

# 59. RESEARCH-ONLY ACQUISITION

Inspect how Source provenance currently works.

If every Document requires a Source record, create or resolve the smallest valid Source representation through existing services.

If the application already supports one-off acquisition without persistent monitoring, reuse that.

Do not weaken Source provenance merely because a Document came from a Research Task.

---

# 60. CANONICAL ACQUISITION CONTRACT

Candidate material that may become evidence must enter:

```text
candidate material
→ Source validation/resolution
→ acquisition
→ Document
→ DocumentVersion
→ ContentArtifact
→ relevance
→ ArticleAnalysis
→ EvidenceSpan
→ Claim
```

Do not introduce a Research Task service that inserts trusted Claims directly.

---

# 61. RESEARCH-SCOPED RELEVANCE

Research-acquired Documents may carry Question/Gap context into relevance evaluation where the existing architecture permits.

This context may answer:

> Why was this Document acquired?

It does not weaken canonical relevance or evidence requirements.

---

# 62. DOCUMENT REUSE

If a Research Task encounters material Newsroom already knows:

```text
reuse existing Document/DocumentVersion identity
```

according to current acquisition rules.

Do not create duplicate content merely because it was encountered by research.

---

# 63. TASK ↔ DOCUMENT PROVENANCE

Persist enough relationship information to answer:

> What material did this Research Task encounter?

Possible states:

```text
candidate
acquired
processed
relevant
irrelevant
produced_claim
```

Use the smallest useful model.

Do not duplicate data already safely represented in durable Job/result relationships.

---

# 64. SEARCH RUN PROVENANCE

If external search is used, retain bounded structured audit information such as:

* Research Task;
* query identity;
* candidate URL/source identity;
* rank/order where useful;
* timestamp;
* resulting Source/Document ID.

Do not persist large raw search responses when not needed.

---

# 65. QUESTION REEVALUATION

New trusted evidence associated with a Question should trigger reevaluation.

Potential triggers include:

```text
eligible Claim added
Claim lifecycle changed
support/contradiction relationship changed
Gap satisfied
Research Task produced qualifying Claims
```

Use durable downstream work where reevaluation is non-trivial.

Avoid expensive provider work inside mutation transactions.

---

# 66. QUESTION EVALUATION JOB

If useful, introduce or reuse a Job concept equivalent to:

```text
research_question_evaluation
```

Identity should derive from:

```text
Question
+
evidence snapshot identity
```

so:

```text
same evidence state
→ one logical evaluation
```

while changed evidence permits another evaluation.

---

# 67. RESEARCH PURSUIT JOB

Likewise, Research Task execution may use a Job equivalent to:

```text
research_question_pursuit
```

only if that cleanly matches current JobService conventions.

Do not add extra Job layers simply to mirror this document.

---

# 68. TASK COMPLETION BOUNDARY

Research execution should not directly set final Question lifecycle based on its original plan.

Preferred architecture:

```text
Research Task completes
→ findings persisted/acquired
→ trusted Claims emerge
→ Question reevaluation runs
→ Question/Gap state changes
```

This protects against stale Tasks and concurrent evidence changes.

---

# 69. STALE TASK RESULT

A long-running Task may begin against snapshot:

```text
H1
```

while current Question evidence becomes:

```text
H2
```

before completion.

The Task should preserve its findings.

Final Question evaluation should use current state.

Do not apply stale lifecycle assumptions from H1 directly.

---

# 70. RESEARCH RESULT CLASSIFICATION

A Task should produce structured counts/results such as:

```text
candidate_material_found
documents_acquired
documents_processed
relevant_documents
new_claims
new_supporting_claims
new_contradictions
new_source_candidates
gap_condition_met
```

Do not define research success purely as:

```text
URLs found > 0
```

---

# 71. RESEARCH PURSUIT POLICY

Each Question should support a pursuit policy equivalent to:

```text
disabled
manual
automatic
```

Reuse existing lifecycle/config conventions.

Possible bounded configuration:

* maximum automatic attempts;
* cooldown;
* allowed search methods;
* provider budget;
* candidate limits.

Default conservatively.

---

# 72. MANUAL PURSUIT

The user must be able to request:

```text
Research this gap now.
```

This creates a bounded durable Research Task.

Manual pursuit is required.

---

# 73. AUTOMATIC PURSUIT

Where enabled:

```text
eligible open Gap
→ bounded Research Task
```

but only when:

* no active Task already exists for that Gap;
* cooldown permits;
* budget permits;
* Question is still eligible;
* Gap is still active.

---

# 74. PURSUIT COOLDOWN

A no-findings Task should not immediately repeat forever.

Conceptually:

```text
completed_no_findings
→ Gap remains open
→ next automatic attempt after cooldown
```

Operational Job retry is separate from a new intentional research attempt.

---

# 75. ONE ACTIVE TASK PER GAP

Unless repository semantics demonstrate a better invariant:

```text
one active Research Task
per Question + active Gap
```

Use database identity and/or Job idempotency.

Do not rely only on check-then-insert.

---

# 76. RESEARCH QUEUE BOUNDS

Automatic scheduling must be bounded.

Define practical limits for:

* Questions evaluated per scheduler cycle;
* Research Tasks created per scheduler cycle;
* active Tasks per Question;
* global active Research Tasks.

Reuse existing scheduler/Job limits where possible.

---

# 77. TASK RESOURCE LIMITS

Each Task must have limits for applicable operations:

```text
query count
provider-call count
candidate count
Document acquisition count
retry count
duration
```

Reuse Phase 24 and existing provider-budget infrastructure.

---

# 78. RESEARCH COST CATEGORY

Where existing budget infrastructure supports categorization, make Research pursuit cost identifiable.

Useful audit information includes:

```text
search operations
provider calls
Documents acquired
Claims produced
approximate provider cost
```

Do not build full Phase 29 analytics.

---

# 79. TASK REPLAY

Retry of one logical Task must not duplicate:

* Documents;
* Source candidates;
* Question-Claim relationships;
* Gaps;
* Claim relationships;
* downstream evidence.

Use canonical acquisition and database identity.

---

# 80. NEW INTENTIONAL ATTEMPT

A later manual rerun is a new logical Task.

Preserve old Task history.

Do not overwrite earlier no-findings attempts.

---

# 81. CONCURRENT QUESTION EVALUATION

Two workers evaluating the same Question snapshot should converge on:

```text
one logical assessment transition
one logical set of active Gaps
```

Use snapshot identity and database constraints.

---

# 82. CONCURRENT GAP CREATION

Two workers identifying the same logical Gap must produce one active Gap.

Use structured uniqueness.

---

# 83. QUESTION HISTORY

Preserve meaningful lifecycle evolution.

The user should be able to inspect:

```text
OPEN
→ PARTIALLY_ANSWERED
→ CONTRADICTED
→ RESOLVED
```

where that sequence actually occurred.

Do not rewrite historical assessments.

---

# 84. AUTOMATIC TRANSITION HISTORY

Automatic transitions should retain:

```text
previous state
new state
reason code
evidence snapshot identity
relevant Claim IDs where useful
timestamp
origin
```

Do not persist provider reasoning transcripts.

---

# 85. MANUAL TRANSITION HISTORY

Manual state changes must remain distinguishable.

Automation must not erase manual history.

---

# 86. QUESTION + STORY INTEGRATION

A Question may relate to a Story.

Research-acquired Claims must still use normal Story resolution.

Do not assign them directly to the Question's Story.

---

# 87. QUESTION + REPORT INTEGRATION

Where Reports already reference Research Questions or gaps, preserve that integration.

Phase 25 may expose:

* open Questions;
* resolved Questions;
* critical Gaps;

where useful.

Do not redesign LivingReport wholesale.

Historical ReportRevisions remain immutable.

---

# 88. QUESTION + ALERT INTEGRATION

Do not create a new Alert engine.

If existing Alert infrastructure can consume deterministic Question events such as:

```text
Question resolved
material contradiction added
```

integrate conservatively through existing cause/audit conventions.

Do not broaden Phase 25 into Alerting v2.

---

# 89. FRONTEND PRODUCT GOAL

Phase 25 must provide a functional Research Question workspace.

The user should be able to:

* create a Research Question;
* inspect current assessment;
* inspect supporting Claims;
* inspect contradictory Claims;
* inspect contextual Claims;
* inspect open/satisfied/dismissed Gaps;
* pursue a Gap;
* configure pursuit policy;
* inspect Research Task history;
* inspect findings;
* dismiss/reopen Gaps where supported;
* manually correct Question relationships where allowed;
* navigate evidence provenance.

Visual redesign may wait.

Functional research workflow may not.

---

# 90. QUESTION LIST UI

Provide a bounded list.

Useful filters may include:

```text
state
Watch
Story
pursuit policy
has open gaps
recently updated
```

Use existing frontend/API patterns.

---

# 91. QUESTION DETAIL UI

At minimum display:

```text
Question text
current assessment
last evaluated
scope
pursuit policy
supporting Claims
contradictory Claims
open Gaps
Research Task history
related Documents/Sources where useful
```

Claims should navigate into existing provenance surfaces.

---

# 92. GAP UI

For each Gap display:

```text
type
description
status
why it exists
last pursued
attempt count
pursue now
dismiss/reopen where supported
```

Generated suggestions should be visually distinguishable from persisted evidence state where relevant.

---

# 93. RESEARCH TASK UI

Show:

```text
Task status
scope
queries/search strategy summary
Sources searched
candidate count
Documents acquired
Claims produced
Question impact
provider/cost summary where available
```

Do not expose raw provider payloads.

---

# 94. FRONTEND OPERATIONAL STATES

Distinguish useful states such as:

```text
waiting
running
processing acquired Documents
completed with evidence
completed with candidates only
completed with no findings
provider unavailable
search unavailable
budget unavailable
cancelled
failed
Question changed during Task
```

Do not collapse all of these into a generic error.

---

# 95. API REQUIREMENTS

Use existing `/api/v1` conventions.

The API should support equivalents of:

## Research Questions

```text
list
detail
create
update
manual lifecycle action where allowed
archive/delete according to domain rules
```

## Question relationships

```text
supporting Claims
contradictory Claims
contextual Claims
related provenance
```

## Evidence Gaps

```text
list
detail
dismiss
reopen where supported
```

## Research Tasks

```text
pursue now
list
detail/status
rerun/new attempt
cancel where supported
```

## Pursuit policy

```text
inspect
update
```

Avoid endpoint proliferation where existing nested routes are cleaner.

---

# 96. API BOUNDS

Every collection must be bounded.

Apply this to:

* Questions;
* Claims per Question;
* Gaps;
* Research Tasks;
* Task Documents;
* Source candidates;
* task history.

---

# 97. API PROVENANCE

Expose stable IDs sufficient to navigate:

```text
Question
→ Claim
→ EvidenceSpan
→ Document
→ Source
```

and:

```text
Research Task
→ Gap
→ search/discovery activity
→ Document
→ Claim
```

Frontend code should not need to parse internal Job JSON.

---

# 98. SANITIZED TASK/JOB PROJECTION

Expose stable operational information such as:

```text
status
attempt count
outcome
reason
counts
related IDs
provider/cost summary
```

Do not expose:

* raw provider prompts;
* large search result payloads;
* internal orchestration blobs.

Reuse the sanitized Job approach established in Phase 23.

---

# 99. EXTERNAL INPUT AND PROVIDER BOUNDARY

Phase 25 handles externally derived Source/search/provider data.

Reuse the application's existing:

* URL and Source validation;
* network-request policy;
* provider-output validation;
* authorization rules;
* privacy controls;
* provider budgets;
* domain-service boundaries.

Externally derived information remains **application data**.

It may affect persistent configuration only through the same validated application services used elsewhere.

Prefer shared validators rather than Phase-25-specific parallel implementations.

---

# 100. RESEARCH INPUT REGRESSION BEHAVIOR

Add focused tests demonstrating:

```text
invalid candidate input
→ rejected safely
→ existing Question/Watch state unchanged
```

```text
invalid provider plan
→ rejected
→ Research Task does not mutate Question state
```

```text
unapproved Source candidate
→ remains inactive as a persistent Watch Source
```

```text
bounded search result without acquired evidence
→ cannot resolve Question
```

Keep regression tests outcome-focused.

---

# 101. PROVIDER DATA MINIMIZATION

Use the smallest context necessary for planning.

Prefer:

```text
Question
Gap
Claim propositions
approved vocabulary
Source metadata
structured criteria
```

over full Document bodies where not required.

Follow existing provider/privacy policy.

---

# 102. SEARCH AND NETWORK OPERATIONS

Any network/search operations added by Phase 25 should use existing request/destination controls.

Do not create a separate unrestricted networking layer.

Validate resolved candidate inputs through current shared services before acquisition.

---

# 103. SEARCH RESULT BOUNDARY

Search result metadata is used to decide what to inspect.

It cannot by itself:

* create a trusted Claim;
* satisfy a Gap;
* resolve a Question.

Only canonically processed evidence can do so.

---

# 104. PROVIDER SUMMARY BOUNDARY

Generated summaries and planning suggestions may guide research.

They are not factual evidence.

If underlying content cannot be acquired and verified, the Question remains governed by its existing trusted corpus.

---

# 105. NO-FINDINGS BOUNDARY

A bounded research attempt that finds nothing means only:

> No qualifying evidence was found within this Research Task's defined scope.

It does not prove the proposition false.

---

# 106. PERFORMANCE

Avoid global scans.

Bound at least:

* Questions considered per Claim;
* Claims considered per evaluation;
* Gaps per Question;
* active Tasks;
* queries per Task;
* candidate results per query;
* Documents per Task;
* history returned through API.

Add indexes only where actual query plans justify them.

---

# 107. NO VECTOR DATABASE

Do not add vector infrastructure in Phase 25.

Prefer:

* normalized text;
* Watch scope;
* Topics;
* Subjects;
* Story relationships;
* SQL-backed retrieval;
* bounded lexical candidate selection;
* optional provider classification.

Phase 26 can revisit retrieval architecture if benchmarks justify it.

---

# 108. DETERMINISTIC-FIRST POLICY

Prefer deterministic logic for:

```text
Question lifecycle
Gap identity
Gap satisfaction
Task identity
resource bounds
scheduler eligibility
state transitions
history identity
```

Provider assistance is most appropriate for:

```text
query suggestions
bounded semantic candidate classification
gap wording
research-plan suggestions
```

The provider should not become the domain state machine.

---

# 109. MANUAL CORRECTION

Users should be able to correct, according to current domain capabilities:

* an incorrect Claim relationship;
* an incorrect support/contradiction classification;
* an irrelevant Gap;
* a Question lifecycle decision.

Preserve origin/history.

---

# 110. RESEARCH ATTEMPT HISTORY

Retain historical Tasks.

Example:

```text
Attempt 1
No qualifying material found.

Attempt 2
Found Document D.
Produced Claim C.
Gap later satisfied.
```

Do not overwrite the first attempt.

---

# 111. RESEARCH STRATEGIES

Where useful, permit a small strategy set such as:

```text
existing_corpus
approved_sources
source_discovery
bounded_search
primary_source_search
date_bounded_search
```

Do not build a generic arbitrary-tool planner.

---

# 112. QUESTION EVALUATION REPLAY

Reevaluating the same evidence snapshot should not create duplicate:

* lifecycle transitions;
* active Gaps;
* summaries;
* provider work where not needed.

---

# 113. NEW EVIDENCE REEVALUATION

When evidence changes:

```text
snapshot H1
→ snapshot H2
```

the Question may legitimately receive a new assessment.

Idempotency must not freeze research state.

---

# 114. HISTORICAL PROVENANCE

If Newsroom considered a Question supported at one time and later contradicted, preserve both states in history.

Do not rewrite the old record.

---

# 115. TASK CANCELLATION

If JobService supports cancellation safely, expose cancellation.

Cancellation stops future research work.

It must not delete valid Documents, Claims, or other evidence already persisted.

---

# 116. TASK RERUN

Allow a new explicit attempt after:

```text
completed_no_findings
completed_with_candidates
```

This creates a new Task while preserving the previous attempt.

---

# 117. SOURCE DISCOVERY FEEDBACK

If research repeatedly identifies a useful Source, Newsroom may suggest:

```text
Add this Source to Watch Y.
```

Persistent Watch changes still use Phase 24 Source approval/services.

---

# 118. RESEARCH QUESTION WATCH

If Phase 24 supports Research Question Watches, Phase 25 may make it easier to create or enable one from Question detail.

Use normal Watch services.

Do not create hidden acquisition state.

---

# 119. WATCH VS RESEARCH TASK

Keep these distinct:

```text
Watch
= continuous observation

Research Task
= one bounded attempt to close one Gap
```

A Question may use both.

Do not convert normal Watch scheduling into a research loop.

---

# 120. LOGICAL EXPORT

Extend logical export with actual implemented Phase 25 state.

Potential records include:

* Research Questions;
* Question state/history;
* Question-Claim relationships;
* Evidence Gaps;
* Gap history/state;
* Research Tasks;
* Task-Document relationships;
* evaluation snapshot identifiers;
* required research provenance.

Do not export large provider/search payloads merely because they exist operationally.

---

# 121. EXPORT RECONSTRUCTION

Add a regression reconstructing:

```text
Research Question
→ supporting Claim
→ ClaimEvidence
→ EvidenceSpan
→ DocumentVersion
→ Document
→ Source
```

and, where findings exist:

```text
Research Question
→ Gap
→ Research Task
→ Document
→ Claim
→ Question relationship
```

Reconstruct from actual export records.

---

# 122. DATABASE INTEGRITY

Extend `check_database()` for correctness-critical structural invariants only.

Potential checks:

```text
Question-Claim relationship resolves

Gap belongs to valid Question

Research Task belongs to valid Question/Gap

satisfied Gap has required qualifying relationship
where deterministically provable

completed evidence-bearing Task references valid Documents/Claims

automatic Question transition references coherent snapshot/state
```

Do not turn subjective research quality into a database integrity rule.

---

# 123. MIGRATION STRATEGY

Inspect the existing Research Question schema before deciding.

Possible additions include:

* richer Question-Claim relationship metadata;
* Evidence Gaps;
* Research Task domain records;
* Task-Document links;
* Question transition history;
* evaluation snapshot identity.

Add only what is necessary.

Reuse existing Research Question and Job infrastructure.

---

# 124. MIGRATION REQUIREMENTS

If schema changes:

* follow existing migration conventions;
* advance schema version correctly;
* support fresh database creation;
* support upgrade from completed Phase 24;
* preserve existing Questions;
* preserve existing relationships;
* preserve manual lifecycle state;
* preserve Watch/Monitor behavior;
* preserve Phase 23 automation;
* pass FK validation;
* test migration repeat/idempotency according to project conventions;
* do not fabricate historical transitions.

---

# 125. BACKWARD COMPATIBILITY

Existing Research Questions must continue functioning after migration.

If old state values map into richer semantics, use deterministic documented migration.

Do not silently reinterpret historical Question meaning.

---

# 126. CONCURRENCY TESTS

Use actual database-backed concurrency where logical identity matters.

Verify:

```text
two Question evaluators
→ same snapshot
→ one logical assessment transition
```

```text
two Gap generators
→ same Question + Gap condition
→ one logical active Gap
```

```text
two schedulers
→ same actionable Gap
→ one active Research Task
```

```text
two retries
→ same resulting Claim relationship
→ one logical Question-Claim relationship
```

---

# 127. FAILURE ISOLATION

Research failure must not invalidate previously trusted state.

Verify:

```text
Research Task fails
→ Question and existing evidence remain valid
```

```text
Question reevaluation fails
→ acquired Document/Claim remain valid
```

```text
Story/Report/Alert downstream fails
→ Question research evidence remains valid
```

No giant transaction should span the full research/evidence/downstream chain.

---

# 128. PROVIDER UNAVAILABLE

Provider-assisted research is optional enhancement.

When unavailable:

```text
Question remains usable

existing corpus evaluation works

deterministic research planning works where supported

manual pursuit remains available

approved Sources remain intact
```

---

# 129. SEARCH UNAVAILABLE

Search unavailability should produce an operational Task outcome appropriate to current Job semantics.

It must not change Question truth state.

---

# 130. ACQUISITION FAILURE

If candidate material cannot be acquired:

```text
Task records candidate/acquisition outcome
Gap remains open
No Claim is created from that failed acquisition
```

---

# 131. OBSERVABILITY

Add concise events consistent with repository logging.

Examples:

```text
Question created
Question evaluated
Question state changed
Gap created
Gap satisfied
Gap dismissed
Research Task created
Research Task completed
Research Task completed with no findings
Question-Claim relationship created
```

Do not log full provider responses or full article content.

---

# 132. CODEBASE-DRIVEN ADJUSTMENT AUTHORITY

Codex is expected to adjust implementation details after repository inspection.

Examples:

```text
If existing gap suggestions already provide durable Gap storage,
extend them.

If Research Questions already have transition history,
reuse it.

If an existing research worker exists,
extend it.

If existing Search/Workbench retrieval is adequate for corpus-first research,
reuse it.

If Phase 24 discovery already satisfies a requested discovery path,
reuse it.

If existing Question states map cleanly to the required semantics,
do not create replacement enums.

If an existing relationship table already stores Question-Claim links,
extend it rather than duplicating it.
```

Document material deviations.

---

# 133. REQUIRED CAPABILITIES MAY NOT BE SILENTLY DEFERRED

Phase 25 must complete with:

```text
persistent Research Questions

structured current assessment

automatic bounded Claim linking

support vs contradiction distinction

persistent Evidence Gaps

Gap lifecycle

deterministic Gap satisfaction

bounded Research Tasks

manual pursuit

automatic pursuit when enabled

corpus-first research

Phase 24 Watch vocabulary reuse

approved Watch Source reuse

Phase 24 Source discovery reuse

bounded external search where required/supported

canonical acquisition/evidence path for findings

Question reevaluation

audited transitions

provider/budget controls

functional API

functional frontend Research Question workspace

logical export

database integrity

concurrency/replay/recovery

end-to-end autonomous research test
```

If an external service cannot be exercised in the test environment, use the production abstraction with controlled fixtures and state clearly what was externally unvalidated.

---

# 134. OUT OF SCOPE

## Phase 26

Do not implement:

* full canonical Entity Intelligence;
* broad smart tagging;
* Workbench v2;
* evidence-grounded Ask;
* vector database.

## Phase 27

Do not implement:

* Story merge;
* Story split;
* Claim reassignment;
* broad Story identity repair;
* advanced Story correction workflows.

## Phase 28

Do not implement:

* advanced Source dependency intelligence;
* universal Source reliability scoring;
* broad Alert delivery expansion;
* major intelligence dashboard redesign.

## Phase 29

Do not perform broad repository-wide hardening beyond Phase 25 surfaces.

## Phase 30

Do not perform final release/dogfood work.

---

# 135. SUGGESTED IMPLEMENTATION ORDER

Codex may adjust this after audit.

A reasonable sequence is:

```text
1. Audit existing Research Question implementation

2. Decide Question lifecycle and relationship model

3. Implement/extend Question ↔ Claim relationships

4. Implement deterministic Question evaluation

5. Implement Evidence Gap persistence

6. Implement deterministic Gap generation/satisfaction

7. Implement bounded Research Task domain

8. Integrate JobService and scheduler

9. Implement corpus-first pursuit

10. Reuse Watch vocabulary / approved Sources

11. Reuse Phase 24 Source discovery

12. Add bounded search abstraction if genuinely required

13. Route findings into normal acquisition

14. Link Tasks to Documents and resulting Claims

15. Trigger Question reevaluation

16. Implement API

17. Implement frontend Research Question workspace

18. Extend export/integrity

19. Add concurrency/replay/recovery coverage

20. Run end-to-end research integration

21. Complete final validation
```

---

# 136. CHECKPOINT COMMIT STRATEGY

Phase 25 is large enough that validated checkpoint commits are preferred.

This is especially important for preserving clear recovery points during long agent sessions.

A reasonable checkpoint structure is:

```text
Checkpoint A:
Question evaluation
+ Claim relationships
+ Evidence Gaps

Checkpoint B:
Research Tasks
+ Jobs
+ corpus-first pursuit
+ Watch/Source integration

Checkpoint C:
bounded search/acquisition
+ reevaluation
+ concurrency/recovery

Final:
API
+ frontend
+ export/integrity
+ full validation
```

Do not force these exact boundaries if repository dependencies suggest better ones.

For each checkpoint:

```text
coherent capability complete
→ focused tests green
→ relevant regression tests green
→ commit
→ continue
```

Do not create microcommits.

Do not push.

---

# 137. INTERRUPTION-RESILIENT EXECUTION

If the agent session ends unexpectedly during Phase 25:

1. do not assume changes were rolled back;
2. inspect current Git/worktree state;
3. preserve legitimate completed work;
4. identify the last validated checkpoint commit;
5. inspect the uncommitted tail before continuing;
6. rerun focused tests for the affected capability;
7. resume from the first incomplete acceptance requirement.

Do not automatically reset or discard partially completed work.

---

# 138. REQUIRED QUESTION TEST COVERAGE

Verify at minimum:

```text
existing Question survives upgrade

supporting Claim association

contradictory Claim association

contextual/irrelevant Claim does not become support

provisional/rejected Claim cannot resolve Question improperly

deterministic evaluation

same snapshot no-op

new snapshot reevaluates

manual lifecycle authority respected

transition history coherent
```

---

# 139. REQUIRED GAP TEST COVERAGE

Verify:

```text
deterministic Gap creation

duplicate Gap convergence

missing additional Source Gap where supported

primary Source Gap where supported

unresolved contradiction Gap

Gap remains open without qualifying evidence

Gap satisfied only by qualifying evidence

dismissed Gap remains dismissed

explicit reconsideration works according to policy
```

---

# 140. REQUIRED RESEARCH TASK TEST COVERAGE

Verify:

```text
manual pursuit creates bounded Task

automatic pursuit obeys policy

one active Task per Gap

duplicate scheduling converges

resource limits enforced

cooldown enforced

no-findings is successful execution

operational failure uses normal retry behavior

budget limitation produces bounded outcome

cancellation preserves existing evidence

new attempt preserves old history
```

---

# 141. REQUIRED PLANNING TEST COVERAGE

Verify:

```text
corpus-first retrieval occurs before broader pursuit

deterministic query generation

Watch vocabulary reuse

query-count bounds

provider-assisted planning where implemented

invalid provider plan leaves Question unchanged

provider unavailability preserves deterministic path
```

---

# 142. REQUIRED ACQUISITION TEST COVERAGE

Verify:

```text
candidate result cannot directly become Claim

generated summary cannot directly become Claim

candidate material uses normal Source/acquisition services

existing Document is reused

Research Task can be linked to existing Document

acquired Document uses normal relevance

ArticleAnalysis/evidence remains authoritative

failed acquisition leaves Gap open
```

---

# 143. REQUIRED REEVALUATION TEST COVERAGE

Verify:

```text
new trusted Claim triggers reevaluation

supporting Claim may satisfy Gap

contradictory Claim changes assessment appropriately

same snapshot does not duplicate transition

stale Task completion evaluates current Question state

replay does not duplicate relationships/history
```

---

# 144. REQUIRED PHASE 24 INTEGRATION TESTS

Verify:

```text
Question can use Watch vocabulary

Question can use approved Watch Sources

Research Source discovery reuses Phase 24

Source candidate remains candidate before approval

persistent Source approval uses Phase 24 services

Question Watch uses normal Watch/Monitor architecture where supported

Research Task failure does not alter normal Watch monitoring
```

---

# 145. REQUIRED CONCURRENCY TESTS

Using real database-backed concurrency where appropriate:

```text
concurrent evaluation
→ one logical Question transition
```

```text
concurrent Gap generation
→ one logical Gap
```

```text
concurrent pursuit scheduling
→ one active Task
```

```text
duplicate result linking
→ one logical Question-Claim relationship
```

---

# 146. REQUIRED API / FRONTEND COVERAGE

Verify:

```text
bounded Question list

Question detail

supporting/contradictory Claims

Gap representation

Task history

pursue action

pursuit policy

sanitized Task/Job status

manual/automatic origin

frontend type support

Question workspace rendering

Gap workflow rendering

Task result rendering

provenance navigation
```

---

# 147. REQUIRED EXPORT / INTEGRITY COVERAGE

Verify:

```text
Question relationships export

Question history export

Gap state/history export

Research Task audit export

Question → Claim → Evidence → Source reconstruction

Task → Document → Claim reconstruction

invalid structural relationships detected by check_database()
```

---

# 148. CRITICAL EVIDENCE-BOUNDARY TESTS

These are release gates.

## Test A

```text
Search returns candidate metadata describing an assertion.

Underlying content is not acquired and verified.

Expected:
No trusted Claim.
No Question resolution.
Gap remains governed by existing evidence.
```

## Test B

```text
Research planner suggests that a Source supports proposition X.

No canonical evidence supports X.

Expected:
No support relationship.
No Question lifecycle change.
```

## Test C

```text
Bounded research completes with no qualifying material.

Expected:
Task records no-findings.
Gap remains open.
Question does not become contradicted merely from absence.
```

## Test D

```text
Trusted Claim B is explicitly incompatible
with trusted supporting Claim A.

Expected:
Question contradiction state/gap updates
according to deterministic policy.
```

## Test E

```text
Research Task finds Document D.

Expected:
D
→ DocumentVersion
→ ContentArtifact
→ relevance
→ ArticleAnalysis
→ EvidenceSpan
→ Claim
→ Question relationship
```

No shortcut.

---

# 149. END-TO-END AUTONOMOUS RESEARCH TEST

Create a production-composition test using real application/runtime services and controlled external boundaries.

Target:

```text
Research Question Q
        ↓
evaluation
        ↓
Evidence Gap G
        ↓
Research Task T
        ↓
bounded planning
        ↓
corpus / Source / controlled search
        ↓
Document D
        ↓
normal acquisition/processing
        ↓
verified EvidenceSpan
        ↓
Claim C
        ↓
Question relationship
        ↓
Gap reevaluation
        ↓
Question lifecycle update
```

If Claim C is material downstream, allow the existing Phase 23 engine to perform:

```text
Claim
→ Story
→ Report
→ Alert
```

through normal runtime wiring.

Do not manually create those downstream objects solely to make the integration test pass.

---

# 150. NO-FINDINGS END-TO-END TEST

Also test:

```text
Question
→ Gap
→ bounded Research Task
→ no qualifying material
→ Task completed with no findings
→ Gap remains open
→ Question does not falsely resolve or contradict
```

---

# 151. HUMAN AUTHORITY END-TO-END TEST

Example:

```text
Question exists
Gap created
Research Task starts
user changes Question/Gap state
Task later produces findings
```

Findings may remain valid evidence.

Final automatic Question mutation must use current human/domain state.

---

# 152. REPLAY TEST

Replay the same logical Research Task.

Expected no duplicate logical:

```text
Document
Claim
Question-Claim relationship
Gap
Question transition
downstream Story/Report/Alert result
```

where existing domain identity requires reuse.

A deliberate future research attempt remains a new Task.

---

# 153. RECOVERY TEST

Simulate interruption after:

```text
Task created
candidate discovered
Document acquired
Document processed
Claim created
Question reevaluation not yet completed
```

Recovery should eventually reevaluate the Question without duplicating evidence.

Use real Job/checkpoint behavior.

---

# 154. MIGRATION VALIDATION

If schema changes, run:

```text
fresh database creation

completed Phase 24 schema
→ Phase 25 upgrade

migration registration

migration repeat/idempotency
according to project conventions

foreign-key validation

existing Research Question compatibility

existing Watch/Monitor compatibility
```

---

# 155. VALIDATION

Run focused Phase 25 suites first.

Then relevant suites covering:

```text
Research Questions
Claims
Evidence
Jobs
Sources
Watches
Watch vocabulary
Source discovery
Scheduler
Acquisition
Relevance
ArticleAnalysis
Story automation
Reports
Alerts
API
frontend
operations/export
integrity
runtime
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

Run the actual configured frontend build if Phase 25 touches production frontend behavior.

Diff hygiene:

```bash
git diff --check
```

Before each checkpoint/final commit:

```bash
git diff --cached --check
```

Run repository-configured lint/format commands where they actually exist.

Do not report unexecuted validation as passed.

---

# 156. PHASE 25 ACCEPTANCE GATE

Phase 25 is complete only when all applicable requirements are demonstrated.

## Research Questions

```text
[PASS] existing Questions remain compatible

[PASS] lifecycle semantics are explicit

[PASS] Question assessment is deterministic

[PASS] automatic transitions are audited

[PASS] manual decisions remain authoritative

[PASS] unchanged evidence does not duplicate transitions

[PASS] supporting Claims are distinguishable

[PASS] contradictory Claims are distinguishable

[PASS] weak contextual overlap does not become strong support automatically
```

## Evidence Gaps

```text
[PASS] persistent Gaps exist

[PASS] Gap conditions are explicit where applicable

[PASS] duplicate Gaps converge

[PASS] Gaps are explainable

[PASS] user dismissal is respected

[PASS] satisfaction requires qualifying persisted evidence

[PASS] Task completion alone cannot satisfy a Gap
```

## Research Pursuit

```text
[PASS] manual bounded pursuit works

[PASS] automatic pursuit works when enabled

[PASS] one active logical Task per Gap is enforced

[PASS] cooldown prevents immediate research loops

[PASS] query/candidate/document limits are enforced

[PASS] provider budgets are enforced

[PASS] no-findings is represented correctly

[PASS] operational failures do not alter Question truth state
```

## Evidence Boundary

```text
[PASS] search candidate metadata is not evidence

[PASS] generated planning summaries are not evidence

[PASS] research planning cannot directly resolve Question lifecycle

[PASS] candidate material enters normal acquisition

[PASS] ArticleAnalysis/evidence verification remains authoritative

[PASS] only trusted Claims influence automatic Question assessment
```

## Phase 24 Integration

```text
[PASS] Research can reuse Watch vocabulary

[PASS] Research can reuse approved Watch Sources

[PASS] Source discovery reuses Phase 24

[PASS] persistent Source approval uses Phase 24 services

[PASS] per-need Monitor architecture is preserved

[PASS] Research failure does not break normal Watch scheduling
```

## Reevaluation

```text
[PASS] new trusted evidence triggers reevaluation

[PASS] stale Task assumptions do not overwrite current state

[PASS] Question assessment uses deterministic snapshot identity

[PASS] replay does not duplicate lifecycle history

[PASS] historical transitions remain auditable
```

## Product Surface

```text
[PASS] Question list/detail API is bounded

[PASS] supporting/contradictory Claims are inspectable

[PASS] Gaps are inspectable

[PASS] Research Tasks are inspectable

[PASS] pursuit can be triggered through supported UI/API

[PASS] pursuit policy is manageable

[PASS] frontend Research Question workspace is functional

[PASS] provenance is navigable from Question detail
```

## External Input / Provider Boundary

```text
[PASS] external candidate data uses shared validation

[PASS] network/search operations use established request controls

[PASS] provider output uses bounded structured validation

[PASS] persistent Source changes use normal domain services

[PASS] provider-data minimization follows existing policy

[PASS] invalid candidate/provider input leaves existing state safe
```

## Audit / Integrity

```text
[PASS] Question relationships are exportable

[PASS] Question history is exportable

[PASS] Gap state/history is exportable

[PASS] Research Task audit state is exportable

[PASS] exported Question chain reaches exact Source evidence

[PASS] Task → Document → Claim reconstruction works

[PASS] structural research corruption is detected

[PASS] raw provider/search payloads are not exposed through normal API/export
```

## Reliability

```text
[PASS] concurrent evaluation converges

[PASS] concurrent Gap generation converges

[PASS] duplicate pursuit scheduling converges

[PASS] replay does not duplicate trusted relationships

[PASS] interrupted research recovers

[PASS] failure isolation preserves valid upstream state
```

## Integration

```text
[PASS] controlled research pursuit reaches verified evidence

[PASS] resulting Claims can enter normal Story/Report/Alert automation

[PASS] no research-specific evidence shortcut exists

[PASS] no-findings end-to-end case preserves open Question/Gap state
```

## Repository

```text
[PASS] focused Phase 25 tests pass

[PASS] relevant Phase 24 tests pass

[PASS] Phase 23 regression suites pass

[PASS] complete backend suite passes

[PASS] compileall passes

[PASS] frontend typecheck passes

[PASS] frontend build passes if applicable

[PASS] git diff --check passes

[PASS] migration/FK validation passes if applicable

[PASS] Phase 25 work is committed

[PASS] tracked worktree is clean
```

---

# 157. FINAL USER EXPERIENCE GATE

Do not declare Phase 25 complete unless this workflow is possible through supported application behavior:

```text
User creates:

"Has recovered NHI material
been scientifically verified by another Source?"

Newsroom evaluates existing trusted evidence.

It displays:

supporting Claims
contradictory Claims
current assessment
open Evidence Gaps

Newsroom identifies an actionable Gap such as:

"Missing primary laboratory documentation."

The user can select:

Research this gap now.

Or automatic pursuit may run if enabled.

Newsroom creates one bounded Research Task.

The Task first checks existing Newsroom knowledge.

It then checks approved Watch Sources where appropriate.

If needed, it uses bounded discovery/search.

Candidate material enters the normal acquisition pipeline.

A real Document is processed.

Evidence is verified.

A Claim is produced.

The Claim is related to the Research Question.

The Gap is reevaluated.

The Question lifecycle changes only if qualifying trusted evidence justifies the change.

The user can inspect:

what the Question currently means
why it has its current state
which Claims support it
which Claims contradict it
which Gaps remain
what each Research Task attempted
what Documents were found
which findings became evidence
what remains unresolved

Replay does not duplicate evidence,
relationships, Gaps, or lifecycle transitions.
```

That is Phase 25.

---

# 158. FINAL RESPONSE FORMAT

## 1. Verdict

Return exactly one:

```text
PHASE 25 COMPLETE AND COMMITTED — PHASE 26 READY
```

or:

```text
PHASE 25 CORRECTED AND COMMITTED — PHASE 26 READY
```

or:

```text
PHASE 25 INCOMPLETE — PHASE 26 BLOCKED
```

---

## 2. Codebase Review and Architecture Decision

Report:

* existing Research Question implementation;
* existing lifecycle;
* existing Claim/Evidence relationships;
* existing gap functionality;
* existing research worker/Job behavior;
* Phase 24 Watch/Monitor integration;
* Source discovery integration;
* final Phase 25 architecture.

List material codebase-driven adjustments.

---

## 3. Research Question Model

Describe:

* lifecycle;
* current assessment;
* state evaluation;
* manual vs automatic authority;
* scope;
* normalized proposition if implemented;
* history/audit behavior.

---

## 4. Claim / Evidence Relationships

Describe:

```text
Research Question
→ supporting Claims
→ contradictory Claims
→ contextual Claims
→ Evidence
```

Report:

* candidate retrieval;
* relationship classification;
* bounds;
* automatic/manual origin;
* conservative handling of ambiguity.

---

## 5. Evidence Gap Model

Report:

* Gap types;
* lifecycle;
* identity;
* generation;
* satisfaction;
* dismissal/reopen behavior;
* contradiction handling.

---

## 6. Research Task Architecture

Describe:

```text
Question
→ Gap
→ Research Task
→ bounded plan
→ corpus / Sources / discovery / search
→ Documents
→ Claims
→ Question reevaluation
```

Report:

* Jobs;
* idempotency;
* limits;
* cooldown;
* retries;
* cancellation;
* no-findings;
* new-attempt behavior.

---

## 7. Research Planning

Describe:

* corpus-first behavior;
* deterministic query planning;
* provider-assisted planning;
* Watch vocabulary reuse;
* approved Source reuse;
* Source discovery;
* bounded search abstraction where implemented.

---

## 8. Evidence Boundary

Show the exact implemented path:

```text
research candidate
→ Source
→ acquisition
→ Document
→ DocumentVersion
→ ContentArtifact
→ relevance
→ ArticleAnalysis
→ EvidenceSpan
→ Claim
→ Research Question
```

Confirm that candidate metadata and provider planning output cannot directly become trusted evidence.

---

## 9. Question Reevaluation

Describe:

* triggers;
* snapshot identity;
* state policy;
* stale Task handling;
* duplicate prevention;
* transition history.

---

## 10. Phase 24 Integration

Describe use of:

* Watches;
* per-need Monitors;
* Watch vocabulary;
* approved Sources;
* Source candidates;
* Phase 24 Source discovery.

Confirm no duplicate Watch or Source-discovery architecture was introduced.

---

## 11. Provider / Search / Cost Behavior

Report:

* deterministic/local behavior;
* provider-assisted behavior;
* bounded search behavior;
* AIRouter/provider abstraction;
* budget enforcement;
* query/provider/document limits;
* behavior when optional services are unavailable.

---

## 12. External Input and Provider Boundary

Summarize how Phase 25 reuses existing:

* input validation;
* Source validation;
* request/destination controls;
* provider-output validation;
* authorization;
* privacy;
* provider budgets.

Keep this section outcome-focused.

---

## 13. API

List new/changed routes for:

* Research Questions;
* Question relationships;
* Evidence Gaps;
* Research Tasks;
* pursuit;
* pursuit policy;
* history/status.

Report collection bounds.

---

## 14. Frontend

Describe the completed Research Question workspace.

Include:

* Question creation;
* current assessment;
* supporting/contradictory evidence;
* Gap management;
* pursue-now workflow;
* automatic pursuit policy;
* Task history;
* findings;
* provenance navigation;
* operational states.

---

## 15. Migration

Report:

```text
migration required: yes/no
starting schema version
ending schema version
```

If applicable, report:

* existing Question preservation;
* fresh database result;
* Phase 24 → Phase 25 upgrade;
* migration repeat/idempotency;
* FK validation.

---

## 16. Export / Integrity

Report:

* exported Question records;
* relationship records;
* history;
* Gaps;
* Research Tasks;
* Task-Document links;
* Question-to-Source reconstruction;
* Task-to-Claim reconstruction;
* integrity checks.

---

## 17. Concurrency / Idempotency / Recovery

Explain:

* duplicate evaluation;
* duplicate Gap generation;
* duplicate Task scheduling;
* duplicate result linking;
* replay;
* stale Task completion;
* interrupted research recovery.

---

## 18. Tests

List focused Phase 25 tests actually added.

Explicitly cover:

* supporting relationships;
* contradiction;
* weak/irrelevant relationship rejection;
* deterministic assessment;
* Gap creation/dedupe;
* Gap satisfaction;
* no-findings;
* manual pursuit;
* automatic pursuit;
* cooldown/budget;
* corpus-first research;
* Watch integration;
* Source discovery;
* bounded search where implemented;
* canonical acquisition/evidence path;
* Question reevaluation;
* stale Task result;
* concurrency;
* replay;
* recovery;
* export/integrity;
* API/frontend;
* end-to-end autonomous research.

---

## 19. Validation

List every command actually executed and result.

Do not report unexecuted checks as passed.

---

## 20. Files Changed

Group changed files by:

```text
domain/schema
Research Questions
Evidence Gaps
Research Tasks
research planning
Watches/Sources
Jobs/runtime
API
frontend
operations/integrity
tests
documentation
```

---

## 21. Commits

Report:

* checkpoint commit SHA(s);
* final commit SHA;
* subjects;
* scope.

Do not push.

---

## 22. Repository State

Report:

* branch;
* current HEAD;
* relation to origin;
* schema version;
* tracked worktree;
* staged state;
* preserved unrelated untracked files;
* whether push occurred.

Do not compare against a prompt-predicted SHA.

---

## 23. Deferred Work

List only genuine later-phase work.

### Phase 26

* canonical Entity intelligence;
* smart tagging;
* Workbench v2;
* evidence-grounded Ask.

### Phase 27

* Story merge;
* Story split;
* Claim reassignment;
* richer correction/evolution semantics.

### Phase 28

* intelligence dashboards;
* advanced Source intelligence;
* Source dependency;
* expanded Alert delivery.

### Phase 29

* broad production hardening;
* performance;
* operations;
* cost optimization.

### Phase 30

* final UX;
* broad dogfood;
* release audit.

Do not classify incomplete Phase 25 requirements as deferred.

---

## 24. Phase 26 Readiness

State whether Newsroom now has:

```text
Sources
Watches
Documents
Evidence
Claims
Stories
Research Questions
Evidence Gaps
Research Tasks
Research provenance
Question assessments

→ ready for canonical Entities
→ ready for smart tagging
→ ready for investigative Workbench
→ ready for evidence-grounded Ask
```

Do not begin Phase 26 in this task.

---

# 25. IMPLEMENTATION COMPLETION REPORT

## 25.1 Codebase-driven architectural decisions

The repository audit found that Phase 10 already owns Research Questions,
Question lifecycle history, Question-to-Claim/Evidence links, gap suggestions,
and the `research_question` Job type. Phase 25 extends those boundaries rather
than creating parallel systems:

* the existing `status` column remains explicit human lifecycle authority;
  `assessment_state`, assessment snapshots, and assessment history are the
  deterministic canonical-evidence projection;
* the existing Phase 10 gap-suggestion records remain historical suggestion
  workflow; durable Phase 25 Evidence Gaps are separate, typed, lifecycle-
  tracked records with deterministic identity and satisfaction;
* the existing Research Question Job is retained and now owns a bounded,
  durable Research Task with one active Task per Gap, normal lease recovery,
  retry, cancellation, and replay behavior;
* corpus-first retrieval reuses the existing SQL/FTS Workbench search. The
  optional external boundary is a narrow injected search interface returning
  validated candidate metadata; it is not a crawler and never writes trusted
  Claims;
* Watch vocabulary, approved Watch Sources, Source candidates, and per-need
  Monitors are reused through Phase 24 services. Research acquisition invokes
  the existing `AcquisitionService`, which enqueues the normal
  `document_version_process` path;
* provider planning is an additional capability on the existing `AIRouter`,
  with bounded `ResearchPlanRequest`/`ResearchPlanOutput`, existing telemetry
  and paid-budget enforcement, and deterministic fallback when unavailable;
* migration 0025 is additive. Existing Questions receive their first
  deterministic assessment lazily on read so the migration does not fabricate
  historical transitions or reinterpret explicit lifecycle state;
* an explicit Job replay remains supported for legacy API behavior, while
  ordinary pursuit scheduling converges on the one-active-Task-per-Gap
  invariant.

No Phase 26 capability was introduced.

## 25.2 Implemented capability surface

Implemented and tested:

* evidence-grounded Question assessment with supporting, contradicting, and
  contextual relationships, manual corrections, criteria, explanations, and
  append-only history;
* persistent Evidence Gaps with deterministic identity, support/contradiction,
  independent-source and primary-source conditions, dismissal/reconsideration,
  and satisfaction lifecycle;
* bounded Research Tasks, query audit, candidate/acquired material
  provenance, resource limits, no-findings success, cooldown, budget checks,
  automatic pursuit, and task/job reconciliation;
* corpus-first planning, approved Watch vocabulary reuse, Phase 24 discovery
  reuse, approved Source reuse, deduplicated bounded external candidates, and
  normal canonical acquisition/processing;
* trusted-evidence reevaluation after Claim/Evidence mutations, including
  late canonical processing that upgrades a completed candidate Task to
  `completed_with_evidence`;
* authenticated bounded API routes and a functional frontend Question
  workspace with explicit TypeScript models for Questions, Claims, Gaps, and
  Tasks;
* logical export allow-list coverage for Question assessment and Task state,
  structural integrity checks, migration 0025, upgrade compatibility, and
  repository-wide migration expectation updates;
* focused regression coverage for provider routing/budgets, candidate
  isolation, approved Watch acquisition, canonical end-to-end processing,
  automatic cooldown, concurrency, replay/recovery compatibility, export,
  and invalid structural state.

## 25.3 Validation

The final validation was run from the repository root unless a frontend
working directory is shown:

* focused backend Phase 10/worker/Phase 15/Phase 25 suite: passing;
* `python -m compileall -q newsroom tests`: passing;
* `pnpm typecheck` from `frontend`: passing;
* `pnpm build` from `frontend`: passing;
* `poetry run pytest -q`: passing, 742 tests collected and passed;
* `git diff --check`: passing;
* database integrity and migration idempotency: covered by focused and full
  tests.

The repository does not define the skill-alias commands `poetry run format`,
`poetry run test`, `pnpm format`, `pnpm lint`, or `pnpm types`; those aliases
were checked and reported as unavailable. The configured test, typecheck, and
build commands above are the authoritative validation paths for this codebase.

## 25.4 Completion record

Checkpoint A: `f732b84` (`Phase 25: add evidence-grounded research tasks`).

Checkpoint B: `73db5b2` (`Phase 25: expose bounded research workspace`).

Implementation commit: `c88d80a` (`Phase 25: complete autonomous research`).
The documentation closeout is the only follow-up commit and contains no code
or behavior changes. No push is performed.

At implementation completion the branch is `main`, schema version is 25, and
the branch is ahead of `origin/main`. The tracked worktree is clean. These
unrelated untracked files were preserved and intentionally not staged:

* `.kilo/`;
* `Newsroom -v2.zip`;
* `plan/phases-v2/Phase 23 Summary.md`;
* `plan/phases/phases - Shortcut.lnk`.
