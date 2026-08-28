# PHASE 28.875 — FINAL ACCEPTANCE CLOSURE

## Executable Semantic Evals, Research-Honesty Fixes, Full-vs-Lite Contract Binding, Historical-Field Truthfulness, and Repository Authority Cleanup

---

# 0. STATUS AND AUTHORITY

Phase 28 is complete.

Phase 28.5 implemented the major architectural subtraction.

Phase 28.75 corrected the migration, Attention, Counterfactual, Research, evaluation, benchmark, and repository-history defects found after Phase 28.5.

Independent review of the Phase 28.75 snapshot found that the architecture is now sound, but **Phase 28.75 is not yet accepted** because a small number of final acceptance blockers remain.

Phase 28.875 is the next permitted work.

**Phase 29 remains blocked until Phase 28.875 is implemented, independently reviewed, and accepted.**

This phase is a final acceptance closure. It is not a new architecture phase.

Active planning authority:

```text
G:\Projects\Newsroom -v2\plan\phases-v2\
```

Primary inputs:

```text
plan/phases-v2/Phase 28.5.md
plan/phases-v2/Phase 28.75.md
plan/phases-v2/Phase 29.md
plan/phases-v2/README.md

docs/EVALUATION.md
docs/TOOLING.md
docs/DOGFOOD_CONTRACT.md
docs/ARCHITECTURE.md
docs/reviews/PHASE_29_PRE_IMPLEMENTATION_ADVERSARIAL_REVIEW.md
```

The live repository is always implementation authority.

Do not assume a starting HEAD, schema, table count, route count, test count, or worktree state. Re-verify them before editing.

The latest reviewed Phase 28.75 implementation reported commits ending with:

```text
41dbe3192083fa9f1281e3d8751c0352ed70f1e3
```

Re-verify the actual current HEAD.

The latest independently comparable schema measurements were:

```text
schema:                         36
SQLite tables total:           118
non-FTS base tables:           112
FTS virtual/shadow tables:       6
logical-export tables:          85
worker handlers:                 9
Simple / Advanced nav:         5 / 9
pytest report:                 806 passed
eval corpus:                    38 cases
```

Use one table-count convention consistently:

```text
base tables = SQLite tables excluding search_fts and all FTS virtual/shadow tables
```

Report total SQLite tables separately.

Preserve unrelated tracked and untracked user work.

Do not reset, clean, rewrite history, or push.

---

# 1. WHY THIS PHASE EXISTS

Phase 28.75 closed the major correctness problems discovered after Phase 28.5:

```text
legacy Attention decisions survive upgrade
reviewed Blind Spot decisions survive upgrade
Snooze expires
Alert-backed Seen/Not useful acknowledges the Alert
Home duplicate Alert rendering is removed
Counterfactual anchors expand dependency components
origin_hypothesis_id survives logical export/import
cross-task Research duplicate suppression exists
safe contrary-evidence strategy exists
source-class diversity is exercised
duplicate JSON keys are rejected
content hashes are validated
Lite snapshot/config/question/blinding enforcement exists
CI was added and committed
```

The remaining blockers are narrow:

```text
1. the eight new semantic eval cases still do not execute actual Newsroom behavior;
   tests can populate semantic_results from assertion.expected itself

2. contrary-evidence state can say "attempted" before the query really executes,
   including when it is later duplicate-suppressed

3. duplicate_suppressed Research rows can renew their own cooldown indefinitely

4. the production Lite path still accepts an arbitrary callable that can imitate
   the expected config

5. there is no minimal Full-side runner/orchestrator binding Full and Lite to the
   same frozen snapshot/config/question contract

6. blind_spot_review_history contains misleading field semantics:
   source_id stores the original Blind Spot suggestion ID, and preserved_at does
   not mean actual preservation time

7. the supplied review ZIP still omitted .github/workflows/ci.yml

8. plan/phases-v2/README.md is stale and still points to Phase 28.5

9. table-count reporting changed conventions between phases
```

Phase 28.875 closes only those defects.

---

# 2. FINAL OBJECTIVE

> **Make every remaining Phase 28.75 acceptance claim mean exactly what it says, and leave one repository state that can be accepted without qualification before dogfood and Phase 29.**

Phase 28.875 is complete when:

```text
every Phase 28.5/28.75 semantic eval case gets actual observed values from
real Newsroom code paths

a semantic regression in Ask / dependency grouping / Story correction /
Story split / DocumentVersion provenance makes the corresponding eval fail

contrary-evidence state distinguishes availability/planning/execution/suppression

duplicate-suppressed proposals cannot perpetually renew execution cooldown

the production Lite runner is constructed from the frozen benchmark contract,
not an arbitrary caller-supplied callable

a minimal Full runner/orchestrator binds Full and Lite to the same frozen snapshot,
question set, provider/model/prompt/config, and scoring/blinding contract

blind_spot_review_history column names and timestamps mean what they say

tracked CI is present in the actual reviewable source artifact

plan/phases-v2/README.md identifies Phase 28.875 and current sequencing correctly

all reports use one explicit table-count convention

full validation passes

the closure is committed coherently

no Phase 29 work has started
```

---

# 3. SCOPE FENCE

Do not add:

```text
new Coverage
new Blind Spot product lifecycle
Evidence Family cache
Fragility scalar
mutable Attention queue
historical Ask
knowledge-time architecture
Shadow Reprocessing
Belief Diff
projection registry framework
new Research executor
generic event/audit framework
dogfood subject/source selection
onboarding
backfill-on-Watch-create
diff-first Reports
packaging
external notifications
new Source connectors
tag authority merge
Entity merge workflow
vector search
new database
```

This phase may add only:

```text
small deterministic eval adapters/executors
small benchmark orchestration code
small migration/schema naming correction if needed
small repository/archive hygiene fixes
tests
docs
```

Nothing else.

---

# 4. PROTECTED ARCHITECTURE

Do not reopen:

```text
Coverage remains deleted
Blind Spot runtime remains deleted
Evidence Families remain deleted
Fragility scalar remains deleted
document_lineage remains canonical dependency truth
dependency groups remain computed on demand
Counterfactual remains non-mutating
Attention ranking remains computed on read
Attention decisions remain append-only human history
Snooze keeps explicit expiry semantics
research_question_gaps remains the sole researchable Gap authority
Research Tasks remain the sole research executor
Hypotheses remain framing/analysis
Simple mode remains five primary items
provenance deep links remain available in Simple mode
SQLite / SQL / FTS / JobService remain the platform
```

The architecture verdict from the Phase 28.75 review was **PASS**.

This phase is not authorized to redesign it.

---

# 5. PHASE STRUCTURE

Four mandatory checkpoints:

```text
28.875.0  EXECUTABLE SEMANTIC EVALUATION
          make semantic cases test actual Newsroom behavior

28.875.1  RESEARCH-HONESTY CLOSURE
          fix contrary-strategy state and cooldown semantics

28.875.2  FROZEN FULL-vs-LITE EXECUTION BINDING
          remove callable bypass and bind both sides to one contract

28.875.3  HISTORICAL / REPOSITORY AUTHORITY CLOSURE
          fix history field semantics, CI artifact, plan authority, counts,
          run final validation, commit
```

---

# 6. STAGE 28.875.0 — EXECUTABLE SEMANTIC EVALUATION

## Objective

The permanent semantic corpus must execute Newsroom behavior, not compare expected values to copies of themselves.

---

# 7. REMOVE CIRCULAR SEMANTIC TESTING

The reviewed Phase 28.75 path can effectively do:

```python
semantic_results = {
    assertion.assertion_id: assertion.expected
    for assertion in case.semantic_assertions
}
```

and score those values against the same expectations.

That only proves the scorer can compare equal values.

It does not prove Ask refused, dependency grouping updated, Story correction worked, or DocumentVersion provenance remained exact.

A case named:

```text
ask-sufficiency-refusal
```

must fail if Ask starts answering instead of refusing.

A case named:

```text
late-dependency-discovery
```

must fail if dependency grouping stops updating after a lineage edge.

This is a hard acceptance requirement.

---

# 8. ADD A REAL SEMANTIC EXECUTION BOUNDARY

Extend the existing `newsroom.evals` framework minimally.

Do not create another evaluation framework.

Use the smallest repository-native abstraction that can:

```text
load semantic case
seed deterministic fixture
execute real Newsroom service/domain operation
collect observed value
pass observed value into existing assertion scorer
```

Possible implementation:

```text
case-type-specific executors
or
a small SemanticCaseRunner registry
```

Do not generalize beyond the current cases unless the existing eval architecture naturally supports it.

No external provider should be required for these regression cases.

---

# 9. REQUIRED REAL PRODUCERS FOR THE EIGHT SEMANTIC CASES

## Ask refusal

Execute the real Ask path.

Observed value:

```text
actual Ask status / refusal code
```

The case must fail if Ask stops returning insufficient evidence.

## Conservative absence

Use the real Ask path.

Observe:

```text
status
statement classification / semantic absence category
```

The case must fail if Newsroom turns corpus absence into existential absence or gives a substantive unsupported answer.

## Late dependency discovery

Execute:

```text
seed Documents/support
read actual dependency grouping
add real document_lineage edge
read SourceRobustness/EvidenceQuality again
```

Observed value:

```text
actual current dependency_group_count
```

## Single-group / non-independent corroboration

Use the current evidence-quality / Report representation.

Observe:

```text
actual dependency-group count
actual user-facing/system semantic output needed to prove there is no independent-confirmation overclaim
```

## Late Story correction

Execute the real correction path.

Observe:

```text
current Story/Claim assignment
append-only correction/history result
```

## Late Story split

Execute the real split path.

Observe:

```text
current canonical Story membership
retired/source Story state where applicable
history/lineage relationship
```

## Retracted/corrected evidence

Measure only behavior actually supported by the canonical model.

Observe the real:

```text
Claim/evidence/document state
correction/invalidation consequence
```

Rewrite the fixture if the old narrative asks for behavior the current product does not actually support.

## Silent Document edit

Execute/replay actual versioned content behavior.

Observe:

```text
distinct DocumentVersion/content identity
distinct content hashes
EvidenceSpan/version provenance
```

Do not derive the semantic result only from case JSON.

---

# 10. CASE RESULT CONTRACT

For every semantic assertion, completion reporting must identify:

```text
case ID
assertion ID
subsystem executed
actual service/function
actual observed value
expected value
result
```

A semantic assertion does not count as machine-scored if the observed value comes directly from:

```text
assertion.expected
fixture.expected
or equivalent copied expectation
```

---

# 11. NEGATIVE-CONTROL PROOF

Add a small negative-control test per executor family.

Examples:

```text
force Ask observed result away from expected
-> semantic scorer fails

omit lineage-edge insertion
-> dependency case fails

skip Story correction
-> correction case fails
```

The point is to prove the evaluation plumbing is attached to observed behavior.

---

# 12. BASELINE INTEGRATION

The normal eval summary/baseline must include semantic assertion results.

The previous independent review found:

```text
38 valid cases
4 baseline results
0 semantic assertions scored by the normal baseline
```

After this stage:

```text
semantic cases participate in normal eval execution
```

not only a bespoke pytest path.

---

# 13. STAGE 28.875.1 — RESEARCH-HONESTY CLOSURE

## Objective

Research must describe what actually happened, and duplicate suppression must measure execution history rather than its own suppression history.

---

# 14. CONTRARY-STRATEGY STATE MUST REFLECT EXECUTION

The current safe contrary-strategy path can say:

```text
attempted
```

before the contrary query really runs.

That can remain true even if the query is later duplicate-suppressed.

Replace that ambiguity with the smallest explicit state vocabulary that distinguishes:

```text
unavailable
available
planned
executed
duplicate_suppressed
failed
```

Binding semantics:

```text
unavailable
    no safe canonical contrary basis exists

available
    safe basis exists, no query selected/executed yet

planned
    concrete contrary query selected for this attempt

executed
    query actually entered normal execution path

duplicate_suppressed
    query was not executed because recent real execution history suppressed it

failed
    execution was genuinely attempted and failed
```

Do not report executed/attempted unless execution occurred.

---

# 15. RECORD CANONICAL CONTRARY BASIS

When a safe contrary strategy exists, preserve why it was safe.

Examples:

```text
contradictory Claim ID
disputed Claim ID / explicit contrary proposition
approved vocabulary entry
canonical contradiction-term source
```

Do not persist provider-generated speculative opposition as canonical basis.

---

# 16. DUPLICATE-SUPPRESSED ROWS MUST NOT RENEW COOLDOWN

If recent query hashes include rows whose strategy/outcome is:

```text
duplicate_suppressed
```

then every suppressed proposal can produce a fresh timestamp and extend the cooldown forever.

The cooldown must be based on **real execution/attempt history**.

Eligible cooldown anchors:

```text
executed
actual attempted-and-failed
other states that represent real execution
```

Not eligible:

```text
duplicate_suppressed
no_safe_contrary_strategy_available
planning-only/proposal rows
```

Suppressed rows may remain audit history.

They simply may not renew the execution cooldown.

---

# 17. REQUIRED COOLDOWN REGRESSION

Deterministic test:

```text
T0:
query Q executes

T1 inside cooldown:
Q proposed
-> duplicate_suppressed

T2 after original execution cooldown expires,
but before a hypothetical cooldown based on T1 would expire:
Q proposed
-> MUST be allowed to execute
```

This proves suppression did not refresh the execution cooldown.

Also preserve explicit rerun override semantics from Phase 28.75.

---

# 18. STAGE 28.875.2 — FROZEN FULL-vs-LITE EXECUTION BINDING

## Objective

The benchmark must be structurally incapable of attributing differences to architecture when corpus/model/prompt conditions were not actually the same.

No final product benchmark result is required now.

---

# 19. REMOVE THE PRODUCTION CALLABLE BYPASS

The Lite production path still accepts an arbitrary callable similar to:

```python
harness.run(question_id, synthesize)
```

and can accept it if the callable presents a matching config attribute.

Separate:

```text
production benchmark execution
test-double injection
```

Production path must:

```text
construct synthesis from the frozen contract
use the existing AI routing boundary
record effective provider/model/prompt/config
not accept arbitrary caller-supplied synthesis function
```

Tests may inject deterministic fakes through an explicitly named test-only seam.

---

# 20. BIND TO EXISTING AI ROUTING

Use the existing:

```text
AIRouter / provider routing boundary
```

or the smallest existing equivalent.

Do not create another provider abstraction.

The frozen benchmark contract must bind:

```text
provider
model
temperature/determinism where supported
prompt version
context budget
retrieval limit
citation limit
```

Record the effective values actually used.

If a provider cannot enforce one field exactly, record the effective supported value instead of pretending.

---

# 21. ADD A MINIMAL FULL RUNNER

Add the smallest Full benchmark adapter that:

```text
opens the same frozen snapshot
uses the same q01-q20 contract
uses the same frozen provider/model/prompt/config
runs the normal Full Newsroom Ask/intelligence path
records the same answer/citation/config envelope
```

Do not duplicate Newsroom.

This is an eval adapter around the actual product.

---

# 22. ADD ONE PAIRED ORCHESTRATOR

Add one small orchestrator that runs:

```text
Full
Lite
```

from one frozen benchmark bundle.

It must reject mismatches in:

```text
snapshot ID
corpus manifest
question contract
provider/model/config
```

before comparing outputs.

No final verdict is required.

---

# 23. BENCHMARK REGRESSIONS

Required tests:

```text
production Lite rejects arbitrary callable injection

explicit Lite test-double seam accepts deterministic fake

Full runner uses actual Full application adapter

orchestrator rejects Full/Lite snapshot mismatch

orchestrator rejects config mismatch

valid paired run records identical benchmark identity for both sides
```

External provider access must not be required for unit tests.

---

# 24. STAGE 28.875.3 — HISTORICAL / REPOSITORY AUTHORITY CLOSURE

## Objective

Durable history fields, tracked source, planning authority, and completion reporting must all use truthful names and one consistent convention.

---

# 25. FIX BLIND SPOT HISTORY FIELD SEMANTICS

The preservation concept is correct:

```text
Blind Spot runtime deleted
human review history preserved
```

But current durable names are misleading.

A field named:

```text
source_id
```

actually stores the original:

```text
blind_spot_suggestions.id
```

Use truthful semantics such as:

```text
original_suggestion_id
```

Do not invent a Source ID that never existed.

For timestamps distinguish only facts actually known:

```text
suggestion_created_at
reviewed_at
preserved_at
```

`preserved_at` must mean migration/preservation time.

If preservation time is not useful, remove or rename the field rather than lie.

---

# 26. MIGRATION COMPATIBILITY

Schema 35 may already exist.

Support:

```text
fresh -> latest
schema 32 -> latest
schema 34 -> latest
schema 35 -> latest
latest -> repeat no-op
```

Preserve all history rows.

Do not rewrite accepted pre-28.5 migrations.

---

# 27. CI MUST BE PRESENT IN THE REVIEWABLE SOURCE ARTIFACT

The report says:

```text
.github/workflows/ci.yml
```

is tracked, but the supplied Phase 28.75 ZIP omitted it.

Required:

```text
git ls-files .github/workflows/ci.yml
verify file contents
verify snapshot/archive process includes tracked dot-directories
produce a fresh review ZIP
inspect raw ZIP listing before declaring success
```

Final review artifact must contain:

```text
.github/workflows/ci.yml
```

If the file is not tracked, add/commit it.

If the archive procedure excludes it, fix the archive procedure.

Do not move CI out of `.github/`.

---

# 28. UPDATE PLAN AUTHORITY README

Update:

```text
plan/phases-v2/README.md
```

It must say:

```text
Phase 28.875 is the active acceptance closure
Phase 29 is blocked until 28.875 acceptance
dogfood begins only after acceptance and explicit user-approved subject/source set
Phase 29 may then proceed in parallel with dogfood
Phase 30 waits for dogfood/Full-vs-Lite evidence
```

Do not mark Phase 29 active yet.

---

# 29. TABLE-COUNT REPORTING CONVENTION

Use one convention:

```text
base tables = SQLite tables excluding search_fts and all FTS virtual/shadow tables
```

Also report:

```text
SQLite total tables
FTS virtual/shadow table count
logical-export table count
```

Latest independently comparable measurements:

```text
Phase 28.5 schema 34:
SQLite total:       117
non-FTS base:       111
FTS virtual/shadow:   6

Phase 28.75 schema 35:
SQLite total:       118
non-FTS base:       112
FTS virtual/shadow:   6

Phase 28.875 schema 36:
SQLite total:       118
non-FTS base:       112
FTS virtual/shadow:   6
```

Re-measure live latest schema.

The one-table increase was intentional history preservation.

Do not optimize it away.

---

# 30. DOCUMENTATION TRUTH PASS

Audit:

```text
docs/EVALUATION.md
docs/TOOLING.md
docs/DOGFOOD_CONTRACT.md
docs/ARCHITECTURE.md
README.md
plan/phases-v2/README.md
```

Correct any statement implying:

```text
semantic evals execute real behavior if they do not
Lite production routing is frozen if arbitrary callable bypass remains
Full-vs-Lite is runnable if only Lite is bound
CI is reviewable if it is absent from the artifact
Phase 28.5 is still the active phase
```

---

# 31. FINAL VALIDATION

Required focused probes:

```text
Ask semantic eval obtains actual Ask value
Ask semantic negative control fails

dependency semantic eval obtains actual SourceRobustness value

Story correction semantic eval executes actual correction

Story split semantic eval executes actual split

silent-edit semantic eval executes actual version/provenance behavior

normal eval baseline includes semantic assertion results

contrary strategy reports unavailable/planned/executed/duplicate_suppressed honestly

duplicate_suppressed row does not renew cooldown

production Lite rejects arbitrary callable

explicit Lite test-double path works

Full runner binds same frozen snapshot/config

orchestrator rejects snapshot mismatch

orchestrator rejects model/config mismatch

blind_spot_review_history field meanings are correct

schema35 -> latest preserves history

CI appears in git ls-files

CI appears in newly produced review ZIP

plan/phases-v2/README.md points to Phase 28.875
```

Then run:

```text
python -m compileall -q newsroom tests

full pytest suite

ruff

frontend lint
frontend typecheck
frontend production build

fresh -> latest migration

schema 32 -> latest
schema 34 -> latest
schema 35 -> latest
repeat migration

PRAGMA foreign_key_check

application integrity

eval corpus validation

normal eval baseline with semantic assertion results

Lite contract validation

Full/Lite frozen-contract validation

logical Class A/B export/import

git diff --check
```

Run mypy under the existing informational baseline policy.

Do not report PASS for commands that did not run.

---

# 32. COMMIT DISCIPLINE

Do not squash or rewrite Phase 28.75 commits unless explicitly instructed.

Create one or more small Phase 28.875 commits.

Suggested grouping:

```text
1. execute semantic evals and correct Research honesty

2. bind Full-vs-Lite production benchmark execution

3. correct history semantics and repository/planning authority
```

Do not commit unrelated archive / `.kilo` / legacy-plan artifacts unless intentionally part of repository authority.

Do not push.

---

# 33. DOGFOOD

Do not run real dogfood unless the user separately supplies:

```text
dogfood subject
approved Source set
```

Phase 28.875 acceptance means:

```text
code ready
benchmark ready
dogfood profile contract ready
```

After acceptance and explicit configuration:

```text
start dogfood
start Phase 29
```

They may run in parallel.

Phase 30 remains downstream of dogfood/Full-vs-Lite evidence.

---

# 34. ACCEPTANCE GATES

## Architecture

```text
Coverage still gone
Evidence Families still gone
Fragility still gone
Blind Spot runtime still gone
Attention current projection still gone
five-item Simple cockpit preserved
```

## Semantic evaluation

```text
every new semantic case executes actual Newsroom behavior
normal eval baseline reports semantic assertion results
negative-control regressions prove the plumbing is real
```

## Research honesty

```text
no contrary query is called executed before execution
duplicate suppression has honest state
suppressed proposals do not renew execution cooldown
```

## Benchmark

```text
production Lite cannot use arbitrary unrecorded callable
Full runner exists
one orchestrator binds Full/Lite to same frozen contract
snapshot/config mismatch is rejected
```

## Historical truth

```text
Blind Spot history fields mean what they say
migration preserves history
```

## Repository authority

```text
CI tracked
CI present in final review artifact
plan README current
table counts use one convention
```

## Validation

```text
full supported automated suite passes
foreign keys/integrity clean
eval corpus/baseline clean
frontend validation clean
git diff --check clean
```

---

# 35. DELIBERATE NON-BLOCKERS

These do not block Phase 28.875 code acceptance:

```text
no real dogfood subject/source set yet
no four-week dogfood results
no final Full-vs-Lite quality verdict
mypy informational baseline remains
historical Ask not implemented
Shadow Reprocessing deferred
Belief Diff deferred
Phase 30 UX/packaging deferred
```

Do not pull them into this phase.

---

# 36. COMPLETION REPORT

Return:

## A. Starting state

```text
branch
starting HEAD
schema
git status
existing commits
unrelated dirty/untracked work
non-FTS base table count
SQLite total table count
FTS table count
export table count
handlers
routes
Simple/Advanced nav count
pytest count
eval corpus count
```

## B. Semantic eval execution

For all eight cases:

```text
case ID
semantic assertion
real subsystem executed
actual service/function
actual observed value
expected value
result
```

Also report:

```text
normal baseline semantic assertion count
negative-control proof
```

## C. Research honesty

```text
final contrary-state vocabulary
when each state is assigned
canonical contrary basis
cooldown eligibility
suppressed-row behavior
focused tests
```

## D. Full-vs-Lite binding

```text
production Lite runner
test-double seam
Full runner
shared orchestrator
frozen snapshot identity
provider/model/prompt/config binding
mismatch rejection tests
```

Do not report final quality comparison.

## E. Historical correction

```text
blind_spot_review_history final schema
field renames
timestamp semantics
migration result
row preservation
```

## F. Repository authority

```text
CI tracked path
git ls-files result
review ZIP inclusion result
plan README update
archive/snapshot procedure correction
```

## G. Final counts

Using the one convention:

```text
schema
non-FTS base tables
SQLite total tables
FTS tables
logical-export tables
handlers
routes
Simple nav
Advanced nav
tests
eval cases
```

## H. Validation

List every command and result.

## I. Commits

For each:

```text
SHA
title
scope
validation
```

## J. Remaining external actions

```text
dogfood subject required
approved Source set required
dogfood start pending user approval
final Full-vs-Lite result pending dogfood snapshot
```

## K. Final verdict

Choose exactly one:

```text
PHASE 28.875 COMPLETE — PHASE 28.5/28.75 CORRECTION CHAIN READY FOR ACCEPTANCE

PHASE 28.875 IMPLEMENTED WITH EXPLICIT ACCEPTANCE BLOCKERS

PHASE 28.875 BLOCKED
```

Do not declare Phase 29 started.

---

# 37. AFTER PHASE 28.875

After independent acceptance:

```text
accept the Phase 28.5 -> 28.75 -> 28.875 correction chain

obtain explicit dogfood subject and Source set

start dedicated dogfood Watch

rewrite Phase 29 against the accepted repository

remove old Phase 29.0 closure work

keep Coverage retired

keep dependency groups / Counterfactual on demand

keep Attention decisions append-only

move historical/knowledge-time Ask work into Phase 29A

keep Shadow Reprocessing / broad Belief Diff deferred

run Full-vs-Lite against the frozen dogfood snapshot before Phase 30
```

---

# 38. FINAL STANDARD

Phase 28.875 should be boring in the best possible way.

No new intelligence architecture.

No new product surface.

No new epistemic subsystem.

It exists to make the remaining claims mechanically true:

```text
semantic eval means real subsystem execution

executed means executed

cooldown means time since real execution

frozen benchmark means production code cannot bypass the freeze

history field names mean what the values actually are

tracked CI appears in the source artifact

planning authority points to the actual active phase
```

Once those are true, stop.

The acceptance question is:

> **Can we finally trust the correction chain enough to start dogfood and Phase 29 without carrying a known semantic or validation lie forward?**

If yes, accept and move on.
