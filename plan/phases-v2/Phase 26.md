# PHASE 26 — KNOWLEDGE WORKSPACE + ASK

## Entity Intelligence, Smart Tagging, Investigative Workbench, and Evidence-Grounded Ask

---

# 0. PHASE 25 COMPLETION RECONCILIATION

Phase 25 is complete, validated, committed, and accepted.

Phase 26 must begin from the **actual repository after Phase 25**, not from assumptions made before Phase 25 was implemented.

Do not assume a specific starting commit SHA.

Before editing, inspect the current branch, current HEAD, schema, worktree, recent commits, Phase 25 documentation, and all relevant implementation surfaces.

The accepted Phase 25 architecture establishes the following important facts.

---

## 0.1 SCHEMA AND RESEARCH DOMAIN

The accepted repository is at conceptual schema:

```text
schema 25
```

Phase 25 extended the existing Research Question system rather than replacing it.

Research Questions now have an important distinction between:

```text
status
= explicit human lifecycle authority
```

and:

```text
assessment_state
= deterministic evidence-derived assessment
```

Phase 26 must preserve this distinction.

Do not flatten these into one generic Question status in API, frontend, search, Entity relationships, or Ask.

---

## 0.2 QUESTION ASSESSMENTS ARE STRUCTURED

Research Question assessment is grounded in persisted Claim relationships and evidence snapshots.

Phase 26 may retrieve and display:

```text
supporting Claims
contradictory Claims
contextual Claims
assessment state
assessment history
```

but must not reinterpret historical assessments merely because new Entity or Tag metadata is added.

New metadata may improve future retrieval.

It does not rewrite the past.

---

## 0.3 DURABLE EVIDENCE GAPS NOW EXIST

Phase 25 introduced durable typed Evidence Gaps.

These are distinct from older historical gap-suggestion functionality.

Phase 26 must use the durable Phase 25 Gap records for:

```text
Workbench navigation
Ask research-status answers
Entity relationships where useful
Research Question detail
```

Do not treat historical suggestion records as equivalent to current Evidence Gaps.

---

## 0.4 RESEARCH TASKS NOW EXIST

Phase 25 introduced bounded durable Research Tasks associated with Research Questions and Evidence Gaps.

Research Tasks preserve information about:

```text
research strategy
queries
candidate material
acquired Documents
resulting Claims
no-findings outcomes
provider/cost behavior
task history
```

Phase 26 may make these records searchable and navigable where useful.

Research Task history remains operational/research provenance.

It is not itself factual evidence.

---

## 0.5 CORPUS-FIRST RETRIEVAL ALREADY EXISTS

Phase 25 reuses the existing SQL/FTS Workbench search for corpus-first research.

Therefore Phase 26 does **not** begin from zero retrieval infrastructure.

The expected evolution is:

```text
existing SQL / FTS retrieval
        ↓
shared typed knowledge retrieval
        ↓
Workbench v2
        +
Ask Newsroom
```

Reuse and generalize the existing implementation before adding parallel search systems.

---

## 0.6 A NARROW OPTIONAL SEARCH BOUNDARY EXISTS

Phase 25 supports a narrow application-owned search boundary for bounded Research Tasks where needed.

Its results are candidate metadata only.

Phase 26 must maintain a strong product distinction:

```text
Ask
= What does Newsroom currently know?
```

versus:

```text
Research
= Go look for additional evidence.
```

Normal Ask must not silently invoke external research.

If the user wants additional evidence, Ask may offer or launch an explicit Phase 25 research flow through existing supported application actions.

---

## 0.7 PROVIDER PLANNING USES AIROUTER

Phase 25 added bounded structured research-planning capability through the existing `AIRouter`.

Phase 26 must reuse the same provider architecture and budget controls for applicable:

```text
Entity classification
Tag suggestions
Ask interpretation
Ask synthesis
```

Do not create an Ask-specific provider subsystem.

---

## 0.8 ACQUISITION REMAINS CANONICAL

Research findings enter through the existing acquisition and document-processing pipeline.

The canonical factual path remains:

```text
Source
→ Acquisition
→ Document
→ DocumentVersion
→ ContentArtifact
→ Relevance
→ ArticleAnalysis
→ EvidenceSpan
→ Claim
```

Phase 26 metadata and generated answers must not introduce another factual path.

---

## 0.9 SOURCE COUNT TERMINOLOGY

Phase 25 may contain criteria involving more than one Source record.

Phase 26 must audit the actual implementation before presenting those criteria to users.

Unless actual Source dependency/independence is modeled:

```text
different Source record
additional Source
two distinct Source records
```

are valid descriptions.

Do not automatically call them:

```text
independent confirmation
independent Sources
```

Phase 28 remains responsible for advanced Source dependency/intelligence.

---

# 1. ROLE

Implement **Phase 26 of Newsroom v2** as the organized-knowledge and investigative-query layer built on Phases 23 through 25.

The progression is:

```text
Phase 23
trusted autonomous intelligence pipeline

Phase 24
intelligent monitoring

Phase 25
bounded autonomous research

Phase 26
organized knowledge
+
investigative exploration
+
evidence-grounded Ask
```

Phase 26 combines four tightly related capabilities:

```text
1. Canonical Entity Intelligence

2. Smart Tagging

3. Investigative Workbench v2

4. Evidence-Grounded Ask Newsroom
```

These should share one coherent knowledge/retrieval architecture.

Do not build four unrelated subsystems.

---

# 2. PHASE 26 PRODUCT OUTCOME

At completion, a user should be able to search:

```text
AARO
```

and reach a canonical knowledge object containing:

```text
Entity:
AARO

Aliases:
All-domain Anomaly Resolution Office
AARO

Related:
Claims
Evidence
Documents
Stories
Research Questions
Watches
Tags
Sources
recent developments
```

The user should be able to pivot naturally:

```text
Entity
→ Claim
→ EvidenceSpan
→ Document
→ Source
```

and:

```text
Entity
→ Story
→ StoryRevision
→ Claims
```

and:

```text
Entity
→ Research Question
→ Evidence Gap
→ Research Task
```

The same knowledge system should support:

```text
"What evidence supports claims
that AARO investigated recovered material?"
```

and return a bounded answer grounded in exact persisted Claims/Evidence.

---

# 3. CENTRAL PHASE 26 PRINCIPLE

Newsroom has spent many phases building structured knowledge.

Do not throw that away by making Ask simply:

```text
article chunks
→ similarity search
→ generated answer
```

Prefer:

```text
question
        ↓
structured interpretation
        ↓
typed retrieval
        ↓
Entities
Claims
Evidence
Stories
Research Questions
Sources
Reports
        ↓
bounded context
        ↓
answer synthesis
        ↓
citation / grounding validation
        ↓
response
```

Structured intelligence is the primary retrieval substrate.

---

# 4. CODEBASE-FIRST INSTRUCTION

Before designing Phase 26, audit the repository.

Review at minimum:

```text
Topics
Subjects
ArticleAnalysis
structured extracted entities
existing Tags/category metadata
Claims
ClaimEvidence
EvidenceSpans
Stories
StoryRevisions
StoryEvolution
Research Questions
assessment_state
Question status/history
Evidence Gaps
Research Tasks
Watches
Watch vocabulary
Sources
existing Workbench/Search
FTS implementation
Phase 25 corpus retrieval
API
frontend
AIRouter
provider budgets
Jobs
scheduler
logical export
check_database()
migrations
tests
```

The plan defines required outcomes and invariants.

Implementation details may change based on repository reality.

Prefer extending mature abstractions.

---

# 5. REPOSITORY STARTING STATE

Assume only:

```text
Phase 25 is complete and committed.
```

Do not assume a starting SHA.

Before editing:

```text
inspect branch
inspect HEAD
inspect recent commits
inspect tracked worktree
inspect index
inspect schema
inspect Phase 25 completion docs
inspect existing search/retrieval code
preserve unrelated files
```

Do not reset repository history.

Do not rewrite existing commits.

Do not push.

---

# 6. FIRST TASK — KNOWLEDGE ARCHITECTURE AUDIT

Answer from the codebase:

```text
1. What does Topic represent?

2. What does Subject represent?

3. Are structured entities already extracted by ArticleAnalysis?

4. What entity-like identifiers already exist?

5. Are aliases/acronyms persisted outside Watch vocabulary?

6. What tag/category systems already exist?

7. Which domain objects are currently indexed by FTS?

8. How does Workbench currently search?

9. How does Phase 25 corpus-first retrieval use Workbench/FTS?

10. How are Claim propositions searched?

11. How are EvidenceSpans searched?

12. How are Story relationships searched?

13. How are Research Question relationships searched?

14. What indexes currently support these queries?

15. Which existing frontend surfaces provide provenance navigation?

16. Which provider operations already support structured classification?

17. What ArticleAnalysis output can support Entity resolution?

18. Which migrations/contracts must remain backward compatible?
```

Document the final architecture decision.

---

# 7. SHARED KNOWLEDGE RETRIEVAL SUBSTRATE

Workbench and Ask should use the same underlying retrieval services wherever practical.

Avoid:

```text
Workbench search implementation A
```

and:

```text
Ask retrieval implementation B
```

that disagree about what Newsroom knows.

Prefer:

```text
typed retrieval request
        ↓
shared retrieval layer
        ↓
typed candidate sets
        ↓
bounded ranking/filtering
        ↓
provenance-aware results
```

Potential consumers:

```text
Workbench
Ask
Entity pages
Research Questions
future dashboards
```

---

# 8. RETRIEVAL RESULT CONTRACT

A shared retrieval result should conceptually expose:

```text
object type
object ID
title/name
summary/snippet where appropriate
match reason
relevance/ranking information
date
related domain IDs where useful
```

Do not flatten every object into generic text.

---

# 9. CANONICAL ENTITY PRODUCT MEANING

An Entity represents a persistent identifiable referent.

Examples:

```text
person
organization
government agency
company
program
location
event
legislation
technology
publication
other
```

Use only categories supported by real application behavior.

---

# 10. ENTITY IS NOT TOPIC

Maintain:

```text
Topic
= thematic area
```

```text
Entity
= identifiable referent
```

Example:

```text
Topic:
UAP disclosure

Entity:
AARO
```

Both may be associated with the same Claim or Watch.

---

# 11. ENTITY IS NOT TAG

Maintain:

```text
Entity
= who / what the intelligence refers to
```

```text
Tag
= descriptive classification
```

Example:

```text
Entity:
NASA

Tag:
government statement
```

---

# 12. SUBJECT VS ENTITY DECISION

Audit the current Subject model carefully.

Possible valid outcomes:

```text
Subject remains independent
```

```text
Subject becomes Entity-backed
```

```text
some Subject records map to Entities
while Subject retains broader semantics
```

Do not blindly replace Subject.

The completion report must explicitly document:

```text
Topic
Subject
Entity
Tag
```

and their final responsibilities.

---

# 13. ENTITY RECORD

Use the smallest durable Entity contract required.

Conceptually:

```text
id
canonical_name
normalized_name
entity_type
description where useful
status
created_at
updated_at
```

Do not create a generic arbitrary-property graph node.

---

# 14. ENTITY ALIASES

Aliases should be first-class records.

Conceptually:

```text
Entity
→ EntityAlias
```

Useful fields may include:

```text
alias
normalized_alias
alias_type
origin
status
created_at
```

Potential alias types:

```text
alternate_name
acronym
expanded_name
abbreviation
former_name
```

Only distinguish types where behavior or UX benefits.

---

# 15. ALIAS ORIGIN

Persist origin where practical:

```text
user
existing Subject
Watch vocabulary
ArticleAnalysis
deterministic
provider-assisted
import
```

This allows Newsroom to explain:

```text
Why does this alias resolve to this Entity?
```

---

# 16. ENTITY CANDIDATES

Do not automatically force every extracted name into a canonical Entity.

Where ArticleAnalysis or provider output produces ambiguous new entity-like material, use an unresolved/candidate state where useful.

Conceptually:

```text
candidate mention
        ↓
deterministic resolution
        ↓
existing Entity
```

or:

```text
candidate mention
        ↓
insufficient identity evidence
        ↓
remains unresolved
```

Only create a new canonical Entity when current policy provides enough evidence.

---

# 17. ENTITY RESOLUTION PRINCIPLE

False merges are worse than temporary duplicates.

Therefore:

```text
possibly same
≠
definitely same
```

Examples such as:

```text
John Smith
DIA
Mercury
```

may be ambiguous.

When uncertain, preserve ambiguity.

---

# 18. DETERMINISTIC ENTITY RESOLUTION

Prefer signals such as:

```text
exact canonical normalized name

approved alias

explicit acronym expansion

existing Subject identity

stable structured identifier

known Watch vocabulary relationship
```

before provider assistance.

---

# 19. PROVIDER-ASSISTED ENTITY CLASSIFICATION

Provider assistance may classify a bounded set of ambiguous candidates.

Use:

```text
AIRouter
bounded structured input
bounded candidate list
structured result schema
existing budgets
```

Provider output should propose a resolution decision or candidate.

It should not bypass normal Entity domain logic.

---

# 20. ENTITY CREATION POLICY

Possible creation paths:

```text
manual Entity creation
```

```text
deterministically mapped existing Subject
```

```text
high-confidence structured ArticleAnalysis extraction
```

```text
approved candidate
```

Avoid creating a durable Entity for every noun phrase in every Document.

---

# 21. ENTITY MENTION

Separate:

```text
Entity
```

from:

```text
EntityMention
```

A mention represents an occurrence of an Entity in analyzed content.

Possible provenance:

```text
Entity ID
Document/DocumentVersion ID
ArticleAnalysis ID
surface text
location/offset where current artifact model supports it
origin
```

---

# 22. ENTITYMENTION IS NOT EVIDENCE

Maintain:

```text
EntityMention
= content contains/references Entity
```

while:

```text
EvidenceSpan
= exact content supporting a Claim
```

An EntityMention does not automatically become Evidence.

---

# 23. CLAIM ↔ ENTITY

Claims should support explicit Entity associations.

At minimum:

```text
Claim
→ Entity
```

If reliable roles already exist, optionally distinguish roles such as:

```text
subject
object
location
organization
mentioned
```

Do not invent semantic role precision unsupported by ArticleAnalysis.

---

# 24. CLAIM-ENTITY PROVENANCE

Automatic Claim-Entity links should retain origin where useful.

Potential origins:

```text
ArticleAnalysis
deterministic alias match
manual
provider-assisted
```

The user should be able to understand why the relationship exists.

---

# 25. STORY ↔ ENTITY

Prefer Story-Entity relationships derived from:

```text
Claims
Documents
StoryRevision content
```

rather than an opaque Entity list.

If materialized for performance, retain provenance or deterministic reconstruction.

---

# 26. RESEARCH QUESTION ↔ ENTITY

Research Questions may relate to canonical Entities.

Entity resolution may improve:

```text
future Claim candidate retrieval
Workbench filtering
Ask scoping
Research Task planning
```

It must not rewrite old:

```text
assessment snapshots
assessment history
Question transition history
```

---

# 27. EVIDENCE GAP ↔ ENTITY

Where useful and semantically clear, a Gap may reference an Entity.

Example:

```text
Need primary documentation from Entity X
```

Do not require every Gap to have an Entity.

---

# 28. RESEARCH TASK ↔ ENTITY

Research Tasks may inherit Entity scope from their Question/Gap.

This should improve query planning.

Do not make Research Tasks another permanent Entity relationship system unless the relationship is useful after execution.

---

# 29. WATCH ↔ ENTITY

Phase 26 may add canonical Entity Watch targets where useful.

Existing Phase 24 Watch targets remain valid.

Do not destructively migrate historical Watch configuration simply because an equivalent Entity now exists.

Prefer backward-compatible mapping.

---

# 30. ENTITY MERGE

Provide a conservative user-correctable duplicate-Entity mechanism if the current architecture can support it cleanly.

Preferred semantics:

```text
Entity B
→ merged/superseded by Entity A
```

Historical IDs should remain reconstructable.

Do not delete provenance.

---

# 31. ENTITY MERGE BOUNDARY

Entity merge is not Story merge.

Phase 26 may resolve two identity records representing the same referent.

Do not implement:

```text
Story merge
Story split
Claim reassignment between Stories
```

Those belong to Phase 27.

---

# 32. SMART TAGGING PRODUCT GOAL

Tags provide lightweight cross-object classification.

Examples might include:

```text
primary source
technical report
government statement
hearing testimony
scientific analysis
legal filing
correction
policy change
eyewitness account
historical context
```

Actual Tag vocabulary should derive from current Newsroom needs.

---

# 33. TAG MODEL

A Tag should conceptually include:

```text
id
name
normalized_name
category where useful
description where useful
status
created_at
updated_at where applicable
```

Avoid uncontrolled duplicate free-text tags.

---

# 34. TAG ASSOCIATION

Tag assignment should be a durable relationship.

Conceptually:

```text
Tag
→ target object
```

Potential targets:

```text
Document
Claim
Story
Research Question
Source
Entity
```

Implement only targets that have product value.

---

# 35. TAG ASSOCIATION ORIGIN

Persist origin where useful:

```text
user
deterministic
ArticleAnalysis
provider-assisted
import
```

Manual Tags must remain distinguishable from automatic Tags.

---

# 36. TAGS SHOULD NOT DUPLICATE EXISTING FIELDS WITHOUT PURPOSE

If:

```text
Document.document_type = technical_report
```

already provides a useful indexed field, do not automatically duplicate it into:

```text
Tag: technical_report
```

unless cross-object unified filtering benefits from the Tag relationship.

---

# 37. DETERMINISTIC TAGGING FIRST

Potential deterministic inputs include:

```text
Source type
Document type
ArticleAnalysis classification
Claim lifecycle
StoryEvolution type
Research Question assessment
Evidence characteristics
```

Only create Tags that have clear retrieval/filtering value.

---

# 38. PROVIDER-ASSISTED TAGGING

Use provider assistance only where semantic classification materially improves tagging.

Reuse:

```text
AIRouter
existing budgets
bounded structured context
bounded result counts
```

Prefer assignment from an existing controlled vocabulary.

---

# 39. NEW TAG SUGGESTIONS

If providers may suggest previously unknown Tags:

```text
suggested Tag
≠
automatically accepted taxonomy
```

Use an explicit validation/approval policy or conservative automatic acceptance only for deterministic normalization.

---

# 40. TAG EXPLOSION CONTROL

Set practical limits on:

```text
Tags per object
new Tag definitions per run
provider suggestions per object/run
backfill batch size
```

Avoid turning the database into semantic confetti.

---

# 41. HISTORICAL ENTITY/TAG BACKFILL

Existing ArticleAnalysis records may need Entity and Tag enrichment.

If so, implement bounded durable Jobs.

Backfill should be:

```text
incremental
bounded
restartable
idempotent
observable
```

---

# 42. BACKFILL MUST NOT REWRITE TRUSTED HISTORY

Entity/Tag backfill may add metadata.

It must not rewrite historical:

```text
EvidenceSpan
Claim proposition
ClaimEvidence
StoryRevision
ReportRevision
Alert
Research Question assessment history
```

unless an existing explicit reprocessing workflow separately authorizes that behavior.

---

# 43. BACKFILL IDENTITY

Repeated processing must converge.

Expected:

```text
same analysis/entity mention
→ one logical EntityMention
```

```text
same deterministic Tag assignment
→ one logical association
```

Use database constraints as the final identity boundary where appropriate.

---

# 44. WORKBENCH V2 PRODUCT GOAL

Workbench becomes Newsroom's primary investigative navigation surface.

It should search:

```text
knowledge objects
```

not merely Documents.

---

# 45. GLOBAL HETEROGENEOUS SEARCH

Support useful bounded search across applicable:

```text
Entities
Claims
Evidence
Documents
Stories
Research Questions
Sources
Reports
Alerts
Watches
Tags
Research Tasks where useful
```

Do not add object types that create noise without investigative value.

---

# 46. TYPED RESULTS

Every result should identify its domain type.

Example:

```text
AARO
Entity

AARO Historical Report
Document

AARO states no evidence of program
Claim

2026 AARO Hearing
Story
```

---

# 47. STRUCTURED RETRIEVAL FIRST

Prefer:

```text
exact ID lookup
canonical names
aliases
acronyms
typed relationships
SQL filters
existing FTS
bounded lexical matching
```

before introducing additional semantic infrastructure.

---

# 48. EXTEND EXISTING FTS

Phase 25 already relies on SQL/FTS Workbench search.

Audit:

```text
current FTS tables
indexed fields
ranking
pagination
query normalization
```

Extend existing indexes only where Phase 26 retrieval requires them.

---

# 49. WORKBENCH FILTERS

Useful filters may include:

```text
object type
date range
Watch
Story
Entity
Research Question
Source
Tag
Claim state
Question assessment state
Question human lifecycle
```

Do not expose inefficient or unindexed filters merely because they sound useful.

---

# 50. QUESTION FILTER SEMANTICS

Because Phase 25 separates:

```text
status
```

from:

```text
assessment_state
```

Workbench must preserve both.

Example filters may distinguish:

```text
Human lifecycle:
open / closed
```

from:

```text
Evidence assessment:
partially answered / contradicted / supported
```

Do not conflate them.

---

# 51. SEARCH FACETS

Where useful and efficient, return bounded facets such as:

```text
result type counts
Entities
Sources
Tags
Stories
date buckets
```

Do not turn Phase 26 into analytics/dashboard work.

---

# 52. SEARCH RANKING

Ranking should be understandable.

Possible signals:

```text
exact canonical Entity name
exact approved alias
exact title
Claim proposition match
explicit Entity relationship
Story relationship
Question relationship
FTS score
recency
```

Do not make an opaque provider score the sole ranking mechanism.

---

# 53. MATCH EXPLANATION

Where practical, expose why a result matched.

Examples:

```text
Exact Entity alias match
```

```text
Claim proposition match
```

```text
Document related to selected Story
```

```text
Research Question linked to Entity
```

---

# 54. SEARCH PAGINATION

All Workbench result collections must be bounded.

Use stable repository pagination conventions.

Do not return the whole corpus.

---

# 55. WORKBENCH PIVOT NAVIGATION

Support natural investigation paths:

```text
Entity
→ Claims
```

```text
Claim
→ EvidenceSpan
```

```text
EvidenceSpan
→ Document
```

```text
Document
→ Source
```

```text
Claim
→ Story
```

```text
Claim
→ Research Question
```

```text
Research Question
→ Evidence Gap
```

```text
Evidence Gap
→ Research Task
```

```text
Story
→ Report
```

Provenance should be navigable, not hidden.

---

# 56. ENTITY DETAIL

At minimum show bounded:

```text
canonical name
aliases
Entity type
description where useful
Claims
Documents
Stories
Research Questions
Watches
Tags
Sources
recent activity
```

---

# 57. CLAIM DETAIL

Improve or preserve:

```text
Claim proposition
Claim state
Story
Entities
Research Question relationships
ClaimEvidence
EvidenceSpans
Documents
Sources
origin/history
```

---

# 58. EVIDENCE DETAIL

The exact provenance chain should remain obvious:

```text
EvidenceSpan
→ DocumentVersion
→ Document
→ Source
→ Claim
```

Do not bury evidence underneath generated prose.

---

# 59. DOCUMENT DETAIL

Expose useful structured relationships such as:

```text
Source
publication date
ArticleAnalysis
Entities
Tags
Claims
Stories
Research Questions
Research Tasks where relevant
```

Respect existing content-display policy.

---

# 60. STORY DETAIL

Phase 26 may improve navigation around:

```text
current StoryRevision
Claims
Documents
Entities
Research Questions
Reports
StoryEvolution
```

Do not implement Story correction operations.

---

# 61. RESEARCH QUESTION DETAIL

Integrate Phase 25 directly.

Expose:

```text
human lifecycle status
evidence assessment_state
supporting Claims
contradictory Claims
contextual Claims
Evidence Gaps
Research Tasks
Entities
Sources
Stories
```

Do not build a second Research Question presentation model.

---

# 62. RESEARCH TASK NAVIGATION

Research Task history may appear in Workbench/detail navigation.

The user should be able to follow:

```text
Question
→ Gap
→ Task
→ candidate/acquired Document
→ resulting Claim
```

where persisted.

---

# 63. SAVED SEARCHES

Saved searches are optional.

Implement only if low-cost and clearly useful.

A saved search must not become a second Watch system.

Continuous monitoring remains Phase 24 Watch behavior.

---

# 64. ASK NEWSROOM PRODUCT GOAL

Ask Newsroom should answer:

> **What does Newsroom currently know about this?**

Examples:

```text
What evidence supports Claim X?

What changed in Story Y?

What contradictions exist around Question Z?

What do we know about AARO?

Which Source records reported this?

What remains unresolved?
```

---

# 65. ASK DEFAULT SCOPE

Normal Ask uses:

```text
Newsroom persisted corpus
```

not external search.

This should be explicit product behavior.

---

# 66. ASK VS RESEARCH

Maintain:

```text
Ask
= retrieve and explain current knowledge
```

```text
Research Task
= seek additional evidence
```

If Ask cannot answer because evidence is missing, it may offer an action such as:

```text
Research this gap
```

or:

```text
Create/pursue Research Question
```

through Phase 25 services.

Do not silently turn Ask into research.

---

# 67. ASK-TO-RESEARCH BRIDGE

Where the product flow supports it, an insufficient-evidence Ask result may identify:

```text
existing open Research Question
existing Evidence Gap
```

or allow the user to initiate:

```text
new Research Question
or
new bounded Research Task
```

using normal Phase 25 APIs/services.

Ask itself still does not treat research candidate data as evidence.

---

# 68. ASK ARCHITECTURE

Preferred flow:

```text
question
        ↓
structured interpretation
        ↓
validated retrieval plan
        ↓
shared knowledge retrieval
        ↓
bounded retrieval packet
        ↓
answer synthesis
        ↓
citation / grounding validation
        ↓
response
```

---

# 69. ASK INTERPRETATION

Interpretation may identify:

```text
Entities
Story
Research Question
Claim
Source
date range
requested evidence type
intent
scope
```

Keep intent taxonomy small.

Potential intents:

```text
factual
evidence
what_changed
contradictions
entity_summary
source_summary
research_status
```

---

# 70. STRUCTURED INTERPRETATION

If AIRouter assists query interpretation:

```text
provider result
→ bounded structured interpretation
→ validation
→ application retrieval operations
```

Provider output should select predefined retrieval semantics.

It does not become application query code.

---

# 71. ASK RETRIEVAL PLAN

A retrieval plan should contain only fields needed by the application.

Conceptually:

```text
scope objects
Entity IDs
Story IDs
Question IDs
date bounds
requested object types
intent
maximum result counts
```

---

# 72. RETRIEVAL ORDER

Prefer:

```text
1. Explicit referenced object

2. Canonical Entity / Story / Research Question

3. Claims

4. EvidenceSpans

5. Documents / Sources

6. ReportRevision / StoryEvolution where intent requires
```

Do not begin with arbitrary article fragments when structured Claims already answer the question.

---

# 73. CLAIM-CENTRIC FACTUAL ANSWERS

For factual questions, Claims should generally be the semantic core.

Example:

```text
Did agency X confirm Y?
```

Prefer:

```text
Claim
→ ClaimEvidence
→ EvidenceSpan
→ Document
→ Source
```

over:

```text
Documents containing the same keywords
```

---

# 74. EVIDENCE QUESTIONS

For:

```text
What evidence supports X?
```

retrieve exact:

```text
Claims
ClaimEvidence
EvidenceSpans
Documents
Sources
```

rather than generating a high-level article summary alone.

---

# 75. WHAT-CHANGED QUESTIONS

For:

```text
What changed in Story X this week?
```

prefer:

```text
StoryRevision
StoryEvolution
ReportRevision causes
Claims
```

Phase 23 already provides structured change information.

Use it.

---

# 76. RESEARCH-STATUS QUESTIONS

For:

```text
What do we still not know?
```

prefer:

```text
Research Question
assessment_state
supporting Claims
contradictory Claims
Evidence Gaps
Research Task history
```

Do not infer that a Gap is resolved because a Task completed.

---

# 77. ENTITY QUESTIONS

For:

```text
What do we know about AARO?
```

retrieve bounded:

```text
Entity
aliases
Claims
Stories
Questions
Documents
Sources
recent trusted evidence
```

Do not produce an unconstrained general biography from model memory.

---

# 78. SOURCE QUESTIONS

For:

```text
Which Sources support this?
```

trace exact:

```text
Claim
→ Evidence
→ Document
→ Source
```

Use precise language around distinct Source records.

---

# 79. ASK RETRIEVAL PACKET

Before synthesis, construct a bounded structured retrieval packet.

Each factual item should have stable IDs.

Example:

```text
Claim C1
EvidenceSpan E1
Document D1
Source S1
```

The model should not need to generate domain IDs.

---

# 80. RETRIEVAL PACKET TYPES

A packet may contain:

```text
Claims
EvidenceSpans
Sources
Entities
Stories
StoryEvolution events
ReportRevision causes
Research Questions
Evidence Gaps
```

Include only what the user question requires.

---

# 81. CLOSED-WORLD ANSWERING

Normal Ask synthesis must operate from the retrieval packet.

Factual answers should derive from:

```text
retrieved Newsroom state
```

not silently from general pretrained knowledge.

---

# 82. CITATION CONTRACT

Factual assertions should cite exact persisted records.

Preferred factual citation:

```text
Claim ID
+
EvidenceSpan ID
```

with navigation to:

```text
Document
Source
```

Structured status statements may instead cite:

```text
Research Question
StoryRevision
StoryEvolution
ReportRevision
```

when those records are the direct factual source.

---

# 83. CITATION VALIDATION

Before returning an answer, validate that every citation:

```text
references an existing record
```

and:

```text
belongs to the current retrieval packet
```

A real ID outside the retrieved context is not a valid citation for that answer.

---

# 84. GROUNDING VALIDATION

Where practical, ensure factual answer statements are supported by retrieved Claims/Evidence.

Do not attempt a universal language-proof engine.

Use a bounded policy:

```text
supported by retrieved persisted evidence
→ include
```

```text
reasonable synthesis from retrieved evidence
→ label as inference where needed
```

```text
unsupported
→ omit or fail validation
```

---

# 85. INFERENCE LABELING

Distinguish:

```text
persisted Claim
```

from:

```text
Source assertion
```

from:

```text
answer synthesis/inference
```

Example:

```text
Taken together, these records suggest...
```

should be distinguishable from:

```text
Newsroom has an accepted Claim that...
```

---

# 86. CONTRADICTION HANDLING

If relevant accepted Claims materially conflict:

```text
present the disagreement
```

Do not silently choose one.

Cite both sides.

---

# 87. QUESTION HUMAN STATE VS ASSESSMENT

When Ask discusses a Research Question, preserve the Phase 25 distinction.

Example:

```text
Question lifecycle:
open

Evidence assessment:
partially answered
```

Do not summarize both as:

```text
status: partially answered
```

if that loses human lifecycle meaning.

---

# 88. INSUFFICIENT EVIDENCE

If the corpus cannot answer:

```text
say so
```

Useful output may identify:

```text
no qualifying Claims found
open Evidence Gap
related but insufficient material
existing Research Question
```

Do not manufacture completion.

---

# 89. SOURCE-COUNT PRECISION

If three Documents derive from one Source record:

```text
do not call them three confirmations
```

Likewise, multiple Source IDs should be described as distinct Source records unless stronger dependency information exists.

---

# 90. ASK RESPONSE STRUCTURE

A useful response may include:

```text
answer
citations
contradictions / uncertainty
open research gaps
```

Avoid forcing every response into a large rigid template.

Structured metadata should still exist behind the response.

---

# 91. ASK HISTORY

Decide after repository audit whether Ask history should be persisted.

Possible:

```text
ephemeral
```

or:

```text
lightweight persisted sessions
```

If persisted, consider:

```text
user question
answer
scope
retrieval IDs
citations
provider provenance
timestamp
```

---

# 92. ASK HISTORY IS NOT EVIDENCE

A previous generated answer does not become a Claim/Evidence source.

On follow-up:

```text
previous conversation
→ conversational context
```

but:

```text
canonical retrieval
→ factual context
```

must still run.

---

# 93. FOLLOW-UP QUESTIONS

Support follow-up where practical.

Example:

```text
Which Sources support Claim X?

Which of those were government Sources?
```

The second request may inherit scope.

It must still query current persisted state.

---

# 94. DOMAIN-SCOPED ASK

Support convenient entry points:

```text
Ask about this Entity

Ask about this Story

Ask about this Claim

Ask about this Research Question

Ask about this Source
```

This provides an exact starting scope.

---

# 95. AMBIGUOUS ENTITY ASK

If the user asks about an ambiguous alias:

```text
DIA
```

do not silently merge multiple possible Entities.

Use:

```text
clear deterministic disambiguation
```

or:

```text
ask user to choose
```

where necessary.

---

# 96. PROVIDER ROLE

Reuse AIRouter/provider infrastructure for:

```text
Ask interpretation
Ask answer synthesis
optional Entity classification
optional Tag classification
```

Do not create a parallel provider stack.

---

# 97. DETERMINISTIC ASK FALLBACK

When synthesis provider is unavailable, return useful structured results where possible.

Example:

```text
Matching accepted Claims:
3

Contradictory Claims:
1

Open Evidence Gaps:
2

Sources:
S1
S2
```

with links/provenance.

Ask should degrade, not disappear.

---

# 98. PROVIDER CONTEXT BOUNDS

Define limits for:

```text
Claims
EvidenceSpans
Documents
Entities
Stories
Research Questions
context characters/tokens
provider calls
```

Never send the entire corpus to the synthesis provider.

---

# 99. PROVIDER DATA MINIMIZATION

Prefer:

```text
Claim propositions
exact Evidence excerpts
Source metadata
Question assessment
Story changes
```

over raw full Documents when full content is unnecessary.

Reuse existing privacy/provider policy.

---

# 100. EXTERNAL CONTENT AND PROVIDER BOUNDARY

Phase 26 processes:

```text
Document content
Entity suggestions
Tag suggestions
Ask interpretation
Ask synthesis
```

Reuse existing application:

```text
input validation
provider-output validation
authorization
privacy
provider budgets
request/destination controls
domain-service boundaries
```

Externally derived/provider-derived content remains application data.

It may mutate canonical state only through the appropriate validated services.

---

# 101. OUTCOME-FOCUSED BOUNDARY REGRESSIONS

Test outcomes such as:

```text
invalid Entity suggestion
→ rejected
→ canonical Entity state unchanged
```

```text
invalid Tag suggestion
→ rejected
→ existing Tag state unchanged
```

```text
invalid Ask interpretation
→ request fails/falls back safely
→ no domain mutation
```

```text
retrieved content
→ remains data
→ does not alter configured application behavior
```

Keep tests focused on product outcomes.

---

# 102. VECTOR RETRIEVAL DECISION GATE

Do not introduce embeddings merely because Phase 26 includes Ask.

First benchmark:

```text
structured relationships
+
aliases
+
FTS
+
normalization
+
bounded provider-assisted interpretation
```

---

# 103. STRUCTURED RETRIEVAL BENCHMARK

Create a reproducible benchmark including:

```text
exact Entity lookup
alias lookup
acronym lookup
Claim phrase lookup
Story lookup
Research Question lookup
evidence question
contradiction question
what-changed question
date-bounded lookup
cross-object lookup
```

---

# 104. BENCHMARK MEASURES

Measure at minimum:

```text
correct object retrieved
top-N candidate recall
ranking quality
false-positive behavior
query bounds
latency appropriate to project scale
```

Do not require elaborate ML metrics where simple retrieval assertions are sufficient.

---

# 105. VECTOR INTRODUCTION CRITERIA

Only introduce embeddings if the benchmark shows material retrieval failures that cannot reasonably be corrected through:

```text
aliases
FTS
structured relations
query normalization
additional deterministic indexes
bounded semantic classification
```

Document the evidence.

---

# 106. IF VECTORS ARE JUSTIFIED

If embeddings are genuinely needed:

```text
vectors
= derivative candidate retrieval aid
```

not:

```text
vectors
= canonical knowledge
```

Prefer semantic units such as:

```text
Claims
Entity descriptions
Research Question propositions
Story summaries
```

before arbitrary Document chunks where practical.

---

# 107. VECTOR REBUILDABILITY

Any derivative vector index must:

```text
use stable canonical record IDs
be rebuildable
not be required for export
not become canonical provenance
```

SQL/domain records remain authoritative.

---

# 108. SEARCH QUALITY BEFORE VECTOR COMPLEXITY

Before adding a new datastore, attempt to improve:

```text
FTS fields
indexes
aliases
typed retrieval
candidate selection
ranking
```

Keep Phase 26 architecture as simple as evidence permits.

---

# 109. API DESIGN

Use existing `/api/v1` patterns.

Phase 26 capability groups may include:

```text
Entities
Entity aliases
Entity relations
Tags
Workbench Search
Ask
Ask sessions/history if persisted
```

Do not create redundant endpoints for relationships already exposed efficiently elsewhere.

---

# 110. ENTITY API

Support equivalents of:

```text
list
detail
create where useful
update where allowed
aliases
related Claims
related Documents
related Stories
related Research Questions
Tags
merge where implemented
```

All collections bounded.

---

# 111. TAG API

Support:

```text
list
detail
create/edit where allowed
associations
suggestions/approval where implemented
```

Do not build a full ontology-management application.

---

# 112. WORKBENCH SEARCH API

Prefer one coherent search contract.

Conceptually:

```text
query
object types
filters
date range
pagination
sort
```

Return:

```text
typed results
stable IDs
match explanation
bounded highlights
```

---

# 113. ASK API

Ask input should conceptually include:

```text
question
optional domain scope
optional conversation/session ID
```

Response:

```text
answer
citations
retrieved domain IDs or concise retrieval summary
limitations/uncertainty
Research Question/Gap suggestion where applicable
provider/cost metadata only if existing API policy exposes it
```

---

# 114. ASK RESPONSE SANITIZATION

Do not expose raw:

```text
provider prompt
provider response blob
internal retrieval orchestration
internal Job result
```

through the normal public Ask contract.

Return stable structured data.

---

# 115. FRONTEND PRODUCT GOAL

Phase 26 must produce a functional investigative experience.

Do not postpone all UX until Phase 30.

Visual polish may continue later.

Core knowledge navigation and Ask must work now.

---

# 116. WORKBENCH UI

Provide useful:

```text
global search
typed results
object-type filters
date filters
Entity filters
Source filters
Tag filters
Story/Question filters where useful
```

Do not expose every database field as UI.

---

# 117. ENTITY UI

Provide:

```text
Entity search/list
Entity detail
aliases
related Claims
related Documents
Stories
Questions
Tags
Sources
```

Manual correction/merge should be available if implemented.

---

# 118. TAG UI

Provide lightweight Tag browsing/filtering.

Keep administration simple.

---

# 119. ASK UI

Provide a dedicated Ask experience where the user can:

```text
ask a question
see answer
see citations
open supporting evidence
see contradictions
see insufficient-evidence state
ask follow-up
```

Evidence should be visible without requiring a developer/debug panel.

---

# 120. ASK-TO-RESEARCH UI

When Ask identifies insufficient evidence:

```text
show existing relevant Research Question/Gap
```

or where appropriate offer:

```text
Research this
```

through Phase 25 workflow.

Do not silently start research unless existing user policy explicitly authorizes that action.

---

# 121. CITATION NAVIGATION

Preferred flow:

```text
Answer citation
→ Claim
→ EvidenceSpan
→ Document
→ Source
```

Citation type may vary depending on the answer.

---

# 122. SCOPE-AWARE ASK

From:

```text
Entity
Story
Claim
Research Question
Source
```

support:

```text
Ask about this
```

with preselected scope.

Allow scope expansion where appropriate.

---

# 123. ASK COST VISIBILITY

Reuse existing provider-cost/budget UI conventions if they exist.

Do not build broad cost analytics.

---

# 124. LOGICAL EXPORT

Extend logical export for durable Phase 26 state.

Depending on final architecture:

```text
Entities
Entity aliases
Entity mentions
Claim-Entity relationships
Question-Entity relationships
Story-Entity relationships where persisted
Tags
Tag assignments
Ask sessions/citations if persisted
```

Do not export derivative indexes as canonical data.

---

# 125. EXPORT RECONSTRUCTION

Add reconstruction tests for:

```text
Entity
→ Claim
→ ClaimEvidence
→ EvidenceSpan
→ Document
→ Source
```

and:

```text
Entity
→ Research Question
→ Evidence Gap
→ Research Task
```

where relationships exist.

If Ask history persists:

```text
Ask response
→ citation
→ exact canonical record
```

must reconstruct.

---

# 126. DATABASE INTEGRITY

Extend `check_database()` only for structural truth.

Potential checks:

```text
EntityAlias → valid Entity

EntityMention → valid Entity + analyzed content

ClaimEntity → valid Claim + Entity

QuestionEntity → valid Question + Entity

TagAssignment → valid Tag + target

persisted AskCitation → valid canonical object
```

Do not try to evaluate whether an alias/tag/Entity merge is semantically good in integrity checks.

---

# 127. MIGRATION STRATEGY

Phase 26 will likely require schema changes.

Potential additions include:

```text
Entities
EntityAlias
EntityMention
ClaimEntity
QuestionEntity
Tag
TagAssignment
AskSession / AskCitation if persisted
```

Do not add all tables automatically.

First reuse existing Subject/Topic/extraction relationships where appropriate.

---

# 128. MIGRATION REQUIREMENTS

If schema changes:

```text
fresh database creation
Phase 25 → Phase 26 upgrade
migration repeat/idempotency
foreign-key validation
existing Research Questions preserved
existing Evidence Gaps preserved
existing Research Tasks preserved
existing Watches preserved
existing Stories preserved
```

No historical evidence loss.

---

# 129. ENTITY CONCURRENCY

Use actual database concurrency where identity matters.

Examples:

```text
two workers resolve same deterministic alias
→ one logical relationship
```

```text
two workers process same Entity mention
→ one logical mention
```

```text
two workers create same normalized Tag
→ one Tag
```

---

# 130. ENTITY IDEMPOTENCY

Repeated analysis/backfill must converge for:

```text
Entity
Alias
Mention
Claim-Entity
Question-Entity
Tag
TagAssignment
```

Use database constraints as the final identity boundary where appropriate.

---

# 131. ASK CONCURRENCY

If Ask is ephemeral, normal request isolation is sufficient.

If Ask history is persisted:

```text
request retry
```

must follow existing request/idempotency semantics.

Do not accidentally deduplicate two independent user questions merely because text matches.

---

# 132. FAILURE ISOLATION

Verify:

```text
Entity backfill failure
→ canonical evidence remains valid
```

```text
Tagging failure
→ core corpus remains searchable
```

```text
Ask provider unavailable
→ canonical state unaffected
→ deterministic retrieval remains available
```

```text
Workbench search failure
→ no domain mutation
```

---

# 133. PROVIDER BUDGETS

Reuse existing budget controls for:

```text
Entity classification
Tag suggestions
Ask interpretation
Ask synthesis
```

No Phase 26-specific independent budget subsystem.

---

# 134. PERFORMANCE

Measure key retrieval paths:

```text
Entity name lookup
alias lookup
heterogeneous search
Claim retrieval
Evidence retrieval
Question retrieval
Story retrieval
Ask context construction
Entity detail relationships
```

Add indexes based on actual query plans and benchmarks.

---

# 135. HARD QUERY BOUNDS

Define backend maximums for:

```text
Workbench results
facets
Entity related objects
Tag associations
Ask Claims
Ask EvidenceSpans
Ask Documents
Ask Stories
Ask Questions
Ask Entities
Ask total context
provider calls
```

One Ask request must never load the whole database.

---

# 136. OBSERVABILITY

Add concise events consistent with repository conventions:

```text
Entity created
Entity alias added
Entity resolved
Entity merged
Entity backfill completed
Tag assigned
Tag backfill completed
Workbench search completed where useful
Ask retrieval completed
Ask answer generated
Ask deterministic fallback used
```

Avoid large content/provider payloads in logs.

---

# 137. PHASE 25 COMPATIBILITY

Regression-test:

```text
Question
→ evidence assessment
→ Gap
→ Research Task
→ Document
→ Claim
→ reevaluation
```

Entity/Tag metadata must not change Question truth state except where ordinary canonical relationship logic legitimately causes future reevaluation.

---

# 138. PHASE 24 COMPATIBILITY

Preserve:

```text
Watches
Watch vocabulary
Watch Sources
per-need Monitors
scheduler
Source discovery
```

Canonical Entities may improve Watch targeting but must not invalidate existing Watch targets.

---

# 139. PHASE 23 COMPATIBILITY

Preserve:

```text
Document
→ Evidence
→ Claim
→ Story
→ Report
→ Alert
```

Entity/Tag/Ask systems must not create an alternate evidence path.

---

# 140. PHASE 27 BOUNDARY

Do not implement:

```text
Story merge
Story split
Claim reassignment
Story unassignment
duplicate Story correction
advanced Story identity repair
```

Those remain Phase 27.

---

# 141. CHECKPOINT COMMIT STRATEGY

Phase 26 is large.

Use validated checkpoint commits.

A reasonable structure:

```text
Checkpoint A
Entity model
+ aliases
+ mentions
+ Claim/Question relationships

Checkpoint B
Smart Tags
+ historical metadata backfill
+ shared retrieval substrate

Checkpoint C
Workbench v2
+ retrieval benchmark
+ API/frontend

Checkpoint D
Ask retrieval
+ interpretation
+ grounding
+ citation validation

Final
Ask UI
+ Ask-to-Research bridge
+ export/integrity
+ concurrency/recovery
+ full validation
```

Adjust boundaries based on repository dependencies.

---

# 142. CHECKPOINT RULE

Before each checkpoint commit:

```text
coherent capability complete
→ focused tests pass
→ relevant regression tests pass
→ diff check passes
→ commit
```

Do not create microcommits.

Do not push.

---

# 143. INTERRUPTION-RESILIENT EXECUTION

If an agent session stops before Phase 26 completion:

```text
inspect current HEAD
inspect checkpoint commits
inspect worktree/index
preserve legitimate work
identify first incomplete requirement
rerun affected focused tests
resume
```

Do not assume partial work was rolled back.

Do not automatically reset.

---

# 144. REQUIRED ENTITY TEST COVERAGE

Verify:

```text
Entity creation

canonical normalization

alias creation

acronym alias

duplicate alias convergence

Subject/Entity compatibility

ArticleAnalysis candidate handling

deterministic existing-Entity resolution

ambiguous candidate remains unresolved

EntityMention persistence

EntityMention != EvidenceSpan

Claim-Entity association

Question-Entity association

Story-Entity provenance where implemented

Watch/Entity compatibility where implemented

manual correction

Entity merge lineage where implemented

export/integrity
```

---

# 145. REQUIRED TAG TEST COVERAGE

Verify:

```text
Tag creation

Tag normalization

duplicate Tag convergence

manual Tag assignment

deterministic Tagging

provider-assisted Tagging where implemented

Tag result limits

invalid suggestion leaves canonical state unchanged

Tag origin/provenance

historical backfill

backfill replay

no historical evidence mutation
```

---

# 146. REQUIRED WORKBENCH TEST COVERAGE

Verify:

```text
Entity search

alias search

acronym search

Claim search

Evidence search where supported

Document search

Story search

Research Question search

Source search

Tag filtering

date filtering

object-type filtering

Question status vs assessment filters

bounded pagination

ranking behavior

match explanation

pivot navigation
```

---

# 147. REQUIRED SHARED RETRIEVAL TESTS

Verify Workbench and Ask retrieve consistent canonical objects for equivalent scopes.

Example:

```text
Workbench:
Entity AARO
→ Claim C1
```

and:

```text
Ask:
What does Newsroom know about AARO?
→ retrieval packet includes C1
```

where C1 is the highest-ranked relevant Claim under the shared rules.

Do not require identical ranking where different intent justifies different weighting.

---

# 148. ASK RETRIEVAL TESTS

Verify:

```text
exact Entity question

alias Entity question

Claim evidence question

Story what-changed question

Research Question assessment question

Research Question gap question

Source question

date-scoped question

contradiction question

insufficient-evidence question

ambiguous Entity handling

bounded context
```

---

# 149. ASK GROUNDING RELEASE TEST A

Scenario:

```text
retrieval packet does not support assertion X
```

and generated synthesis proposes X.

Expected:

```text
X omitted
or
answer validation fails safely
```

Canonical state remains unchanged.

---

# 150. ASK GROUNDING RELEASE TEST B

Scenario:

```text
answer cites a real canonical ID
that was not part of the retrieval packet
```

Expected:

```text
citation rejected
```

---

# 151. ASK GROUNDING RELEASE TEST C

Scenario:

```text
retrieved Document contains text
that resembles application directives
```

Expected:

```text
text remains content data
configured application behavior remains unchanged
```

---

# 152. ASK SOURCE-PRECISION RELEASE TEST

Scenario:

```text
three supporting Documents
all from Source S1
```

Expected:

```text
Ask describes one Source record
with multiple Documents
```

not multiple independent confirmations.

---

# 153. ASK CONTRADICTION RELEASE TEST

Scenario:

```text
Claim A supports proposition X

Claim B contradicts proposition X
```

Expected:

```text
answer acknowledges both
cites both
does not hide the conflict
```

---

# 154. ASK INSUFFICIENT-EVIDENCE RELEASE TEST

Scenario:

```text
no qualifying Claim/Evidence supports requested assertion
```

Expected:

```text
Ask states Newsroom lacks sufficient evidence
```

and may identify:

```text
open Question
Gap
research option
```

where applicable.

---

# 155. ASK PROVIDER FAILURE TEST

If synthesis provider is unavailable:

```text
shared retrieval still executes
```

and:

```text
deterministic evidence summary is returned
```

where feasible.

No canonical state changes.

---

# 156. ASK HISTORY TEST

If Ask history is persisted:

```text
previous generated answer
```

must not become evidence or a Claim.

A follow-up must rerun canonical retrieval.

---

# 157. ASK-TO-RESEARCH TEST

Scenario:

```text
Ask cannot answer from current evidence
```

User explicitly selects:

```text
Research this
```

Expected:

```text
existing Phase 25 Research Question/Gap/Task service
is used
```

No parallel research architecture is introduced.

---

# 158. VECTOR DECISION TEST

Before adding embeddings:

```text
run structured retrieval benchmark

document retrieval failures

attempt reasonable SQL/FTS/alias/index improvements

rerun benchmark
```

Only then make the vector decision.

---

# 159. VECTOR DECISION REPORT

Final report must state exactly:

```text
vector retrieval introduced: yes
```

or:

```text
vector retrieval introduced: no
```

and explain why.

---

# 160. ENTITY/TAG BACKFILL TEST

If historical backfill exists:

```text
existing ArticleAnalysis corpus
→ bounded backfill
→ Entity/Tag metadata
```

Replay must converge.

Verify exact trusted historical evidence remains unchanged.

---

# 161. END-TO-END KNOWLEDGE TEST

Create a controlled production-composition scenario:

```text
Source
→ Document
→ ArticleAnalysis
→ EvidenceSpan
→ Claim
→ Entity resolution
→ Tagging
→ Story
→ Research Question
```

Then:

```text
Workbench search
→ Entity
→ Claim
→ Evidence
→ Document
→ Source
```

using real services.

---

# 162. END-TO-END ASK TEST

With persisted controlled evidence:

```text
user asks factual question
        ↓
interpretation
        ↓
shared retrieval
        ↓
Claim + Evidence
        ↓
bounded synthesis
        ↓
citation validation
        ↓
answer
```

Every factual citation must resolve to exact persisted context.

---

# 163. END-TO-END CONTRADICTION TEST

Controlled corpus:

```text
Claim A supports X
Claim B contradicts X
```

Ask:

```text
Is X supported?
```

Expected:

```text
both evidence positions shown
both cited
uncertainty/disagreement preserved
```

---

# 164. END-TO-END RESEARCH QUESTION TEST

Controlled Research Question:

```text
human status = open
assessment_state = partially answered
supporting Claim exists
Evidence Gap remains open
```

Ask:

```text
What do we know about this Question?
```

Expected:

```text
human status described correctly
assessment described correctly
supporting evidence shown
open Gap shown
```

No conflation.

---

# 165. REPLAY / RECOVERY

Where durable Jobs are introduced for:

```text
Entity backfill
Tag backfill
derived search indexing
```

verify interruption recovery and replay.

Ask itself should remain a normal request flow unless the actual architecture requires durability.

Do not make Ask unnecessarily job-heavy.

---

# 166. LOGICAL EXPORT TEST

Export a representative Phase 26 knowledge set containing:

```text
Entity
Alias
EntityMention
Claim-Entity relationship
Research Question-Entity relationship
Tag
Tag assignment
```

Reconstruct relationships from export.

If Ask history persists, reconstruct exact citations.

---

# 167. MIGRATION VALIDATION

If schema changes:

```text
fresh schema creation

completed Phase 25
→ Phase 26 upgrade

migration registration

migration repeat/idempotency

foreign-key validation

Research Question compatibility

Evidence Gap compatibility

Research Task compatibility

Watch compatibility

Story compatibility
```

---

# 168. REQUIRED PRODUCT CAPABILITIES MAY NOT BE SILENTLY DEFERRED

Phase 26 must finish with:

```text
canonical Entity model

Entity aliases/acronyms

conservative Entity resolution

ambiguous resolution handling

Entity mentions

Claim-Entity relationships

Research Question-Entity integration

Story/Watch Entity integration where useful

Smart Tags

Tag provenance

bounded historical Entity/Tag backfill if required

shared typed retrieval substrate

Workbench heterogeneous search

filters

ranking/match explanation

pivot navigation

Entity detail experience

evidence-grounded Ask

structured interpretation

bounded retrieval packet

closed-world factual synthesis

citation validation

contradiction handling

insufficient-evidence behavior

source-count precision

provider fallback

Ask-to-Research bridge

retrieval benchmark

explicit vector decision

functional APIs

functional frontend

logical export

integrity checking

concurrency/idempotency

controlled end-to-end Workbench test

controlled end-to-end Ask test
```

---

# 169. OUT OF SCOPE

## Phase 27 — Advanced Story Intelligence

Do not implement:

```text
Story merge
Story split
Claim reassignment
Claim unassignment
duplicate Story repair
advanced Story correction
```

## Phase 28 — Intelligence Experience + Source Intelligence

Do not implement:

```text
advanced Source dependency
Source reliability intelligence
major intelligence dashboards
expanded Alert delivery channels
```

## Phase 29 — Production Hardening

Do not perform:

```text
repository-wide hardening
large-scale performance overhaul
broad deployment redesign
full cost optimization program
```

## Phase 30 — Completion

Do not perform:

```text
full UX redesign
large dogfood campaign
release audit
```

---

# 170. SUGGESTED IMPLEMENTATION ORDER

Codex may adjust this after the repository audit.

A reasonable sequence:

```text
1. Audit Topic / Subject / Entity / Tag / Search architecture

2. Define final knowledge-domain boundaries

3. Implement canonical Entity model

4. Implement aliases and conservative resolution

5. Integrate ArticleAnalysis

6. Add EntityMention

7. Add Claim/Question/Story relationships

8. Implement Smart Tags

9. Add bounded historical metadata backfill if necessary

10. Generalize existing SQL/FTS into shared typed retrieval

11. Upgrade Workbench heterogeneous search

12. Add filters/ranking/explanations

13. Build Entity/knowledge detail surfaces

14. Run structured retrieval benchmark

15. Implement Ask interpretation contract

16. Implement Ask retrieval packet builder

17. Implement synthesis and deterministic fallback

18. Add citation validation and grounding behavior

19. Add contradictions/insufficient-evidence handling

20. Implement Ask-to-Research bridge

21. Decide vector/no-vector based on benchmark

22. Add/complete APIs

23. Add/complete frontend

24. Extend export/integrity

25. Add concurrency/replay/recovery tests

26. Run controlled Workbench/Ask E2E

27. Run complete validation
```

---

# 171. VALIDATION

Run focused Phase 26 suites continuously.

Then relevant regression suites covering:

```text
ArticleAnalysis
Evidence
Claims
Stories
Reports
Research Questions
Evidence Gaps
Research Tasks
Watches
Sources
Workbench
Search / FTS
Jobs
runtime
AIRouter
provider budgets
API
frontend
logical export
integrity
migrations
```

Run the complete configured backend suite.

Use the actual repository test command.

Based on the current project that may be equivalent to:

```bash
poetry run pytest -q
```

but verify current configuration instead of assuming.

Compile:

```bash
python -m compileall -q newsroom tests
```

Frontend:

```bash
pnpm typecheck
pnpm build
```

from the correct frontend directory where those remain the configured commands.

Diff hygiene:

```bash
git diff --check
```

Before commits:

```bash
git diff --cached --check
```

Run migration/FK validation if schema changes.

Do not report unavailable aliases such as formatter/lint commands as passed.

Do not report any validation that was not actually executed.

---

# 172. PHASE 26 ACCEPTANCE GATE

## Knowledge Architecture

```text
[PASS] Topic responsibility remains explicit

[PASS] Subject responsibility remains explicit

[PASS] Entity responsibility is explicit

[PASS] Tag responsibility is explicit

[PASS] no unnecessary duplicate knowledge abstractions were introduced
```

## Entity Intelligence

```text
[PASS] canonical Entities exist

[PASS] aliases are first-class

[PASS] acronyms/expansions work

[PASS] Entity resolution is conservative

[PASS] ambiguous candidates are not forcibly merged

[PASS] EntityMention is distinct from EvidenceSpan

[PASS] Claims relate to Entities

[PASS] Research Questions relate to Entities where useful

[PASS] Entity provenance is inspectable

[PASS] historical Question assessment is not rewritten

[PASS] Entity merge lineage is preserved where implemented
```

## Smart Tagging

```text
[PASS] Tags are distinct from Entities

[PASS] duplicate Tags converge

[PASS] Tag assignments preserve origin

[PASS] deterministic tagging works

[PASS] provider-assisted tagging is bounded where implemented

[PASS] Tag proliferation is bounded

[PASS] historical backfill is bounded/idempotent where required

[PASS] Tag backfill does not rewrite trusted evidence
```

## Shared Retrieval

```text
[PASS] existing SQL/FTS search is reused/generalized

[PASS] typed retrieval exists

[PASS] retrieval collections are bounded

[PASS] Workbench and Ask share retrieval infrastructure where practical

[PASS] canonical relationships are preferred over raw text matches

[PASS] ranking is explainable

[PASS] match explanations are available where useful
```

## Workbench

```text
[PASS] heterogeneous search works

[PASS] Entity search works

[PASS] alias/acronym search works

[PASS] Claim search works

[PASS] Story search works

[PASS] Research Question search works

[PASS] Source search works

[PASS] Tag filtering works

[PASS] object/date filters work

[PASS] Question human status and assessment filters remain distinct

[PASS] pagination is bounded

[PASS] pivot navigation reaches exact provenance
```

## Ask

```text
[PASS] Ask defaults to persisted Newsroom corpus

[PASS] Ask does not silently invoke external research

[PASS] structured interpretation works

[PASS] retrieval is bounded

[PASS] factual answers prefer Claims/Evidence

[PASS] retrieval packets use stable canonical IDs

[PASS] citations reference exact retrieved records

[PASS] citations are validated

[PASS] unsupported factual additions are omitted/rejected

[PASS] inference is distinguishable where applicable

[PASS] contradictory evidence is represented

[PASS] insufficient evidence is represented

[PASS] Source-count terminology is precise

[PASS] Question status vs assessment_state remain distinct

[PASS] provider fallback remains useful

[PASS] Ask history does not become evidence

[PASS] follow-up requests rerun canonical retrieval

[PASS] Ask-to-Research uses Phase 25 services
```

## Vector Decision

```text
[PASS] structured retrieval benchmark exists

[PASS] SQL/FTS/alias improvements were evaluated first

[PASS] vector decision is explicitly documented

[PASS] vector infrastructure is absent unless benchmark justified it

[PASS] any vector index remains derivative/rebuildable
```

## Product Surface

```text
[PASS] Entity APIs are bounded

[PASS] Tag APIs are bounded

[PASS] Workbench API is bounded

[PASS] Ask API is bounded

[PASS] Entity frontend exists

[PASS] Workbench v2 is functional

[PASS] Ask UI is functional

[PASS] citations navigate to evidence

[PASS] scoped Ask works

[PASS] insufficient-evidence flow can reach Research where appropriate
```

## Auditability

```text
[PASS] Entities are exportable

[PASS] aliases are exportable

[PASS] Entity relationships are exportable

[PASS] Tags/assignments are exportable

[PASS] Ask citations are exportable if history is persisted

[PASS] Entity → Claim → Evidence → Source reconstructs

[PASS] Entity → Question → Gap/Task reconstructs where present

[PASS] integrity covers critical structural relationships
```

## Reliability

```text
[PASS] duplicate Entity identities converge where deterministic identity applies

[PASS] aliases converge

[PASS] mentions converge

[PASS] Tags converge

[PASS] backfill replay converges

[PASS] provider failure leaves canonical knowledge intact

[PASS] Workbench failure produces no domain mutation

[PASS] Ask failure produces no evidence mutation
```

## Compatibility

```text
[PASS] Phase 23 automatic evidence/Story/Report/Alert chain remains intact

[PASS] Phase 24 Watch/Monitor architecture remains intact

[PASS] Phase 25 Question/Gap/Research Task architecture remains intact

[PASS] no alternate evidence path exists
```

## Repository

```text
[PASS] focused Phase 26 tests pass

[PASS] relevant Phase 25 regressions pass

[PASS] relevant Phase 24 regressions pass

[PASS] relevant Phase 23 regressions pass

[PASS] complete backend suite passes

[PASS] compileall passes

[PASS] frontend typecheck passes

[PASS] frontend production build passes

[PASS] migration/FK tests pass where applicable

[PASS] git diff --check passes

[PASS] staged diff checks pass before commits

[PASS] Phase 26 work is committed

[PASS] tracked worktree is clean
```

---

# 173. FINAL USER EXPERIENCE GATE

Do not declare Phase 26 complete unless this workflow is supported:

```text
User searches:

AARO
```

Newsroom returns:

```text
canonical Entity
aliases
Claims
Evidence
Documents
Stories
Research Questions
Tags
Sources
```

The user opens a Claim.

The Claim leads to:

```text
EvidenceSpan
→ Document
→ Source
```

The user returns to the Entity.

They ask:

```text
What evidence supports claims
that AARO investigated recovered material?
```

Newsroom:

```text
interprets the request

identifies the Entity

retrieves relevant trusted Claims

retrieves exact EvidenceSpans

retrieves Source provenance

constructs a bounded retrieval packet

synthesizes an answer

validates every citation
```

If conflicting evidence exists:

```text
both sides are represented
```

If Newsroom lacks sufficient evidence:

```text
it says so
```

and, where appropriate:

```text
shows an existing Research Question/Gap
or offers an explicit Research action
```

The user can open answer citations and reach the persisted evidence.

Ask does not silently search outside Newsroom.

A follow-up question uses conversational context but reruns retrieval against current canonical state.

That is Phase 26.

---

# 174. FINAL RESPONSE FORMAT

## 1. Verdict

Return exactly one:

```text
PHASE 26 COMPLETE AND COMMITTED — PHASE 27 READY
```

or:

```text
PHASE 26 CORRECTED AND COMMITTED — PHASE 27 READY
```

or:

```text
PHASE 26 INCOMPLETE — PHASE 27 BLOCKED
```

---

## 2. Codebase Review and Architecture Decision

Explain:

```text
Topic
Subject
Entity
Tag
existing FTS
Phase 25 retrieval
```

and the final boundaries chosen.

List material changes to this plan based on repository reality.

---

## 3. Entity Intelligence

Report:

```text
Entity schema
Entity types
aliases
acronyms
candidate handling
resolution rules
mentions
Claim relationships
Question relationships
Story/Watch integration
manual correction/merge
```

---

## 4. Smart Tagging

Report:

```text
Tag model
Tag categories
Tag assignments
origin
deterministic behavior
provider behavior
limits
backfill
```

---

## 5. Shared Retrieval Architecture

Describe:

```text
existing SQL/FTS reused
typed retrieval
ranking
filters
pagination
match explanations
```

Explain how Workbench and Ask share it.

---

## 6. Workbench v2

Report:

```text
searchable objects
filters
facets where implemented
ranking
match reasons
pivot navigation
Entity detail
Claim/Evidence navigation
Research Question integration
```

---

## 7. Ask Architecture

Describe:

```text
question
→ interpretation
→ retrieval plan
→ retrieval packet
→ synthesis
→ citation validation
→ answer
```

---

## 8. Ask Grounding

Report:

```text
citation contract
citation validation
unsupported-assertion behavior
inference labeling
contradiction handling
insufficient-evidence behavior
Source-count semantics
Question lifecycle/assessment semantics
```

---

## 9. Ask-to-Research

Explain how insufficient evidence can transition into explicit Phase 25 Research behavior.

Confirm normal Ask does not silently conduct external research.

---

## 10. Vector Decision

State exactly:

```text
vector retrieval introduced: yes/no
```

Then report:

```text
benchmark results
retrieval failures
SQL/FTS improvements attempted
rationale
```

If introduced, explain scope/rebuildability.

---

## 11. Provider / Cost Behavior

Report:

```text
Entity provider use
Tag provider use
Ask interpretation
Ask synthesis
AIRouter
budgets
context bounds
deterministic fallbacks
```

---

## 12. External Input and Provider Boundary

Summarize reuse of existing:

```text
input validation
provider validation
request controls
authorization
privacy
domain services
budgets
```

Keep the report outcome-focused.

---

## 13. API

List new/changed:

```text
Entity routes
Tag routes
Workbench routes
Ask routes
Ask history routes where implemented
```

Report collection bounds.

---

## 14. Frontend

Describe:

```text
Workbench v2
Entity experience
Tag experience
Ask experience
citations
follow-ups
scoped Ask
Ask-to-Research
```

---

## 15. Migration

Report:

```text
migration required: yes/no
starting schema version
ending schema version
```

Include:

```text
fresh create
Phase 25 upgrade
repeat/idempotency
FK validation
compatibility
```

---

## 16. Backfill

If implemented, report:

```text
Job types
bounds
batch sizes
provider behavior
replay
recovery
historical immutability
```

---

## 17. Export / Integrity

Report:

```text
Entity export
aliases
mentions
Entity relationships
Tags
Tag assignments
Ask history/citations if persisted
reconstruction
integrity checks
```

---

## 18. Concurrency / Idempotency / Recovery

Explain:

```text
Entity identity
aliases
mentions
Tags
backfills
Ask persistence where applicable
```

---

## 19. Search Benchmark

Report actual benchmark results.

Include:

```text
exact Entity
alias
acronym
Claim
Story
Question
evidence
contradiction
what-changed
date-filtered retrieval
```

---

## 20. Ask Evaluation

Report controlled results for:

```text
factual evidence
contradiction
Story changes
Entity question
Source question
Research Question
insufficient evidence
citation validity
provider fallback
Ask-to-Research
```

---

## 21. Tests

List focused Phase 26 tests actually added.

---

## 22. Validation

List every actual command and result.

Do not claim unexecuted checks.

---

## 23. Files Changed

Group by:

```text
domain/schema
Entities
Tags
retrieval/search
Workbench
Ask
providers
Jobs/backfill
API
frontend
operations/integrity
tests
documentation
```

---

## 24. Commits

Report:

```text
checkpoint commit SHAs
final commit SHA
subjects
scope
```

Do not push.

---

## 25. Repository State

Report:

```text
branch
current HEAD
origin relationship
schema
tracked worktree
index
preserved unrelated untracked files
whether push occurred
```

Do not compare to a predicted starting SHA.

---

## 26. Deferred Work

### Phase 27

```text
Story merge
Story split
Claim reassignment
Claim unassignment
duplicate Story correction
richer Story evolution/correction
```

### Phase 28

```text
intelligence dashboards
advanced Source intelligence
Source dependencies
Source reliability
expanded Alert delivery
```

### Phase 29

```text
production hardening
performance
operations
cost optimization
```

### Phase 30

```text
final UX
multi-domain dogfood
release audit
```

Do not classify incomplete Phase 26 requirements as deferred.

---

## 27. Phase 27 Readiness

State whether Newsroom now has:

```text
trusted evidence
Claims
Stories
Research Questions
Evidence Gaps
Research Tasks
canonical Entities
Tags
shared knowledge retrieval
Workbench
evidence-grounded Ask

→ sufficient substrate for advanced Story intelligence
```

Do not begin Phase 27.