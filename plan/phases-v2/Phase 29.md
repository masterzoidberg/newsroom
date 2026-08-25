# PHASE 29 — PROVE THE INTELLIGENCE

## Temporal Truth, Closed-Loop Research Proof, Dogfood, Full-vs-Lite Validation, and the Phase 30 Decision Gate

---

# 0. PHASE STATUS AND AUTHORITY

The Phase 28 correction chain is accepted:

```text
Phase 28
Phase 28.5
Phase 28.75
Phase 28.8
```

Latest accepted reported repository state:

```text
branch:                  main
HEAD:                    c30cbf0677f43746c2ef905b766c40f05e467c86
schema:                  36
SQLite total tables:     118
non-FTS base tables:     112
FTS virtual/shadow:        6
logical-export tables:    85
worker handlers:           9
Simple / Advanced nav:   5 / 9
pytest:                  813 passing
eval corpus:              38 cases
```

The live repository is always implementation authority.

Do not assume the reported HEAD, schema, counts, worktree, routes, or tests remain current. Re-verify them before implementation.

Active planning authority:

```text
G:\Projects\Newsroom -v2\plan\phases-v2\
```

Binding prior plans and reviews:

```text
plan/phases-v2/Phase 27.md
plan/phases-v2/Phase 28.md
plan/phases-v2/Phase 28.5.md
plan/phases-v2/Phase 28.75.md
plan/phases-v2/Phase 28.8.md
plan/phases-v2/Strategic Architecture Review.md
plan/phases-v2/Final Architecture Reconciliation Memo.md
docs/reviews/PHASE_29_PRE_IMPLEMENTATION_ADVERSARIAL_REVIEW.md
```

Preserve unrelated tracked and untracked work.

Do not reset, clean, rewrite history, or push unless explicitly instructed.

---

# 1. PHASE MISSION

Phase 29 is the first phase whose primary question is not:

```text
Can Newsroom implement this architecture?
```

It is:

> **Does Newsroom's evidence-first architecture produce materially better longitudinal intelligence than a much simpler document-search + strong-LLM system?**

Roadmap meaning:

```text
Phase 29 = PROVE THE INTELLIGENCE
Phase 30 = SHIP THE PRODUCT
```

Phase 29 must not become another broad infrastructure phase.

It exists to prove or falsify the intelligence thesis before shipping work consumes the roadmap.

---

# 2. PRODUCT THESIS TO PROVE

The strongest target user is a:

> **longitudinal single-domain investigator**

Likely users:

```text
independent domain researchers
policy / regulatory analysts
investigative journalists
serious subject-matter researchers
industry / risk analysts
```

Core job:

> **Over months, tell me what actually changed about the thing I care about, show me why I should believe it, remember what I already decided, distinguish dependent reporting from real corroboration, and help me investigate what remains uncertain without making me reread everything.**

The three strongest product verbs remain:

```text
REMEMBER
CORROBORATE
CORRECT
```

Phase 29 must show that those capabilities create measurable value over Newsroom Lite.

---

# 3. FINAL PHASE OBJECTIVE

Phase 29 succeeds only if Newsroom demonstrates all of the following:

```text
1. TEMPORAL TRUTH
   Current belief can be distinguished from what was supportable earlier.

2. CORRECTION INTELLIGENCE
   Later evidence/corrections change current conclusions without rewriting history.

3. DEPENDENCY-AWARE CORROBORATION
   Copied/derived reporting is not mistaken for independent confirmation.

4. CLOSED-LOOP RESEARCH
   Question -> Gap -> Task -> canonical evidence -> reevaluation works end to end.

5. GROUNDED ASK
   Ask answers from canonical evidence and refuses when evidence is insufficient.

6. MATERIAL CHANGE
   Newsroom explains what materially changed and why using canonical causes.

7. USER VALUE
   A real Watch produces useful output with acceptable noise/correction burden.

8. COMPARATIVE VALUE
   Full Newsroom materially outperforms Newsroom Lite on the structural tasks
   that justify the extra architecture.
```

If the evidence does not support those claims, Phase 29 must recommend simplification before Phase 30.

---

# 4. DEFINING CONSTRAINT — PROVE, DO NOT EXPAND

Preference order:

```text
1. test existing capability
2. expose existing canonical facts
3. connect an existing lifecycle
4. add a narrow missing invariant
5. add minimal persistence only if current history cannot answer the question
6. add a new subsystem only if the proof literally cannot be made otherwise
```

A successful Phase 29 may reduce future scope.

Do not protect an abstraction merely because it was expensive to build.

---

# 5. DELIBERATE NON-GOALS

Do not implement by default:

```text
general bitemporal conversion
generic ProcessingRun framework
generic event envelope
generic projection registry
generic Belief Diff framework
Shadow Reprocessing platform
progressive-autonomy framework
vector database
graph database
PostgreSQL migration
new workflow engine
event bus
retention/purge architecture
installer/packaging
external notification delivery
large Source connector program
provider-generated Hypotheses
Entity merge workflow
new Coverage subsystem
new Evidence Family subsystem
new Fragility scalar
```

Anything deleted during the Phase 28 correction chain stays deleted.

If dogfood provides evidence that one of these is genuinely needed, record the evidence and defer the architecture decision unless it blocks the Phase 29 proof.

---

# 6. PHASE STRUCTURE

Four workstreams:

```text
29A  TEMPORAL TRUTH
     narrow knowledge-time semantics and historical Ask

29B  CLOSED-LOOP INTELLIGENCE
     prove correction, dependency, Research, Reports, and Ask end to end

29C  COMPARATIVE VALIDATION
     dogfood + frozen Full-vs-Lite + utility/correction measurement

29D  PRODUCT DECISION GATE
     decide what survives into Phase 30
```

Recommended sequence:

```text
29A
  ↓
29B
  ↓
29C readiness / controlled validation
  ↘
   dogfood runs in parallel once explicitly configured
  ↓
29D after sufficient evidence exists
```

Do not accumulate the whole phase into one giant commit.

Checkpoint after coherent capabilities and focused validation.

---

# 7. WORKSTREAM 29A — TEMPORAL TRUTH

## Objective

Newsroom must answer:

```text
What does Newsroom believe now?

What did Newsroom have enough evidence to believe at time T?

What changed between then and now?

Why did it change?
```

without pretending today's state existed in the past.

---

# 8. NARROW TEMPORAL MODEL, NOT UNIVERSAL BITEMPORALITY

Do not convert every table into `valid_from / valid_to`.

First audit existing canonical history:

```text
DocumentVersion
ContentArtifact
EvidenceSpan
Claim state/history where available
Story corrections
story_target_resolution_history
story_lineage
ReportRevision
report_revision_causes
Research attempts/history
Attention decisions
Alert history
```

Only add missing historical persistence where a real Phase 29 as-of query cannot be reconstructed from current durable history.

Binding principle:

> **Historical truth should be reconstructed from canonical history, not from a second shadow copy of the database.**

---

# 9. EVENT TIME, KNOWLEDGE TIME, AND CHANGE TIME

Where the domain actually exposes these facts, distinguish:

```text
event/source time
    when the source says something happened

observed/knowledge time
    when Newsroom first had the evidence available

processing/correction time
    when Newsroom changed a canonical conclusion or relationship
```

Do not invent precision.

If event time is unknown or approximate, preserve that uncertainty.

---

# 10. CHANGE-CAUSE IDENTITY

Do not introduce a generalized processing-event platform.

Newsroom only needs enough cause identity to answer:

```text
Why did this belief / Story / Report state change?
```

Prefer existing canonical IDs:

```text
DocumentVersion ID
EvidenceSpan ID
Claim ID/state transition
Story correction ID
Report revision cause ID
Research result/evidence ID
human correction ID
```

Only add a narrow cause record if a demonstrated temporal query cannot be explained from current histories.

---

# 11. AS-OF EVIDENCE / CLAIM READS

Add or prove a deterministic read boundary that can answer:

```text
What accepted/usable evidence was known by T?

What Claims were supportable by T?

What Claim state was current as of T?
```

Requirements:

```text
later DocumentVersions are excluded

later EvidenceSpans are excluded

later Claim acceptance/state changes are excluded

later Story corrections are not back-projected

today's current pointers are never mistaken for historical state
```

If the history is insufficient, fail explicitly rather than manufacture an as-of answer.

---

# 12. AS-OF STORY READS

For a Story, support the narrow historical view needed to answer:

```text
Which accepted Claims belonged to this Story as of T?

What corrections/merge/split events had occurred by T?

What Story identity was current at T?
```

Use existing correction and lineage histories.

No generic temporal ORM.

---

# 13. REPORT REVISION DIFF

Reports already have revisions and revision causes.

Use them.

Support:

```text
current Report

Report as of revision/time T

what materially changed between revisions

exact canonical causes
```

Preferred read shape:

```text
ADDED
NO LONGER SUPPORTED
CHANGED
STILL UNCERTAIN
CAUSES
```

Do not build a generalized Belief Diff subsystem.

---

# 14. HISTORICAL ASK

Implement:

> **What did Newsroom know about X as of T?**

Historical Ask must:

```text
use the same closed-world grounding/refusal policy as current Ask

restrict grounding to knowledge available by T

cite exact historical DocumentVersion / EvidenceSpan / Claim / Report revision

exclude later evidence

exclude later corrections from the historical view

refuse when historical grounding is insufficient

state clearly that the answer is an as-of answer
```

Historical Ask performs no external search merely because a question is historical.

---

# 15. UN-CONFIRMATION / RETRACTION THROUGH KNOWLEDGE TIME

Required semantic:

```text
T1:
evidence supports proposition P

T2:
later correction/retraction means P is no longer supported
```

Newsroom must be able to say:

```text
as of T1:
P was supported by evidence then available

now:
P is no longer supported / is disputed / has been corrected
```

It must not rewrite the historical record into:

```text
Newsroom never supported P
```

---

# 16. 29A PERMANENT SEMANTIC EVALS

Add real executable semantic cases for at least:

```text
belief at T1 vs T2

historical Ask:
T1 refusal / T2 answer

late evidence changes current belief but not historical belief

late Story correction does not rewrite earlier Story view

late Story split preserves earlier identity context

Report revision diff with exact cause

silent Document edit:
T1 cites version A
T2 cites version B

retraction / un-confirmation across knowledge time
```

Every observed result must come from actual Newsroom code through the executable semantic evaluation system established in Phase 28.8.

No decorative JSON cases.

---

# 17. WORKSTREAM 29B — CLOSED-LOOP INTELLIGENCE

## Objective

Prove the canonical intelligence loops work end to end.

Automatic monitoring chain:

```text
Watch
→ approved Source / Monitor
→ acquisition
→ Document / DocumentVersion
→ ContentArtifact
→ relevance / ArticleAnalysis
→ EvidenceSpan / Claim
→ Story
→ Report / Alert / Ask
```

Research chain:

```text
Research Question
→ assessment
→ canonical Gap
→ Research Task
→ corpus-first / bounded pursuit
→ normal acquisition
→ canonical evidence
→ Question reevaluation
```

No alternate evidence path is permitted.

---

# 18. WATCH-TO-STORY PROOF

Using deterministic replay/fixtures first, prove:

```text
approved Watch Source
→ Monitor/acquisition
→ DocumentVersion
→ canonical evidence
→ Claim
→ Story
```

Prove idempotency:

```text
rerunning the same acquisition/processing
does not create duplicate canonical authority
```

Database uniqueness remains the final idempotency boundary.

---

# 19. CORRECTION PROOF

Exercise:

```text
late contradictory evidence

human correction

Story reassignment

Story split

Story merge if current implementation already supports it robustly

silent Document edit

retraction/correction
```

For each prove:

```text
current state is correct

history remains preserved

Report revision/cause updates where applicable

current Ask sees current truth

historical Ask sees correct as-of truth
```

---

# 20. DEPENDENCY-AWARE CORROBORATION PROOF

Use a deliberately adversarial fixture:

```text
A = primary report
B = article derived from A
C = syndication of B
D = apparently separate report
```

Discover lineage progressively.

Prove:

```text
known dependency groups update immediately

Ask/Reports do not call one dependency group independent corroboration

Counterfactual removal of one anchor removes its current dependency component

late dependency discovery reduces current apparent corroboration without
rewriting earlier observations
```

Use:

```text
known dependency group
```

not “independent source/family” unless separately proven.

---

# 21. RESEARCH QUESTION CLOSED LOOP

Prove:

```text
Question created
assessment exists
canonical Gap exists
Task planned
duplicate suppression works
source-class diversity works
safe contrary strategy is used only when available
Task executes
new material enters normal acquisition
canonical Evidence/Claim changes
Question reevaluates
Gap closes / changes / remains open based on canonical evidence
```

Hard invariant:

> **Research changes factual Question state only through canonically processed evidence or explicit human decisions.**

A Research Task may not directly write a factual conclusion into Question state.

---

# 22. HYPOTHESES STAY NARROW

Hypotheses remain:

```text
framing / comparison objects
```

They may help compare:

```text
supporting Claims
contradicting Claims
discriminating Claims
unresolved canonical Gaps
```

Do not add:

```text
provider-generated Hypotheses
automatic belief probabilities
Bayesian scoring
new Hypothesis Gap authority
```

If dogfood shows the surface is not useful, record that for Phase 30 simplification.

---

# 23. MATERIAL-CHANGE EXPLANATION

Expose:

> **What materially changed, and why?**

Prefer a thin read model over persistence.

For a Story / Report, derive from canonical history:

```text
new evidence
corrected/retracted evidence
Claim state change
dependency discovery
Story correction
Report revision cause
Research result
human decision
```

Only include a cause if canonical history supports it.

No generated post-hoc causal story.

---

# 24. WORKSTREAM 29C — DOGFOOD AND COMPARATIVE VALIDATION

## Objective

Measure whether Full Newsroom earns its complexity.

Use two independent evidence sources:

```text
controlled frozen Full-vs-Lite benchmark

real longitudinal dogfood
```

Neither substitutes for the other.

---

# 25. DOGFOOD START CONTRACT

Dogfood requires explicit user approval of:

```text
subject
approved Source set
```

Do not invent either.

Use a dedicated database/profile.

Never use the default developer DB.

Recommended first Watch:

```text
one contested / messy / slow-moving longitudinal subject

8–15 approved Sources across:
    primary / official
    mainstream
    specialist
    aggregator / secondary
```

Freeze at start:

```text
subject
initial Source set
provider/model
budget
major prompt/config versions
```

Later Source additions must be recorded as explicit events.

Run API/worker/backups/telemetry for a minimum four-week evidence window unless a severe defect invalidates the run.

If interrupted, extend the window rather than erasing the record.

---

# 26. DOGFOOD HUMAN USEFULNESS LOG

Maintain a lightweight structured human log.

For material outputs capture:

```text
useful / not useful

already knew this?

would I have noticed it without Newsroom?

did provenance change my confidence?

did Newsroom overstate anything?

did I correct it?

did I take an action?

rough time saved / time-to-understanding where practical
```

Do not build a new telemetry platform for this.

---

# 27. DOGFOOD TELEMETRY

Use existing durable state where possible.

Track:

```text
time to first useful output

Attention useful / Not useful rate

Alert acknowledgement/action rate

Story automatic-assignment correction rate

Research attempt yield

Research Gap closure/change rate

Ask refusal rate

Ask grounded-answer/citation rate

Story correction frequency

dependency discovery frequency

Report revision frequency

human correction burden

provider use / estimated AI cost where already measurable
```

If a metric cannot be measured honestly, report it unavailable.

Do not invent proxies.

---

# 28. FROZEN FULL-vs-LITE RUN

Use the accepted Phase 28.8 benchmark system.

At comparison time:

```text
create immutable SQLite snapshot

bind corpus manifest

freeze q01–q20

freeze provider/model/config

verify effective execution configuration

run Full

run Lite

reject fallback/config mismatch

blind outputs

score under preregistered rubric
```

Do not change the contract after seeing results.

---

# 29. BENCHMARK QUESTION SET

Keep the frozen q01–q20 contract intact.

If the existing temporal questions cannot evaluate historical Ask adequately, add a **separate versioned temporal tranche**.

Do not silently rewrite the original frozen questions.

---

# 30. COMPARISON RUBRIC

Freeze before the real run.

Score:

```text
factual correctness

citation/provenance correctness

calibrated refusal

dependency awareness

correction awareness

temporal/change accuracy

uncertainty honesty

answer usefulness

research/actionability when relevant

latency

provider cost
```

Structural categories are why Full exists.

Do not let stylistic smoothness dominate epistemic correctness.

---

# 31. PRE-REGISTER THE DECISION RULE

Before scoring the dogfood snapshot, commit a decision rule.

Full must demonstrate a clear advantage in architecture-dependent categories:

```text
dependency-aware corroboration

temporal/correction intelligence

grounded uncertainty/refusal

longitudinal material-change explanation

Research usefulness
```

while remaining reasonably competitive on:

```text
basic factual retrieval

latency

cost
```

If numeric thresholds are used, commit them before the run.

Do not move goalposts.

---

# 32. REQUIRED FALSIFICATION CONDITIONS

The architecture thesis is challenged if:

```text
Lite is effectively equivalent on dependency/correction/temporal cases

Full frequently needs user correction despite its extra structure

Full citations/provenance are not materially more trustworthy

Research rarely yields useful new evidence

Home/Attention is mostly noise

user maintenance burden outweighs intelligence value

Full cost/latency is materially worse without compensating benefit
```

Those outcomes must be reported as evidence against the product thesis.

---

# 33. CONTROLLED PRE-DOGFOOD VALIDATION

Phase 29 implementation should not idle while dogfood accumulates.

Use deterministic/frozen corpora to:

```text
debug temporal reads

validate Historical Ask

exercise correction/dependency cases

verify scoring

verify Full/Lite paired execution
```

These are engineering signals.

They are not the final product-value verdict.

---

# 34. WORKSTREAM 29D — PRODUCT DECISION GATE

## Objective

End Phase 29 with evidence-based product decisions.

For each major capability classify:

```text
KEEP
SIMPLIFY
CONTEXTUALIZE
DEFER
REMOVE
```

Review:

```text
EvidenceSpan / Claim ledger
Stories + corrections
Reports
Ask
Alerts
Attention/Home
Watches
Research Questions/Gaps/Tasks
Hypotheses
Entities
Tags
dependency analysis
Counterfactual
Historical Ask
Workbench
Diagnostics
```

Do not protect sunk cost.

---

# 35. EXPECTED CORE SURVIVORS, SUBJECT TO EVIDENCE

Current expectation:

```text
versioned evidence
EvidenceSpan provenance
Claims
correctable Stories
Reports/revisions
Ask
Alerts
Watches
canonical Research
document_lineage
Entities
JobService
AIRouter/local fallback
SQLite/FTS
integrity/eval framework
```

Phase 29 may still recommend simplifying presentation around them.

---

# 36. CAPABILITIES THAT MUST EARN PRODUCT SURFACE

Explicit value review:

```text
Hypotheses
Workbench
Counterfactual UI
advanced dependency tooling
Historical Ask prominence
Tags
advanced Diagnostics
```

A capability may remain technically available while being removed from primary product presentation.

---

# 37. PHASE 30 MUST BE GENERATED FROM EVIDENCE

Do not inherit the old Phase 30 wish list automatically.

Generate Phase 30 from:

```text
dogfood friction
Full-vs-Lite results
correction rates
human usefulness
time-to-first-value
remaining reliability issues
commercial blockers
```

Likely categories, subject to evidence:

```text
intent-first onboarding
Watch creation/backfill
Source templates/catalog
diff-first Reports
notification delivery
packaging/installer
primary-source connector expansion
UX polish
performance/recovery/retention
commercial defaults
```

Phase 30 is for shipping a proven intelligence product, not proving it for the first time.

---

# 38. PRODUCTION-HARDENING BOUNDARY

Allowed in Phase 29 if needed for the proof:

```text
bounded query fixes
idempotency fixes
eval/replay fixes
backup/reconstruction fixes
provider-contract correctness
deterministic temporal reads
diagnostic telemetry required by the experiment
```

Defer broad programs:

```text
retention policy
large failure-injection matrix
SLO program
installer
multi-user deployment
large performance program
notification delivery
```

---

# 39. CLASS A / B / C DISCIPLINE

Continue:

```text
Class A
    canonical evidence/reference truth

Class B
    human intent, decisions, corrections, history

Class C
    rebuildable/derived state
```

Do not build a generic projection framework.

For every new persisted table report:

```text
class
authority owner
writer
reader
rebuild/recovery semantics
retention expectation
```

Prefer no new table when current canonical history suffices.

---

# 40. CLASS C RECONSTRUCTION — ONLY WHERE REAL

Do not create Class C state just to demonstrate rebuilding.

For current Class C state that matters:

```text
identify it
rebuild from A/B
compare semantic result
```

If little/no critical Class C state remains after Phase 28 cleanup, report that and stop.

---

# 41. ASK INVARIANTS

Normal and Historical Ask preserve:

```text
closed-world grounding
exact citations
insufficient_evidence refusal
derived/qualifying context cannot satisfy grounding alone
fact / inference / uncertainty / contradiction / user_hypothesis distinction
external content remains data, never instructions
```

Historical Ask adds only:

```text
knowledge-time restriction
```

---

# 42. RESEARCH INVARIANTS

```text
Research Questions change factually only through canonical evidence
or explicit human decision

Research Tasks never directly write Claims

duplicate suppression is bounded and based on real execution

safe contrary strategy never invents arbitrary opposition

source-class diversity remains bounded

optional discovery failure does not break monitoring

unapproved Sources never become active automatically
```

---

# 43. DOGFOOD STATE SAFETY

Dogfood must use an explicit dedicated DB/profile.

Never:

```text
default developer DB
test DB
migration fixture
```

Backups must be reliable enough not to lose the evidence window.

The dogfood database becomes the source for the later immutable benchmark snapshot.

---

# 44. PERMANENT EVAL EXPANSION

Add only executable Phase 29 semantic cases.

Mandatory themes:

```text
belief T1 vs T2

Historical Ask T1 refusal / T2 answer

late evidence changes current but not historical belief

un-confirmation / retraction through knowledge time

Report revision exact-cause explanation

Story correction as-of view

Story split as-of view

silent edit with version-specific historical citations
```

Every case must execute actual Newsroom behavior through the accepted semantic runner.

---

# 45. TESTING LAYERS

Use three separate layers:

```text
1. focused unit/integration tests

2. permanent executable semantic eval corpus

3. dogfood / Full-vs-Lite product evidence
```

Do not confuse them.

Passing pytest does not prove product value.

Dogfood anecdotes do not replace deterministic regression tests.

---

# 46. MIGRATION DISCIPLINE

Forward-only.

Do not preselect migration numbers in this plan.

Before adding schema:

```text
prove existing history cannot answer the required temporal question
```

For every new migration:

```text
fresh install
upgrade from current accepted schema
repeat no-op
foreign_key_check
integrity
logical export/import impact
```

No filesystem side effects.

No silent Class B history loss.

---

# 47. API / UI SURFACE DISCIPLINE

Do not create top-level navigation for:

```text
Historical Ask
Belief Diff
temporal state
dependency analysis
benchmark
```

Historical Ask belongs inside Ask.

Report temporal comparison belongs inside Reports/Story context.

Counterfactual remains contextual/Advanced.

Benchmark tooling remains internal eval/Diagnostics tooling.

Simple nav remains:

```text
Home
Stories
Ask
Reports
Watches
```

Any Simple-nav change requires explicit product evidence and review.

---

# 48. STAGE GATES

## 29A — Temporal Truth

PASS only if:

```text
as-of evidence excludes later knowledge

historical Story reads preserve earlier identity/correction state

Report revision differences have canonical causes

Historical Ask grounds only from as-of material

Historical Ask refuses when as-of evidence is insufficient

un-confirmation preserves historical support while changing current support

permanent semantic cases execute real code
```

## 29B — Closed-Loop Intelligence

PASS only if:

```text
Watch -> evidence -> Claim -> Story is proven

corrections propagate without rewriting history

dependency discovery changes current corroboration immediately

Question -> Gap -> Task -> canonical evidence -> reevaluation is proven

no alternate evidence path exists

material-change explanation uses canonical causes
```

## 29C — Comparative Validation Readiness

PASS only if:

```text
dogfood environment is explicitly configured and running once inputs exist

telemetry collects

human usefulness log exists

Full/Lite paired benchmark remains contract-valid

controlled validation passes
```

Final Phase 29 acceptance additionally requires:

```text
sufficient dogfood window

frozen dogfood snapshot

real Full-vs-Lite run

blind scoring

preregistered decision rule applied
```

## 29D — Product Decision Gate

PASS only if:

```text
capability survival review completed

Full-vs-Lite conclusion stated honestly

dogfood utility/correction conclusion stated honestly

Phase 30 scope generated from evidence

features not earning complexity are simplified/deferred/removed in the plan
```

---

# 49. ENGINEERING ACCEPTANCE

At implementation completion run:

```text
python -m compileall -q newsroom tests

full pytest

ruff

frontend lint/typecheck/build

fresh migration

accepted-schema -> latest

repeat migration

PRAGMA foreign_key_check

application integrity

logical Class A/B export/import

eval corpus validation

normal eval baseline including new temporal semantics

Full/Lite contract validation

git diff --check
```

Mypy may remain under the documented informational policy unless the baseline becomes tractable.

No command may be reported PASS unless actually executed.

---

# 50. INTELLIGENCE VALUE ACCEPTANCE

Phase 29 cannot be accepted merely because engineering gates pass.

It requires:

```text
PHASE_29_INTELLIGENCE_VALUE_REPORT.md
```

covering:

```text
dogfood subject/source set
dogfood duration
corpus size
Source mix

useful Attention rate
Not useful rate
Alert action rate
Research yield
correction burden
Ask refusal/answer behavior
Report revision usefulness
dependency discoveries
human usefulness notes
time-to-first-value
estimated provider cost

Full-vs-Lite scores by category
blind-scoring method
effective provider/model validation
latency/cost comparison

where Full clearly won
where Lite matched or won
where both failed
```

No spin.

---

# 51. REQUIRED FINAL PRODUCT VERDICT

Choose exactly one:

```text
A. INTELLIGENCE THESIS PROVEN
   Proceed to Phase 30 shipping.

B. INTELLIGENCE THESIS PARTIALLY PROVEN
   Simplify named capabilities and run one bounded validation tranche.

C. LITE EFFECTIVELY EQUIVALENT
   Collapse architecture/product surface before Phase 30.

D. CORE VALUE NOT PROVEN
   Do not enter Phase 30 as currently conceived.
```

This decision must happen before Phase 30.

---

# 52. STRONG RESULT EXAMPLES

Strong evidence would include cases where:

```text
Full catches dependency/correction/temporal issues Lite misses

Full explains exactly why a conclusion changed

Ask refuses where Lite overreaches

Research produces new canonical evidence that changes a Question

dogfood regularly produces useful "what changed" output

correction burden remains low

extra latency/cost is justified by intelligence advantage
```

---

# 53. FAILURE EXAMPLES

Failure includes:

```text
richer metadata but no more trustworthy conclusions

dependency machinery rarely changes decisions

Historical Ask is technically correct but not useful

Research mostly rediscovers known material

manual correction burden is high

Lite matches Full on the moat categories

benchmark/dogfood criteria move after results appear
```

Do not hide failure behind engineering sophistication.

---

# 54. CHECKPOINT / COMMIT STRATEGY

Suggested coherent checkpoints:

```text
1. Phase 29A temporal authority / Historical Ask

2. Phase 29A executable temporal semantic evals

3. Phase 29B closed-loop proof / missing glue

4. Phase 29B material-change explanation

5. Phase 29C dogfood instrumentation / controlled validation readiness

6. Phase 29D intelligence-value report / Phase 30 planning reconciliation
```

Use fewer if naturally smaller.

Avoid microcommit confetti.

Do not push.

Dogfood data should not be casually committed to source control.

---

# 55. ENGINEERING COMPLETION REPORT

Report:

```text
starting branch / HEAD / schema / worktree

final HEAD / schema / worktree

commits

tables added/removed
Class A/B/C classification for every new table

routes added/removed
nav before/after

tests before/after
semantic eval cases before/after

migration results

Historical Ask implementation
as-of read implementation

closed-loop Research proof

material-change cause model

Full/Lite readiness

dogfood state
```

Distinguish:

```text
implemented
tested
dogfooded
comparatively proven
```

---

# 56. INTELLIGENCE VALUE REPORT

After the evidence window, produce:

```text
docs/reviews/PHASE_29_INTELLIGENCE_VALUE_REPORT.md
```

Include:

```text
method
frozen benchmark contract
dogfood setup
data-quality limitations
results
category scores
human usefulness observations
correction burden
cost/latency
falsification findings
feature survival decisions
recommended Phase 30 scope
```

A skeptical reviewer must be able to inspect the same evidence and disagree.

---

# 57. PHASE 30 HANDOFF

Phase 30 is:

> **SHIP THE PRODUCT**

It should contain only capabilities justified by Phase 29.

Possible evidence-driven categories:

```text
intent-first onboarding
Watch creation/backfill
Source templates/catalog
diff-first Reports
notification delivery
packaging/installer
primary-source connector expansion
UX polish
performance/recovery/retention
commercial defaults
```

Phase 30 must not contain:

```text
proof that the intelligence is useful
fundamental epistemic corrections
large speculative research abstractions
```

---

# 58. FINAL ACCEPTANCE QUESTION

At the end of Phase 29 ask:

> **If Newsroom Lite were free to build and maintain, what concrete intelligence would we lose by deleting Full Newsroom's evidence, correction, dependency, Story, and Research architecture?**

A weak answer such as:

```text
Full has richer metadata and more features.
```

means Phase 29 failed.

A strong answer is demonstrated by concrete cases, for example:

```text
Lite counted syndicated reporting as corroboration,
missed that a formerly supported Claim had been corrected,
could not reconstruct what was knowable two weeks earlier,
and failed to pursue the evidence Gap that later changed the Research Question.

Full handled all four with exact provenance.
```

That is the standard.

The intended endpoint is not:

> **The architecture works.**

It is:

> **The architecture produces better longitudinal intelligence, and we can prove where and why.**
