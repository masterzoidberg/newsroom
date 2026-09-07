# PHASE 27 — ADVANCED STORY INTELLIGENCE

## Story Identity, Correction, Merge/Split, Claim Reassignment, Historical Truth, and Durable Reconciliation

---

# 0. PHASE STATUS AND AUTHORITY

Phase 26 is complete.

Phase 27 is the next permitted implementation phase.

Active forward planning authority:

```text
G:\Projects\Newsroom -v2\plan\phases-v2\
```

Historical implementation plans:

```text
G:\Projects\Newsroom -v2\plan\phases-old\
```

The following planning documents are binding inputs for this phase:

```text
plan/phases-v2/Strategic Architecture Review.md
plan/phases-v2/Final Architecture Reconciliation Memo.md
```

Where the Final Architecture Reconciliation Memo narrows or changes the Strategic Architecture Review, the reconciliation memo wins.

This Phase 27 plan incorporates those decisions and resolves the remaining product-policy questions.

---

# 1. FINAL PHASE OBJECTIVE

Phase 27 turns Story membership from an effectively one-time automatic grouping into a **correctable, auditable, historically truthful identity system**.

The system must support:

```text
Claim reassignment
Claim unassignment

Story merge
Story split
Claim extraction into a new Story

duplicate Story suggestion
duplicate approval
duplicate dismissal

Story lineage
Story correction history

manual authority over stale automation

historical Story membership queries

current Story membership queries

durable downstream reconciliation
```

while preserving the existing provenance-first intelligence architecture.

The governing principle is:

> **Correct the present without rewriting the past.**

Equivalent shorthand:

```text
current interpretation
can change

historical interpretation
must remain inspectable
```

After Phase 27, Newsroom must be able to truthfully answer both:

```text
Where does this Claim belong now?
```

and:

```text
Where did Newsroom previously believe this Claim belonged,
when did that change, and why?
```

---

# 2. DO NOT ASSUME REPOSITORY STATE

Before implementation:

1. inspect the current branch;
2. inspect current HEAD;
3. inspect tracked and untracked worktree state;
4. inspect recent commits;
5. inspect current migration/schema version;
6. inspect `plan/phases-v2/`;
7. inspect the Strategic Architecture Review;
8. inspect the Final Architecture Reconciliation Memo;
9. confirm whether any relevant Story code changed since those reviews.

Do not assume a starting commit SHA.

The accepted architectural baseline at the time of reconciliation was schema version 28, but verify the actual live repository before creating a migration.

Preserve unrelated tracked and untracked files.

Do not:

```text
reset
rewrite history
force clean
delete unrelated artifacts
push
```

unless explicitly instructed.

---

# 3. CODEBASE-FIRST AUDIT

Before designing migrations or services, inspect the live implementation.

At minimum audit:

## Claim / Story membership

```text
claims.story_id
claims_story_association_immutable
claim_story_assignment_history
EvidenceService.assign_claim_to_story()
EvidenceService._assign_claim_to_story_tx()
automatic Story assignment paths
```

Confirm all current readers that assume:

```text
claims.story_id
= current Story membership
```

---

## Story automation

Inspect:

```text
automatic_story_resolution.py
story_automation.py
story_evolution.py
EvidenceService Story helpers
automatic Story Jobs
manual Story assignment paths
```

Identify:

```text
all Story candidate retrieval inputs
historical vs current Story inputs
manual authority handling
duplicate handling
Story creation rules
```

---

## Story Documents

Audit every reader/writer of:

```text
story_documents
```

Especially:

```text
automatic Story candidate retrieval
StoryEvolution
corroboration
Living Reports
Workbench
Story timelines
Story revision provenance
Source-targeted Story lookup
```

The binding Phase 27 semantic is defined below.

---

## Story Entities

Audit:

```text
story_entities
claim_entities
KnowledgeService.link_claim_entity()
KnowledgeService._link_claim_entity_tx()
Entity detail
Workbench
Ask
logical export
integrity
```

Determine actual manual/import/backfill/automatic uses before migrating.

---

## Story Tags / Topics / Subjects

Audit:

```text
story_tags
tag_assignments
story_topics
story_subjects
Story review metadata
```

Identify:

```text
manual authority
automatic authority
compatibility dual-writes
current readers
export behavior
```

Do not silently redesign Tags beyond what Phase 27 requires.

---

## Downstream Story consumers

Inspect:

```text
StoryRevision
StoryEvolution
LivingReport
ReportRevision
Alert
Alert delivery
Research Questions
Evidence Gaps
Research Tasks
Watches
Monitors
Workbench
Ask
Search/FTS
logical export
integrity checks
Jobs
worker recovery
```

For every Story-dependent structure determine:

```text
CURRENT
HISTORICAL
HUMAN DECISION
DERIVED PROJECTION
CACHE / INDEX
```

This classification is essential.

---

# 4. CORE INVARIANTS

The following invariants are mandatory.

## 4.1 Canonical evidence is not rewritten

Phase 27 must not weaken:

```text
ContentArtifact immutability
DocumentVersion history
EvidenceSpan verification
Claim proposition/hash immutability
ClaimEvidence provenance
automatic Claim provenance identity
accepted_at immutability
```

Story correction changes **organizational interpretation**, not factual evidence provenance.

---

## 4.2 `claims.story_id` remains the current membership pointer

Binding architecture:

```text
claims.story_id
= nullable current Story membership
```

Do not introduce a parallel current Story-membership table unless live repository evidence proves the reconciliation decision is no longer viable.

The current pointer is allowed to change only through the controlled Story membership/correction service introduced by Phase 27.

---

## 4.3 Historical membership is append-only

Phase 27 must generalize existing one-time assignment history into:

```text
NULL → Story A
Story A → Story B
Story A → NULL
Story B → Story C
```

Historical membership transitions are never rewritten or deleted.

---

## 4.4 Historical Story associations remain historical

A valid later correction must not invalidate:

```text
old StoryRevision
old StoryEvolution
old ReportRevision
old Alert
old Research Task
old Ask audit record
old automatic assignment Job result
```

because those records represented what Newsroom believed or did at that time.

---

## 4.5 Derived current state follows current membership

Current projections must follow:

```text
current Claim Story membership
```

not stale historical Story associations.

---

## 4.6 Human corrections override stale automation

A later explicit human decision takes precedence over stale automatic assignment work.

Automation must not silently undo:

```text
manual reassignment
manual unassignment
Story merge
Story split
duplicate dismissal
```

---

## 4.7 Same Story is not same Topic/Entity/Tag

These are not sufficient identity evidence alone:

```text
same Topic
same Subject
same Entity
same Tag
same Source
same Research Question
generic vocabulary overlap
historical Story Document
```

---

## 4.8 No alternate evidence path

Story correction does not create factual Evidence.

Story correction metadata is audit/cause information, not canonical evidence for real-world propositions.

---

# 5. CLAIM → STORY TRANSITION MODEL

The current repository deliberately enforces one-time Story association.

Phase 27 must replace that narrow invariant without weakening Claim provenance.

Preferred model:

```text
claims.story_id
= current pointer

claim_story_assignment_history
= append-only transition history
```

---

# 6. CLAIM STORY HISTORY

Generalize the existing assignment-history structure.

The exact migration may adapt to repository conventions, but semantically each transition must support:

```text
id
claim_id
from_story_id nullable
to_story_id nullable
correction_id
origin
reason_code
reason
occurred_at
```

Origins should include only actual supported cases, expected approximately:

```text
human
automatic
import
repair
```

Do not add provider as a direct authority unless the repository actually permits provider-origin Story mutation.

Provider suggestions remain suggestions.

Constraints should include:

```text
from_story_id != to_story_id

not both NULL
```

Indexes should support:

```text
Claim history
source Story history
destination Story history
correction history
chronological reconstruction
```

Remove the existing assumption equivalent to:

```text
UNIQUE(claim_id)
```

because multiple transitions are now valid.

Historical rows must remain immutable.

---

# 7. INITIAL ASSIGNMENT VS CORRECTION

Do not redefine every existing automatic Story assignment as a Story correction.

Keep the conceptual distinction:

```text
initial automatic assignment
= normal Story automation

later reassignment/unassignment/merge/split
= Story correction
```

Existing historical initial assignments must remain reconstructable.

Migration must not fabricate historical reassignments.

---

# 8. STORY CORRECTION AGGREGATE

Introduce one domain-specific correction aggregate.

Preferred semantic model:

```text
story_corrections

id
operation_type
origin
actor / actor reference where repository supports it
reason_code
reason
cause_class
caused_by_type nullable
caused_by_id nullable
occurred_at
```

Supported Phase 27 operation types should include:

```text
reassign
unassign
merge
split
duplicate_dismissal
```

If implementation of Claim extraction benefits from its own operation label:

```text
extract
```

may be added, but avoid creating an unnecessary new backend semantic if extraction is cleanly represented as:

```text
create Story
+
reassign Claims
```

A single correction may own:

```text
multiple Claim transitions
multiple lineage rows
manual metadata decisions
one durable reconciliation Job
```

This is important for merge/split atomicity.

Do not build a generic cross-domain event system.

---

# 9. CORRECTION CAUSE CLASS

Store a lightweight semantic cause classification on the Story correction:

```text
new_evidence
reprocessing
human_correction
administrative
```

This is a Phase 29 compatibility hook, not full processing provenance.

Use:

```text
caused_by_type
caused_by_id
```

where an exact existing cause exists.

Examples:

```text
newly promoted Claim
ArticleAnalysis
Job
user action
repair operation
```

The important distinction is:

```text
new world evidence changed our organization
```

versus:

```text
existing evidence was reinterpreted/corrected
```

Do not duplicate `cause_class` across every downstream record.

Downstream objects should reference the exact Story correction.

---

# 10. STORY LINEAGE

Introduce the smallest required Story identity lineage model.

Required relationships:

```text
merged_into
split_into
```

Only.

Do not automatically add:

```text
duplicate_of
superseded_by
related_to
parent_child
```

unless a concrete Phase 27 workflow requires them.

Duplicate approval becomes a merge.

Duplicate dismissal becomes a durable negative decision, not Story lineage.

---

# 11. STORY LINEAGE RULES

## Merge

```text
Story B
merged_into
Story A
```

means:

```text
B and A represent the same underlying Story

A is the current canonical Story

B remains historically inspectable
```

Rules:

```text
no self-edge
one merged_into destination per source
cycle prevention
transitive canonical resolution
merged source excluded from normal automatic matching
```

---

## Split

```text
Story S0
split_into
Story S1

Story S0
split_into
Story S2
```

is one-to-many.

Never force:

```text
S0 → one canonical child
```

A historical split source resolves to:

```text
its own historical view
+
list of active resulting Stories
```

---

# 12. FINAL SPLIT POLICY

Binding product decision:

> **A true Story split retires the source Story.**

A split means the source Story itself was an incorrect current grouping.

Therefore:

```text
S0
→ historical / retired

S1
→ active

S2
→ active
```

All Claims selected as current members must end up in resulting active Stories according to the approved split grouping.

The retired split source is excluded from normal automatic Story matching.

---

# 13. CLAIM EXTRACTION IS NOT A TRUE SPLIT

Newsroom must distinguish:

```text
MOVE CLAIM

EXTRACT

SPLIT STORY
```

## Move Claim

```text
Claim C
Story A → existing Story B
```

Meaning:

> This Claim belongs somewhere else.

---

## Extract

```text
selected Claims from Story A
→ newly created Story B

Story A remains active
```

Meaning:

> Story A remains valid, but part of it deserves a separate Story.

Backend implementation may compose:

```text
create Story
+
reassignment corrections
```

rather than inventing unnecessary architecture.

---

## Split Story

```text
Story A was itself an incorrect grouping

A retires

B and C become active
```

Meaning:

> The current Story identity was wrong.

Make these distinctions clear in API semantics and UI language.

---

# 14. SAME STORY VS RELATED STORY

Binding editorial rule:

## Same Story

Records describe the same underlying:

```text
event
decision
release
incident
proceeding
or continuously developing outcome
```

such that defining Claims can coexist on one chronological evidence ledger without changing the subject of the event.

Examples of changes that can remain within one Story:

```text
correction
contradiction
updated quantity
later confirmation
clarification
retraction
resolution
```

provided they concern the same underlying development.

---

## Related but separate Story

Stories share context, Entities, causes, consequences, or Questions but contain distinct defining events/decisions.

Each Story can be:

```text
corrected
reported
tracked
resolved
```

independently.

Do not merge merely because two developments are closely related.

---

## Follow-on development

A later development may depend on an earlier Story but have its own defining event.

Example pattern:

```text
announcement
→ investigation
→ ruling
```

Keep these as separate Stories unless Phase 27 finds a concrete product need for parent/child lineage.

Do not introduce parent/child lineage speculatively.

---

# 15. AUTOMATIC STORY MATCHING SIGNALS

Strong matching may consider repository-supported combinations such as:

```text
identical canonical Document identity
unique compatible defining Claim
strong proposition identity
compatible temporal identity
compatible location/event identity
Entity-backed defining proposition identity
```

Named-event/event-key information may corroborate matching.

It is not sufficient alone.

Weak signals insufficient alone:

```text
Topic
Subject
Entity
Tag
Source
Research Question
generic vocabulary
historical story_documents row
```

No vector Story identity engine.

No embedding infrastructure.

Use existing structured/deterministic retrieval first.

Optional provider classification may assist ambiguity only through existing AIRouter conventions and cannot mutate Story identity directly.

---

# 16. `story_documents` BINDING SEMANTICS

This is a mandatory Phase 27 correction.

Binding meaning:

```text
story_documents
= append-only historical Story/Document observation provenance
```

Do not delete/move historical rows when a Claim changes Story.

However:

```text
story_documents
must NOT be treated as current Story membership context
without filtering against current Claim membership.
```

---

# 17. CURRENT STORY DOCUMENTS

Current Story Document context must derive from:

```text
current Story
→ claims.story_id
→ ClaimEvidence
→ EvidenceSpan
→ DocumentVersion
→ Document
```

Implement one shared current-Story-document query abstraction.

Possible implementation:

```text
shared SQL helper
CTE
view
bounded projection
```

Do not materialize a new table unless query benchmarks justify it.

---

# 18. REMOVE STALE `story_documents` CURRENT-STATE USAGE

Audit and fix every relevant reader.

At minimum inspect:

```text
AutomaticStoryResolutionService
legacy StoryEvolution resolver
StoryEvolution corroboration
Source-targeted Report Story discovery
Workbench Story/Monitor Source context
Story update classification
Story candidate entity/location/source/time summaries
```

Historical Story timelines may continue using historical `story_documents`.

Current candidate matching must not.

---

# 19. STALE-CONTEXT RELEASE TEST

Mandatory test:

```text
Document D
→ Claim C
→ Story A

user moves C
A → B
```

Historical:

```text
story_documents(A, D)
```

may remain.

But D must no longer:

```text
rank A as current candidate
count as current corroboration for A
cause Source-targeted current Report selection for A
appear as current Story A document context
influence current Story A entity/event/location matching
```

unless another current Claim in A independently reaches D.

---

# 20. STORY ENTITIES

Binding effective model:

```text
effective current Story Entities

=

explicit/manual Story-Entity relationships

UNION

Entities on currently assigned Claims
```

Claim-derived Story Entities are **derived current projection state**.

Manual Story-Entity relationships are human decisions.

These authorities must be distinguishable.

---

# 21. STORY ENTITY STORAGE

The current:

```text
story_entities(story_id, entity_id, origin)
```

shape may not be sufficient because one row cannot safely represent both:

```text
manual authority
derived Claim relationship
```

if uniqueness collapses them.

Choose the smallest safe live-repository-compatible design.

Options may include:

```text
separate manual and derived tables
```

or:

```text
authority-aware representation that permits coexistence
```

Do not choose solely for schema elegance.

Manual relationships must survive projection rebuild.

Derived relationships must be rebuildable.

---

# 22. STORY ENTITY RECONCILIATION

After:

```text
Claim reassignment
Claim unassignment
Story merge
Story split
```

recompute derived current Story Entities for all affected Stories.

Do not mutate Claim-Entity relationships merely because Claim Story membership changed.

Claim Entities remain attached to the Claim.

---

# 23. ENTITY MERGE COMPATIBILITY

Phase 27 does not need broad Entity merge UX.

But Story-Entity reconciliation should tolerate existing/future Entity merge lineage.

Prefer effective reads through current/canonical Entity resolution.

Avoid introducing Phase 27 behavior that prevents later Entity merge reconciliation.

---

# 24. STORY TAG AUTHORITY

Current repository contains both:

```text
story_tags
tag_assignments
```

The long-term desired direction is:

```text
tag_assignments
= modern Tag assignment authority

story_tags
= compatibility projection / legacy representation
```

but Phase 27 must not perform a broad Tag migration unless required for correctness.

---

# 25. STORY TAG PHASE 27 RULES

Claim move:

```text
no Story Tag mutation
```

Story merge:

```text
destination keeps its manual Tags

source historical Tags remain historical

copying source Tags to destination
requires explicit user selection
```

Story split:

```text
children do not automatically inherit manual Tags

user explicitly assigns desired Tags
```

Derived/automatic Tags may later be recomputed according to their existing authority model, but Phase 27 must not deepen dual-authoritative Tag behavior.

Use existing service paths for touched Tag changes so compatibility writes remain coherent.

Add focused integrity/parity checks for Story Tags touched by Phase 27 corrections where appropriate.

---

# 26. STORY TOPICS AND SUBJECTS

Treat explicit Story Topics and Subjects as Story-level metadata/human intent unless live code proves a different authority.

Do not automatically union them during merge.

Do not automatically clone them during split.

Merge preview may offer explicit metadata propagation choices.

Split preview may offer explicit per-child assignment.

---

# 27. REVIEW STATE

Story review state is Story-specific human decision state.

Never silently propagate review state through:

```text
merge
split
extract
```

A review decision about one historical Story is not automatically a review decision about another.

---

# 28. GENERAL METADATA PROPAGATION RULE

Binding product rule:

> **Derived metadata recomputes. Human-authored metadata propagates only by explicit decision.**

Equivalent:

```text
derived
→ recompute

human intent
→ explicitly propagate
```

This applies throughout Phase 27.

---

# 29. MERGE SEMANTICS

A merge asserts:

```text
Story B
and Story A
are the same underlying Story
```

One explicit canonical destination is required.

Example:

```text
B → A
```

After commit:

```text
A active/current
B historical/non-matchable
```

B remains inspectable.

Historical:

```text
StoryRevisions
StoryEvolution
Reports
Alerts
Claim memberships
Research context
Ask audit
```

remain.

---

# 30. MERGE PREVIEW

Merge must have a bounded, non-mutating preview.

Display at minimum:

```text
source Story
destination Story
current revisions
date ranges
current Claim counts
key Claims
current Documents
Entities
Topics
Subjects
Tags
Source counts
linked Research Questions
linked Watches
Living Reports
manual metadata differences
expected Claim moves
Watch/Monitor impact
```

If Source terminology does not support true independence, display:

```text
distinct Source records
```

not unsupported independence claims.

---

# 31. MERGE STALE-STATE PROTECTION

The merge preview must carry enough expected-current-state identity to reject materially stale execution.

Use repository-appropriate values such as:

```text
current revision identity
membership fingerprint/version
correction sequence
Claim membership hash
```

Do not invent a giant optimistic-locking framework if current IDs can accomplish this.

Execution must re-read current state in the mutation transaction.

If material state changed:

```text
reject as stale
or
require refreshed preview
```

Do not silently execute an obsolete merge decision.

---

# 32. MERGE CONFLICT CHECKS

Before mutation verify:

```text
both Stories exist
source != destination
source is eligible/current
destination is eligible/current
no lineage cycle
source not already merged elsewhere
preview still current
Claim moves remain valid
manual authority is not violated
duplicate dismissal policy does not forbid operation
```

---

# 33. MERGE CURRENT CLAIM MEMBERSHIP

Current Claims from merged source normally consolidate to destination.

Each changed Claim receives an append-only membership transition tied to the same merge correction.

Do not rewrite historical Claim Story membership rows.

---

# 34. MERGE WATCH / MONITOR POLICY

Binding product decision:

> **A Story-targeted Watch automatically follows the canonical merge destination.**

Reason:

Merge asserts identity continuity.

If:

```text
Watch W targets Story B

B merged_into A
```

then:

```text
historical target
= B

current effective target
= A
```

The merge preview must disclose:

```text
which Watches follow the destination
which Monitors/scopes will be reconciled
```

The user's merge approval authorizes this consequence.

Do not require a second confirmation.

Do not duplicate a Watch merely because its historical target was merged.

---

# 35. MERGE MONITOR HISTORY

Do not rewrite pinned historical Monitor scope.

Current operational Monitor scope may be reconciled or recreated according to existing Monitor conventions.

Historical scopes remain auditable.

Optional discovery/provider failures must not break the committed merge.

---

# 36. MERGE MANUAL METADATA POLICY

Destination Story keeps its current manual metadata.

Source Story retains its manual metadata historically.

No automatic union.

Merge preview may offer explicit selections such as:

```text
copy Topic X from B to A
copy Subject Y from B to A
copy Tag Z from B to A
copy manual Entity link E from B to A
```

Only explicitly selected metadata is propagated.

Review state is never propagated automatically.

---

# 37. MERGE REPORT / QUESTION / ALERT BEHAVIOR

Merge transaction must not synchronously generate Reports, Alerts, or Question assessments.

The committed correction schedules durable reconciliation.

Old Reports remain.

Old Alerts remain.

Old Question assessment history remains.

Current state may receive new revisions/assessments through normal downstream services.

---

# 38. SPLIT SEMANTICS

A true split asserts:

```text
one current Story was actually multiple incompatible developments
```

The source Story becomes historical/retired.

Resulting Stories become active.

The user must explicitly approve final Claim grouping.

Provider/deterministic clustering may assist preview but cannot finalize a split.

---

# 39. SPLIT PREVIEW

Display at minimum:

```text
source Story
current Claims
Claim dates
Documents
Sources
Entities
Topics
Subjects
Tags
Research Questions
Reports
Watches
suggested clusters
manual metadata
expected resulting Stories
```

Claims must be assignable explicitly into groups.

Support bounded selection/pagination for Stories with many Claims.

Do not render hundreds of Claims as one unbounded form.

---

# 40. SPLIT WATCH POLICY

Binding product decision:

> **A Watch targeting a split source Story must not silently choose a child.**

For:

```text
Watch W → S0

S0 split_into S1, S2
```

preserve:

```text
historical target = S0
```

Current Story target becomes:

```text
ambiguous / needs review
```

User can choose:

```text
S1
S2
both
another current Story
```

Normal Source acquisition may continue where valid, but Story-target resolution must not guess.

Persist a real review/ambiguous state according to the existing Watch/Monitor domain rather than deriving it only in the frontend.

---

# 41. SPLIT RESEARCH QUESTION POLICY

Story-scoped Research Questions must not silently choose one split child.

Preserve historical scope.

For future evaluation/search behavior use the smallest existing-domain-compatible approach:

```text
lineage-aware future scope
or
needs-review scope state
```

based on the current Research Question schema.

Do not change historical Question assessments merely because the Story split later.

---

# 42. SPLIT MANUAL METADATA POLICY

Source Story keeps historical metadata.

Children receive:

```text
derived Documents from their Claims
derived Entities from their Claims
other explicitly recomputable metadata
```

Manual Story metadata does not automatically inherit.

Split preview may suggest metadata for each child.

User confirmation makes it authoritative.

Review state does not inherit.

---

# 43. CLAIM REASSIGNMENT

Support:

```text
Claim C
Story A → Story B
```

Validation must confirm:

```text
Claim current Story is still A
destination B is current/eligible
manual authority permits transition
B is not merged/inactive
preview/current state is not stale
```

Create one Story correction.

Append one transition.

Update:

```text
claims.story_id = B
```

Schedule reconciliation for both A and B.

---

# 44. CLAIM UNASSIGNMENT

Support:

```text
Story A → NULL
```

A Claim remains valid evidence-backed intelligence after unassignment.

Unassignment does not:

```text
reject Claim
remove Evidence
weaken Claim provenance
delete Entity relations
```

It changes only Story membership.

Accepted unassigned Claims must remain discoverable in Workbench/retrieval if the current domain permits accepted unassigned Claims.

---

# 45. MANUAL UNASSIGNMENT IS AUTHORITATIVE

A manually unassigned Claim is not equivalent to:

```text
never assigned
```

Automatic Story resolution must distinguish:

```text
no assignment history
→ eligible for initial assignment
```

from:

```text
latest human transition to NULL
→ intentionally unassigned
→ automatic resolver defers
```

Do not add a redundant lock boolean unless actual query/performance needs justify it.

History is the authority.

---

# 46. DUPLICATE STORY SUGGESTIONS

Add bounded duplicate candidate detection/review using existing structured signals.

Signals may include:

```text
overlapping accepted Claims
strong proposition identity
same canonical Entities
compatible event identity
narrow date overlap
defining Documents
Source/document lineage where useful
Research Question context
normalized titles
```

Weak overlap is insufficient.

Do not add vector duplicate infrastructure.

Optional AIRouter classification may assist suggestion ranking only.

Provider output cannot merge Stories.

---

# 47. DUPLICATE SUGGESTION IDENTITY

Persist enough durable suggestion identity to prevent unchanged duplicate noise.

Support:

```text
suggested
approved
dismissed
superseded/reconsiderable if materially new evidence appears
```

Avoid creating a generic suggestion framework unless one already exists and fits.

---

# 48. DUPLICATE APPROVAL

Duplicate approval calls the canonical merge service.

No alternate merge mutation path.

---

# 49. DUPLICATE DISMISSAL

A dismissal is durable negative human authority.

It means:

```text
do not keep presenting this unchanged pair as the same Story
```

Persist an exclusion/decision identity.

Automatic candidate retrieval may still discover the pair internally, but final suggestion/assignment logic must honor the dismissal until materially changed evidence justifies a new review state.

---

# 50. AUTOMATIC STORY RESOLVER AFTER PHASE 27

Update the existing resolver.

Do not create a second matcher.

The resolver must:

```text
exclude merged Stories
exclude retired split sources
resolve canonical merge targets
respect duplicate dismissals
respect manual reassignment
respect manual unassignment
use current Claims
use current Story Documents
use effective current Story Entities
treat Tags as weak context
re-read authority inside mutation boundary
```

---

# 51. STALE AUTOMATIC JOBS

Mandatory behavior:

```text
automatic Job proposes/selected Story A
```

but before mutation:

```text
user moves Claim to B
or
user unassigns Claim
or
A merges into C
```

The worker must:

```text
re-read current state
respect human/current authority
canonicalize where valid
or defer/complete without undoing the decision
```

No check-then-write outside the final transaction.

---

# 52. STORY EVOLUTION

Audit the current taxonomy before adding anything.

Phase 27 may add or clarify only grounded distinctions useful to Story correction.

Potential categories include:

```text
new_development
corroboration
contradiction
correction
retraction
clarification
escalation
resolution
source_disagreement
evidence_strength_change
identity_correction
```

Do not force all categories if the current domain does not need them.

---

# 53. IDENTITY CORRECTION VS FACTUAL EVOLUTION

Keep distinct:

```text
Story identity correction
```

and:

```text
new fact about the Story
```

A merge/split/reassignment may be reflected in a timeline, but the exact Story correction must remain the authoritative cause.

Do not pretend a Story merge was a new real-world event.

---

# 54. CORRECTION VS RETRACTION

A correction is not automatically a retraction.

Retraction requires evidence that a Source/person/organization explicitly withdrew or disavowed a claim/publication.

Do not derive retraction solely from:

```text
Claim moved
Story split
Story merged
contradiction detected
```

---

# 55. CORROBORATION TERMINOLOGY

Until Phase 28 Source dependency is complete:

```text
distinct Source records
```

is not automatically:

```text
independent confirmation
```

If Phase 27 touches relevant code/UI:

use:

```text
distinct_source_count
lineage_group_count
```

where accurate.

Avoid `independent_source_count` unless the actual calculation explicitly defines the dependency model.

Existing misleading terminology identified by reconciliation should be corrected when touched, and otherwise explicitly deferred to Phase 28.

---

# 56. CURRENT VS HISTORICAL STORY REVISION BEHAVIOR

Old StoryRevisions remain immutable.

Correction may create new current Story revisions where materially appropriate.

Do not edit old revisions.

For merge:

```text
destination may receive new revision
source historical revisions remain
```

For split:

```text
source old revisions remain
children receive current revisions
```

For reassignment:

```text
old and new Stories may each require a new current revision
```

Use existing materiality rules where appropriate.

---

# 57. `stories.current_revision_id`

The repository has inconsistent current-revision semantics.

Do not expand Phase 27 into a broad current-revision refactor unless required.

Phase 27 must explicitly choose one reliable current revision read rule for its own operations and tests.

If current code effectively treats latest revision as authoritative, preserve that consistently.

Record `stories.current_revision_id` as a Phase 29 simplification/reliability item unless correcting it now is necessary for Phase 27 correctness.

---

# 58. LIVING REPORT RECONCILIATION

Old ReportRevisions remain immutable.

Story correction does not mutate historical Reports.

Durable correction reconciliation may request Report reevaluation for affected current Stories.

Report generation must continue through the existing canonical report path.

No correction-specific report engine.

A correction ID may be recorded as exact non-evidence cause alongside the current Claim set.

---

# 59. ALERT RECONCILIATION

Old Alerts and deliveries remain immutable.

A Story correction does not automatically send an Alert.

Alerts arise only through existing Alert rules after a new ReportRevision or other existing valid cause.

This prevents correction operations from creating notification storms.

Replay must not duplicate Alert delivery.

---

# 60. RESEARCH QUESTION RECONCILIATION

Story correction service must not directly mutate:

```text
assessment_state
Question lifecycle status
Evidence Gap truth
```

Instead enqueue normal Question reevaluation for affected Questions.

Questions linked directly to moved Claims remain linked unless existing domain semantics say otherwise.

Historical assessment snapshots remain unchanged.

Research Tasks remain historical records of what was searched.

A Story correction cannot retroactively satisfy a Gap.

---

# 61. WATCH SOURCE MONITORING

Story corrections do not alter approved Watch Sources merely because Story identity changed.

Watch Source acquisition continues through normal Monitor/Watch architecture.

Only Story-target semantics are reconciled.

Do not silently add/remove Sources because a Story merged or split unless the user separately authorizes that action through existing Watch mechanisms.

---

# 62. PHASE 26 ENTITY INTEGRATION

Claim-Entity relationships do not move when Claims change Stories.

They remain relationships to the Claim.

Current Story Entity view recomputes from current Claim membership plus explicit manual Story Entity decisions.

Historical Story context remains reconstructable from history/revisions.

---

# 63. PHASE 26 TAG INTEGRATION

Claim and Document Tags remain unchanged by Story membership correction.

Manual Story Tags follow the explicit metadata policy.

Derived automatic Story Tag behavior remains bounded by existing Tag authority and is not rearchitected broadly here.

---

# 64. SHARED RETRIEVAL / WORKBENCH

Reuse Phase 26 shared typed SQL/FTS retrieval.

No correction-specific search engine.

Workbench must support:

```text
current Story
historical merged Story
historical split source
split children
current Claim membership
historical Claim membership
Story correction timeline
Story lineage
duplicate suggestions
unassigned accepted Claims where valid
```

Normal search should prefer current active Story identity.

Historical match must remain visible with labels such as:

```text
merged into Story A
split into Stories B and C
historical membership
```

---

# 65. ASK INTEGRATION

Ask must distinguish current from historical membership.

Examples Phase 27 should support:

```text
Which Story does Claim C belong to now?

Was Claim C always in Story B?

Why was Story A merged into Story B?

Why was Claim C moved?

What happened to Story S0 after the split?

Which Stories resulted from S0?
```

Answers about correction reasons must rely on persisted correction/history records.

Do not infer the reason from semantic similarity after the fact.

---

# 66. ASK CORRECTION CITATIONS

Add stable retrieval packet types/IDs for the smallest necessary Phase 27 audit records, such as:

```text
story correction
Story lineage
Claim Story transition
```

Existing packet-bound citation validation remains mandatory.

Correction rationale is audit evidence of:

```text
why the user/system changed Story organization
```

It is not factual evidence that the real world itself supports the rationale.

For example:

```text
"The user merged these because they believed X"
```

is different from:

```text
"X is established by canonical evidence."
```

Preserve that distinction in Ask synthesis.

---

# 67. API

Use existing `/api/v1` conventions.

Provide bounded endpoints or repository-equivalent APIs for:

```text
merge preview
merge execute

split preview
split execute

Claim reassignment
Claim unassignment

extract into new Story if exposed as first-class UX

Story lineage
Story correction history

duplicate suggestions
duplicate approval
duplicate dismissal
```

Mutation APIs must carry enough expected-current-state identity to detect stale operations.

Avoid raw database-ID manipulation as the primary UX.

---

# 68. FRONTEND

Phase 27 frontend scope is limited to Story correction workflows.

Do not build the Phase 28 unified investigative shell now.

Required UX:

```text
Story correction actions
Claim move
unassign
extract
merge
split
history
lineage
duplicate review
```

---

# 69. MERGE UX

Preview should make consequences obvious:

```text
canonical destination
Claims moving
historical source preserved
Watches following canonical Story
Monitor reconciliation
manual metadata choices
Report/Question impacts
```

User approval authorizes all displayed merge consequences.

---

# 70. SPLIT UX

Allow explicit Claim grouping.

Display:

```text
dates
Entities
Documents
Sources
Tags
key Claims
suggested clusters
```

Make clear:

```text
source Story becomes historical
children become current
Story-targeted Watches require review
manual metadata must be assigned explicitly
```

---

# 71. EXTRACT UX

Expose a simple action where useful:

```text
Extract selected Claims into new Story
```

Explain:

```text
current Story remains active
new Story is created
selected Claims move
history is preserved
```

This avoids using "split" for partial separation.

---

# 72. UNASSIGN UX

Explain:

```text
Claim remains accepted
Claim remains evidence-backed
Claim becomes temporarily/currently unassigned
automatic Story matching will not silently reassign it
```

---

# 73. CORRECTION HISTORY UX

Story detail should expose a bounded timeline of:

```text
Claim moved in
Claim moved out
merged into
split into
duplicate dismissed
manual correction reason
origin
time
```

Do not expose raw internal Job machinery unless requested through existing operational UI.

---

# 74. DURABLE CORRECTION RECONCILIATION

Preferred architecture:

```text
Story correction transaction
        ↓
persist correction + current membership + lineage
        ↓
enqueue durable correction reconciliation Job
        ↓
re-read current state
        ↓
rebuild current projections
        ↓
StoryRevision reevaluation
        ↓
Report reevaluation
        ↓
Alert evaluation
        ↓
Question reevaluation
        ↓
Search/Workbench reconciliation
```

Use existing JobService.

Do not create another worker framework.

---

# 75. SQLITE TRANSACTION BOUNDARY

Atomic mutation transaction must contain only necessary current-state identity changes.

## Reassignment

Atomically:

```text
re-read current membership
validate authority
create correction
update claims.story_id
append transition
mark affected projections dirty
enqueue durable reconciliation Job
```

---

## Unassignment

Atomically:

```text
create correction
update claims.story_id = NULL
append transition
record intentional human authority
mark dirty
enqueue Job
```

---

## Merge

Atomically:

```text
validate source/destination
validate stale preview
create correction
append selected Claim transitions
update current Claim pointers
create merged_into lineage
retire source Story
record duplicate decision resolution
persist explicit metadata propagation decisions
reconcile effective Watch target state required for canonical merge
mark projections dirty
enqueue Job
```

Do not generate reports or call providers inside transaction.

---

## Split

Atomically:

```text
validate current source
validate Claim grouping
validate stale preview
create correction
create child Stories
append Claim transitions
update current Claim pointers
create split_into lineage
retire source Story
record explicit metadata choices
mark Story-targeted Watch resolution needs-review
mark projections dirty
enqueue Job
```

---

# 76. RECONCILIATION JOB

Dedicated Phase 27 correction reconciliation Job should:

1. load exact correction;
2. verify membership transition chain;
3. resolve active lineage;
4. rebuild current Story Document context;
5. rebuild derived Story Entities;
6. reconcile touched Tag compatibility state if required;
7. create new Story revisions where material;
8. reconcile current Monitor Story scopes;
9. reevaluate Living Reports;
10. evaluate Alerts only through normal report causality;
11. reevaluate affected Research Questions;
12. mark/rebuild search projection;
13. run bounded integrity validation;
14. complete with deterministic counts/identities.

Use correction ID for logical idempotency.

---

# 77. CORRECTION JOB IDEMPOTENCY

Replay of the same correction must not create:

```text
duplicate transitions
duplicate lineage
duplicate Story revisions
duplicate Reports
duplicate Alerts
duplicate Question history
duplicate search records
duplicate Watch effects
```

Database uniqueness remains the final idempotency boundary.

Do not rely on check-then-insert only.

---

# 78. FAILURE ISOLATION

Once the Story correction transaction commits:

```text
Report failure
Question failure
search failure
Alert failure
projection failure
```

must not roll back or invalidate the committed Story correction.

Downstream Jobs recover independently.

---

# 79. HISTORICAL INTEGRITY FIX

The reconciliation audit identified a critical issue:

Some current integrity checks validate historical automatic Story-stage results against the Claim's **current** Story membership.

After Phase 27, that is wrong.

Mandatory invariant:

> Historical automatic assignment validity is checked against the historical membership/revision chronology that existed at the time, not against the Claim's current Story.

Release test:

```text
automatic Job correctly assigns Claim C → Story A
Job completes

later human correction:
C → Story B

check_database()
```

Expected:

```text
PASS

historical automatic assignment valid
current human correction valid
```

Do not let valid corrections make historical Jobs appear corrupt.

---

# 80. MIGRATION

Only create migration after live audit.

Accepted starting architecture was schema version 28.

Migration should:

```text
add story_corrections
add story_lineage
generalize claim_story_assignment_history
add duplicate/exclusion authority if required
separate manual vs derived StoryEntity authority
add minimal Watch split-review representation if needed
```

Avoid speculative Phase 28/29 schema.

---

# 81. LEGACY ASSIGNMENT HISTORY MIGRATION

Existing historical assignment rows represent initial assignment only.

Convert without fabricating history.

Where safe infer origin from real provenance:

```text
automatic Claim with ArticleAnalysis provenance
→ automatic
```

otherwise use repository-supported human/import origin.

Use:

```text
reason_code = initial_assignment
```

or equivalent.

If no trustworthy correction cause exists:

```text
legacy cause may be explicit NULL
or deterministic migration identity
```

Do not invent human reasons.

---

# 82. MIGRATION VALIDATION

Mandatory:

```text
fresh database → new schema

schema 28 → new schema

repeat migration behavior

foreign keys

integrity

existing Story assignment reconstruction

historical assignment transition reconstruction

no fabricated reassignments
```

---

# 83. LOGICAL EXPORT

Extend logical export with durable Phase 27 state:

```text
Story corrections
Story lineage
Claim Story transition history
duplicate decisions/suggestions if durable
manual authority required for reconstruction
```

Current Story membership must reconstruct.

Historical membership must reconstruct.

Merge lineage must reconstruct.

Split lineage must reconstruct.

Do not unnecessarily export rebuildable search/projection state as canonical truth.

Maintain compatibility policy for existing StoryEntity/Tag projections until later simplification.

---

# 84. INTEGRITY

`check_database()` remains structural.

Add checks for:

```text
Story correction references valid
transition chain valid
transition chain ends at claims.story_id
no impossible NULL→NULL transitions
no lineage self-edge
no merge cycles
merged source resolves to one canonical target
split source has valid one-to-many children
retired split source not active match target
manual unassignment authority coherent
duplicate dismissals valid
StoryEntity projection/manual authority coherent
correction Job references coherent
historical automatic assignment checks use historical membership
```

Do not make integrity checks judge subjective Story quality.

---

# 85. CONCURRENCY

Mandatory tests:

## Concurrent identical merge

Allowed result:

```text
one logical merge
```

or:

```text
one success
one explicit stale/already-applied outcome
```

Never two competing correction graphs.

---

## Concurrent Claim reassignment

Only one current membership may win.

Other request must:

```text
detect stale state
or
return explicit conflict
```

---

## Manual vs automatic

Manual/current authority wins.

---

## Merge vs automatic assignment

Worker must:

```text
canonicalize merged target
or
defer safely
```

Never restore membership to retired source.

---

## Split vs automatic assignment

Retired split source must not receive new automatic assignments.

---

# 86. INTERRUPTION / RECOVERY TEST

Simulate:

```text
correction transaction committed

process dies before reconciliation completes
```

Restart worker.

Expected:

```text
same persisted correction found
same Job identity recovered
all required downstream reconciliation completes
no duplicates
```

---

# 87. PERFORMANCE BOUNDS

Do not assume Story corrections are always tiny.

Benchmark representative:

```text
small Story
medium Story
large Story
```

Pay attention to:

```text
Claim transitions
SQLite write lock duration
projection rebuild
Report fan-out
Question fan-out
search refresh
```

Avoid one downstream Job per Claim unless existing architecture requires it.

Prefer correction-level bounded reconciliation.

If extremely large corrections are operationally unsafe:

```text
impose explicit bounded UX limits
```

before inventing distributed transaction machinery.

---

# 88. EVALUATION INTEGRATION

Extend existing:

```text
newsroom.evals
```

Do not create another evaluation framework.

The repository already contains a semantic corpus.

Add Phase 27 fixtures/checkpoints for:

```text
Claim reassignment
unassignment
merge
split
extract
historical membership
stale Story Document context
duplicate approval/dismissal
manual authority
```

---

# 89. EVALUATION METRICS

Add targeted evaluation metrics where useful:

```text
Claim current-membership correctness
historical-membership correctness
merge correctness
split correctness
stale-context correctness
automatic-assignment correction burden
```

Do not distort existing false-merge/false-split metrics.

Use separate transition/history metrics.

---

# 90. PRODUCTION STORY QUALITY TELEMETRY

Do not create a new metrics platform.

Capture durable inputs from domain records so later analysis can calculate:

```text
automatic assignments
manual reassignments
manual unassignments
merge suggestions
merge approvals
merge dismissals
splits
time-to-correction
origin
resolver algorithm/version
```

Later phases should be able to calculate:

```text
manual corrections per 100 automatic Story assignments
```

This is required for Progressive Autonomy decisions.

---

# 91. RESOLVER ALGORITHM IDENTITY

Persist a bounded resolver algorithm/version identifier where current automatic assignment result already stores:

```text
reason
signals
candidate IDs
Job identity
```

Do not introduce full Phase 29 processing-run architecture.

We only need enough Phase 27 telemetry to know which resolver behavior created an automatic assignment later corrected by a human.

---

# 92. ENGINEERING ACCEPTANCE GATE

Phase 27 has two separate acceptance dimensions.

First:

# ENGINEERING ACCEPTANCE

Must pass all relevant:

```text
unit tests
integration tests
migration tests
worker tests
replay tests
concurrency tests
integrity tests
API tests
frontend tests
logical export tests
E2E tests
compileall
frontend typecheck
frontend production build
focused evaluation regressions
full backend suite
```

No accepted invariant may rely solely on mocks if a real SQLite/worker test is practical.

---

# 93. INTELLIGENCE VALUE ACCEPTANCE GATE

Second:

# INTELLIGENCE VALUE ACCEPTANCE

Phase 27 must demonstrate that the correction architecture improves Story quality rather than merely adding machinery.

At minimum targeted evaluation should demonstrate:

```text
incorrect assignments can be repaired

historical truth remains queryable

correction does not poison current matching

merge produces one coherent current Story

split produces coherent active children

partial separation does not require false split semantics

manual decisions cannot be immediately undone by automation

duplicate dismissal prevents repetitive noise

correction burden is measurable
```

Do not claim broad statistical Story accuracy from a small fixture set.

The gate is functional intelligence value, not marketing accuracy.

---

# 94. REQUIRED UNIT / INTEGRATION TESTS

At minimum:

```text
initial assignment still works

Claim reassignment

Claim unassignment

manual unassignment blocks automatic reassignment

multiple transition history

transition-chain integrity

merge

merge chain

merge cycle prevention

split one-to-many

retired split source non-matchable

extract/new Story workflow

duplicate suggestion

duplicate approval

duplicate dismissal

dismissal replay suppression

manual metadata merge policy

manual metadata split policy

Story Topics/Subjects policy

Story Tag policy

Story Entity rebuild

Story Document current-vs-historical semantics

StoryRevision historical immutability

ReportRevision historical immutability

Alert historical immutability

Question history immutability

Research Task historical immutability

Watch merge canonical follow

Watch split ambiguity/review

Monitor historical scope preservation

Workbench current/historical Story retrieval

Ask current Story membership

Ask historical membership

Ask why move

Ask why merge

Ask why split

logical export reconstruction

integrity historical assignment

migration fresh/upgrade/repeat

foreign keys
```

---

# 95. REQUIRED E2E TEST — REASSIGNMENT

Construct real canonical pipeline data:

```text
Source
→ Document
→ Evidence
→ Claim
→ Story A
```

Then user moves Claim to Story B.

Prove:

```text
claims.story_id = B

history contains A → B

Story A current Documents no longer include moved-only Document

Story B current context includes it

historical Story A timeline still can

automation cannot undo move

Workbench shows current B and historical A

Ask answers current and historical membership
```

---

# 96. REQUIRED E2E TEST — MERGE

Create:

```text
Story A
Story B
current Claims in both
Watch targeting B
historical revisions
```

Approve:

```text
B → A
```

Prove:

```text
A active
B historical
Claims consolidate
lineage preserved
Watch follows A
historical Watch target remains B
Monitor history preserved
old revisions remain
new revision/report reconciliation happens durably
no duplicate Alert
Workbench finds B historically
Ask explains merge from correction record
```

---

# 97. REQUIRED E2E TEST — SPLIT

Create:

```text
Story S0
Claims representing two incompatible developments
Watch targeting S0
Report
Question
```

Approve:

```text
S0 → S1 + S2
```

Prove:

```text
S0 retired
S1 active
S2 active
Claims grouped exactly as approved
S0 history intact
Watch target enters review/ambiguous state
no child silently selected
children receive derived current Documents/Entities
manual metadata not silently copied
Question reconciliation occurs normally
Workbench/Ask show lineage
```

---

# 98. REQUIRED E2E TEST — EXTRACT

Create valid Story A.

Move selected Claims into new Story B without retiring A.

Prove:

```text
A remains active
B becomes active
selected Claims transition A → B
unmoved Claims remain A
history preserved
operation is not represented as a true split lineage
```

unless implementation has a justified explicit extract lineage that does not violate the minimal lineage rule.

---

# 99. REQUIRED E2E TEST — HISTORICAL INTEGRITY

Create:

```text
automatic Job J
assigns Claim C → Story A

J completes
```

Then:

```text
human C → Story B
```

Run:

```text
check_database()
```

Must pass.

Historical Job J remains valid against historical chronology.

---

# 100. REQUIRED E2E TEST — INTERRUPTION

Commit correction.

Terminate before downstream reconciliation.

Resume worker.

Prove:

```text
same correction
same logical Job
all projections converge
no duplicate Reports
no duplicate Alerts
no duplicate Question transition
no duplicate search state
```

---

# 101. FRONTEND VALIDATION

Run current repository-standard frontend validation.

At minimum if available:

```text
TypeScript check
production build
relevant component tests
```

Do not claim success for checks not actually run.

---

# 102. CHECKPOINT STRATEGY

Because Phase 27 crosses schema, automation, history, downstream Jobs, retrieval, and UI, use coherent checkpoints.

Suggested sequence:

## Checkpoint A — Identity foundations

Implement:

```text
story_corrections
transition-capable Claim Story history
story_lineage
manual authority semantics
migration
integrity foundation
```

Validate focused tests.

Commit.

---

## Checkpoint B — Current-state correctness

Implement:

```text
Claim reassignment
unassignment
current Story Documents
StoryEntity authority/projection
automatic resolver compatibility
duplicate exclusions
```

Validate focused tests and races.

Commit.

---

## Checkpoint C — Merge

Implement:

```text
merge preview
merge execution
canonical resolution
Watch merge policy
manual metadata selection
duplicate approval/dismissal
durable reconciliation
```

Validate merge E2E.

Commit.

---

## Checkpoint D — Split / Extract

Implement:

```text
true split
retired source
one-to-many lineage
Watch ambiguity
manual metadata choices
extract workflow
split suggestions where justified
```

Validate split/extract E2E.

Commit.

---

## Checkpoint E — Intelligence integration

Implement:

```text
Workbench
Ask
correction timeline
API
frontend
evaluation fixtures
telemetry
```

Validate current/historical behavior.

Commit.

---

## Final checkpoint — Production closure

Implement/finalize:

```text
logical export
integrity
migration matrix
replay
recovery
concurrency
performance bounds
full test suite
frontend build
documentation
```

Commit final completion state.

Checkpoint decomposition may be adjusted to fit actual repository dependencies.

Avoid microcommit confetti.

---

# 103. INTERRUPTION RESUME RULE

If work is interrupted:

1. inspect current branch/HEAD;
2. inspect tracked worktree/index;
3. inspect existing Phase 27 checkpoint commits;
4. identify last fully validated capability;
5. preserve legitimate uncommitted work;
6. resume the first incomplete requirement.

Do not reset to an assumed starting state.

---

# 104. OUT OF SCOPE — PHASE 28A

Do not implement:

```text
CoverageRun architecture
observation denominator
full Source dependency/evidence families
Evidence Fragility
Counterfactual Evidence Lab
Qualified Negative Evidence
blind-spot engine
research prioritization
```

except minimal compatibility hooks required by Phase 27.

---

# 105. OUT OF SCOPE — PHASE 28B

Do not implement:

```text
Attention Engine
Simple/Advanced mode
capability-level risk gating
progressive autonomy configuration
unified investigative frontend shell
Competing Hypotheses
Alert value optimization
```

Phase 27 only records telemetry needed later.

---

# 106. OUT OF SCOPE — PHASE 29

Do not implement:

```text
full processing-run identity
bitemporal knowledge framework
Shadow Reprocessing
Belief Diff
projection registry
global Job/backfill consolidation
retention policy
logical restore/import framework
global event timeline
SLO architecture
broad Tag authority migration
```

unless a tiny non-speculative hook is necessary for Phase 27 correctness.

---

# 107. OUT OF SCOPE — PHASE 30

Do not implement:

```text
Newsroom Lite
full temporal benchmark expansion
long-term dogfood framework
feature subtraction release gate
```

Phase 27 should only extend the existing evaluation subsystem enough to measure its own value.

---

# 108. NO NEW PLATFORM SPRAWL

Do not introduce:

```text
vector database
embedding service
new hosted database
new orchestration system
new provider stack
external notification platform
```

for Phase 27.

Continue:

```text
SQLite
existing JobService
shared SQL/FTS retrieval
AIRouter only where justified
existing provider budgets
existing canonical evidence path
```

---

# 109. USER AUTHORITY PRINCIPLE

Phase 27 must make Story organization **correctable without becoming fragile**.

The final authority hierarchy should effectively be:

```text
canonical evidence provenance
cannot be rewritten by Story correction

current Story organization
can be corrected

human correction
beats stale automatic organization

historical organization
remains auditable
```

---

# 110. FINAL UX ACCEPTANCE SCENARIO

The finished system should support this entire sequence.

## Initial state

Newsroom automatically creates:

```text
Story A
```

with:

```text
Claims
Documents
Entities
Tags
Research Questions
Reports
StoryEvolution
```

---

## Duplicate correction

Newsroom suggests Story B may be the same Story.

User opens merge preview and sees:

```text
key Claims
dates
Documents
Entities
Tags
distinct Sources
Research Questions
Reports
Watches
manual metadata choices
```

User approves:

```text
B → A
```

Result:

```text
A remains current
B becomes historical
current Claims consolidate
old revisions remain
Watch targeting B follows A
historical Watch target remains B
Monitor history remains
new reconciliation occurs durably
Workbench finds A current / B historical
Ask explains why B merged into A
```

---

## Later Claim correction

User discovers Claim C should be Story D.

User moves:

```text
C
A → D
```

Result:

```text
current membership = D
history records A → D
automatic worker cannot undo move
old Story A revision remains historical
derived current Documents/Entities reconcile
Ask answers:
"Was C always in Story D?"
```

correctly from persisted history.

---

## Partial separation

User decides several Claims in A deserve their own Story, but A remains valid.

User selects:

```text
Extract into new Story
```

Result:

```text
A stays active
new Story E becomes active
selected Claims move
history preserved
no false split identity asserted
```

---

## True split

Later Story S0 proves to contain two incompatible developments.

User approves:

```text
S0
→ S1 + S2
```

Result:

```text
S0 becomes historical
S1/S2 active
Claim grouping explicit
history intact
manual metadata assigned explicitly
derived metadata recomputed
Watch targeting S0 requires review
Question/report/search reconciliation occurs durably
Ask explains the split
```

This end-to-end behavior is the Phase 27 product gate.

---

# 111. REQUIRED FINAL VALIDATION

Before declaring completion run all applicable:

```text
focused Phase 27 tests
Story automation regression tests
Phase 23 Report/Alert regression tests
Phase 25 Research regression tests
Phase 26 Knowledge/Search/Ask regression tests

migration fresh
migration upgrade
migration repeat
foreign-key checks

compileall
full backend test suite

frontend typecheck
frontend production build

Phase 27 evaluation fixtures
Phase 26 retrieval benchmark or appropriate shared-search regression

logical export reconstruction test
integrity checks
concurrency tests
worker recovery tests
performance bounds
```

If anything cannot be run, state exactly why.

Do not infer success.

---

# 112. ENGINEERING COMPLETION CRITERIA

Phase 27 is not complete unless all of the following are true:

```text
Claim reassignment works
Claim unassignment works

current membership pointer remains coherent
append-only history reconstructs past membership

historical Story Documents remain historical
current Story Documents use current Claims

Story Entities cannot go stale from Claim moves
manual Story Entity authority survives rebuild

merge works
split works
extract works

merge lineage resolves correctly
split lineage preserves one-to-many ambiguity

Watch merge follows canonical Story
Watch split does not guess a child

manual metadata never silently propagates

automation cannot undo human corrections

Reports/Alerts/Questions reconcile durably

old revisions/alerts/questions/research remain historical

Workbench understands current vs historical Story

Ask understands current vs historical Story

integrity recognizes historical automatic assignments correctly

migration/export/recovery/replay/concurrency all pass
```

---

# 113. INTELLIGENCE VALUE COMPLETION CRITERIA

The phase must also demonstrate:

```text
Story mistakes are actually repairable

repairs do not create new stale context

duplicate Story noise can be corrected

split ambiguity is represented honestly

user correction burden can be measured

history remains explainable

automatic Story organization becomes safer because it can be corrected
without corrupting provenance
```

---

# 114. DOCUMENTATION

Update active forward planning/architecture documentation only where necessary.

Ensure:

```text
plan/phases-v2/README.md
```

clearly identifies:

```text
Phase 27 current
Phase 28 next only after Phase 27 completion
```

Do not rewrite historical Phase 01–26 plans for stylistic consistency.

If top-level overview plans remain stale and are part of this phase's preconditions, reconcile only the forward roadmap portions required to prevent agents from following obsolete Phase definitions.

---

# 115. FINAL REPORT FORMAT

At completion provide exactly these sections:

## 1. Verdict

Choose exactly one:

```text
PHASE 27 COMPLETE AND COMMITTED — PHASE 28 READY

PHASE 27 CORRECTED AND COMMITTED — PHASE 28 READY

PHASE 27 INCOMPLETE — PHASE 28 BLOCKED
```

---

## 2. Codebase Review / Architecture

Describe actual starting architecture and any adjustments made after inspecting live code.

---

## 3. Claim Story Membership

Report:

```text
current pointer model
history model
manual authority
unassignment
migration behavior
```

---

## 4. Story Corrections

Report correction aggregate, cause identity, and authority behavior.

---

## 5. Story Documents

Report historical/current separation and every relevant current-context reader corrected.

---

## 6. Story Entities

Report manual authority and derived projection behavior.

---

## 7. Story Metadata

Report Tags, Topics, Subjects, Entity metadata, and review-state propagation behavior.

---

## 8. Story Merge

Report:

```text
preview
execution
lineage
Watch behavior
metadata decisions
reconciliation
```

---

## 9. Story Split

Report:

```text
retired source
children
Claim grouping
Watch ambiguity
metadata
lineage
```

---

## 10. Claim Extraction

Report partial-separation behavior.

---

## 11. Duplicate Suggestions

Report suggestion identity, approval, dismissal, replay behavior.

---

## 12. Story Evolution

Report any taxonomy changes and identity-correction behavior.

---

## 13. StoryRevision / Historical Immutability

Report historical preservation.

---

## 14. Reports / Alerts

Report durable reconciliation and immutable historical behavior.

---

## 15. Research Questions / Watches / Monitors

Report merge/split/reassignment effects.

---

## 16. Phase 26 Knowledge Integration

Report Entity, Tag, Workbench, shared retrieval, and Ask integration.

---

## 17. API

Report endpoints and stale-state protection.

---

## 18. Frontend

Report correction workflows and user-visible current/historical semantics.

---

## 19. Migration

Report:

```text
starting schema
ending schema
fresh test
upgrade test
repeat/idempotency test
FK test
```

---

## 20. Export / Integrity

Report historical reconstruction and integrity changes.

---

## 21. Concurrency / Idempotency / Recovery

Report races, replay, interruption, lease recovery.

---

## 22. Evaluation / Intelligence Value

Report Phase 27 evaluation cases and observed correction-quality metrics.

---

## 23. E2E Tests

List all Phase 27 end-to-end workflows run.

---

## 24. Tests

Report focused and regression tests.

---

## 25. Validation

Report:

```text
compileall
full backend
frontend typecheck
frontend build
benchmarks
migration checks
integrity
```

with exact results.

---

## 26. Files Changed

List meaningful files.

---

## 27. Commits

List Phase 27 checkpoint/final commits.

Do not report a predicted starting SHA.

---

## 28. Repository State

Report:

```text
branch
actual final HEAD
tracked worktree state
index state
preserved unrelated untracked artifacts
push status
```

Do not push.

---

## 29. Deferred Work

Explicitly list Phase 28/29/30 items not pulled forward.

---

## 30. Phase 28 Readiness

State whether:

```text
Phase 28A — Observation and Source Robustness
```

can safely begin.

---

# 116. FINAL IMPLEMENTATION PRINCIPLE

Phase 27 should leave Newsroom with a much clearer semantic boundary:

```text
Evidence says what the Source actually supports.

Claims represent accepted assertions.

Stories organize Claims into evolving developments.

Story organization can be corrected.

Corrections alter current organization.

Corrections do not rewrite evidence.

History preserves what Newsroom previously believed.

Derived current context follows the corrected present.

Human decisions cannot be silently undone by stale automation.
```

That is the target.

Proceed codebase-first, make the smallest coherent architectural changes required by the live repository, checkpoint validated capabilities, preserve historical truth, and do not pull future intelligence systems into this phase.