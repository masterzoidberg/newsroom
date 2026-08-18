# Phase 20 — Semantic Scope and Automatic Relevance

## Objective

Automatically evaluate changed DocumentVersions against the actual information
need and Monitor scope.

## Why this phase exists

The relevance cascade exists, but production Source acquisition currently does
not invoke it. Source Monitor scope ownership is also ambiguous when a Source is
being monitored for a Topic or other information need.

## Current-state gap

`candidate_text` supports a manual/unit-test path, while the production path
records `changed` with `relevant_items=0`. Approved vocabulary is persisted, but
there is no automatic changed-version scope handoff.

## Scope

- Define the canonical effective-scope owner for each processing obligation.
- Require a Source Monitor that is intended to represent an information need to
  carry an explicit Topic/information-need association or be classified as
  acquisition-only.
- Snapshot exact terms, approved vocabulary, aliases, acronyms, concepts, and
  exclusions at processing time.
- Run the deterministic `RelevanceCascade` from a processing Job.
- Persist relevant/not-relevant outcome, matched terms, score, scope version,
  and provider signal.

## Non-goals

- No real LLM provider or autonomous vocabulary expansion.
- No accepted Claims or Story/report changes.
- No silent inference of scope from Source name or URL.

## Existing components to reuse

`RelevanceCascade`, `RelevanceScope`, `_scope_for_target`, topic term approval,
`MonitorService` scope history, `AIRouter` local relevance contracts, the Phase
19 processing Job, and Phase 18 artifact access.

## Required implementation

Load and verify normalized content, load the immutable effective scope snapshot,
apply exclusions first, then exact/vocabulary/entity/concept/semantic/local
stages, and persist the result. A non-relevant version must terminate cleanly
without article analysis. A relevant version must produce a stable handoff for
Phase 21.

## Data model/migration expectations

Persist processing scope identity/version and relevance result with enough data
to reproduce the decision. Use existing monitor scope history where possible;
add a migration only if a durable processing-result record is required.

## Runtime integration

The Phase 19 worker calls relevance after loading the artifact. The result is
idempotent by DocumentVersion and scope version. It must not call the manual
`candidate_text` route or make acquisition synchronous.

## Security/privacy considerations

Keep content and scope bounded. Treat acquired text as untrusted input; do not
execute or render it. Preserve exclusion semantics and prevent a source from
silently widening a user's information need.

## Tests

- Changed version loads durable content and evaluates automatically.
- Exact, alias, acronym, concept, semantic, and exclusion paths are covered.
- Scope changes create a new reproducible scope version without mutating history.
- Manual `candidate_text` remains test-only/manual and is not required by Jobs.
- No-change, failed, irrelevant, and relevant outcomes are distinct.

## Acceptance criteria

```text
changed DocumentVersion
  → processing Job
  → durable normalized content
  → deterministic relevance
  → persisted relevant/not-relevant result
```

No manual candidate text is required in the production path.

## Live-test gate

After Phase 20, real public-source relevance canaries may run using the
deterministic/local provider. No model-generated Claims may be accepted.

## Dependencies

Phase 19 and Phase 18; scope ownership must be resolved before implementation.

## Exit criteria

Every changed version receives a reproducible automatic relevance decision tied
to an explicit information need and scope version. Phase 21 may add article
analysis and a real provider.
