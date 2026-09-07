# PHASE 23 — COMPLETE IMPLEMENTATION SUMMARY

## Story Automation, Audited Claim Acceptance, Living Reports, Exact-Cause Alerts, Compatibility, Recovery, and Final Acceptance

# 1. Executive Summary

Phase 23 completed the **core autonomous intelligence pipeline of Newsroom v2**.

Before Phase 23, Newsroom had already developed the infrastructure required to:

- acquire and version Documents;
- normalize content into immutable ContentArtifacts;
- determine relevance;
- perform canonical ArticleAnalysis;
- extract candidate Claims;
- create exact EvidenceSpans;
- maintain ClaimEvidence relationships;
- verify provenance;
- operate durable Jobs;
- perform retries and recovery;
- maintain Sources, Monitors, Topics, Subjects, Stories, Reports, Alerts, and Research Questions.

What Phase 23 added was the automation necessary to turn those trustworthy analysis primitives into a continuously evolving intelligence product.

The completed automatic chain is:

```text
Source / Monitor
        ↓
Acquisition
        ↓
Document
        ↓
DocumentVersion
        ↓
ContentArtifact
        ↓
ArticleAnalysis
        ↓
verified automatic promotion
        ↓
EvidenceSpan
        ↓
Claim
        ↓
automatic_story_stage
        ↓
Story resolution
        ↓
Story
        ↓
StoryEvolution
        ↓
evidence-bound StoryRevision
        ↓
automatic_report_stage
        ↓
audited Claim acceptance
        ↓
LivingReport
        ↓
material ReportRevision
        ↓
exact ReportRevision causes
        ↓
automatic_alert_stage
        ↓
Alert
        ↓
durable in_app delivery
```

The defining achievement of Phase 23 is not merely that these records can be created.

It is that the entire pipeline is:

- **provenance-preserving**;
- **deterministic where appropriate**;
- **idempotent**;
- **concurrency-safe**;
- **recoverable after interrupted Jobs**;
- **respectful of human decisions**;
- **inspectable through APIs**;
- **reconstructable through logical export**;
- **validated by database integrity checks**;
- **proven through an unattended end-to-end runtime test**.

Phase 23 therefore transformed Newsroom from a system that could analyze information into a system that can **automatically turn verified incoming evidence into evolving Stories, Living Reports, and user Alerts without losing the evidence chain that justifies those outputs**.

---

# 2. Architectural Principle of Phase 23

The central Phase 23 rule was:

> **Automation may advance trusted domain state, but it may never weaken the provenance requirements established by the evidence pipeline.**

Every downstream stage therefore revalidates the persisted state on which it depends.

The architecture intentionally avoids trusting a previous worker merely because that worker reported success.

Instead:

```text
Stage A writes durable result
        ↓
Stage B loads persisted result
        ↓
Stage B independently validates required invariants
        ↓
Stage B performs its own bounded mutation
```

This principle is repeated throughout:

```text
promotion
→ Story verification

Story-stage checkpoint
→ Report verification

ReportRevision / causes
→ Alert verification
```

This makes the system much more resilient to:

- stale Jobs;
- retries;
- worker crashes;
- manual database corruption;
- incomplete checkpoints;
- concurrent processing;
- incorrectly copied identifiers;
- human intervention between stages.

---

# 3. Foundation Entering Phase 23

A critical prerequisite immediately before Phase 23 was the final trust-boundary work completed in Phase 22.3.

Phase 22.3 established:

```text
verify_automatic_promotion()
```

as the canonical verifier for automatic Claim promotion.

That verifier reconstructs the promotion from persisted canonical records rather than trusting the fact that a row merely exists.

It verifies relationships including:

```text
ContentArtifact
→ ArticleAnalysis
→ candidate Claim
→ EvidenceSpan
→ Claim
→ ClaimEvidence
→ promotion
→ Claim state history
```

Among other checks, it verifies:

- ArticleAnalysis provenance;
- canonical analyzed-content reconstruction;
- content hashes;
- expected lengths;
- candidate identity;
- EvidenceSpan offsets;
- exact excerpt membership;
- excerpt uniqueness where required;
- Claim identity;
- ClaimEvidence identity;
- promotion identity;
- coherent Claim state history.

This closed a critical trust-boundary defect in which plausible automatic evidence graphs could previously be fabricated directly in persistence and later appear valid.

Phase 23 treats this verifier as the entrance gate into automatic downstream intelligence.

---

# 4. Phase 23A — Deterministic Claim Qualification and Story Resolution

Phase 23A answered:

> **Given a verified automatic Claim, does it belong to an existing Story, require a new Story, or remain unresolved?**

The important design choice was to make this stage **resolution-only**.

It does not mutate Stories.

It does not assign Claims.

It does not accept Claims.

It determines what should happen next.

---

## 4.1 Automatic Story Resolution Service

Phase 23A introduced the automatic Story resolution flow around:

```text
AutomaticStoryResolutionService.resolve(promotion_id)
```

Resolution begins by validating the promotion through the canonical automatic-promotion verifier.

Therefore:

```text
unverified promotion
→ cannot participate in Story automation
```

---

# 5. Automatic Claim Qualification

A Claim must satisfy strict persisted conditions before Story automation considers it eligible.

The exact implementation is codebase-specific, but Phase 23 established requirements around:

- verified automatic promotion;
- valid ArticleAnalysis provenance;
- coherent candidate identity;
- pending Claim state;
- valid ClaimEvidence;
- at least one supporting evidence relationship;
- no incompatible contradiction state;
- appropriate Monitor state;
- appropriate Source state;
- current information need;
- compatible provenance;
- no existing invalid assignment.

Qualification deliberately remains distinct from Claim acceptance.

At this point:

```text
Claim state = pending
```

The system knows the Claim is eligible for Story processing.

It has **not** yet decided that the Claim should become accepted intelligence.

---

# 6. Bounded Story Candidate Retrieval

Story matching was deliberately bounded.

Phase 23A prevented the resolver from scanning an unlimited Story corpus or resolving ambiguous matches through arbitrary ordering.

Representative bounds included:

- limited candidate Story count;
- a saturation probe;
- bounded retrieval terms;
- bounded associated Claims;
- bounded Documents;
- bounded Topics;
- bounded Subjects;
- bounded text collected per Story;
- temporal compatibility constraints.

The important invariant is:

```text
candidate set incomplete / saturated
→ do not manufacture certainty
```

Instead the resolver fails conservatively.

---

# 7. Story Resolution Outcomes

Resolution returns one of a small deterministic set of outcomes:

```text
MATCHED_EXISTING
NO_MATCH
AMBIGUOUS
DEFERRED
```

### MATCHED_EXISTING

There is a sufficiently strong deterministic match to one existing eligible Story.

### NO_MATCH

No existing Story satisfies the required matching criteria.

This permits downstream creation of a new Story.

### AMBIGUOUS

Multiple candidates are plausible and the system cannot prove the correct assignment.

No automatic assignment occurs.

### DEFERRED

The system cannot safely produce a decision because eligibility, bounds, saturation, lifecycle, or another prerequisite prevents a trustworthy result.

---

# 8. Story Matching Signals

Phase 23A intentionally rejected simplistic Story matching.

Strong signals may include:

- exact proposition equality;
- strong normalized proposition overlap;
- entity-backed proposition/headline overlap;
- temporally compatible evidence.

Weak contextual signals such as:

```text
same Source
same broad Topic
same Subject
generic lexical overlap
```

cannot independently force a Story match.

Identifiers and insertion order are not used as semantic tie-breakers.

This matters because false Story merging is substantially more damaging than conservatively deferring uncertain material.

---

# 9. Phase 23B — Durable Story Automation

Phase 23B converted Story resolution into a durable asynchronous workflow.

It introduced:

```text
automatic_story_stage
```

as a Job-backed orchestration stage.

The logical obligation is associated with the verified automatic promotion.

The Stage uses the existing Job infrastructure for:

- uniqueness;
- leasing;
- retries;
- crash recovery;
- reruns;
- failure state;
- result checkpoints.

No separate orchestration framework was introduced.

---

# 10. Story-Stage Enqueue

The document-processing completion path inspects verified automatic promotions and creates the appropriate Story-stage obligations.

Important transaction boundary:

```text
document-processing completion transaction
→ durable Story-stage Job created
```

but:

```text
Story mutation
```

does **not** happen inside that transaction.

This provides failure isolation.

Document processing can complete successfully even if Story automation later encounters a temporary problem.

---

# 11. Story Worker Reverification

When a Story-stage worker executes, it does not trust the original resolution blindly.

Its conceptual flow is:

```text
load Story-stage Job
        ↓
verify automatic promotion again
        ↓
qualify Claim again
        ↓
resolve Story state
        ↓
enter protected mutation boundary
        ↓
re-read / re-resolve current state
        ↓
perform mutation
        ↓
write checkpoint
```

This second resolution inside the protected mutation boundary is a particularly important Phase 23 feature.

---

# 12. Mutation-Time Re-resolution

Consider two automatic Claims arriving at nearly the same time.

Both might initially observe:

```text
NO_MATCH
```

Without re-resolution, both could create new Stories.

Instead:

```text
Worker A
→ acquires mutation boundary
→ still NO_MATCH
→ creates Story X

Worker B
→ later acquires mutation boundary
→ resolves again
→ now sees Story X
→ matches Story X
```

This prevents a classic concurrent Story-creation race.

Database uniqueness and protected mutation behavior are the final idempotency boundary, not pre-insert existence checks alone.

---

# 13. Story Mutation

A successful Story-stage operation performs the necessary domain mutations atomically where appropriate.

The result may include:

```text
Story creation
or
existing Story assignment
```

plus:

```text
Claim → Story assignment
```

```text
Story ↔ Document relationship
```

```text
StoryEvolution event
```

```text
StoryRevision
```

and the durable Job checkpoint.

---

# 14. Evidence-Bound Story Revisions

One subtle but important Phase 23B correction prevented automatically created Stories from beginning with an authoritative revision that had no evidence citations.

For automatic Story creation:

```text
new Story
→ first meaningful StoryRevision
→ exact Claim
→ exact Document
```

The authoritative revision is evidence-bound from the beginning.

The provenance can therefore be followed:

```text
Story
→ StoryRevision
→ Claim
→ ClaimEvidence
→ EvidenceSpan
→ DocumentVersion
→ Document
→ Source
```

---

# 15. Deferred Story Outcomes

Phase 23B treats uncertainty as a valid durable outcome.

Examples include:

- ambiguous match;
- saturated candidate set;
- unqualified Claim;
- incompatible lifecycle state.

These outcomes can be persisted in the Story-stage checkpoint without producing unsafe downstream mutation.

A deferred Stage is not necessarily an infrastructure failure.

This distinction became important later for operator visibility and integrity checking.

---

# 16. Phase 23C — Audited Claim Acceptance

Story assignment alone is not sufficient to make a Claim accepted intelligence.

Phase 23C added a separate automatic acceptance policy.

The automatic system must verify that the Claim has successfully passed Story automation and still satisfies the acceptance conditions.

Relevant checks include:

- promotion still verifies;
- expected Story-stage Job completed successfully;
- expected Story still exists;
- Story remains in an eligible lifecycle;
- exact Claim → Story assignment remains intact;
- StoryRevision provenance matches;
- StoryEvolution provenance matches;
- relevant Document/Source/Monitor state remains compatible;
- ClaimEvidence remains valid;
- supporting evidence exists;
- contradictory state does not invalidate acceptance;
- Claim remains in an automatic-compatible state.

---

# 17. Audited State Transition

Automatic acceptance uses the existing Claim state machinery.

Conceptually:

```text
pending
→ supported
→ accepted
```

with an automatic reason associated with the Story-stage operation.

The important point is that automation does **not** directly toggle a boolean and call the Claim accepted.

It goes through the audited domain state path.

This preserves:

- transition history;
- timestamps;
- reason;
- replay identity;
- manual/automatic distinction.

---

# 18. Human Authority

Human decisions outrank automation.

Examples:

```text
Claim manually rejected
→ automatic Report stage cannot accept it
```

or an incompatible manually assigned state:

```text
automation
→ DEFER
```

rather than:

```text
automation
→ overwrite human state
```

This human-authority principle continues throughout subsequent stages.

---

# 19. Acceptance Replay

Replay must recognize the exact automatic acceptance transition already performed.

It must not append:

```text
supported → supported
```

or another duplicate acceptance-history record.

This helped preserve a clean domain audit trail under retries and recovery.

---

# 20. Durable Report Automation

Phase 23C introduced:

```text
automatic_report_stage
```

A Report-stage Job is created only after successful Story-stage completion.

The logical relationship is:

```text
successful automatic_story_stage
→ one automatic_report_stage obligation
```

Deferred or unsuccessful Story processing does not create valid downstream Report work.

---

# 21. Report Worker Revalidation

Report processing again revalidates persisted state.

The Report stage checks:

```text
verified promotion
Story-stage Job
Claim
Story
StoryRevision
StoryEvolution
ClaimEvidence
accepted Claim state
```

before generating/updating a LivingReport.

This avoids treating the upstream Job checkpoint as self-authenticating.

---

# 22. Living Reports

Phase 23 turned LivingReports into automatically maintained Story intelligence.

Conceptually:

```text
Story
→ accepted material Claims
→ LivingReport
→ immutable ReportRevisions
```

Each new ReportRevision represents a material change in the report state.

The LivingReport points to its current revision while previous ReportRevisions remain historically immutable.

---

# 23. Deterministic Report Materiality

A major Phase 23C design choice was to determine **materiality before creating another ReportRevision**.

The system builds a stable material identity from deterministically ordered report content inputs, including the closed-world Claim set/propositions while excluding fields such as generated `what_changed` text that should not determine input identity.

Conceptually:

```text
same material input
→ NO_CHANGE
→ no new ReportRevision
```

while:

```text
materially changed trusted input
→ MATERIAL
→ new ReportRevision
```

This prevents endless revisions caused by retries or textual variation.

---

# 24. NO_CHANGE Semantics

`NO_CHANGE` is a first-class Report-stage outcome.

It means:

```text
Report automation ran correctly
but trusted material state did not change.
```

Therefore:

- no new ReportRevision;
- no unnecessary provider call where generation is avoidable;
- no downstream Alert obligation.

This is distinct from failure.

---

# 25. Closed-World Report Generation

Automatic Reports use an exact eligible Claim set.

The conceptual flow is:

```text
accepted eligible Claims
        ↓
deterministic ordering
        ↓
closed-world propositions
        ↓
materiality calculation
        ↓
ReportRevision
```

Generated Report content may only be supported by the persisted Claims included in that revision's closed-world context.

This makes it possible to answer:

> Why does this Report sentence exist?

through persisted relationships rather than prose interpretation.

---

# 26. Report Proposition Provenance

Each proposition can expose its exact Claim IDs.

The provenance path becomes:

```text
ReportRevision
→ proposition
→ Claim
→ ClaimEvidence
→ EvidenceSpan
→ DocumentVersion
→ Document
→ Source
```

The system does not need to search text afterward to reconstruct what evidence justified a proposition.

---

# 27. Exact Report Change Causes

Phase 23C also created persistent exact causes for `what_changed`.

Each material change stores relationships including:

```text
ReportRevision
→ ReportRevisionCause
→ Claim
→ EvidenceSpan
```

and, where applicable:

```text
StoryEvolution
→ Story / Document
```

The cause must correspond to the actual ReportRevision and actual material change.

---

# 28. Report Concurrency

Concurrent workers attempting to produce the same logical Report update must converge on one ReportRevision.

The implementation uses:

- SQLite write serialization/protected mutation;
- materiality recomputation inside the final mutation boundary;
- deterministic input ordering;
- stable identity.

Therefore:

```text
Worker A computes material state M
Worker B computes material state M
```

cannot legitimately persist:

```text
revision N
revision N+1
```

for the same logical material state.

---

# 29. Report Failure Isolation

The stages intentionally remain separate.

If:

```text
Story automation succeeds
Report processing temporarily fails
```

then:

```text
Story remains valid
Report Job retries
```

The Story is not rolled back.

This becomes a core full-pipeline recovery property.

---

# 30. Phase 23D — Exact-Cause Alert Automation

Phase 23D introduced:

```text
automatic_alert_stage
```

An Alert-stage Job is created only when Report automation produced a new material ReportRevision.

Conceptually:

```text
MATERIAL Report result
→ automatic_alert_stage
```

while:

```text
NO_CHANGE
DEFERRED
FAILED
```

do not produce an executable material Alert obligation.

---

# 31. Alert Rule Revalidation

When the Alert worker runs, it re-reads currently enabled Alert rules.

A rule can therefore change between:

```text
Report creation
```

and:

```text
Alert execution
```

If the rule has been disabled or removed:

```text
no Alert
```

The queued Job does not carry permanent authority to ignore current rule state.

---

# 32. Alert Matching

Alert rule evaluation considers persisted characteristics such as:

- event/cause types;
- Report scope;
- Monitor scope;
- Story scope;
- global scope;
- minimum importance;
- exact ReportRevision causes.

Only matching persisted causes are allowed to trigger an Alert.

---

# 33. Critical Exact-Cause Fix

A significant Phase 23D defect was discovered during implementation.

The eligibility filter correctly calculated:

```text
matching_causes
```

but the resulting Alert serialized **all ReportRevision causes**.

That meant an Alert could contain unrelated causes that did not satisfy its rule.

The fix established the invariant:

```text
Alert causes
⊆
ReportRevision causes
```

and more specifically:

```text
Alert causes
=
only ReportRevision causes satisfying the Alert rule
```

This exact set is used consistently for:

- body;
- payload;
- Story linkage;
- importance;
- Claim IDs;
- EvidenceSpan IDs;
- Document IDs;
- provenance;
- deduplication identity.

No unrelated Report cause should leak into the Alert's explanation.

---

# 34. Stable Alert Identity

Alert identity is deterministic.

Its logical identity incorporates stable persisted information including:

```text
Alert rule
exact ReportRevision
sorted exact matching cause set
```

Therefore:

```text
same rule
+ same ReportRevision
+ same cause set
→ same Alert
```

while:

```text
different ReportRevision
→ new Alert
```

and:

```text
different rule
→ different Alert
```

Cause ordering does not change logical identity.

---

# 35. Durable In-App Delivery

Phase 23D completed the automatic pipeline with durable delivery.

Each Alert receives one logical:

```text
in_app
```

delivery.

A database uniqueness boundary such as:

```text
UNIQUE(alert_id, channel)
```

ensures replay and concurrency converge.

Therefore:

```text
same Alert retried repeatedly
→ one logical in_app delivery
```

---

# 36. Acknowledgement Preservation

Automation does not own human acknowledgement state.

Replay must not:

- acknowledge an Alert;
- clear an acknowledgement;
- replace acknowledgement metadata.

This ensures user interaction remains durable even while automation retries.

---

# 37. Revision Pinning

Alert-stage Jobs remain tied to the exact ReportRevision that created the obligation.

If:

```text
ReportRevision N
```

creates Alert work and:

```text
ReportRevision N+1
```

appears later, the older Job does not switch to the newer causes.

The architecture remains:

```text
Alert Job for N
→ ReportRevision N
→ causes from N
```

This preserves historical correctness under delayed processing.

---

# 38. Phase 23E — Compatibility and Product Visibility

After the automatic backend chain was complete, Phase 23E made it inspectable and usable through the rest of Newsroom.

The Phase 23E completion report confirmed the addition of bounded pending/unassigned Claim retrieval, richer provenance serialization, sanitized Job status, Story audit export, complete-chain integrity checks, Workbench visibility, and Live Test C.

---

# 39. Pending / Unassigned Claim API

Phase 23E added bounded global Claim retrieval.

The API supports filtering equivalent to:

```text
state=pending
assignment=unassigned
provenance=automatic
```

with bounded pagination.

This allows automatic Claims to exist in the user-visible system before they have Story ownership.

The application no longer needs to pretend:

```text
every Claim belongs to a Story
```

---

# 40. Claim Provenance API

Claim responses now expose stable IDs sufficient to navigate:

```text
Claim
→ ClaimEvidence
→ EvidenceSpan
→ DocumentVersion
→ Document
→ Source
```

Automatic Claims additionally expose provenance such as:

```text
promotion
promotion identity
ArticleAnalysis
candidate index
Story where assigned
```

Manual Claims remain distinct and do not receive fabricated automatic provenance fields.

---

# 41. StoryRevision API

StoryRevision serialization was expanded to expose the actual audit relationships.

Relevant information includes:

```text
revision ID
revision number
Claim IDs
Document IDs
origin
StoryEvolution event ID
created timestamp
```

This allows frontend/operator tooling to understand exactly what evidence formed a Story revision.

---

# 42. Report API Provenance

Existing Phase 23C Report contracts were verified and preserved.

A Report can expose:

```text
proposition
→ exact Claim IDs
```

and:

```text
what_changed
→ exact persisted cause IDs
```

No new inference is performed during serialization.

The API exposes persisted relationships.

---

# 43. Alert API Provenance

Alerts expose the exact matching provenance established in Phase 23D.

Relevant identifiers include:

```text
Alert rule
ReportRevision
Story
Report cause
Claim
EvidenceSpan
Document
```

This provides API/frontend parity with the backend exact-cause model.

---

# 44. Workbench Pending Claims

Phase 23E added minimal frontend visibility for pending automatic Claims.

Workbench can retrieve and represent an automatic Claim that has:

```text
state = pending
story_id = NULL
```

without pretending Story ownership already exists.

This closes an important product compatibility gap in the asynchronous pipeline.

---

# 45. Orchestration Status Visibility

The existing Job API was adapted to expose Phase 23 automation status.

Relevant Job types include:

```text
automatic_story_stage
automatic_report_stage
automatic_alert_stage
```

The operator can distinguish outcomes such as:

```text
queued
running / leased
retrying
completed
deferred
no_change
no_alert
terminal failure
```

---

# 46. Sanitized Job Projection

The public/operator Job projection intentionally avoids dumping internal Job payload/result blobs.

Instead it exposes bounded operational information such as:

```text
Job ID
Job type
status
attempt count
retry/lease information
failure reason
compact outcome
reason code
Story ID
ReportRevision ID
Alert IDs
```

where applicable.

This preserves observability without turning internal orchestration JSON into a public API contract.

---

# 47. Story Audit Export

Phase 23E completed previously missing Story audit relationships in logical export.

Added/exported relationships include:

```text
story_revision_claims
story_revision_documents
story_evolution_events
```

Report relationships added earlier remained:

```text
report_revision_claims
report_revision_causes
```

Alert provenance/delivery relationships also remained included.

---

# 48. Export Reconstruction

Phase 23 moved beyond testing that table names merely appear in an export configuration.

The export regression actually reconstructs relationships from exported data.

For example:

```text
Alert
→ ReportRevision
→ report_revision_claims
→ Claim
→ ClaimEvidence
→ EvidenceSpan
→ DocumentVersion
→ Document
→ Source
```

and also validates Story provenance:

```text
Claim
→ Story
→ StoryRevision
→ StoryRevision Claim relationship
```

This establishes logical export as an actual audit artifact.

---

# 49. Story Checkpoint Integrity

Phase 23E extended `check_database()` to verify completed Story-stage checkpoints.

The checker ties together:

```text
Story-stage Job
→ promotion
→ Claim
→ Story
→ StoryRevision
→ Document
→ StoryEvolution event
```

A completed checkpoint cannot merely contain identifiers for plausible existing records.

They must correspond to the exact upstream obligation.

---

# 50. Full Automatic Chain Integrity

By Phase 23E, `check_database()` could validate the conceptual chain:

```text
automatic promotion
→ Claim
→ Story-stage Job
→ Story
→ StoryEvolution
→ StoryRevision
→ audited Claim acceptance
→ Report-stage Job
→ LivingReport
→ ReportRevision
→ Report causes
→ Alert-stage Job
→ Alert
→ in_app delivery
```

This transformed integrity checking from table-level validation into a meaningful pipeline audit.

---

# 51. End-to-End Runtime Integration

Phase 23E added end-to-end testing through production composition.

The test uses:

- real JobService;
- real Worker handlers;
- real completion hooks;
- real domain services;
- real SQLite behavior.

It does not merely call private mutators in the expected order.

The runtime chain itself must create downstream obligations.

---

# 52. Full Replay

The automatic pipeline was replayed using supported runtime semantics.

Expected convergence includes the same logical:

```text
promotion
Story
Claim assignment
StoryRevision result
Claim acceptance
ReportRevision
Alert
delivery
```

No duplicate domain history should appear merely because processing is replayed.

Where upstream acquisition legitimately creates a new DocumentVersion, that is distinguished from an orchestration idempotency defect.

---

# 53. Lease Recovery

Recovery testing covers all three Phase 23 stages:

```text
automatic_story_stage
automatic_report_stage
automatic_alert_stage
```

A leased worker may disappear.

After lease expiration, another worker can recover the obligation.

Important invariant:

```text
domain mutation committed
+
Job completion not committed
→ retry discovers/reuses existing domain result
```

rather than duplicating it.

---

# 54. Cross-Stage Failure Isolation

Phase 23 verifies:

```text
Story succeeds
Report fails
→ Story remains valid
→ Report retries
```

and:

```text
Report succeeds
Alert fails
→ Report remains valid
→ Alert retries
```

The pipeline does not wrap all stages in one giant transaction.

That architecture is intentional.

---

# 55. Deterministic Defer

A legitimate uncertain outcome stops downstream processing safely.

For example:

```text
ambiguous Story resolution
→ Story-stage DEFERRED
→ no unsafe Story mutation
→ no Report Job
→ no Alert Job
```

The state remains inspectable.

This is materially different from pretending all automatic input can be resolved.

---

# 56. Human Override Tests

Phase 23 verifies human authority between asynchronous stages.

Representative cases include:

```text
Claim manually rejected
before Report stage
→ automatic acceptance/report mutation blocked
```

and:

```text
Alert rule disabled
before Alert worker executes
→ no Alert
```

Human/domain state is re-read at execution time.

---

# 57. Live Test C

Phase 23 established and executed **Live Test C** as the final production-composition release gate.

The repository's defined Live Test C uses a controlled Source or fixture through the real runtime architecture.

The executed chain was:

```text
controlled Source fixture
→ Scheduler
→ acquisition Worker
→ Document processing
→ local deterministic analysis
→ verified promotion
→ Story-stage Job
→ Story
→ StoryRevision
→ Report-stage Job
→ ReportRevision
→ Alert-stage Job
→ Alert
→ in_app delivery
```

The test used:

```text
1 controlled fixture acquisition
0 public-network calls
0 hosted/paid provider calls
```

while still exercising the actual application composition.

---

# 58. Live Test Persisted Verification

The Live Test was not accepted merely because a script printed `PASS`.

The resulting SQLite state was independently inspected.

The final audit confirmed:

```text
Alert
→ Report
→ Claim
→ Evidence
→ Document
→ Source
```

resolved correctly.

It also verified:

```text
checkpoint/Job mismatches = 0

Alerts lacking exactly one in_app delivery = 0

PRAGMA foreign_key_check = clean

check_database().ok = true
```

---

# 59. Live Test Replay

Live Test C was replayed.

The final validation compared exact logical identities rather than only row counts.

Result:

```text
exact_logical_identities_unchanged
```

This is stronger than:

```text
"the database still has the same number of rows"
```

because two different duplicated records could otherwise conceal a replay defect.

---

# 60. Final Phase 23 Audit

After Phase 23E was reported complete, a separate final acceptance audit was performed.

That audit deliberately treated:

```text
PHASE 23 COMPLETE
```

as a claim requiring independent verification.

The audit discovered three remaining issues.

---

# 61. Final Audit Finding 1 — Checkpoint Job Identity

Completed Report and Alert checkpoints could contain otherwise valid result data associated with a different Job.

A checkpoint could therefore be structurally plausible while belonging to the wrong orchestration obligation.

The final correction requires:

```text
checkpoint embedded Job identity
=
owning persisted Job
```

for completed Report/Alert checkpoints.

This prevents copying a valid downstream result into an unrelated completed Job and having integrity accept it.

---

# 62. Final Audit Finding 2 — False Downstream Mutation IDs

Deferred or terminal Story, Report, and Alert checkpoints could contain identifiers that falsely implied successful downstream mutation.

Examples conceptually included:

```text
DEFERRED Story checkpoint
+ StoryRevision ID
```

or:

```text
terminal Report checkpoint
+ ReportRevision ID
```

or:

```text
terminal Alert checkpoint
+ Alert / delivery IDs
```

The final correction makes these states fail integrity.

Non-success outcomes cannot falsely claim success-only mutations.

---

# 63. Final Audit Finding 3 — Recovery Proof Quality

The final audit found that recovery had strong stage-specific coverage but insufficient proof across the integrated:

```text
Story
→ Report
→ Alert
```

queue chain.

Additionally, Live Test replay had been relying too heavily on counts.

The corrections added:

- integrated real-SQLite lease recovery;
- full worker-chain recovery verification;
- exact persisted-identity replay comparison.

This strengthened the evidence supporting final acceptance.

---

# 64. Phase 23F Final Correction

The final bounded correction was committed as:

```text
Phase 23F: close final acceptance gaps
```

The Phase 23F correction touched the integrity checker, Live Test C, Phase 23E compatibility tests, and Phase documentation.

No schema migration was required.

Schema remained:

```text
23
```

---

# 65. Final Evidence Trust Boundary

At the end of Phase 23, automatic downstream intelligence depends on a verified chain.

Conceptually:

```text
ContentArtifact
        ↓
ArticleAnalysis
        ↓
automatic promotion verifier
        ↓
EvidenceSpan
        ↓
ClaimEvidence
        ↓
Claim
        ↓
Story-stage verifier
        ↓
Story / StoryRevision
        ↓
Report-stage verifier
        ↓
accepted Claim
        ↓
ReportRevision
        ↓
exact Report cause
        ↓
Alert-stage verifier
        ↓
exact Alert cause
        ↓
in_app delivery
```

Each major trust transition validates the persisted state it consumes.

---

# 66. Complete Provenance Chain

One of Phase 23's most important final properties is that a user or auditor can walk backward from an Alert to the original Source.

The chain is approximately:

```text
Alert
        ↓
Alert exact cause
        ↓
ReportRevision
        ↓
ReportRevisionCause
        ↓
Claim
        ↓
ClaimEvidence
        ↓
EvidenceSpan
        ↓
DocumentVersion
        ↓
Document
        ↓
Source
```

Story provenance can also be reconstructed:

```text
Claim
        ↓
Story
        ↓
StoryRevision
        ↓
StoryRevision Claims
        ↓
StoryRevision Documents
        ↓
StoryEvolution
```

This is the signature architectural property of Newsroom.

---

# 67. Automatic Pipeline State Machine

The completed system can be thought of as three durable downstream automation stages:

```text
ARTICLE / EVIDENCE PIPELINE
        ↓
verified promotion
        ↓
┌─────────────────────────────┐
│ automatic_story_stage       │
└─────────────────────────────┘
        ↓
Story + StoryRevision
        ↓
┌─────────────────────────────┐
│ automatic_report_stage      │
└─────────────────────────────┘
        ↓
accepted Claim + ReportRevision
        ↓
┌─────────────────────────────┐
│ automatic_alert_stage       │
└─────────────────────────────┘
        ↓
Alert + in_app delivery
```

Each Stage has independent:

- Job identity;
- leasing;
- retry;
- checkpoint;
- validation;
- failure semantics.

---

# 68. Idempotency Model

Phase 23 established a strong distinction between:

```text
same logical obligation
```

and:

```text
new material event
```

Replay of the same logical obligation should reuse state.

Materially new trusted evidence may legitimately create new state.

Examples:

```text
same promotion
→ same Story-stage logical result
```

```text
same material Report state
→ no new ReportRevision
```

```text
same ReportRevision + Alert rule + causes
→ same Alert
```

```text
new material ReportRevision
→ potentially new Alert
```

Idempotency therefore does not freeze the system.

It prevents accidental duplication while still allowing genuine evolution.

---

# 69. Concurrency Model

Phase 23 does not assume a single worker.

Important mutations are protected through:

- Job uniqueness;
- SQLite mutation serialization where necessary;
- database uniqueness constraints;
- mutation-time revalidation;
- deterministic identities.

This applies to:

- Story creation/assignment;
- Story revisions;
- Report revisions;
- Alerts;
- deliveries.

Concurrency is tested with real database interactions rather than only sequential mocks.

---

# 70. Failure Model

Phase 23 distinguishes several classes of outcome.

## Success

Domain mutation completed and checkpoint corresponds exactly.

## No-op / no material change

Processing succeeded but produced no new domain mutation.

Example:

```text
Report NO_CHANGE
```

## Deferred

The system cannot safely act.

Example:

```text
ambiguous Story
```

## Retryable failure

Infrastructure or temporary operational problem.

The Job may run again.

## Terminal failure

The Job cannot safely proceed under current conditions.

These outcomes are deliberately distinguishable through orchestration status.

---

# 71. Human vs Automation Principle

Throughout Phase 23:

```text
human domain decision
>
stale automatic intention
```

Examples:

- rejected Claim;
- archived Story;
- disabled Alert rule;
- acknowledged Alert.

Workers re-read current state rather than assuming the world remained unchanged since the Job was enqueued.

---

# 72. API Compatibility Completed

By the end of Phase 23, the API supports operator/user inspection of the important asynchronous states.

This includes:

- pending/unassigned automatic Claims;
- Claim provenance;
- StoryRevision citations;
- Report proposition Claim IDs;
- Report exact causes;
- Alert exact causes;
- Phase 23 Job status.

This is important because the underlying pipeline is asynchronous.

Intermediate state is a normal part of the product.

---

# 73. Frontend Compatibility Completed

The frontend can represent at least the key Phase 23 states necessary for compatibility.

Most importantly:

```text
pending automatic Claim
+ no Story yet
```

is a valid displayable state.

Frontend types were updated for:

- Claims;
- StoryRevisions;
- Job projections;
- Alert/Report provenance where required.

Phase 23 intentionally did **not** perform a broad frontend redesign.

---

# 74. Logical Export Completed

The audit-oriented export now preserves enough relationship records to reconstruct the major Phase 23 chain.

Key relationships include:

```text
Story revisions
Story revision Claims
Story revision Documents
Story evolution events

Report revisions
Report revision Claims
Report revision causes

Alerts
Alert causes/provenance
Alert deliveries

Claims
ClaimEvidence
EvidenceSpans
Documents
DocumentVersions
Sources
```

This makes the logical export materially useful for auditing rather than merely a collection of domain rows.

---

# 75. Integrity Checking Completed

The final integrity checker verifies not only that referenced rows exist, but increasingly that they correspond to the **correct obligation**.

Final Phase 23 integrity includes checking areas such as:

```text
automatic promotion integrity

Story-stage checkpoint integrity

Report-stage checkpoint integrity

Alert-stage checkpoint integrity

success-only downstream identifiers

exact Job ownership

Report cause ownership

Alert cause ownership

delivery relationships
```

This establishes a robust persisted-state audit boundary.

---

# 76. No Schema Migration in Final Phase 23 Work

The Phase 23E and Phase 23F completion work did not require another schema migration.

Final schema remained:

```text
23
```

Fresh creation, upgrades, and foreign-key validation continued to pass.

This was intentional.

Hardening was performed through application invariants, validation, APIs, export relationships, and tests where a new schema relationship was not necessary.

---

# 77. Validation Completed

The final Phase 23 audit reran the individual Phase suites, including:

```text
Phase 22.3 trust boundary

Phase 23A Story resolution

Phase 23B Story automation

Phase 23C Report automation

Phase 23D Alert automation

Phase 23E compatibility/recovery
```

The combined Phase 23 selection passed.

Relevant tests for:

- foundation;
- migrations;
- APIs;
- domain services;
- evidence;
- acquisition;
- Jobs;
- Stories;
- Reports;
- Workbench;
- export;
- integrity;
- document processing;
- relevance;
- ArticleAnalysis;
- Research-worker compatibility;

also passed.

The complete backend suite passed.

Additional validation passed:

```text
python -m compileall -q newsroom scripts tests

npm run typecheck

python scripts/live_test_c.py

git diff --check

git diff --cached --check

foreign-key validation
```

Only existing `httpx` TestClient deprecation warnings remained.

---

# 78. Final Accepted Repository State

The final Phase 23 acceptance audit completed with:

```text
Branch:
main

Final accepted commit:
52ab0ad093406faff333058d23d003b5620e806f

Commit:
Phase 23F: close final acceptance gaps

Schema:
23

Tracked worktree:
clean

Staged state:
empty

Push:
not performed
```

This SHA is historical documentation of the accepted Phase 23 checkpoint, not a required starting SHA for later phase plans.

Future phases should inspect the actual current repository HEAD.

---

# 79. What Phase 23 Deliberately Did Not Do

Phase 23 intentionally stopped once the trusted autonomous intelligence engine was complete.

It did **not** implement:

```text
semantic Watch vocabulary expansion
Source discovery
AI-assisted Source discovery
unified Watch management
autonomous Research Question pursuit
Evidence Gap research loops
smart tagging
canonical Entity intelligence
advanced Workbench search
evidence-grounded Ask
Story merge
Story split
Claim reassignment
advanced Source dependency intelligence
browser Push
email/SMS/Slack delivery
broad frontend redesign
vector database
generic knowledge graph
multi-provider architecture
```

Those became later product phases.

---

# 80. Why Phase 23 Matters

Before Phase 23, Newsroom could increasingly understand a Document.

After Phase 23, Newsroom can **maintain intelligence over time**.

That difference is substantial.

Before:

```text
article
→ analysis
→ Claim
```

After:

```text
incoming evidence
        ↓
verified Claim
        ↓
Story evolves
        ↓
Living Report changes
        ↓
material cause identified
        ↓
Alert delivered
```

and every part remains traceable to the original evidence.

---

# 81. Final Phase 23 Architecture

The complete Newsroom core at the end of Phase 23 can be summarized as:

```text
MONITORING
Source / Monitor
        ↓

ACQUISITION
Document
        ↓
DocumentVersion
        ↓
ContentArtifact
        ↓

ANALYSIS
Relevance
        ↓
ArticleAnalysis
        ↓

EVIDENCE
verified promotion
        ↓
EvidenceSpan
        ↓
ClaimEvidence
        ↓
Claim
        ↓

STORY INTELLIGENCE
automatic_story_stage
        ↓
deterministic Story resolution
        ↓
Story
        ↓
StoryEvolution
        ↓
StoryRevision
        ↓

INTELLIGENCE ACCEPTANCE
audited Claim state transition
        ↓
accepted Claim
        ↓

REPORTING
automatic_report_stage
        ↓
materiality evaluation
        ↓
LivingReport
        ↓
ReportRevision
        ↓
exact causes
        ↓

AWARENESS
automatic_alert_stage
        ↓
Alert rule evaluation
        ↓
exact matching causes
        ↓
Alert
        ↓
durable in_app delivery
```

Surrounding the entire chain are:

```text
Jobs
leases
retries
replay
concurrency controls
human override
API visibility
logical export
integrity validation
runtime integration tests
Live Test C
```

---

# 82. Phase 23 Final Acceptance Result

The final independent audit verified:

```text
[PASS] canonical evidence trust boundary

[PASS] deterministic automatic Story qualification

[PASS] bounded Story candidate retrieval

[PASS] conservative ambiguous resolution

[PASS] durable Story-stage automation

[PASS] mutation-time Story re-resolution

[PASS] Story concurrency safety

[PASS] evidence-bound StoryRevision creation

[PASS] audited automatic Claim acceptance

[PASS] human Claim-state authority

[PASS] durable Report-stage automation

[PASS] deterministic Report materiality

[PASS] NO_CHANGE without duplicate revisions

[PASS] closed-world Report provenance

[PASS] exact Report change causes

[PASS] Report concurrency safety

[PASS] durable Alert-stage automation

[PASS] exact Alert cause filtering

[PASS] stable Alert identity

[PASS] exactly-one in_app delivery

[PASS] Alert acknowledgement preservation

[PASS] pending/unassigned Claim visibility

[PASS] Claim provenance API

[PASS] StoryRevision citation API

[PASS] Report provenance API

[PASS] Alert provenance API

[PASS] sanitized orchestration visibility

[PASS] Story audit export

[PASS] Report audit export

[PASS] Alert delivery/provenance export

[PASS] Alert-to-Source export reconstruction

[PASS] complete-chain database integrity

[PASS] exact checkpoint-to-Job ownership

[PASS] invalid downstream identifiers rejected for non-success stages

[PASS] production runtime orchestration

[PASS] full logical replay

[PASS] Story-stage lease recovery

[PASS] Report-stage lease recovery

[PASS] Alert-stage lease recovery

[PASS] cross-stage failure isolation

[PASS] deterministic defer

[PASS] human override

[PASS] Live Test C

[PASS] exact-identity Live Test replay

[PASS] final foreign-key validation

[PASS] full backend suite

[PASS] frontend typecheck

[PASS] clean repository state
```

---

# 83. Final Verdict

```text
PHASE 23: COMPLETE
```

Phase 23 completed the trustworthy autonomous core of Newsroom v2.

The system can now take new monitored information and, without manual orchestration:

```text
acquire it
→ analyze it
→ verify exact evidence
→ create a Claim
→ determine its Story
→ evolve the Story
→ audit and accept the Claim
→ update the Living Report
→ identify exactly what changed
→ evaluate Alert rules
→ generate an exact-cause Alert
→ deliver it in-app
```

while retaining enough provenance to trace the resulting intelligence all the way back to the original Source.

That completed foundation is what allows Phase 24 and later phases to focus on making Newsroom **broader, smarter, more investigative, and easier to use** without rebuilding the trust machinery underneath it.