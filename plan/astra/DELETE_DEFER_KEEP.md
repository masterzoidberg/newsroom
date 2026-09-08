> Rebaseline 2026-09-07: retained narrow reference. TASKS.md, NEXT.md and COMPLETION_ROADMAP.md supersede any task order/status in this document. AST-01–04 are DONE on an unmerged stack; AST-05 qualification is the sole READY task. Old AST-12–15/19 scopes are replaced per TASKS; no trial continuation, paid call or cleanup is authorized by this reference. Historical counts/observations below are dated records, not fresh verification.

# Delete, defer, keep

No application code or historical document is deleted by this audit. “Delete candidate” requires caller/data/compatibility proof in AST-20; phase-named files are not automatically dead.

| Area | Decision | Evidence / action |
|---|---|---|
| Evidence/artifact/promotion/correction/temporal boundaries | KEEP | `content_artifacts.py`, `evidence_promotion.py`, `story_corrections.py`, `temporal.py`; differentiated, tested and data-bearing |
| Durable jobs and staged completion hooks | KEEP | `runtime.build_worker_queue`, stage services; do not replace with a generic event bus |
| Monolithic domain API | KEEP now | large file is real debt but a global split delays provider/startup delivery; small new service modules only where a boundary earns them |
| Two paid-limit layers | SIMPLIFY under AST-08 | retain durable BudgetService authority; router-local counters may remain defensive but cannot define global spending |
| Environment-only analysis configuration | RETIRE normal managed authority under AST-09 | preserve explicit one-time import/dev mode; no silent fallback after removal |
| Three normal installed launchers/tasks | RETIRE normal entry point after AST-05 | supervisor becomes authority; retain advanced commands and safe existing-install migration |
| `scripts/phase12_server.py` | GUARD/RETIRE normal usage | creates temp DB but hard-codes 8127, collides with product; use explicit safe test endpoint |
| `scripts/phase12_browser_smoke.py` | REPLACE/GUARD test entry | hard-coded active port and fixture writes, stale navigation expectations; preserve historical screenshots, make new harness explicit/test-only |
| `scripts/live_test_a.py`, `live_test_b.py`, `live_test_c.py` | KEEP operator-only | historical acceptance tools; paid harness must never be normal startup or CI |
| `scripts/create_review_snapshot.py`, ZIP | KEEP distinct from release | review artifact is not installed release provenance; user's ZIP is unrelated work |
| `newsroom/ai_benchmark.py`, `newsroom/evals/` | KEEP development/eval | executable evidence and frozen comparison contracts; package-size cleanup is low value |
| `newsroom/ai_pipeline.py` | INVESTIGATE, not proven dead | historical/manual vertical slice; trace API/test users and trust contract before proposing deletion |
| `domain.py` story-tag dual write to `tag_assignments` | INVESTIGATE compatibility | legacy bridge visibly writes real state; not safe to delete without import/reader/caller audit |
| `jobs.py:_legacy_paid_analysis_usage` | KEEP | historic spend must not disappear from budgets merely to simplify code |
| Legacy missing-artifact paths | KEEP | pre-artifact data must report unavailable honestly; do not manufacture or backfill provenance |
| Migration chain and retained review history | KEEP | schema 36 preserves immutable histories; never squash applied migrations or delete user decisions |
| Coverage/Blind Spot/fragility/evidence-family runtime projections | DO NOT REINTRODUCE | Phase 28.5–28.875 intentionally removed these; source dependencies computed on demand, Research Gaps canonical |
| Hidden Topics/Subjects/Sources/Runs/Saved/History hash routes | KEEP access, contextualize | routes remain reachable and may support deep links; absence from primary nav does not prove unused |
| Simple/Advanced | KEEP presentation-only | `experience.py`, AppShell; never fork data/routing/provenance based on UI density |
| Raw IDs/JSON in normal Settings/Watch/Ask | REMOVE from normal UX | AST-11/23–27/54 typed controls; identifiers remain Advanced diagnostics |
| Historical comments claiming promotion never occurs in processing | CORRECT narrowly | `document_processing.py` module prose predates its current `ArticleAnalysisPromotionService` call; runtime behavior authoritative |
| `plan/phases-old`, old master/phase authority statements | PRESERVE historical | Astra README is new ordering; do not rewrite old approvals or pretend old “next phase” is current |
| Light/System appearance | DEFER | complete dark and fix measured mobile issue first |
| Paid Ask | DEFER AST-21 | shared managed config first, then measured value and safe citation adapter |
| Provider SDK catalog / remote relevance | DEFER | current structured compatible adapter sufficient for first provider slice |
| Tray/services/cloud/teams/billing | DEFER | no demonstrated requirement or market evidence offsets added support cost |

Deletion proof checklist: exact symbol/path; all callers and tests; supported external API/import consumers; persisted data affected; replacement verified; rollback; owner-scope compatibility. If any evidence is missing, keep and record uncertainty. No generic “cleanup phase” is authorized.
