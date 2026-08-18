# Phase 24 — Source Discovery and Semantic Vocabulary

## Objective

Turn a user information need such as “Monitor UFO sightings” into a
reviewable vocabulary and usable Source/Monitor configuration.

## Why this phase exists

SourceSuggestion persistence is not autonomous discovery, and current “AI
suggestions” are lexical token extraction rather than semantic expansion.

## Current-state gap

No discovery/search provider produces candidate Sources. Vocabulary storage can
represent several term types, but no mechanism derives synonyms, acronym
expansions, concepts, or ambiguity handling.

## Scope

- Define information-need input and reviewable suggestion provenance.
- Produce vocabulary candidates for canonical terms, aliases, synonyms,
  acronyms, acronym expansions, related/broader/narrower concepts, exclusions,
  and ambiguity/disambiguation.
- Add a bounded discovery/search provider abstraction.
- Evaluate candidate Sources with rationale, authority/quality context,
  limitations, methods, and provenance.
- Require explicit user approval before Source configuration.
- Make approved vocabulary affect Phase 20 relevance scope.

## Non-goals

- No silent Source creation or open-ended crawling.
- No claim that lexical tokenization is AI.
- No unbounded external URL fetching or provider marketplace.

## Existing components to reuse

`ScopeSuggestionService`, `RelevanceCascade`, `topic_terms`, SourceSuggestion
and SourceProfile services, acquisition policy, monitor scope history, and the
Phase 23 unattended loop.

## Required implementation

The flow must be:

```text
information need → bounded discovery/search → candidate vocabulary/Sources
                  → rationale/limitations/provenance → explicit approval
                  → configured Source and Monitor scope
```

Candidate results must be reviewable independently. Approval must create or
configure only the approved canonical record and preserve the decision history.

## Data model/migration expectations

Extend suggestion provenance and candidate evaluation fields only where the
current tables cannot represent provider, query, timestamp, authority context,
limitations, and review decisions. Preserve existing manual suggestions.

## Runtime integration

Approved vocabulary feeds the immutable scope snapshot used by Phase 20.
Approved Sources use the existing bounded AcquisitionService and Monitor Jobs.
Discovery itself must run under a bounded, cancellable, budgeted Job.

## Security/privacy considerations

Treat discovered URLs as untrusted. Apply URL normalization, SSRF protections,
redirect checks, response limits, and connection-time DNS rebinding mitigation
before fetching. Do not expose provider credentials or raw prompt content.

## Tests

- UFO/UAP example produces typed, reviewable candidates.
- Approval/rejection is explicit and idempotent.
- Approved vocabulary changes scope history and relevance behavior.
- Discovery returns bounded rationale, authority, limitations, and provenance.
- Hostile/private/redirected discovered URLs are rejected.
- Duplicate Sources and duplicate candidates are suppressed.

## Acceptance criteria

```text
information need only
  → reviewable vocabulary suggestions
  → reviewable Source candidates
  → approval
  → usable Source/Monitor configuration
```

## Live-test gate

After Phase 24, a bounded discovery canary may use a real search/discovery
provider, with no automatic approval and no unbounded crawling.

## Dependencies

Phases 17, 18, 20, and 23. DNS/connection-time SSRF hardening must be in this
phase or completed before any real discovery provider is enabled.

## Exit criteria

Users can configure a semantically expanded, reviewable Source Monitor from an
information need without manually entering every term and URL.
