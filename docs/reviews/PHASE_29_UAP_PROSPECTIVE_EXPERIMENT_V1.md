# Phase 29 UAP prospective comparative experiment v1

Status: preregistered on 2026-09-06; no outcomes collected or scored.

Experiment ID: `newsroom-phase29-uap-20q-v1`

This is a new prospective experiment. It does not modify the frozen
`newsroom-lite-20q-v1` contract, its questions, its corpus, or its cutoff.
It exists because the frozen contract is a historical benchmark and cannot
answer the prospective UAP Watch value question by substituting a later
runtime snapshot.

## Question set

The experiment has twenty fixed question slots, four per architecture-dependent
category. The text is fixed now; the evidence unit is selected later by the
rules below, not by output quality or operator preference.

| ID | Category | Fixed prompt template |
|---|---|---|
| U01 | dependency-aware corroboration | Which retrieved items concern the same UAP event, and which known dependency groups do they form? |
| U02 | dependency-aware corroboration | How many known dependency groups support the event after lineage evidence is applied? |
| U03 | dependency-aware corroboration | What later lineage fact changes the interpretation of earlier source agreement? |
| U04 | dependency-aware corroboration | If the strongest source is removed, what corroboration remains, and what does not? |
| U05 | temporal and correction intelligence | What did the eligible evidence support at the earlier knowledge boundary? |
| U06 | temporal and correction intelligence | What later evidence or correction changed the current conclusion? |
| U07 | temporal and correction intelligence | Which DocumentVersion is later, what changed, and what remains historically true? |
| U08 | temporal and correction intelligence | What did Newsroom know before the later evidence arrived, and what must not be back-projected? |
| U09 | grounded refusal and uncertainty honesty | Which proposition is established by exact evidence, and which parts remain uncertain? |
| U10 | grounded refusal and uncertainty honesty | Can this corpus establish the requested negative, or should Newsroom refuse or qualify it? |
| U11 | grounded refusal and uncertainty honesty | Does absence of a retrieved report establish that the event or response did not happen? |
| U12 | grounded refusal and uncertainty honesty | Is the available source set sufficient for a definitive answer? State the calibrated outcome. |
| U13 | longitudinal material-change explanation | What materially changed in the current Story or Report? |
| U14 | longitudinal material-change explanation | Which canonical evidence or Claim state caused the material change? |
| U15 | longitudinal material-change explanation | Was the new item a material update, a correction, a dependency discovery, or repetition? |
| U16 | longitudinal material-change explanation | What remains unchanged, what is no longer supported, and why? |
| U17 | Research usefulness and canonical question reevaluation | What canonical Research Gap remains open for this UAP question? |
| U18 | Research usefulness and canonical question reevaluation | Which next source class or bounded Research Task would most reduce that Gap? |
| U19 | Research usefulness and canonical question reevaluation | Did the Research result add canonical evidence that changed the Question state? |
| U20 | Research usefulness and canonical question reevaluation | Was the Research result actionable, evidence-grounded, and honest about what it did not establish? |

## Evidence-unit selection

After the minimum observation window, create one immutable evidence snapshot from
the dedicated `phase29-trial/prod` runtime. Include the approved eight Source
IDs and canonical DocumentVersions observed at or after
`2026-09-06T21:20:48Z`. Retain the clean pre-boundary baseline rows needed to
answer an as-of question, but do not include A3 rehearsal objects. The final
cutoff is the snapshot's exact UTC creation time and is recorded in the bound
contract.

For each category, select up to four eligible evidence units using this fixed
order:

1. satisfy the minimum evidence rule for that category;
2. sort by earliest qualifying `DocumentVersion.retrieved_at`, then stable
   canonical ID;
3. take the first four; and
4. mark the category inconclusive if fewer than four are available.

No unit may be selected because Full or Lite appears likely to win. A unit may
be used by more than one question only when the question asks a different
pre-registered category property; the scorer records that reuse explicitly.

Minimum evidence:

- Dependency: at least two relevant Documents and a known or testable lineage
  relationship. Without lineage evidence, the question is unavailable rather
  than scored as independent corroboration.
- Temporal/correction: at least two knowledge-time or DocumentVersion states,
  or one canonical correction/retraction with preserved history.
- Refusal/uncertainty: at least one sufficient-evidence case and one bounded
  insufficiency/absence case. If only one side exists, the category is
  inconclusive.
- Material change: a Story or Report revision, or a canonical Claim/dependency
  change, with an inspectable cause. A new document alone is not enough.
- Research: a Question, Gap, or Task and a result that either entered normal
  acquisition/canonical evidence or was truthfully recorded as yielding no
  material evidence.

The final result must retain the selected unit IDs, excluded eligible units,
selection order, and reason for every unavailable slot.

## Execution identity and budget

Both sides use the same requested controlled route:

```text
provider: openai
model: gpt-4o-mini
temperature: 0.0
deterministic: true
prompt_version: phase29-uap-synthesis-v1
context_budget_tokens: 6000
retrieval_limit: 8
citation_limit: 8
```

The exact effective provider, model, route, fallback flag, settings, latency,
cost, refusal state, corpus manifest, cutoff, and execution validity are
recorded for every pair. The controlled allowance is at most 20 questions per
side, 40 provider calls total, and a deliberately bounded estimated maximum of
`$2.00` total. No paid call is permitted in the unattended Watch. A provider
outage produces an invalid/incomplete pair; it does not authorize a silent
fallback or a changed retry route.

This prospective specification is not yet passed to the historical v1 loader:
the current loader intentionally enforces the frozen q01–q20/case binding. A
future execution must add an explicit UAP evidence manifest and contract binding
or fail closed. It must not make the UAP snapshot look like a v1 corpus case.

## Scoring and inconclusive outcome

Each answer receives the frozen common dimensions—factual correctness,
evidence/citation entailment, citation completeness, and refusal/calibration—on
the 0–2 scale. Each question also receives its one category dimension on the
same 0–2 scale. Category results use the mean category dimension over eligible
paired questions and show the common trustworthiness dimensions separately.

An invalid execution receives no ordinary quality score. A category with fewer
than four eligible units, or without its minimum evidence, is inconclusive and
cannot count as a Full advantage. The prospective result must report all
inconclusive categories rather than impute them.

The Phase 29 decision rule remains unchanged: Full needs a clear advantage in
at least three of five architecture-dependent categories and no material
trustworthiness regression. A tie is not an advantage. A Full-only result must
be a concrete structural result, not a stylistic preference.
