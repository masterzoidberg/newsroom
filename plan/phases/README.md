# Newsroom Execution Phases

This directory is the authoritative execution sequence for completing Newsroom.
The product contract remains `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md`; the
mature-product description and `plan/MASTER_PLAN.md` provide broader context.

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
