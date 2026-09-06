# Phase 29 Full-versus-Lite evaluation protocol

Status: frozen before comparative outcomes; preregistered 2026-09-06.

Protocol implementation: `phase29-evaluation-protocol-v1`.

This document freezes the comparison procedure. It does not contain Full/Lite
outcomes, human preference scores, or a Phase 29 intelligence-value verdict.

## Authority

The governing sources, in descending implementation authority, are:

- `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md`;
- `plan/phases-v2/Phase 29.md`, `Phase 29.5.md`, and `Phase 29.6.md`;
- `docs/EVALUATION.md` and the executable code under `newsroom/evals/`;
- `docs/reviews/PHASE_29_DECISION_RULE.md`;
- `docs/reviews/PHASE_29_BASELINE_ACCEPTANCE.md`;
- `docs/reviews/PHASE_29_TRIAL_READINESS.md`;
- `docs/reviews/PHASE_29_PIPELINE_REHEARSAL.md`;
- `docs/reviews/PHASE_29_HUMAN_USEFULNESS_LOG_TEMPLATE.md`; and
- `docs/DOGFOOD_CONTRACT.md` and `PHASE_29_OBSERVATION_PROTOCOL.md`.

The current engineering baseline is schema 36 and descends from the accepted
A3 commit `9dea30949cf5a17dc4fb6e95eaad098f6e8e707b`.

## Experiment question

The controlled comparison asks:

> Given exactly the same frozen evidence basis, question set, requested route,
> and effective execution conditions, does Full Newsroom produce materially
> better longitudinal, evidence-grounded intelligence than Lite on the
> architecture-dependent tasks that justify the extra architecture?

The comparison is one evidence source. The four-week UAP dogfood observation
is a separate evidence source. Neither substitutes for the other.

The frozen historical benchmark is not itself a prospective UAP product-value
test. The UAP-specific prospective experiment is preregistered separately in
`PHASE_29_UAP_PROSPECTIVE_EXPERIMENT_V1.md`.

## Frozen contracts and eligibility audit

### Historical contract: `newsroom-lite-20q-v1`

The file `evals/lite/20q_contract.json` remains immutable. It specifies:

```text
corpus cutoff:       2026-08-25T00:00:00Z
questions:           q01–q20
provider/model:      openai / gpt-4o-mini
temperature:         0.0
deterministic:       true
prompt version:      lite-document-synthesis-v1
context budget:      6000 tokens
retrieval:           SQLite FTS5, document-only, BM25, limit 8
citations:           limit 8
scoring:             four dimensions, 0–2 each
```

It binds questions to fixed case IDs in `evals/corpus/cases/`, not to the
prospective runtime Watch. Its source cases are a mixture of synthetic edge
cases and historical/v1-derived metadata. A later UAP database snapshot cannot
be substituted into this contract while retaining its identity.

The current loader validates that the declared case IDs exist and that a run is
bound to one SQLite manifest hash. It does not prove that a bound database
contains every declared case candidate or that all rows satisfy the cutoff.
Therefore a final historical run is invalid unless an external snapshot
manifest explicitly maps every declared case candidate to its eligible source,
Document, DocumentVersion/content hash, and cutoff status. The protocol wrapper
adds the cutoff audit; the operator must preserve that manifest with the raw
run.

### Question-by-question evidence audit

| Question | Frozen case/evidence basis | Primary measurement |
|---|---|---|
| q01 | `official-announcement-product-launch`: one Acme first-party announcement and one supported claim | factual retrieval guardrail |
| q02 | `changing-death-toll`: claims/evidence for 5, 20, and 40; earlier claims superseded | temporal change signal |
| q03 | `correction-earnings`: secondary $1.2B report followed by official $1.1B correction | correction signal |
| q04 | `official-announcement-regulatory-rule`: one government final-rule source and claim | factual retrieval guardrail |
| q05 | `primary-vs-secondary-nous-funding`: only an “in talks” secondary report; closed funding is unsubstantiated | evidence calibration guardrail |
| q06 | `developing-story-outage`: partial outage followed by full outage/resolution in a later document | evolving-story signal |
| q07 | `conservative-absence`: unrelated retrieval only; expected outcome is uncertainty/refusal | grounded refusal |
| q08 | `rumor-unsubstantiated-exec`: one unconfirmed rumor, no confirmation | grounded refusal |
| q09 | `conservative-absence`: absence of retrieved reporting cannot establish absence | grounded refusal |
| q10 | `single-dependency-group-support`: three publications share one known dependency group | refusal plus dependency calibration |
| q11 | `late-dependency-discovery`: primary and derivative documents become one known group | dependency-aware corroboration |
| q12 | `single-dependency-group-support`: primary plus two rewrites, one dependency group | dependency-aware corroboration |
| q13 | `duplicate-syndication-hermes-v0201`: identical canonical URL across isolated profiles | dependency/identity calibration |
| q14 | `late-dependency-discovery`: later lineage fact changes earlier apparent agreement | dependency-aware corroboration |
| q15 | `silent-document-edit-version`: same document identity with distinct before/after hashes | DocumentVersion change |
| q16 | `late-story-correction`: current membership changes while correction history remains | correction/history signal |
| q17 | `late-story-split`: similar events split into distinct current Stories with prior history | Story-history signal |
| q18 | `official-announcement-product-launch`: future announcement is not in evidence | refusal guardrail |
| q19 | `single-dependency-group-support`: no evidence of a secret coordinating source | refusal/dependency guardrail |
| q20 | `rumor-unsubstantiated-exec`: private motive is not established | refusal guardrail |

### Five architecture-dependent categories

The exact categories are those in `PHASE_29_DECISION_RULE.md`:

1. dependency-aware corroboration;
2. temporal and correction intelligence;
3. grounded refusal and uncertainty honesty;
4. longitudinal material-change explanation; and
5. Research usefulness and canonical question reevaluation.

For the frozen historical q01–q20 set:

| Category | Eligible questions | Minimum evidence | Coverage status |
|---|---|---|---|
| dependency-aware corroboration | q11–q14; q10 is a refusal cross-check | known lineage/dependency groups and at least two related documents | covered for fixed historical cases |
| temporal and correction intelligence | q02, q03, q06, q15–q17 | distinct knowledge-time/version states or preserved correction/split history | covered for fixed historical cases, not the UAP Watch |
| grounded refusal and uncertainty honesty | q07–q10, q18–q20 | bounded sufficient and insufficient/absence cases | covered for fixed historical cases |
| longitudinal material-change explanation | q15–q17, with q02/q03 as change cross-checks | canonical Story/Report revision and exact cause, not merely a new document | partial; the frozen questions do not provide full Report-cause coverage |
| Research usefulness and canonical question reevaluation | none | Question → Gap → Task → canonical evidence/result → reevaluation | uncovered; inconclusive |

The historical contract therefore cannot validly establish the Phase 29 product
decision for the prospective UAP trial. It is a useful fixed historical
benchmark and engineering signal, but it is not both a historical benchmark
and a prospective UAP comparison. The separate
`newsroom-phase29-uap-20q-v1` experiment is the preregistered prospective
tranche. No v1 question, expected evidence, provider, or cutoff is changed.

An uncovered or under-covered category is **inconclusive**, never a Full win,
Lite win, or manufactured pass. The same rule applies if the prospective UAP
tranche lacks its category minimum evidence.

## Category scoring and decision rule

The historical v1 common rubric remains its four dimensions: answer
correctness, citation entailment, citation completeness, and conservative
refusal, each scored 0–2. The prospective UAP tranche adds one pre-registered
category dimension per question, also 0–2, as specified in its separate
experiment record. Category means are calculated before any identity reveal.

`0` means false, unsupported, materially incomplete, or unsafe for that
dimension; `1` means partially correct, qualified, or incomplete but useful;
`2` means correct, sufficiently complete, and appropriately grounded. A
category-specific `2` requires the structural evidence named by that category;
polished prose does not qualify.

- A tie is not an advantage.
- Both good is a tie unless one side has the pre-registered Full-only
  structural result.
- Both bad remains visible as two low scores; it is not converted to a win.
- A refusal is good when evidence is insufficient and calibrated; it is weak
  when evidence is sufficient and the answer was available.
- A concrete Full-only result means Full scores 2 on the category property,
  Lite scores 0, and the difference is supported by an exact canonical
  evidence/lineage/history fact rather than style.

The unchanged Phase 29 rule is:

> Full must show a clear advantage in at least three of five
> architecture-dependent categories, with no material trustworthiness
> regression.

Basic factual retrieval, latency, and cost are reported separately. They do
not erase a structural-category failure.

## Trustworthiness gates and invalidity

### Valid but weaker output

The following remain valid executions and receive ordinary rubric scores,
including a zero where appropriate:

- unsupported synthesis or a proposition not entailed by accepted evidence;
- incorrect citation or citation to the wrong DocumentVersion;
- fabricated evidence, nonexistent span, or invented source identity;
- false Story merge or failure to merge a clearly same Story where material;
- refusal when the frozen evidence is sufficient; and
- answering as established fact when the frozen evidence is insufficient.

These are quality/trustworthiness disadvantages, not reasons to discard an
unfavorable result. Fabricated evidence or materially wrong citations also
trigger the no-material-regression gate.

### Invalid execution

The pair receives no ordinary quality score and cannot be called a valid
comparison when any of these occurs:

- the source snapshot, manifest hash, eligible case mapping, or cutoff differs;
- Full or Lite uses a different requested/effective provider, model, prompt,
  temperature, context, retrieval limit, or citation limit;
- an unapproved fallback, hidden provider, or route substitution occurs;
- requested or effective execution metadata is missing or contradictory;
- the run reads later-than-cutoff evidence for a historical/as-of contract;
- a timeout, provider outage, interruption, or partial envelope leaves the pair
  incomplete;
- an automatic retry changes the provider, model, route, or contract settings;
- the run executes against the only immutable source snapshot rather than an
  identified execution copy; or
- output is a test double, rehearsal artifact, or other non-production result
  presented as a scored production run.

An invalid run is retained with its failure reason and cannot be silently
replaced or relabeled. A later retry is a new attempt and must preserve the
original invalid record.

## Effective execution identity

Every pair must retain, for both sides:

- requested provider and model;
- effective provider and model;
- provider route, paid/local identity, and fallback flag;
- temperature, deterministic flag, prompt version, context budget, retrieval
  limit, and citation limit;
- immutable source snapshot path, manifest hash, eligible DocumentVersion
  identity, and cutoff;
- contract/question version and question ID;
- pair latency, side latency where available, actual cost, and cost source;
- refusal/uncertainty state;
- raw provider usage where available; and
- execution validity and all mismatch fields.

Configuration labels are not evidence of effective identity. The existing
`verify_execution` and `PairedBenchmarkOrchestrator` checks remain mandatory.
`ResumablePairRecorder` adds the operator-layer fields and preserves the raw
envelopes without reducing them to an aggregate score.

## Corpus snapshot and binding procedure

1. Stop or quiesce API/worker/scheduler writers for the source backup.
2. Use `freeze_corpus_snapshot` to create an online SQLite backup outside the
   repository from the explicitly named source runtime/database.
3. Verify SQLite/application integrity, compute the SHA-256, compute the
   existing `corpus_manifest`, and write the protocol `snapshot_manifest`
   containing cutoff, eligible DocumentVersion IDs, excluded post-cutoff IDs,
   case-to-document mapping, Source IDs, and repository commit.
4. Bind the frozen contract with `bind_contract`. Store the resulting binding
   and the separate snapshot manifest together. Recompute both before running.
5. Mark the source snapshot immutable/read-only. Never run Ask against it.
6. For each question, create a fresh execution copy from the immutable source
   snapshot. Full and Lite use the same per-question copy so the existing
   orchestrator's same-path identity check remains meaningful; Full's Ask audit
   writes stay in the copy. Preserve the copy or its hash for audit, and never
   let those writes alter the evidence manifest.
7. Reject the run if any document version is outside the frozen cutoff or if a
   declared historical case lacks an exact manifest mapping.

The prospective UAP snapshot uses the approved Watch runtime and the
selection/binding rules in `PHASE_29_UAP_PROSPECTIVE_EXPERIMENT_V1.md`. It is
not permitted to bind that snapshot to `newsroom-lite-20q-v1` merely because
the API accepts an arbitrary SQLite path.

## Full and Lite execution

Full is `FullBenchmarkRunner` through the real `AskService` path. Lite is
`LiteHarness` through document-only SQLite FTS5 retrieval and the contracted
synthesis route. `PairedBenchmarkOrchestrator` must validate shared identity
before execution and effective conditions after each pair.

Frozen behavior:

- Execute in the deterministic blind-plan question order from seed `20260906`.
- For each question, run Full then Lite on the same clean execution copy.
- Do not use automatic retries. A resumed attempt uses the same contract,
  snapshot, and requested route and records a new attempt number.
- Provider timeout/failure produces an invalid or partial record; it never
  silently falls back or changes the route.
- A partial pair is not scoreable, even if one answer looks useful.
- Resume only from the last durable per-question record. Never overwrite raw
  envelopes or replace an invalid attempt.
- Production execution must use the real adapters. Test doubles are allowed
  only in the explicitly marked non-scored rehearsal.

## Blinding

The deterministic seed is `20260906`. The recorder shuffles the frozen
question IDs and independently assigns `system-a`/`system-b` to Full and Lite.
It stores:

- `blind-mapping.operator-only.json`: the mapping and seed;
- `raw-envelopes.jsonl`: unredacted Full/Lite envelopes and execution records;
- `blind-answers.jsonl`: scorer-facing answers with opaque question IDs and no
  runner, scope, provider, model, route, cost, or mapping fields; and
- `run-manifest.json`: identity, status, attempts, and artifact hashes/paths.

The mapping and raw files are operator-only until scoring is complete. The
scorer sees the question, A/B labels, answer, citations, and refusal state.
The scorer does not see Full/Lite identity, provider/model, cost, latency,
snapshot path, case IDs, or the mapping. In this single-operator project,
file separation and delayed reveal reduce avoidable bias but do not create
independent operation or scoring; that limitation is reported.

Identity reveal occurs only after all valid blind scores are durably written.
If a score-entry mistake is found before reveal, append a correction record
with the original row, reason, replacement, timestamp, and scorer; do not
delete or silently edit the original. A correction cannot change the rubric or
the invalidity rules.

## Human scoring rubric

The scorer records one 0–2 score per applicable dimension and a short evidence
note. The applicable dimensions are:

- factual correctness;
- evidence/citation entailment;
- citation completeness;
- conservative refusal/uncertainty calibration; and
- the fixed category dimension for the prospective tranche.

The scorer must mark `not_applicable` only where the pre-registered question
does not test that dimension; no post-hoc dimension may be added. For each
pair the scorer also records `both_good`, `both_bad`, `tie`, `invalid`, or
`one_structural_advantage` as applicable.

Invalid pairs receive no quality score. Both-bad and both-good pairs remain
scored and visible. A refusal is judged against the evidence sufficiency in
the frozen snapshot, not against whether the scorer personally wants an
answer. Citation quality requires the cited DocumentVersion and span to entail
the proposition; a citation to a related but wrong version is not partial
credit for entailment.

## Paid-provider policy

The unattended Watch remains zero-paid-budget: `paid_requests = 0` and
`usd = 0`. The controlled benchmark is a separate, explicitly authorized
allowance. For the historical v1 contract, the requested route is
`openai/gpt-4o-mini`, with at most 20 calls per side and the provider contract's
bounded per-work cap. For the prospective UAP tranche, the separate record
sets a maximum of 40 total calls and `$2.00` estimated total.

No final paid benchmark call is made by this protocol-freeze task. A provider
outage invalidates the affected pair. A paid/local fallback is not a valid
substitute when the requested contract requires the hosted route.

## Non-scored rehearsal

The rehearsal proves mechanics only. It may use a controlled test provider and
test doubles, and must be labeled `test_double=true` and
`scoring_started=false`. It must:

1. load the frozen contract;
2. bind a permitted rehearsal snapshot without changing `20q_contract.json`;
3. create Full and Lite envelopes through the existing runner test seams;
4. verify requested/effective metadata and shared pairing;
5. generate the deterministic blind plan;
6. write resumable raw and blind artifacts; and
7. confirm no human score, identity reveal, or superiority interpretation was
   produced.

The rehearsal is not Phase 29 evidence and is not included in any later
category mean.

## Data retention

Keep outside Git, under an access-controlled evaluation directory:

- immutable source snapshot and SHA-256;
- protocol/corpus manifest and contract binding;
- per-question execution copies or their verified hashes;
- raw Full/Lite envelopes and provider usage;
- blind answers and operator-only mapping;
- resumable manifest, invalid attempts, outage logs, and correction log;
- human scores and scorer notes; and
- final category calculations only after the preceding artifacts are complete.

Do not commit runtime databases, acquired content, secrets, raw provider
credentials, final benchmark results, or human scores.

## Known limitations

- The frozen v1 cases are historical/synthetic and cut off at 2026-08-25;
  they do not represent the later UAP Watch evidence.
- v1 has no Research usefulness/question-reevaluation coverage and only
  partial longitudinal material-change coverage.
- The current benchmark loader does not itself prove case-to-snapshot
  completeness; the external manifest is mandatory.
- A single operator may configure, run, and score the experiment; delayed
  file-separated blinding reduces but does not eliminate that bias.
- The controlled benchmark provider allowance and zero-paid-budget dogfood
  policy are intentionally different.
- Low UAP event volume, source outages, or behavioral changes can make the
  prospective category result inconclusive and require extension or a
  pre-registered segment rather than a rewritten contract.
