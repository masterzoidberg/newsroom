# Phase 25 — External Research Question Pursuit

## Objective

Upgrade Research Questions from bounded local retrieval into bounded external
investigation that can produce genuinely new evidence.

## Why this phase exists

The repaired Question lifecycle and worker are durable, but current pursuit
searches existing local Claims and Evidence rather than discovering or
acquiring new material.

## Current-state gap

`ResearchQuestionExecutionService._research()` queries the local FTS projection
for Claims and Evidence. It does not create a new DocumentVersion or external
EvidenceSpan.

## Scope

- Add bounded external search/discovery and candidate Source/document handling.
- Reuse acquisition and Phase 18 content artifacts.
- Route acquired results through Phase 19–22 processing and verification.
- Link verified Claims/Evidence to the Question.
- Preserve attempts, budgets, retries, cancellation, partial outcomes, and
  explicit research history.
- Avoid duplicate Sources/documents and repeated identical searches.

## Non-goals

- No open-ended autonomous research loops.
- No automatic resolution of a Question without reviewable evidence.
- No bypass of Source/URL security controls or evidence verification.

## Existing components to reuse

`ResearchQuestionService`, attempt lifecycle, `research_question` Jobs,
completion/recovery hooks, budgets, acquisition, content artifacts, processing,
EvidenceService, and Question link tables.

## Required implementation

Implement:

```text
Question → bounded external search → candidate Source/document
         → acquisition → normalized content → processing
         → verified Evidence/Claims → Question links → terminal attempt
```

Each attempt must record query/provider/provenance, candidates considered,
successful artifacts, failures, units/cost, and terminal semantics.

## Data model/migration expectations

Extend attempt/search provenance only if current fields cannot retain provider,
query, candidate, artifact, and failure history. Preserve existing local-search
attempts and distinguish local from external modes.

## Runtime integration

External pursuit runs through durable Jobs with one canonical Question attempt
owner. The existing atomic completion hook remains authoritative for terminal
attempt status and Job status.

## Security/privacy considerations

Apply acquisition SSRF, parser, size, timeout, and redirect controls to every
candidate. Bound query count and provider cost. Treat retrieved content as
untrusted prompt input and keep credentials out of logs and exports.

## Tests

- One unresolved Question obtains a new external DocumentVersion and verified
  Evidence.
- Repeated pursuit avoids duplicate candidates and artifacts.
- Retry, partial, cancellation, lease recovery, and budget exhaustion remain
  coherent.
- Existing-local versus newly-acquired findings are distinguishable.

## Acceptance criteria

An unresolved Question can obtain genuinely new external evidence, link it to
the Question, and terminalize its owning attempt/job without contradictory
states.

## Live-test gate

After Phase 25, a controlled real external-research canary may run with strict
query and cost budgets. It must not silently resolve production Questions.

## Dependencies

Phases 18–22 and Phase 24 discovery/security contracts.

## Exit criteria

Research Questions can safely extend the local evidence ledger with new,
provenance-rich external findings under durable lifecycle control.
