# PHASE 28.75 — ACCEPTANCE CLOSURE AND SEMANTIC CORRECTION

## Phase 28.5 Closure: Migration Safety, Attention Semantics, Counterfactual Correctness, Research Loop Protection, Evaluation Honesty, Benchmark Enforcement, and Commit Hygiene

---

# 0. PHASE STATUS AND AUTHORITY

Phase 28 is complete and committed.

Phase 28.5 has been implemented and independently reviewed. Its architectural direction is accepted, but **Phase 28.5 is not yet accepted** because the Phase 28 → Phase 28.5 delta review found targeted correctness and validation defects.

Phase 28.75 is the next permitted work.

**Phase 29 is blocked until Phase 28.75 is accepted.**

Phase 28.75 is a closure pass, not a new product phase.

Active planning authority:

```text
G:\Projects\Newsroom -v2\plan\phases-v2\
```

Primary implementation input:

```text
plan/phases-v2/Phase 28.5.md
```

Also inspect:

```text
plan/phases-v2/Phase 27.md
plan/phases-v2/Phase 28.md
plan/phases-v2/Phase 29.md
plan/phases-v2/Strategic Architecture Review.md
plan/phases-v2/Final Architecture Reconciliation Memo.md
docs/reviews/PHASE_29_PRE_IMPLEMENTATION_ADVERSARIAL_REVIEW.md
```

The live repository is always implementation authority.

Do not assume a starting HEAD, schema version, test count, table count, or worktree state. Re-read them before editing.

The latest reviewed Phase 28.5 snapshot reported approximately:

```text
schema:                 34
base tables:            111
logical-export tables:   84
runtime worker handlers:  9
Simple nav items:         5
Advanced nav items:       9
tests collected:        778
eval corpus cases:       38
```

Re-verify all of those.

The Phase 28.5 implementation was not committed. Preserve all unrelated tracked and untracked work. Do not reset, rewrite history, clean the tree, or push.

---

# 1. WHY PHASE 28.75 EXISTS

Phase 28.5 successfully removed most of the unsafe Phase 28 derived layer:

```text
Phase 28 epistemic Coverage removed
Evidence Family persistence removed
Fragility scalar/persistence removed
Blind Spot lifecycle removed
mutable Attention queue removed
four ceremonial Phase 28 Jobs removed
one canonical Research Gap authority established
Simple mode reduced to five primary surfaces
known dependency groups computed on demand
```

That architectural subtraction is correct and must not be reversed.

However, independent review of the Phase 28.5 snapshot found a smaller set of closure defects:

```text
1. schema-32 -> Phase-28.5 migration can silently discard human Attention feedback
2. reviewed Blind Spot decisions can also be discarded on upgrade
3. Snooze is permanent suppression rather than temporary suppression
4. Home Attention and Alert acknowledgement still have conflicting semantics
5. Counterfactual document/source anchors exclude only exact rows, not the
   current dependency component the reconciled design promised
6. logical export omits Research Gap -> originating Hypothesis provenance
7. Research duplicate-query protection does not span later Tasks/attempts,
   and safe contrary-evidence pursuit is incomplete
8. the Lite harness does not yet enforce several fields the frozen contract claims
9. new evaluation cases are partly narrative fixtures rather than machine-scored
   semantic regressions
10. the new corpus contains fixture-quality defects, including duplicate JSON keys
    and a silent-edit content-hash inconsistency
11. CI could not be verified from the supplied Phase 28.5 archive
12. the entire Phase 28.5 implementation remains uncommitted
```

Phase 28.75 closes those defects.

It must not re-open the broad architectural decisions already settled in Phase 28.5.

---

# 2. FINAL PHASE OBJECTIVE

> **Make the Phase 28.5 architecture safe to accept, safe to migrate to, semantically consistent in the UI, and honest in its evaluation claims.**

Phase 28.75 is complete when:

```text
no human decision is silently lost during a legitimate Phase-28 -> current upgrade

Snooze expires

an Alert has one coherent acknowledgement/attention meaning

Counterfactual exclusion follows current document_lineage dependency components

Hypothesis-origin Research Gap provenance survives logical reconstruction

Research does not repeatedly issue the same normalized query across later Tasks
without an explicit cooldown/retry reason

Newsroom never claims to have run a contrary-evidence strategy when no safe
strategy existed

the Lite harness actually binds the frozen comparison contract

every newly named semantic eval case has a machine-evaluated assertion that tests
the behavior its title claims

eval corpus JSON cannot silently contain duplicate keys

content hashes in eval fixtures are internally consistent

CI exists in the live repository and is included in the committed source state

the Phase 28.5 + 28.75 implementation is committed in coherent commits

dogfood can start immediately after acceptance without known code blockers
```

---

# 3. SCOPE FENCE

Do **not** use this correction pass to add new product ambitions.

Do not implement:

```text
historical Ask
knowledge-time architecture
Shadow Reprocessing
general Belief Diff
new Coverage
new Blind Spot subsystem
new Evidence Family cache
new Fragility score
new Attention lifecycle
provider-generated Hypotheses
onboarding
backfill-on-Watch-create
diff-first Reports
external notifications
packaging/installer
new Source connectors
tag authority merge
Entity merge workflow
vector search
new database
projection framework
event bus
generic audit/event envelope
```

Freed scope stays free.

This phase exists to close Phase 28.5, not to begin Phase 29 early.

---

# 4. PROTECTED PHASE 28.5 DECISIONS

Do not reverse these unless live code proves the plan premise false:

```text
Phase 28 epistemic Coverage stays deleted

Blind Spot runtime stays deleted

Evidence Families stay deleted

known dependency groups stay on-demand from document_lineage

Fragility scalar stays deleted

Counterfactual stays on-demand and non-mutating

Attention current ranking stays computed on read

only Attention human decisions persist

one canonical Research Gap authority remains research_question_gaps

Hypotheses remain framing/analysis, not Claims and not research executors

Simple mode remains a small cockpit

provenance deep links remain reachable in Simple mode

SQLite / SQL / FTS / JobService remain the platform
```

The desired result is still:

> **Less Newsroom, with the proven parts stronger.**

---

# 5. PHASE STRUCTURE

Five checkpoint stages:

```text
28.75.0  UPGRADE AND HUMAN-DECISION SAFETY
         repair migration semantics before anything else

28.75.1  ATTENTION / ALERT / COUNTERFACTUAL SEMANTICS
         make visible behavior match the design

28.75.2  RESEARCH AND LOGICAL-EXPORT CORRECTNESS
         close query-loop and reconstruction defects

28.75.3  EVALUATION / LITE / CI HONESTY
         make validation claims measurable and reproducible

28.75.4  FINAL VALIDATION, COMMIT, AND DOGFOOD READINESS
         prove the closure and create coherent repository history
```

**28.75.0 and 28.75.1 are a hard gate.**

Do not proceed to validation-readiness cleanup while upgrade safety or user-facing semantics remain wrong.

---

# 6. STAGE 28.75.0 — UPGRADE AND HUMAN-DECISION SAFETY

## Objective

A legitimate Phase 28 database must not lose Class B human decisions when upgraded to the accepted post-28.5 schema.

---

# 7. 28.75.0A — REPAIR ATTENTION FEEDBACK MIGRATION

## Verified defect

The reviewed Phase 28.5 migration path drops:

```text
attention_feedback
attention_items
```

and creates:

```text
attention_decisions
```

without migrating existing human Attention feedback.

A schema-32 adversarial upgrade probe confirmed that legacy Attention feedback disappeared while the upgrade itself succeeded.

That violates:

```text
no human decision is silently lost
```

## Required outcome

Before the legacy tables are dropped, migrate every user-authored Attention feedback/decision that can be semantically preserved into the new append-only Attention decision history.

Preserve at minimum where available:

```text
object_type
object_id
reason_code
legacy material identity/fingerprint
actor
created_at
original feedback/action meaning
note or migration provenance when the old action has no exact new equivalent
```

Do not silently reinterpret an ambiguous historical action.

If an old action maps exactly to:

```text
seen
not_useful
```

use the current action.

If it does not map exactly, preserve the original meaning in migration metadata/note rather than inventing certainty.

## Migration-history rule

Phase 28.5 migrations 33–34 were not accepted as release history and the Phase 28.5 implementation was not committed.

Inspect the live migration registry and actual database usage before deciding whether to:

```text
repair the unaccepted migration in place
and/or
add a new forward migration for already-created schema-34 development DBs
```

Binding acceptance behavior matters more than migration-number aesthetics.

Do **not** rewrite any migration that predates the unaccepted Phase 28.5 work.

## Required upgrade probes

Create a true schema-32 temporary database using Phase 28 code or an equivalent historical migration fixture.

Seed:

```text
Attention item
at least one human feedback row
at least one feedback value whose mapping is exact
at least one legacy value whose meaning requires preserved provenance if available
```

Upgrade to latest.

Assert:

```text
the human decision is still present in durable history
actor/timestamp are preserved
object/reason identity is preserved
no legacy decision disappears silently
foreign_key_check passes
integrity passes
```

---

# 8. 28.75.0B — REVIEWED BLIND SPOT DECISION PRESERVATION

## Verified defect

Phase 28.5 correctly deletes the Blind Spot product lifecycle because Coverage was deleted.

However, a schema-32 upgrade probe showed reviewed Blind Spot rows can be dropped along with the subsystem.

The runtime must remain deleted.

The **human decision** must not be silently discarded.

## Required decision procedure

Before choosing a migration mechanism:

```text
inspect the actual schema-32 Blind Spot columns
inspect existing human review fields/statuses
inspect whether a semantically correct existing Class B history destination exists
```

Preference order:

```text
1. migrate the review into an existing semantically correct Class B history
2. if no correct destination exists, preserve it in the smallest narrow historical
   audit representation that does NOT resurrect Blind Spot runtime
3. never overload an unrelated domain object merely to avoid one historical record
4. never silently delete the review
```

A narrow historical preservation structure, if truly necessary, is acceptable even if it slightly changes the Phase 28.5 table-count target. It must be:

```text
read-only after migration
not a product lifecycle
not an Attention candidate source
not a Research executor
clearly historical
logically exported as Class B history
```

Do not make a schema migration create arbitrary filesystem sidecar files.

## Acceptance

Upgrade a schema-32 fixture containing:

```text
reviewed/dismissed Blind Spot
reviewer
review timestamp
reason/rationale if available
```

and assert that the human review remains recoverable after the Blind Spot runtime tables are gone.

---

# 9. 28.75.0C — SCHEMA-34 COMPATIBILITY

Some development/test databases may already be schema 34.

The correction must support:

```text
fresh -> latest
schema 32 -> latest
schema 34 -> latest
```

A schema-34 database cannot recover human decisions already discarded by an older local migration unless an external backup still has them.

Do not fabricate recovery.

For any inspected schema-34 user database:

```text
state whether recoverable legacy data exists
state whether a pre-migration backup exists
state exactly what cannot be reconstructed if not
```

The accepted migration path must prevent the loss for future schema-32 upgrades.

---

# 10. STAGE 28.75.1 — ATTENTION / ALERT / COUNTERFACTUAL SEMANTICS

## Objective

User-facing actions and analytical controls must do exactly what their labels/design contract say.

---

# 11. 28.75.1A — SNOOZE MUST EXPIRE

## Verified defect

The current `attention_decisions` implementation has no expiry field and suppresses every matching historical decision indefinitely.

Therefore:

```text
Seen       suppresses
Not useful suppresses
Snooze     also suppresses forever
```

A permanent suppression labeled Snooze is false UI semantics.

## Required model

Attention decisions remain append-only.

Add the minimum expiry semantics needed for Snooze, conceptually:

```text
snoozed_until
```

or the smallest repository-native equivalent.

Decision behavior:

```text
Seen
    suppress the same material basis until that basis changes

Not useful
    suppress the same material basis and contribute to usefulness telemetry

Snooze
    suppress the same material basis only until the explicit expiry time
```

An expired Snooze must not suppress the candidate.

A newer decision for the same identity supersedes an older one for visibility evaluation, while history remains append-only.

Do not add a mutable Attention state machine.

## Acceptance

Using a deterministic clock/test seam:

```text
candidate visible
Snooze 7d
candidate hidden before expiry
candidate visible after expiry if underlying condition still exists
new material basis surfaces even before old basis expiry
Seen remains suppressed for the same basis
```

---

# 12. 28.75.1B — ALERT ACKNOWLEDGEMENT AND HOME ATTENTION MUST AGREE

## Verified defect

An unread Alert can appear:

```text
as an Attention candidate
and
again in a raw "Needs your attention" Alert section
```

Marking the Attention instance Seen can hide the first representation while leaving the same Alert unread in the second representation.

That recreates the three-inbox problem Phase 28.5 was supposed to remove.

## Required product relationship

Keep:

```text
Attention = ranking logic
Home      = the normal "look here" surface
Alert     = high-threshold interruption/history/delivery object
```

Home must not show the same Alert twice through two independent current-state surfaces.

Preferred implementation:

```text
remove the duplicate raw Alert "needs attention" block from Home

Alert-backed Attention action:
    Seen / Not useful -> acknowledge the Alert and append the Attention decision
    Snooze            -> do not acknowledge; temporarily suppress on Home

Advanced Alerts may remain an audit/history/configuration view
```

If the live UI suggests an even smaller equivalent, use it.

Do not create an Alert/Attention synchronization job.

## Acceptance

```text
one unread Alert appears once on Home
Seen removes it from current Home attention and marks the Alert acknowledged
Not useful removes it and records usefulness feedback
Snooze hides it temporarily without falsely acknowledging it
the same Alert does not remain in a second competing Home block
```

---

# 13. 28.75.1C — COUNTERFACTUAL ANCHORS MUST RESOLVE CURRENT DEPENDENCY COMPONENTS

## Verified defect

Phase 28.5 changed Counterfactual inputs to canonical anchors:

```text
exclude_document_ids
exclude_source_ids
```

but the implementation excludes only the exact documents/sources.

The reconciled design promised:

```text
canonical anchor
-> resolve CURRENT document_lineage connected component
-> exclude that dependency component
```

Without component expansion, selecting one derivative document can leave the same underlying evidence alive through another document in the same dependency group.

## Required behavior

For each `exclude_document_id`:

```text
resolve the current dependency group containing that Document
exclude every Document in that group
```

For each `exclude_source_id`:

```text
find the Source's relevant supporting Documents
resolve the current dependency group(s) containing those Documents
exclude the union of those groups
```

Use current `document_lineage` at execution time.

Do not persist group IDs.

Return enough resolved information for the user/test to understand what was removed, such as:

```text
input anchors
resolved excluded document IDs
resolved dependency-group membership/count
surviving/dropped Claims
```

Preserve the non-mutation invariant.

## Acceptance probe

Create:

```text
Document A
Document B syndicated_from A
both support Claim C
```

Exclude B.

The counterfactual must exclude both A and B's current dependency component.

If C has no support outside that component, C must drop from the counterfactual.

Canonical Claim state must remain unchanged.

---

# 14. 28.75.1D — MATERIAL-BASIS ATTENTION IDENTITY REGRESSION

Preserve the Phase 28.5 identity invariant:

```text
(object_type, object_id, reason_code, basis_fingerprint)
```

Add/retain a regression proving:

```text
same object + same reason + same material cause
    may remain suppressed

same object + same reason + NEW canonical material cause
    surfaces again
```

Do not base `basis_fingerprint` only on:

```text
story_id + broad event_type
```

if the domain has a more precise canonical cause identity.

No explanation prose, ranking score, or timestamp-only fingerprinting.

---

# 15. STAGE 28.75.2 — RESEARCH AND LOGICAL-EXPORT CORRECTNESS

## Objective

Research must not loop through the same work indefinitely, and logical reconstruction must preserve the new canonical provenance introduced in Phase 28.5.

---

# 16. 28.75.2A — PRESERVE `origin_hypothesis_id` THROUGH LOGICAL EXPORT/IMPORT

## Verified defect

Phase 28.5 correctly moved Hypothesis-originated research work into canonical:

```text
research_question_gaps
```

with provenance equivalent to:

```text
origin_hypothesis_id
```

But the logical export allow-list omits that provenance field.

A round-trip probe showed:

```text
before export:
origin_hypothesis_id = H

after import:
origin_hypothesis_id = NULL

import still reports verified
```

## Required correction

Include the originating-Hypothesis provenance in logical export/import.

Add a round-trip regression containing:

```text
Research Question
Hypothesis
canonical discriminating Research Gap originated from that Hypothesis
```

Assert after fresh import:

```text
same Gap ID/semantic record
same origin_hypothesis_id
same Question relationship
same human/history authority
```

Do not expand this stage into the complete Phase 29 Class A/B/C rebuild program.

Fix the demonstrated loss.

---

# 17. 28.75.2B — QUERY DUPLICATE SUPPRESSION MUST CROSS TASK/ATTEMPT BOUNDARIES

## Verified defect

Current query de-duplication works inside one planned query list and persisted uniqueness is scoped approximately to:

```text
task_id + query_hash
```

Therefore a later Task can issue the same normalized query again.

A Question-level pursuit cooldown is not equivalent to query-history suppression.

## Required behavior

Use existing Research Question / Gap / attempt history to suppress the same normalized query across later work for the same investigative scope for a bounded cooldown.

Minimum rule:

```text
normalize query
hash normalized query
before executing:
    check recent attempts for the same Research Question or canonical Gap scope
    if the same hash was already attempted inside the configured cooldown:
        skip it
        record duplicate-suppressed outcome/reason
```

Do not add another research executor.

Do not permanently ban a query. A later retry is valid after cooldown or an explicit materially changed scope/reason.

Choose the smallest scope that matches the existing data model:

```text
prefer canonical Gap
fall back to Research Question if Task/Gap history requires it
```

Document the chosen scope.

## Acceptance

Create two sequential Tasks/attempt cycles under the same Question/Gap.

The second attempt must not execute the same normalized query within cooldown.

After cooldown or a documented changed-scope condition, retry may be allowed.

---

# 18. 28.75.2C — SAFE CONTRARY-EVIDENCE PURSUIT MUST BE REAL OR EXPLICITLY UNAVAILABLE

Phase 28.5 correctly rejected generic natural-language negation.

However, the closure review did not find a complete implementation of the allowed safe path.

Required rule:

```text
Newsroom may claim contrary-evidence pursuit only if it had a safe canonical basis.
```

Safe bases may include:

```text
existing contradictory Claim
disputed Claim with explicit contrary proposition
human-approved alternative/exclude vocabulary
canonical contradiction terms already stored
```

When one exists:

```text
derive the bounded contrary query from that canonical material
execute it through the normal Research path
record the basis/source of the contrary strategy
```

When none exists:

```text
record:
no_safe_contrary_strategy_available
```

Do not synthesize a fake opposite proposition.

Do not claim a disconfirming search occurred when it did not.

## Acceptance

Test both:

```text
safe contradictory basis exists -> contrary strategy is attempted and auditable

no safe basis -> no contrary query is invented; explicit unavailable outcome recorded
```

---

# 19. 28.75.2D — RESEARCH SOURCE-CLASS DIVERSITY MUST BE TESTED END TO END

Phase 28.5 added source-kind rotation/diversification behavior.

Add a focused test proving it actually changes selected/executed Research candidates when supporting evidence/results are concentrated in one source class.

The test must fail if the diversification logic is removed.

Do not turn this into a generalized strategy engine.

---

# 20. STAGE 28.75.3 — EVALUATION / LITE / CI HONESTY

## Objective

The evaluation system must measure the semantics its case names claim, and the Lite harness must enforce the frozen comparison rather than merely describe it.

---

# 21. 28.75.3A — EVERY NEW SEMANTIC CASE MUST HAVE A MACHINE-EVALUATED ASSERTION

## Verified defect

The eval corpus grew from 30 to 38 cases, but several new case titles describe semantics that the current evaluator does not actually score.

Examples include:

```text
Ask refusal correctness
conservative absence
late dependency discovery
single dependency-group support
```

A JSON fixture with that title is not a regression test unless the evaluator checks that behavior.

## Required outcome

For every Phase 28.5/28.75 semantic case:

```text
name the behavior
name the expected machine-readable outcome
name the metric/assertion that checks it
prove the case fails if the behavior regresses
```

Prefer extending the existing `newsroom.evals` case/prediction/metric structures minimally.

Do **not** create a second evaluation framework.

Required measured semantics include at minimum:

```text
Ask insufficient_evidence/refusal where applicable
conservative absence language/status
current dependency-group count after late lineage discovery
no independent-corroboration overclaim for one dependency group
late Story correction current/history correctness
late Story split current/history correctness
DocumentVersion/content provenance after silent edit
retraction/correction behavior actually supported by current canonical model
```

If one of the existing eight cases describes behavior the current architecture cannot yet evaluate honestly, rewrite or defer that case rather than keeping a narrative placeholder.

---

# 22. 28.75.3B — EVAL CORPUS PARSER MUST REJECT DUPLICATE JSON KEYS

## Verified defect

The new eval JSON fixtures contain duplicate keys, including duplicate `content_hash` keys.

The default JSON parser silently accepts the last duplicate key.

That means corpus validation can pass malformed fixtures.

## Required behavior

The eval corpus loader/validator must reject duplicate keys.

Use the smallest robust parser technique available, e.g. a duplicate-detecting `object_pairs_hook` or equivalent.

Error output should identify:

```text
case file
duplicate key
location/object context where practical
```

Do not silently normalize malformed fixtures.

## Acceptance

A temporary eval case with a duplicate key fails corpus validation.

All committed corpus files validate without duplicate keys.

---

# 23. 28.75.3C — CONTENT HASH CONSISTENCY

## Verified defect

The reviewed `silent document edit` case changed content:

```text
"The threshold is 10."
->
"The threshold is 12."
```

while retaining the same content hash.

That contradicts the DocumentVersion/content-hash provenance invariant the case claims to test.

## Required correction

Audit all newly added cases for:

```text
duplicate content_hash fields
same hash assigned to materially different content
different hashes assigned inconsistently with the repository's canonical hash function
```

Where the case schema stores content plus hash, compute the expected hash using the same canonical method used by runtime fixtures.

Add validator support where practical so future inconsistent cases fail mechanically.

The silent-edit case must have distinct hashes for distinct content.

---

# 24. 28.75.3D — DOCUMENTATION MAY CLAIM ONLY MEASURED EVAL COVERAGE

Audit `docs/EVALUATION.md`.

Do not claim the permanent corpus covers:

```text
Simple/Advanced navigation
Hypothesis UI/links
Attention UI actions
```

unless actual corpus cases and metrics measure them.

Those may be engineering/integration tests instead.

Clearly distinguish:

```text
permanent semantic eval corpus
pytest engineering/integration tests
frontend tests/type checks
Lite benchmark
dogfood telemetry
```

State the true counts.

---

# 25. 28.75.3E — LITE HARNESS MUST ENFORCE THE FROZEN CONTRACT

## Verified defect

The Phase 28.5 Lite contract contains fields for:

```text
corpus cutoff
provider/model
temperature
prompt version
context budget
retrieval limit
questions
scoring
blinding
```

but the harness currently enforces only part of that contract and can accept an arbitrary synthesis function over the live database.

That is not yet a frozen apples-to-apples comparator.

## Binding comparison principle

> **Full and Lite must run against the same frozen corpus state and the same model/provider conditions.**

The benchmark must not compare:

```text
different corpora
different cutoff windows
different model configurations
or an arbitrary caller-supplied Lite synthesizer
```

and then attribute the difference to architecture.

---

# 26. 28.75.3F — FROZEN CORPUS BINDING

The current static cutoff predates dogfood and is not suitable as the final dogfood benchmark corpus.

Replace it with a frozen-snapshot contract.

Preferred mechanism:

```text
at benchmark freeze time:
    create a named immutable SQLite snapshot using the existing backup mechanism
    record snapshot timestamp
    record a manifest/hash of included Document/DocumentVersion identity
    run BOTH Full and Lite against that same snapshot
```

Equivalent manifest-based isolation is acceptable if smaller and equally enforceable.

Do not run one side against the current mutable dogfood DB and the other against a filtered subset.

The contract may define the **cutoff policy now** and bind the actual immutable timestamp/snapshot when dogfood reaches the comparison point.

No final Full-vs-Lite verdict is required in Phase 28.75.

The harness must merely be incapable of running a supposedly frozen comparison without a valid frozen corpus binding.

---

# 27. 28.75.3G — MODEL / PROMPT / BUDGET ENFORCEMENT

The production benchmark runner must bind:

```text
provider
model
temperature/deterministic settings where supported
prompt version
context budget
retrieval limit
citation limit
```

from the frozen benchmark contract.

Test seams may inject deterministic synthesizers.

The real benchmark entry point must not accept an arbitrary unrecorded synthesizer that bypasses the contract.

Full and Lite must use the same intended model/provider class and comparable budget/context rules.

Record every effective value in the benchmark result.

---

# 28. 28.75.3H — QUESTION SET / SCORING / BLINDING ENFORCEMENT

The harness must use the frozen 20-question contract rather than an arbitrary question list.

Question IDs/case associations in the contract must actually participate in the run.

The result must record:

```text
question ID
system-blinded answer ID
retrieved/cited document IDs
effective model/config
scores
```

Where scoring is human:

```text
strip Full/Lite identity
shuffle answer order
record scorer decision before revealing attribution
```

Where scoring is deterministic, record the metric implementation/version.

Pre-registered falsification criteria remain fixed before results.

---

# 29. 28.75.3I — CI WORKFLOW MUST BE VERIFIED IN THE LIVE REPOSITORY

## Artifact discrepancy

The Phase 28.5 report claimed:

```text
.github/workflows/ci.yml
```

but that file was not present in the supplied Phase 28.5 ZIP.

This may be an archive/packaging omission or a repository omission.

Required:

```text
inspect the live worktree
```

If CI exists:

```text
verify its contents
stage/commit it
ensure repository snapshots/archive procedure includes dotfiles
```

If it does not exist:

```text
add the minimal CI workflow required by Phase 28.5
```

CI should run the supported hard gates without inventing a large matrix.

At minimum:

```text
ruff
backend tests
frontend typecheck
```

Include frontend lint/build only if the supported CI environment can run them reliably.

Do not claim CI exists unless it is tracked.

---

# 30. STAGE 28.75.4 — FINAL VALIDATION, COMMIT, AND DOGFOOD READINESS

## Objective

Finish with an accepted, reproducible repository state rather than another large uncommitted worktree.

---

# 31. 28.75.4A — REQUIRED FOCUSED REGRESSION PROBES

Before the full suite, run focused tests proving each closure defect.

Required probes:

```text
schema-32 Attention feedback survives upgrade

schema-32 reviewed Blind Spot decision survives or is preserved in the approved
historical destination

schema-34 upgrades cleanly

Snooze hides before expiry and returns after expiry

new material Attention cause reappears despite old decision

Alert-backed Seen acknowledges the Alert

Home does not render one Alert through two current-attention blocks

Counterfactual anchor excludes the entire current dependency component

origin_hypothesis_id survives export/import

duplicate Research query is suppressed across later Task/attempt within cooldown

safe contrary-evidence strategy runs when a canonical basis exists

no-safe-basis case does not invent a contrary query

source-class diversity changes candidate selection where required

duplicate JSON keys fail eval validation

silent-edit fixture uses consistent distinct content hashes

each new semantic eval case has a machine-scored assertion

Lite runner refuses an unfrozen/unbound corpus

Lite result records effective model/prompt/retrieval contract

CI workflow is tracked
```

---

# 32. 28.75.4B — FULL VALIDATION

Run the strongest supported final validation.

At minimum:

```text
python -m compileall -q newsroom tests

full pytest suite

pytest collection count

ruff

frontend typecheck

frontend lint if configured

frontend production build in the supported environment

fresh migration -> latest

schema 32 -> latest adversarial upgrade

schema 34 -> latest upgrade

repeat migration/no-op

PRAGMA foreign_key_check

application integrity

existing evaluation corpus validation

existing evaluation summary/baseline

new semantic case assertions

Lite contract validation

Lite harness freeze-enforcement tests

logical Class A/B export/import round trip

git diff --check
```

Run mypy and report the informational baseline/non-regression according to the Phase 28.5 policy.

If a check cannot run because of environment/platform constraints, report the exact reason.

Do not report PASS for a command that was not executed.

---

# 33. 28.75.4C — COMMIT THE PHASE 28.5 + 28.75 WORK COHERENTLY

The lack of commits is now an acceptance defect.

Preserving unrelated dirty work does not require leaving all phase implementation uncommitted.

After validation:

```text
inspect git status
identify unrelated pre-existing tracked/untracked work
stage only Phase 28.5/28.75 implementation, tests, docs, migrations, tooling,
and phase-plan files intended for repository authority
```

Create several coherent commits.

Suggested grouping, adjust to the actual diff:

```text
1. Phase 28.5/28.75 truth and migration closure
   Coverage deletion, migration preservation, dependency/Counterfactual fixes,
   Attention semantics

2. Phase 28.5/28.75 research and reconstruction closure
   canonical Gap migration, query-loop protection, export provenance

3. Phase 28.5/28.75 product compression
   Simple/Advanced/Home/Alert/frontend changes

4. Phase 28.5/28.75 evaluation and tooling
   eval semantic assertions, Lite harness, CI, docs
```

Fewer commits are acceptable if the diff is naturally smaller.

Do not create microcommit confetti.

Do not include unrelated user artifacts.

Do not push.

---

# 34. DOGFOOD GATE

Do not start real dogfood before Phase 28.75 is accepted.

The code currently has no explicit dogfood subject/source configuration supplied by the user.

That remains an intentional external-input blocker, not a code defect.

At Phase 28.75 acceptance:

```text
request/use the explicit subject and approved Source set
create the dedicated dogfood DB/profile
freeze provider/model/budget
start the worker/API
record start date
start backup policy
```

Phase 29 may begin after:

```text
Phase 28.75 is accepted
and
the dogfood Watch has been explicitly configured and started
```

Phase 29 does not wait four weeks.

Phase 30 still waits for the dogfood/Full-vs-Lite evidence window.

---

# 35. DELIBERATE NON-BLOCKERS

The following do **not** block Phase 28.75 acceptance unless a new correctness defect is found:

```text
no final Full-vs-Lite quality verdict yet

no four-week dogfood results yet

mypy still has the documented pre-existing informational baseline

Phase 30 onboarding/packaging/notifications remain deferred

Phase 29 historical Ask/knowledge-time remain deferred

legacy `independent_support` vocabulary in purely historical migration/data contexts
may remain if no current user-facing output uses it
```

Current user-facing and active API terminology must use the corrected dependency wording.

---

# 36. SUBTRACTION / SURFACE RULE

Phase 28.75 is allowed to add a **small amount of persistence required to preserve human history or implement real Snooze semantics**.

Do not game the Phase 28.5 subtraction target by losing Class B data.

Hard rule:

```text
correct preservation beats an arbitrary table-count target
```

But the architectural trend must remain subtractive:

```text
Coverage stays gone
Evidence Families stay gone
Fragility stays gone
Blind Spot runtime stays gone
Attention current-state table stays gone
four Phase 28 analytical Jobs stay gone
Simple cockpit stays small
```

Report final table/export/route/nav/job counts and explain any difference from Phase 28.5.

---

# 37. FINDING-TO-CORRECTION MAP

| Finding | Phase 28.75 handling |
|---|---|
| Legacy Attention feedback silently dropped | 28.75.0A |
| Reviewed Blind Spot decisions dropped | 28.75.0B |
| Schema-34 compatibility/recovery ambiguity | 28.75.0C |
| Snooze suppresses forever | 28.75.1A |
| Home Attention vs Alert acknowledgement mismatch | 28.75.1B |
| Counterfactual anchors exclude exact rows only | 28.75.1C |
| Attention material-cause regression risk | 28.75.1D |
| `origin_hypothesis_id` lost on logical roundtrip | 28.75.2A |
| Duplicate Research queries recur across later Tasks | 28.75.2B |
| Contrary-evidence strategy incomplete | 28.75.2C |
| Source-class diversity lacks E2E proof | 28.75.2D |
| New eval cases partly narrative-only | 28.75.3A |
| Duplicate JSON keys accepted | 28.75.3B |
| Silent-edit content hashes inconsistent | 28.75.3C |
| Eval docs overclaim coverage | 28.75.3D |
| Lite harness does not enforce frozen contract | 28.75.3E–H |
| CI absent from supplied snapshot | 28.75.3I |
| Phase 28.5 remains uncommitted | 28.75.4C |

---

# 38. TESTS THAT MUST CHANGE OR BE ADDED

Do not preserve an old test if it encodes the defect.

At minimum add/modify tests for:

```text
schema32_attention_feedback_upgrade_preserves_decision

schema32_reviewed_blind_spot_upgrade_preserves_human_review

attention_snooze_expires

attention_new_material_cause_reappears

alert_attention_seen_acknowledges_alert

home_does_not_duplicate_alert_attention

counterfactual_document_anchor_expands_dependency_component

counterfactual_source_anchor_expands_dependency_components

logical_roundtrip_preserves_origin_hypothesis_id

research_query_duplicate_suppressed_across_tasks

research_contrary_strategy_uses_canonical_basis

research_contrary_strategy_unavailable_does_not_invent_query

research_source_class_diversity_changes_selection

eval_loader_rejects_duplicate_json_keys

eval_validator_rejects_inconsistent_content_hash

new_phase285_cases_have_semantic_assertions

lite_requires_frozen_corpus_binding

lite_enforces_contract_model_prompt_retrieval_settings

ci_workflow_is_tracked_or_repository_validation_equivalent
```

Names may follow existing conventions.

Behavior is binding, not the exact test names.

---

# 39. MIGRATION ACCEPTANCE MATRIX

The final migration suite must explicitly cover:

| Starting state | Seeded data | Expected result |
|---|---|---|
| Fresh DB | none | latest schema succeeds |
| Phase 28 / schema 32 | Attention feedback | decision preserved |
| Phase 28 / schema 32 | reviewed Blind Spot | human review preserved |
| Phase 28 / schema 32 | hypothesis gap | canonical Research Gap provenance preserved |
| Phase 28 / schema 32 | all three together | all survive correctly |
| Phase 28.5 / schema 34 | current Attention decisions | upgrade succeeds, Snooze-capable schema valid |
| latest | repeat migration | no-op |

Every path:

```text
foreign_key_check = clean
integrity = clean
```

---

# 40. EVALUATION ACCEPTANCE MATRIX

For each new permanent semantic case, completion report must show:

```text
case ID
semantic claim
machine-evaluated expected output
metric/assertion implementation
actual result
```

A case does not count toward Phase 28.75 acceptance merely because:

```text
the JSON parses
or
the case title describes a scenario
```

The evaluator must measure the behavior.

---

# 41. LITE HARNESS ACCEPTANCE

The Lite harness is accepted when it can demonstrate, without running the final product comparison:

```text
the exact frozen question set is loaded

a mutable/unbound DB is rejected for a frozen benchmark run

a valid immutable snapshot/manifest is accepted

the same snapshot identity is available to Full and Lite runners

provider/model/prompt/context/retrieval settings are loaded from the contract

effective settings are emitted in results

question IDs are preserved

document citations are preserved

scoring/blinding metadata is preserved

an arbitrary unrecorded production synthesizer cannot bypass the contract

no final product verdict is fabricated
```

---

# 42. DOCUMENTATION UPDATES

Update:

```text
plan/phases-v2/README.md
docs/EVALUATION.md
docs/TOOLING.md
docs/ARCHITECTURE.md
docs/API.md if behavior/API changed
docs/DOGFOOD_CONTRACT.md if benchmark freeze sequencing changed
```

Document:

```text
Phase 28.75 exists as Phase 28.5 acceptance closure

dogfood starts after 28.75 acceptance, not before

Full-vs-Lite final result remains pending

which eval cases are permanent semantic cases vs engineering tests

what the Lite frozen-corpus mechanism actually is

what historical Phase 28 user decisions are preserved during migration
```

Do not claim anything stronger than code/tests prove.

---

# 43. WHAT MUST NOT BE TOUCHED

Do not weaken:

```text
Document -> DocumentVersion -> ContentArtifact -> EvidenceSpan -> Claim

exact EvidenceSpan/Claim provenance

Story correction authority/history

story_target_resolution_history

story_entities.authority = 'manual'

report_revision_causes

document_lineage

Ask insufficient_evidence refusal

Ask statement classes:
fact / inference / uncertainty / contradiction / user_hypothesis

Counterfactual non-mutation

AIRouter deterministic/local fallback

SQLite

SQL/FTS

JobService

integrity framework

one canonical Research Gap authority

five-item Simple cockpit

Simple-mode provenance deep-link access
```

---

# 44. FINAL VALIDATION GATES

## Engineering gate

```text
all focused closure tests pass
full pytest suite passes
compileall passes
ruff passes
frontend typecheck passes
frontend build passes in supported environment
frontend lint passes if configured
git diff --check passes
```

## Migration/data-safety gate

```text
schema 32 -> latest preserves seeded human decisions
schema 34 -> latest succeeds
fresh -> latest succeeds
repeat migration no-op
foreign_key_check clean
integrity clean
```

## Semantic gate

```text
Snooze expires
Alert/Home semantics agree
Counterfactual expands dependency component
Research duplicate suppression crosses Tasks
safe contrary-evidence behavior is auditable
logical roundtrip preserves Hypothesis-origin Gap provenance
```

## Evaluation-honesty gate

```text
duplicate JSON keys rejected
content-hash consistency validated
new semantic cases are actually machine scored
docs describe only measured eval coverage
Lite contract is enforced
CI is tracked
```

## Repository-history gate

```text
Phase 28.5 + 28.75 implementation is committed coherently
unrelated user work remains preserved
nothing is pushed
```

---

# 45. PHASE ACCEPTANCE

Phase 28.75 is complete only when all automated gates above pass.

Two items are **not** required for code acceptance:

```text
final four-week dogfood results
final Full-vs-Lite quality verdict
```

But Phase 28.75 acceptance must leave both ready to start/run correctly.

The remaining external action after code acceptance may be:

```text
user supplies/approves dogfood Watch subject and Source set
```

That is not a reason to mislabel the code as incomplete if every code gate passes.

---

# 46. COMPLETION REPORT

Return a detailed report.

## A. Starting state

```text
branch
HEAD
schema
worktree
tracked/untracked pre-existing changes
base table count
export table count
worker handler count
route count
Simple/Advanced nav counts
test count
eval corpus count
```

## B. Migration decisions

Explain:

```text
whether unaccepted migrations 33/34 were repaired in place
whether a new forward migration was added
why that choice was safe
how schema-32 Attention feedback is preserved
how reviewed Blind Spot decisions are preserved
schema-34 compatibility
```

## C. Human-decision preservation counts

Report fixture/real inspected counts:

```text
legacy Attention feedback rows found/migrated
reviewed Blind Spot rows found/preserved
Hypothesis Gap rows migrated
```

Never imply a real user database contained zero rows merely because a dev DB did.

## D. Attention/Alert semantics

Report:

```text
final Attention decision schema
Snooze expiry semantics
material basis semantics
Alert acknowledgement mapping
Home duplicate-alert removal
```

## E. Counterfactual

Report:

```text
anchor request shape
dependency-component resolution algorithm
resolved-membership response
non-mutation test
```

## F. Research

Report:

```text
duplicate suppression scope
cooldown
safe contrary-evidence bases
no-safe-strategy behavior
source-class diversity test
```

## G. Logical reconstruction

Report:

```text
origin_hypothesis_id roundtrip result
Class A/B export/import result
foreign keys/integrity
```

## H. Evaluation

For each new semantic case:

```text
case ID
what is machine scored
metric/assertion
result
```

Also report:

```text
duplicate-key validator
content-hash validator
final corpus count
```

## I. Lite harness

Report:

```text
frozen corpus mechanism
snapshot/manifest contract
model/provider enforcement
prompt/config enforcement
question-set enforcement
scoring/blinding enforcement
tests
```

Do not report final Full-vs-Lite quality results unless they were legitimately run against the future dogfood snapshot.

## J. CI/tooling

Report:

```text
CI workflow path
tracked status
commands
ruff
pytest
frontend typecheck/lint/build
mypy informational baseline
```

## K. Commits

For each commit:

```text
SHA
title
scope
validation performed
```

## L. Final repository deltas

```text
schema before -> after
base tables before -> after
export tables before -> after
handlers before -> after
routes before -> after
nav before -> after
production Python LOC before -> after
```

Explain any increase caused by required Class B preservation.

## M. Dogfood readiness

State:

```text
code readiness
dedicated DB/profile readiness
remaining required subject/source input
benchmark contract readiness
backup readiness
```

## N. Final verdict

Choose exactly one:

```text
PHASE 28.75 COMPLETE — PHASE 28.5 READY FOR ACCEPTANCE

PHASE 28.75 IMPLEMENTED WITH EXPLICIT ACCEPTANCE BLOCKERS

PHASE 28.75 BLOCKED
```

Do not declare Phase 29 ready until Phase 28.75 has been independently accepted.

---

# 47. AFTER PHASE 28.75

After independent acceptance:

```text
accept Phase 28.5 + 28.75 as the corrected Phase 28 closure

configure/start the real dogfood Watch with explicit user-approved subject/Sources

rewrite Phase 29 against the post-28.75 repository

delete the old Phase 29.0 closure stage

keep Coverage retired

keep dependency groups and Counterfactual on-demand

keep Attention decisions append-only

move historical/knowledge-time Ask evaluation into Phase 29A

defer broad Shadow Reprocessing and Belief Diff

run Full-vs-Lite against the frozen dogfood snapshot before Phase 30
```

Phase 29 should not reopen corrections that Phase 28.75 proves closed.

---

# 48. FINAL STANDARD

Phase 28.5 made the architecture substantially better.

Phase 28.75 exists to ensure that the smaller architecture is also:

```text
safe to upgrade to
semantically coherent
reconstructable
measurably tested
benchmarkable
committed
```

The phase should feel like tightening bolts after a major refit, not adding another wing to the building.

The acceptance question is simple:

> **Can we trust this post-Phase-28 architecture enough to begin measuring its real intelligence value?**

If the answer is yes after the gates above, accept it and move on.
