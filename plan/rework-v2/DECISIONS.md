# Decisions

Append-only. Date for D01–D19: 2026-09-14. Owner's two planning requests control product scope; implementation choices below are architect recommendations made within that authorization. New evidence may supersede an entry with a new ID, never delete it.

| ID | Decision / authority | Rationale and rejected alternative |
|---|---|---|
| D01 | Research is Watch.id; keep backend names. Architect confirms owner preference. | Watch owns lifecycle/policy/source Monitors across Topic/Question. Topic or Question alone cannot express that; new Research entity duplicates it. Preserve one Watch per target. |
| D02 | Focus areas are approved versioned scope metadata, not scheduled objects. Owner. | Organization/coverage does not justify a new hierarchy. Independent cadence/budget/state requires later evidence and decision. |
| D03 | AI proposes, deterministic services validate, user approves and can override. Owner. | Neither AI confidence nor URL reachability is authorization or factual truth. Manual mode reaches same durable model. |
| D04 | Full guided AI/search requires capable configured services; no-equivalence zero-paid promise. Owner answer 1. | Manual intent/scope/URL inspection/monitoring remain usable. A new local model/search platform would enlarge MVP unnecessarily. |
| D05 | Bootstrap Scout and corpus discovery stay distinct; extend existing recommendation lane. Owner + code. | Model-only source_discovery exists but URLs are unverified; corpus feed_discovery is origin discovery, not RSS detection. No replacement of working review/provenance code. |
| D06 | Shared acquisition, contextual processing tuple (version, Monitor, scope). Owner + architect. | Version-only keys AND active guards collapse B. Contextual relevance/analysis identities already exist. No duplicate downloading to repair semantic ownership. |
| D07 | Membership intervals + durable observations preserve Research knowledge after detach. Owner answer 3 + architect. | Current attachments alone are insufficient. Reattach opens a new interval; unknown legacy dates stay unknown. No destructive purge or historical reclassification. |
| D08 | Use Source endpoints and feed discovery edges, preserve canonical Documents. Architect. | Slug identity conflates unrelated publishers; hosted feed and article origin differ. Do not create a broad Source ontology or silently merge by domain/name. |
| D09 | Feeds are sensors; bounded linked article retrieval is MVP, with fidelity-aware fallback. Owner answer 2. | Summary/full-feed/article representations must not masquerade as each other or churn latest-version comparison. Same acquisition service/queue/safety path. |
| D10 | Extend Runs with expected sources/work joins, not a second check engine. Architect. | Current Runs/jobs cannot attribute shared descendants or exclude old failures. Durable expected set is necessary for “this check”; global timestamps/count heuristics rejected. |
| D11 | Start/resume makes eligible work due now; Check now idempotently schedules bounded work. Owner + architect. | Existing scheduler produces work; API does not synchronously acquire. Active source items as well as jobs prevent duplicates during continuation. |
| D12 | Common exact-version Research evidence projection for Ask, Updates, Briefing and explanations. Architect confirms owner isolation requirement. | Topic bridge/source filtering/global Story summaries are semantically unsafe. Apply boundary after all expansions and at final serialization. |
| D13 | Watch target in existing LivingReport provides current Briefing; backend Briefing remains scoped delivery digest. Architect. | Existing three target paths mismatch. Preserve immutable revisions/causes/audits; do not add second report system or relabel legacy scope as isolated. |
| D14 | Layered Source assessment assertions; user override wins; operational health separate; no truth score. Owner + architect. | Current source_profiles stores operations counters. Global Source role and Research relevance/coverage have different scopes. Neither changes Claim truth/acceptance. |
| D15 | Typed hash router; Home/Research/Settings; contextual Ask/evidence. Owner + architect. | Current React stack needs addressable identity, not a new framework/router library. Keep draft storage distinct from navigation. |
| D16 | Reuse explicit review boundary, attention, correction and lineage machinery; preserve knowledge time. Architect. | Opening Home must not silently acknowledge unseen changes. Claim Diff/Belief History/Time Machine remain later UI, supported by retained history. |
| D17 | Additive migrations and controlled CHECK/index rebuilds are necessary; preserve old rows/IDs/keys. Architect. | Product requires relationships absent today. Broad schema replacement unnecessary. Old/new writers cannot overlap; migration/export/integrity/recovery ship together. |
| D18 | Final adversarial review moves foundational isolation ahead of UI, constrains fallback and completion paths. Architect. | Initial-only Ask filter, version-key-only fix, generic run timestamp aggregation and indiscriminate Briefing rename all fail counterexamples. M0–M7 are the resulting sequence. |
| D19 | Cross-domain feed article authority is proved through membership/discovery/version lineage; preserve legacy source-equality checks. Architect, final code challenge. | Processing and provenance currently reject differing Monitor/Document Sources. Globally removing that guard would weaken authority; the narrow new proof path supports owner-approved linked retrieval without arbitrary cross-source processing. |

## Final challenge outcome

No second scheduler, transport, worker system, root Research entity, report model or design-system rewrite is proposed. New job kinds are thin continuations in the existing queue; new tables preserve missing causality/approval, not alternate truth. Historical reports are kept rather than mass-rewritten. All new paid capabilities use existing vault/budget authority with explicit operation grants. Unknown publisher/legacy history is visible. Exact provenance, correction history and closed-world boundaries remain binding.

Final review also requires implementation to prove: unchanged content creates missing Research obligations; scope transitions are atomic; paused/detached subscribers cannot admit new work; in-flight operations cannot widen paid permission; shared global Claim/Story text cannot bypass scoped rendering; feed/article comparison is representation-specific; check closure waits for durable descendants or explicit terminal failure. These are acceptance gates, not optional polish.


## Final M0 audit decisions — append-only refinements

| ID | Decision and authority | Supersedes / reason |
|---|---|---|
| D20 | Watch ID remains Research; preserve existing Story correction target changes with immutable target-binding history. Architect, compatibility correction. | Refines D01/no-retarget wording: no new retarget UI, but existing merge/split behavior must not be broken or history inferred from current target. |
| D21 | Pin Watch revision and semantic Monitor scope independently; atomic existing scope writers preserve Watch overlays. | Refines original scope-reference proposal: identical semantic JSON legitimately reuses Monitor history. |
| D22 | Persist endpoint snapshot item/version edges before relying on feed 304; pending observations precede execution cutover. | Corrects unchanged-feed assumption; acquisition events currently lack item manifests. Legacy missing fidelity/history remains unknown. |
| D23 | Preserve metadata-only logical export privacy; full reconstructable recovery uses verified backup. New partial archive cannot confer runtime eligibility. | Supersedes blanket full logical round-trip implication in AC-R03/initial M0. No private artifact export expansion or data destruction authorized. |
| D24 | Endpoint uniqueness is per Source+normalized URL+kind; retain unresolved duplicate publisher bindings. Share compatible transport separately. | Supersedes global normalized URL uniqueness in original endpoint proposal. No lossy merge/backfill or automatic alternate-feed equivalence. |
| D25 | M0 becomes six review-gated slices; each ships recovery/integrity. Minimal shared endpoint coordination moves to M0.5; M1 extends it. | Supersedes monolithic M0 and deferral of all shared-fetch work to M1. Same MVP/queue/scheduler, safer dependency order. Watch Run closure must bypass legacy jobs-only finalizer. |
| D26 | Projection owns eligibility only; membership writes, admission and check coordination have separate bounded owners. Keep canonical promotion identities and global truth. | Refines research_context module responsibility; no new Story truth table, semantic ledger or universal Research service. |

No owner decision is required for these corrections: identity, retention, cost, privacy, Source authority and MVP boundaries are preserved. A destructive real-data migration or requested expansion of private logical export would require a separate decision; neither is proposed.
