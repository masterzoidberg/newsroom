# Newsroom Execution Phases

This directory is the authoritative execution sequence for completing Newsroom.
The product contract remains `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md`; the
mature-product description and `plan/MASTER_PLAN.md` provide broader context.

## Post-Audit Status — 2026-08-18

Phases 01–16 are the original implementation program and remain historical
records. An independent post-remediation audit verified that the Source Monitor
runtime is substantially reliable through acquisition and DocumentVersion
persistence, but the unattended intelligence pipeline stops there. Earlier
completion claims remain valid only within their documented component/manual
scope where the annotations in those phase files say so.

Phases 17–28 are the audit-driven integration and completion roadmap. They
supersede conflicting or insufficient acceptance assumptions from Phases 01–16
without rewriting those historical records.

**Current active phase: Phase 18 — Durable Normalized Content Artifact.**
Phase 17 (runtime reconciliation and green baseline) and Live Test A (real
public sources) are complete; both gates passed.

## How to assign work to Luna

Point Luna to exactly one implementation or review file. Luna must read this
index, the assigned file, the product contract, and any prerequisites named by
the assigned file. It must not begin later work.

Implementation phases are followed by a mandatory independent review after each
block of four:

1. Phases 01-04, then `PHASE_04_REVIEW.md`
2. Phases 05-08, then `PHASE_08_REVIEW.md`
3. Phases 09-12, then `PHASE_12_REVIEW.md`
4. Phases 13-16, then `PHASE_16_REVIEW.md`

The next block may not begin until its review verdict is **Approve**.

## Implementation contract

For every implementation phase Luna must:

1. Confirm prerequisites and inspect the existing implementation before editing.
2. Work in small, testable increments and preserve unrelated user changes.
3. Add behavior-focused tests with each behavior change.
4. Run phase-specific verification and the full applicable test/build suite.
5. Update documentation only where behavior or operator instructions changed.
6. Record completed work, commands, results, risks, and the commit hash in the
   phase file's Completion Record.
7. Create one coherent local checkpoint commit; never push automatically.
8. Stop at the end of the assigned phase.

## Review contract

Review tasks are read-only until findings are reported. They inspect all four
phase commits and evaluate correctness, tests, readability, architecture,
security, performance, dependency discipline, and scope compliance. Findings
must be severity-ranked with exact file/line evidence. A review may approve only
when all Critical and Required findings are fixed and verification is rerun.

The review agent writes its final evidence to `docs/reviews/PHASE_XX_REVIEW.md`,
records the accepted commit, and creates one local review/fix commit if fixes
were required.

## Phase index

| Phase | Task | Gate |
|---|---|---|
| 01 | Evaluation repair | |
| 02 | Foundation and schema | |
| 03 | Core domain and authentication | |
| 04 | Evidence Ledger vertical slice | Review 04 |
| 05 | AI capabilities and routing | |
| 06 | Source discovery and acquisition | |
| 07 | Durable jobs, scheduler, and cost | |
| 08 | Monitors and semantic relevance | Review 08 |
| 09 | Story evolution, lineage, and novelty | |
| 10 | Research Questions and evidence gaps | |
| 11 | Reports, briefings, and alerts | |
| 12 | Product UI and PWA | Review 12 |
| 13 | Search, comparison, and diagnostics | |
| 14 | Ask Newsroom | |
| 15 | Hardening, performance, and operations | |
| 16 | Windows deployment and final acceptance | Review 16 |

## Post-Audit Phase Index

| Phase | Task | Gate |
|---|---|---|
| 17 | Runtime reconciliation and green baseline | Green baseline |
| 18 | Durable normalized content artifact | Artifact verification |
| 19 | Changed DocumentVersion processing Jobs | Processing lifecycle |
| 20 | Semantic scope and automatic relevance | Relevance result |
| 21 | Article analysis and real AI provider | Live Test B |
| 22 | Verified Evidence and Claims automation | Evidence verification |
| 23 | Story, Living Report, and Alert automation | Live Test C |
| 24 | Source discovery and semantic vocabulary | Discovery canary |
| 25 | External Research Question pursuit | External evidence |
| 26 | Smart tagging | Tag provenance |
| 27 | Complete product workflow UX | Browser workflow |
| 28 | Browser delivery, hardening, and final acceptance | Final Live Test |

## Recommended Dependency Map

The primary sequence is intentionally conservative and SQLite/local-first:

```text
17 → 18 → 19 → 20 → 21 → 22 → 23 → 24 → 25 → 26 → 27 → 28
```

Phase 24 may prepare discovery/vocabulary contracts in parallel with late Phase
23 review, but its runtime activation depends on Phase 20's scope contract.
Phase 26 consumes Phase 21/22 analysis and verification even though it appears
after Phase 25 in the primary sequence. No later phase may silently treat an
isolated service or schema as an unattended product capability.

## Live-Test Sequence

- **Live Test A — after Phase 17:** real RSS/HTML → Scheduler → Worker →
  Acquisition → DocumentVersion, including truthful `changed`, `no_change`, and
  `error`; no AI.
- **Live Test B — after Phase 21:** real public Source → changed content →
  relevance → one real model-backed article analysis. Claims remain candidates.
- **Live Test C — after Phase 23:** Source → relevance → analysis → verified
  Evidence/Claims → Story → Living Report → in-app Alert.
- **Final Live Test — after Phase 28:** public-source production workflow,
  real browser delivery, and multi-day unattended execution.

The historical review gates remain evidence for Phases 01–16. Phase 17 is the
new active gate and must establish the baseline before the post-audit sequence
advances.

### Live Test A status — 2026-08-18

**PASSED** against the Phase 17 green baseline (`4c235d1`). Evidence recorded
in `PHASE_17_RUNTIME_RECONCILIATION_AND_GREEN_BASELINE.md`. Real RSS (NPR),
HTML (`example.com`), and official US government (`usa.gov`) acquisitions all
succeeded through the production Scheduler → durable Job → Worker →
Acquisition → DocumentVersion path with truthful `changed`/`no_change`/`error`,
verified deduplication, queue durability across process-object recreation, and
disabled-monitor safety. One genuine acquisition defect was exposed and fixed
minimally (redirect handler followed the re-normalized `www.`-stripped target,
causing a self-bounce). No AI/relevance/analysis was invoked. The post-audit
sequence (Phase 18) may begin.
