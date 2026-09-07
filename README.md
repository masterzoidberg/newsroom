# Newsroom

Standalone, evidence-first personal news intelligence.

Target workspace: `G:\Projects\Newsroom -v2`

This repository is the standalone successor to the completed Hermes Newsroom
reference implementation. **Hermes is not a runtime dependency.**

Current completion execution is governed by `plan/astra/`. The phase summaries
below are retained as historical implementation evidence; they are not the
current task-order authority. See `docs/reviews/ASTRA_EXECUTION_BASELINE.md` for
the isolated development target and current reproducibility record.

## Current state

The standalone deterministic core, evaluation foundation, evidence-ledger
vertical slice, Phase 05 local-first AI routing, Phase 06 bounded source
acquisition, Phase 07 durable jobs/scheduling, and Phase 08 persistent monitor
and relevance infrastructure are implemented. Autonomous Source discovery and
automatic post-acquisition relevance remain incomplete. Phase 09 Story evolution,
lineage, novelty classification, and review-independent material-update
resurfacing are implemented. Phase 10 Research Questions, evidence-gap
suggestions, and bounded follow-up Jobs are implemented. Phase 11
evidence-bound Living Reports, timezone-aware Monitor briefings, durable alert
rules, acknowledgement, deduplication, and optional browser delivery state are
implemented. Phase 12 adds the responsive authenticated product workspace,
evidence/provenance inspection views, operator/admin surfaces, accessible
keyboard navigation, and an installable same-origin PWA shell with offline
fallback behavior. Phase 13 adds the bounded local research workbench:
namespaced tags, notes/hypotheses, FTS search, evidence-bound comparison,
Subject context/timelines, and state-derived monitor-health diagnostics.
Phase 14 adds bounded local Ask Newsroom conversations with object-scoped
retrieval, structured fact/inference/uncertainty/contradiction classifications,
resolvable citations, cancellation, and audit metadata without raw prompt
storage. Hosted providers remain optional and disabled by default.
Phase 15 adds request-size/rate/session hardening, privacy-preserving runtime
telemetry, verified online backup/restore and migration upgrade commands,
bounded logical export and retention, representative workload tests, and
operator/recovery runbooks. Phase 16 adds an explicit Windows release identity,
outside-repository production install layout, same-origin process launchers,
bounded Task Scheduler restart configuration, and opt-in private Tailscale Serve
configuration with final acceptance rehearsal evidence; final promotion remains
pending.

The post-audit roadmap is authoritative at `plan/phases-v2/README.md`. Phases
01–16 remain historical implementation records; **Phase 21 — Structured
Article Analysis and one real AI provider** is complete (offline gate and the
recorded Live Test B), following the completed
Phase 20 semantic-scope/automatic-relevance, Phase 19 changed-DocumentVersion
processing jobs, and Phase 18 durable content artifact work. The current
production Monitor path is reliable through Source acquisition and
DocumentVersion persistence: since Phase 18 every newly acquired
DocumentVersion references a durable, immutable, hash-verifiable normalized
content artifact stored in SQLite (`content_artifacts`), since Phase 19 every
changed acquisition also creates exactly one durable
`document_version_process` Job, and since Phase 20 that Job automatically
evaluates the verified content against the approved semantic scope of the
originating Monitor (explicit `need_type`/`need_id` information-need
association, scope version pinned at acquisition) using the deterministic
local `RelevanceCascade`, and persists an explainable relevant/not-relevant
decision (`document_version_relevance`, Migration 0017). A confirmed
relevance emits the existing `relevant_change` activity and minimum-cadence
acceleration; a truthful not-relevant or acquisition-only result is a
successful outcome and never fails the Job. Since Phase 21, a `relevant=true`
decision also produces a durable structured ArticleAnalysis record
(`article_analyses`, Migration 0018; durable paid invocation hardening in
Migration 0019; exact input provenance in Migration 0020) through the
provider-neutral `AIRouter`:
the deterministic local provider by default (zero cost, offline), or exactly
one opt-in real provider (OpenAI-compatible chat completions, bundled SDK
`openai>=1.68,<2.0`) when `NEWSROOM_ANALYSIS_PROVIDER=openai` plus an API key
(`NEWSROOM_ANALYSIS_API_KEY`, or the conventional `OPENAI_API_KEY`) are set in
the environment and the `budget.paid_enabled` setting is enabled. Live Test B
passed 2026-08-18 with a real NASA UAP page analyzed by gpt-4o-mini; the
manual harness is `scripts/live_test_b.py` (never part of CI, no secrets, tiny
bounded budget). Model input always comes from the verified Phase 18
artifact; candidate Claims/Excerpts remain proposals — Phase 21 never creates
accepted Evidence/Claims, Stories, Reports, or Alerts (Phase 22 is the
verification boundary). Phase 22 now validates the complete Phase 21H.2
provenance chain, reconstructs the exact analyzed slice, verifies candidate
excerpts by unique exact code-point match, and atomically persists immutable
verified EvidenceSpans, pending Claims, and ClaimEvidence links. Ambiguous,
fabricated, and out-of-slice candidates fail closed; model offsets are never
trusted, and legacy/manual spans remain distinct. The current applied schema
is migration 0036 / schema version 36. Phase 23A–E now connect verified
automatic Claims to deterministic Story resolution, audited Claim acceptance,
evidence-bound Living Reports, exact-cause Alerts, and durable in-app delivery.
The complete chain has bounded compatibility/status APIs, logical-export
reconstruction, full-chain integrity checking, and replay-safe recovery;
controlled-fixture Live Test C passed on 2026-08-23. Only `source`
Monitor targets perform real acquisition today;
`topic`, `subject`, `story`, and `research_question` are accepted by the
schema/API but explicitly unsupported at runtime
(`error`/`unsupported_target`).

Phase 28.5 removes non-canonical Coverage, Blind Spot, evidence-family, and
fragility runtime state. Source dependency groups and counterfactuals are
computed on demand from lineage; Attention is a read-time queue with append-only
human decisions; Research Gaps are canonical; and Simple/Advanced changes
navigation density only. Ask refuses when no qualifying Evidence grounds the
answer.

Phase 29.6 engineering closure is complete at the current schema-36 baseline.
Phase 29 real-use/value acceptance remains pending. It still requires one
approved Watch configuration, unattended observation, human usefulness logging,
reproducible Full-vs-Lite evaluation, and an intelligence-value verdict. The
project is not a fully qualified first release merely because engineering
checks pass: installed Windows qualification, upgrade/recovery, and phone/PWA
acceptance remain separate release gates. Phase 30 is conditional on the Phase
29 value verdict.

The command-by-command historical Phase 29 engineering baseline and its
non-claims are recorded in `docs/reviews/PHASE_29_BASELINE_ACCEPTANCE.md`.
Current Astra execution/reproducibility evidence is recorded separately in
`docs/reviews/ASTRA_EXECUTION_BASELINE.md`. Dogfood requires an explicitly
user-approved subject and Source set; those inputs must not be invented.

## Authority

1. `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md` — product invariants and intended product contract.
2. `plan/astra/README.md` — current completion execution layer and reading order.
3. `plan/astra/TASKS.md` and `plan/astra/NEXT.md` — canonical task states and immediate queue.
4. `docs/ARCHITECTURE.md` — architecture overview.
5. `docs/PORTING_AUDIT.md` — what was reused, redesigned, or rejected from v1.

Historical phase plans and `plan/MASTER_PLAN.md` remain evidence and migration
history; they do not override Astra task ordering.

## Bootstrap validation

```powershell
python -m pytest -q
```

The imported deterministic core and standalone storage tests must remain green.

## Runtime-data rule

No runtime database, logs, backups, secrets, provider caches, or downloaded
article bodies belong in this repository. The planned standalone runtime roots
are under `%LOCALAPPDATA%\Newsroom\...` with explicit dev/prod selection.
Astra development uses the explicit isolated root/endpoint contract in
`docs/reviews/ASTRA_EXECUTION_BASELINE.md`; it must not default to the active
Phase 29 trial root or port.

Operational procedures live in `docs/OPERATIONS_RUNBOOK.md` and
`docs/RECOVERY_RUNBOOK.md`. The Phase 16 deployment rehearsal is
`scripts/phase16_windows_deploy.ps1`; runtime databases and backup files remain
outside the repository.

## v1 provenance

Reference implementation Git HEAD used for bootstrap:
`76a0be19ea3e0978743024d9283433a827c9e901`.

The v1 implementation report is retained under `reference/hermes-v1/`.
