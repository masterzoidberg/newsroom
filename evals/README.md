# Evaluation Harness

Evaluation is a release subsystem, not an afterthought. See `docs/EVALUATION.md`
for the full contract, taxonomy, metric definitions, replay, and baseline
methodology.

- `corpus/cases/`: human-labeled cases (JSON) for discovery, event identity,
  claims, evidence, contradiction, corrections, and source quality.
- `fixtures/`: frozen retrieval inputs used for deterministic replay.
- `baseline/v1_predictions.json`: metadata-only export of v1 story groupings and
  primary sources, used to score the reference implementation against gold.

## Commands

```powershell
python -m newsroom.evals validate
python -m newsroom.evals list
python -m newsroom.evals summary
python -m newsroom.evals replay <case-id>
python -m newsroom.evals baseline
python -m newsroom.evals score <case-id> --prediction <file.json>
```

Do not commit copyrighted full-text material unless storage/use is permitted.
Fixtures contain the minimum metadata, URLs, hashes, and short factual excerpts
required for the specific evaluation case, with provenance and retrieval
timestamps.
