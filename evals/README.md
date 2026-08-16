# Evaluation Harness

Evaluation is a release subsystem, not an afterthought.

- `corpus/`: human-labeled cases for discovery, event identity, claims, evidence,
  contradiction, corrections, and source quality.
- `fixtures/`: frozen retrieval inputs used for deterministic replay.

Do not commit copyrighted full-text material unless storage/use is permitted.
Prefer compact fixtures containing the minimum source material required for the
specific evaluation case, with provenance and retrieval timestamps.
