# Phase 26 — Smart Tagging

## Objective

Turn existing `tag_type='smart'` schema/API support into an actual
classifier-backed, provenance-rich tagging pipeline.

## Why this phase exists

The tag schema can label a record smart, but no classifier/model currently
produces smart tags from Documents, DocumentVersions, or Stories.

## Current-state gap

`CoreService.create_tag()` and tag joins persist user-supplied tag metadata.
There is no automatic classifier, confidence, provenance, review, or override
pipeline.

## Scope

- Classify analyzed DocumentVersions and Stories into normalized namespaces.
- Persist confidence, provider/model identity, input analysis/version, and
  creation reason.
- Make repeated processing idempotent.
- Support human review, override, removal, and provenance inspection.
- Keep user tags distinct from smart tags.

## Non-goals

- No free-form unbounded taxonomy generation.
- No replacement of evidence, Claim, or Story decisions.
- No automatic publication or alerting based solely on a tag.

## Existing components to reuse

Tag schema and joins, Workbench/search, Phase 21 analysis records, AI routing,
budgets, telemetry, and the existing review surfaces.

## Required implementation

Define a stable namespace and normalization policy. Run a bounded classifier
after verified analysis, validate candidate tags, persist confidence and
provenance, and expose review/override state. Classification failures must not
fail the source acquisition or corrupt the evidence ledger.

## Data model/migration expectations

Add tag assignment provenance/confidence/review fields only if the existing
schema cannot represent them. Preserve existing tag rows and user-created
assignments without reinterpretation.

## Runtime integration

Smart-tag work runs as a bounded post-analysis step or Job keyed by the
DocumentVersion/Story and classifier version. It must coalesce duplicate work
and be independently retryable.

## Security/privacy considerations

Do not leak source text into tag labels or logs. Validate namespace and label
lengths, enforce model budgets, and keep user overrides authoritative.

## Tests

- Analysis creates stable smart tags with confidence and provenance.
- Reprocessing is idempotent.
- User tags and smart tags remain distinct.
- Review/override survives reprocessing according to documented policy.
- Classifier failure leaves source/intelligence state usable.

## Acceptance criteria

```text
analyzed DocumentVersion / Story
  → classifier/model
  → normalized namespace
  → confidence + provenance
  → persisted smart tag
```

## Live-test gate

No separate live gate is required; smart tagging may use the Phase 21 provider
canary only after deterministic classifier tests pass.

## Dependencies

Phases 21 and 22; Phase 27 review UI follows this backend contract.

## Exit criteria

Smart tags are generated, explainable, reviewable, idempotent, and distinct
from manually supplied tags.
