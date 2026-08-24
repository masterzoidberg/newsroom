# Phase 26 Completion Report

## Architecture decision

- Topic remains a thematic area.
- Subject remains the broader editorial/monitoring concept and is not replaced.
- Entity is a persistent identifiable referent with canonical identity, aliases, conservative resolution, candidate status, mentions, and explicit relationships.
- Tag is a controlled descriptive classification. Tags are distinct from Entity identity and assignments retain origin/reason metadata.
- Entity mentions remain metadata about content occurrence; they are not EvidenceSpans and do not create an alternate evidence path.

Phase 26 extends the existing SQL/FTS Workbench projection rather than adding a second knowledge store. Workbench and Ask use the shared bounded typed retrieval service. Phase 25 Question, Gap, Task, and assessment records remain authoritative and their lifecycle status is kept separate from assessment state.

## Delivered

- Canonical Entities, aliases/acronyms, candidate handling, conservative ambiguity, ArticleAnalysis indexing, EntityMention provenance, Claim/Story/Question/Gap/Task/Watch relationships, and append-only merge lineage storage.
- Smart Tags with normalized identity, cross-object assignments, deterministic suggestions, bounded durable backfill, and replay-safe convergence.
- Heterogeneous Workbench search with stable typed results, filters, facets, ranking, match explanations, Entity detail pivots, and bounded pagination.
- Ask retrieval packets with stable canonical IDs, closed-world synthesis, packet-bound citation validation, contradiction and stale-evidence handling, precise Source/Document counts, insufficient-evidence metadata, and deterministic fallback when hosted synthesis is unavailable.
- Explicit Ask-to-Research endpoint that queues the existing Phase 25 Research Task service only after user action.
- Logical export and structural integrity coverage for Phase 26 canonical state. Search projections remain derivative and are not exported as logical knowledge.
- Fresh, upgrade, repeat, and foreign-key migration coverage through schema version 28. Version 28 widens persisted Ask scopes to Source records.

## Retrieval benchmark

`python scripts/phase26_search_benchmark.py` exercises exact Entity, alias, acronym, Claim, Story, Research Question, Evidence, contradiction, what-changed, date-bounded, and cross-object cases.

- 11 cases
- Hit@5: 1.0
- False-positive cases: 0
- Total controlled-fixture latency: about 165 ms
- Result bound: 5

vector retrieval introduced: no

The controlled corpus achieved complete top-five recall with aliases, typed relationships, normalization, and SQL/FTS. No material failure justified the operational and export complexity of a derivative vector index.

## Checkpoints

- `7bbfd8c` — canonical knowledge entities and relationships
- `3244c73` — Smart Tags and typed retrieval foundations
- `87b8509` — shared retrieval, Workbench/API/UI, Ask grounding, benchmark, export/integrity coverage

The final Phase 26 completion commit follows this report’s validation pass.
