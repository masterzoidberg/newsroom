# ADR-007 — Conservative Story Evolution and Lineage

## Status

Accepted 2026-08-16.

## Decision

Persist Story-document observations, immutable evolution classifications,
document-lineage edges, and revision-document provenance in SQLite. Resolve
candidates from several bounded signals, but treat deterministic exclusions and
low-confidence ambiguity as a reason to create a separate Story. Invoke an
adjudicator only for an ambiguous top candidate.

Syndication, wire propagation, rewritten reporting, and common primary-document
edges form lineage groups. Independent corroboration is counted from those
groups and source identities separately from publication count. Review state
continues to live independently from immutable Story revisions, so material
updates can set attention without changing saved/dismissed/not-useful state.

## Consequences

- False merges remain more costly than false splits.
- Corrections and material changes are observable through append-only events and
  Claim supersession/revision history.
- Provenance is inspectable without treating embeddings or entities as a
  knowledge graph.
- A later phase may add richer adjudication or extraction, but it must preserve
  the persistence and ambiguity gates defined here.
