# Evaluation Subsystem — Contract, Corpus, Metrics, Replay, Baseline

Evaluation is a permanent product subsystem (`newsroom.evals`). It answers:
*how will we prove that standalone evidence-first Newsroom is actually better
than the v1 reference?*

- CLI: `python -m newsroom.evals {validate,list,summary,lite-contract,replay,baseline,score}`
- Case schema: `newsroom/evals/schema.py`
- Metrics: `newsroom/evals/metrics.py`
- Replay: `newsroom/evals/replay.py`
- v1 baseline: `newsroom/evals/baseline.py`
- executable semantic cases: `newsroom/evals/semantic.py`
- Full/Lite contract runners: `newsroom/evals/benchmark.py` and
  `newsroom/evals/lite.py`

## 1. Case taxonomy

Every case carries exactly one `case_type`. The corpus deliberately spans the
difficult cases, not just easy announcements.

| code | description |
|------|-------------|
| `official_announcement` | simple official announcement |
| `multi_outlet` | one event reported by many outlets |
| `similar_distinct_events` | similar-but-distinct events, same subject |
| `developing_story` | developing / breaking story |
| `rumor_confirmed` | rumor followed by confirmation |
| `rumor_unsubstantiated` | rumor remaining unsubstantiated |
| `conflicting_reports` | conflicting credible reports |
| `official_correction` | official correction |
| `changing_numeric_claim` | numerical/date claim changing over time |
| `primary_vs_secondary` | primary source vs secondary reporting |
| `cross_topic` | cross-topic story |
| `stale_recycled` | stale / recycled article |
| `low_quality_noise` | low-quality aggregation / noise |
| `duplicate_syndication` | duplicate publication / syndication |
| `corroboration_no_update` | corroboration with no material update |
| `material_update` | genuine material story update |
| `mutating_document` | source document changes after retrieval |
| `ambiguous_merge` | ambiguous merge where false merge is harmful |

## 2. Corpus

Location: `evals/corpus/cases/*.json`. Fixtures: `evals/fixtures/*.json`.

Sources of the initial 30 cases:

- **Real v1-derived (4 cases)** — extracted read-only from the completed Hermes
  Newsroom dev and prod SQLite databases. These use the actual stories, sources,
  URLs, and titles v1 produced. Provenance records the source DB path.
- **Synthetic edge cases (26 cases)** — reserved-domain (`.test`) entities and
  facts designed from real-world failure modes observed during v1 review
  (rumor/confirmation, corrections, false merges, changing figures, mutating
  pages). They are labeled "synthetic" in `provenance` and are *not* real
  reporting; they exist to exercise deterministic pipeline behavior precisely.

**Content/provenance policy:** no copyrighted full-text is stored. Cases contain
metadata (URLs, titles, publishers, timestamps), content hashes, and short
factual excerpts only. v1-derived cases store metadata, never article bodies.

### Case model

`EvaluationCase` — case_id, title, description, case_type, monitored_targets,
observation_window, provenance, reviewer_notes, candidates, gold_groups,
gold_claims, gold_evidence, expected_primary_sources, noise_candidates,
contradictions, material_changes, and optional machine-verifiable
`semantic_assertions`.

Referential integrity is machine-validated: groups reference known candidates,
claims reference known events, evidence references known claims and candidates,
contradictions reference known claims and evidence, and primary/noise lists
reference known candidates.

## 3. Metric definitions

The current corpus contains 38 bounded cases: 30 established cases plus eight
Phase 28.875 regressions covering late dependency discovery, conservative
absence language, Ask evidence-sufficiency refusal, late Story correction and
split handling, dependency-group support, correction-versus-contradiction
semantics, and silent DocumentVersion edits. These cases use the same
canonical evidence ledger; they do not create a second truth path.

Simple/Advanced navigation density, Attention acknowledgement, hypothesis
provenance, migration history, and other product invariants are covered by
engineering and integration tests, not misrepresented as corpus cases.

Coverage, Blind Spots, persisted evidence families, and fragility scores are
not runtime evaluation targets. Knowledge-time and historical-time Ask
semantics remain deferred until the Phase 29A benchmark contract is frozen.

All metrics are pure functions of a gold `EvaluationCase` and a `Prediction`.
Predictions are provider-neutral structured outputs (see
`newsroom/evals/prediction.py`). The eight closure cases are executed by
`SemanticCaseRunner` against fresh migrated SQLite databases through the real
Ask, SourceRobustness, StoryCorrection, Evidence, and DocumentVersion
services; their observed values are then scored. The normal `baseline` CLI
includes both the v1 results and these semantic assertion results.

### Lite comparator

The frozen Lite contract is `evals/lite/20q_contract.json` and is validated by
`python -m newsroom.evals lite-contract`. A benchmark run must bind to an
immutable SQLite online-backup snapshot whose document-corpus manifest matches
the contract, and its synthesis adapter must declare the exact contracted
provider, model, prompt version, temperature, context budget, retrieval limit,
and citation limit. It retrieves Documents with SQLite FTS5 only. Lite does
not read Claims, Stories, Coverage, or dependency groups; synthesis and
document citations are supplied by the contracted model route through
`newsroom/evals/lite.py`. Arbitrary databases and production callables are
rejected; deterministic callables are available only through the explicit
`run_with_test_double` seam. `FullBenchmarkRunner` uses the real Ask adapter,
and `PairedBenchmarkOrchestrator` rejects snapshot, corpus, question-contract,
model/config, or blinding mismatches. No Full-vs-Lite quality verdict has been
run.

### Table-count convention

When reporting schema size, `base tables` means all SQLite tables excluding
`search_fts` and every FTS virtual/shadow table. Report SQLite total, FTS
virtual/shadow count, base count, and logical-export table count separately.

### Event / Story metrics (pairwise over candidate documents)

Let `S_g` be the set of unordered document pairs gold places in the same event,
and `S_p` the pairs a prediction places in the same story. Over all candidate
pairs:

- **true positives** = `S_g ∩ S_p`
- **false merges** = `S_p − S_g` (predicted same, gold different)
- **false splits** = `S_g − S_p` (gold same, predicted different)

Then:

- `precision = |S_g ∩ S_p| / |S_p|` (1.0 if `S_p` empty)
- `recall    = |S_g ∩ S_p| / |S_g|` (1.0 if `S_g` empty)
- `false_merge_rate = |S_p − S_g| / |pairs not in S_g|`
- `false_split_rate = |S_g − S_p| / |S_g|`
- `duplicate_rate` = fraction of gold events covered by more than one predicted
  story (per-event duplication measure)
- `f1 = 2·precision·recall / (precision + recall)`
- `candidate_coverage` = predicted candidate documents covered by at least one
  predicted Story / all case candidates. Pairwise precision and recall are
  multiplied by this coverage so empty or partial predictions cannot receive a
  perfect event score.
- `important_story_recall` = important gold Events covered by at least one
  predicted candidate / important gold Events. A gold Event is important when
  it has at least one `major` gold Claim.

Vacuous-truth: when no merges are predicted (or expected), precision/recall are
1.0 — there are no merge errors. This makes "keep N distinct events separate"
  score correctly.

### Claim metrics

Claims are matched gold↔predicted by normalized proposition text (casefold +
whitespace collapse). `important` = `importance == "major"`.

- `important_claim_recall` = matched important gold claims / important gold claims
- `all_claim_recall` = matched gold claims / all gold claims
- `claim_precision` = matched predicted claims / predicted claims
- Claim matches require both the normalized proposition and the correct gold
  Event. `expected_state_accuracy` measures the fraction of matched Claims
  whose predicted state equals the gold `expected_state`.

### Evidence metrics

- `citation_correctness` = fraction of predicted claim→evidence links whose
  (claim, candidate, span) matches a gold evidence span for that claim.
- `evidence_coverage` = fraction of gold evidence spans matched by ≥1 correct link.
- `contradiction_detection` = recall of gold contradictions (a gold
  contradiction is detected when a predicted contradiction links the matched
  claim to the contradicting evidence's candidate).
- `unsupported_proposition_rate` = fraction of synthesized propositions whose
  `claim_ids` do not reference only accepted predicted Claims. Accepted states
  for this metric are `supported` and `partially_supported`; pending,
  disputed, unsubstantiated, and superseded Claims do not ground synthesis.
  This is the Phase-0 measurable proxy for the closed-world synthesis invariant.

### Semantic assertions

Cases may declare `semantic_assertions` with a stable id, metric name, and
expected JSON value. Predictions provide `semantic_results`; scoring accepts
the assertion id (and supports the metric name as a compatibility alias) and
reports assertion count, pass count, and failed ids. This is the bounded
machine-verifiable layer for refusal codes, current-versus-historical Story
state, dependency-group counts, and distinct document hashes; it does not
invent unsupported domain states.

### Primary source

- `primary_source_recall` = matched expected primary candidates / expected.
- `primary_source_precision` = matched / predicted primary candidates.
- `false_primary_count` = predicted primary candidates not in gold.

### Economics / operations

From the prediction `usage` record: acquisition_requests, paid_requests,
local_model_calls, frontier_calls, latency_ms, cost_usd. Derived:
`useful_story_count` (predicted stories containing ≥1 gold-grouped candidate) and
`cost_per_useful_story = cost_usd / useful_story_count`. "Cost per resolved
Research Question" is defined but not computed in Phase 0 (no such object yet).

There is intentionally **no single opaque quality score** in Phase 0.

## 4. Deterministic replay

A fixture (`evals/fixtures/<case_id>.json`) is a frozen, normalized capture of a
retrieval step. Replay (`newsroom/evals/replay.py`):

1. loads the fixture JSON;
2. verifies `schema_version`;
3. recomputes the whole-document `content_hash` and compares to the stored value;
4. re-normalizes each document through the ported deterministic modules
   (`url_norm.normalize_url`, `similarity.normalize_headline`,
   `event_sig.normalize_event_signature` / `fallback_event_key`);
5. returns stable `NormalizedCandidate`s plus a `replay_hash`.

Guarantees (each covered by a test):

- **integrity** — a tampered `content_hash` fails clearly;
- **determinism** — the same fixture always yields the same `replay_hash`;
- **no network** — replay only reads local data and hashes strings; a test
  patches `socket.create_connection`/`socket.socket.connect` to raise, and replay
  still completes;
- **invalid data** — wrong schema version, empty documents, duplicate candidate
  ids, malformed timestamps, invalid content types, and bad URLs all fail with
  a precise `ValidationError`. Case and prediction boundaries likewise reject
  invalid IDs, references, enums, duplicate assignments, and negative usage.

Replay is provider-neutral: evaluation code consumes the normalized form, not a
provider's raw response.

URL identity is scheme-, hostname-, and non-default-port-aware. HTTP(S) URLs
without a host are rejected before they can enter a case, fixture, or dedupe
decision.

## Phase 27 Story correction measures

`newsroom.evals.story_intelligence.story_correction_metrics` scores current
Claim membership, historical membership, merge targets, split children, and
stale current context separately from the existing pairwise clustering
metrics. It also reports bounded manual-correction burden per 100 automatic
assignments. Production counts and time-to-correction are derived from
`claim_story_assignment_history`, `story_corrections`, and duplicate decision
records through `GET /api/v1/story-intelligence/metrics`.

## 5. v1 baseline

`newsroom/evals/baseline.py` scores the completed v1 implementation's *actual*
behavior against gold. A committed, metadata-only export
(`evals/baseline/v1_predictions.json`) maps v1 stories/sources to corpus
candidates. It is regenerable from the read-only v1 databases via
`extract_v1_db`, which opens the databases with `mode=ro` and never writes.

**Methodology and limits:**

- v1 produced story groupings and primary-source flags, **not** a
  Claim/Evidence Ledger. Claim-level and evidence-level metrics are therefore
  not computed for v1 (the export has no claims/evidence); event/grouping and
  primary-source metrics are the meaningful comparison.
- The `duplicate_syndication` case false-splits in v1 only because the two v1
  profiles never shared a database — an environment artifact, not an algorithm
  defect, and documented as such.
- The `primary_vs_secondary` case records that v1 marked a secondary "in talks"
  report as primary while no primary source was retrieved — a real finding the
  standalone product must improve on.

## 6. Reproduction

```powershell
python -m pytest -q                    # all tests, no network / Hermes / paid API / v1 DB
python -m newsroom.evals validate      # corpus integrity
python -m newsroom.evals summary       # taxonomy distribution
python -m newsroom.evals lite-contract  # frozen Lite contract integrity
python -m newsroom.evals baseline      # v1 baseline vs gold
python -m newsroom.evals replay <id>   # deterministic replay of one case
```
