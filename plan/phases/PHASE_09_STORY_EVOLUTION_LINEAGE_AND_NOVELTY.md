# Phase 09 — Story Evolution, Lineage, and Novelty

## Objective

Organize incoming evidence into conservative evolving Stories and distinguish
new information from repetition.

## Required work

- Resolve candidates using URL identity, time, entities, location, shared Claims,
  semantic similarity, deterministic exclusions, and adjudication only when
  ambiguity warrants it.
- Classify incoming material as duplicate, corroboration, contradiction,
  qualification, correction, material update, or new Story.
- Track citations, syndication, wire propagation, rewritten reporting, and common
  primary-document lineage.
- Count independent corroboration separately from publication count.
- Build evidence-backed Story timelines and immutable revisions.
- Resurface material updates without destroying saved/dismissed review state.

## Boundaries

When uncertain create a separate Story. Do not introduce a generic knowledge
graph or silently merge based on embeddings, entities, or signatures alone.

## Verification and exit gate

- Dedicated false-merge, false-split, correction, mutation, lineage, and
  corroboration fixtures.
- False merges remain zero on the accepted corpus.
- Repeated reporting is not independent evidence; timelines link to provenance.
- Review state and material-update attention remain independent; full checks pass.

## Completion Record

Completed 2026-08-16.

- Added migration 0008 for Story-document observation links, immutable
  evolution events, document lineage, and revision-document provenance.
- Added conservative candidate resolution using URL/document identity, temporal
  compatibility, entities, locations, shared Claims, bounded text/embedding
  similarity, event attributes, deterministic exclusions, and optional
  ambiguity-only adjudication.
- Added duplicate/corroboration/contradiction/qualification/correction/material
  update classification, independent corroboration counts, evidence-backed
  timelines, immutable lineage/evolution records, and review-independent
  `new_update` resurfacing.
- Added authenticated resolver, processing, timeline, lineage, corroboration,
  evolution, and review API routes.
- Added false-merge/false-split corpus replay coverage plus correction,
  mutation, lineage, corroboration, immutable-record, and review fixtures.
- Verification: `python -m compileall -q newsroom`; `python -m pytest -q`
  (254 passed); `python -m newsroom.evals validate`; deterministic fixture
  replay and Phase 09 corpus grouping checks.
- `poetry run format` and `poetry run test` remain unavailable because the
  repository's Poetry scripts are misconfigured; direct checks above pass.
