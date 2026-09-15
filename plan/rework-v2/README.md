# Newsroom Research rework

Status: **planning complete; implementation partially started, M0.1 not acceptance-complete**. Owner decisions incorporated 2026-09-14. The adversarial review was performed against commit `2b367356d56a02acff9138792a772b938e087a68`; subsequent commits added the managed migration-authority prerequisite and schema-40 M0.1 foundation. This is not a release-qualified baseline.

Newsroom currently asks the user to configure its machinery before it gives them useful research. Some problems are presentational, but shared-source processing, Research evidence isolation, source discovery, first-check semantics, and managed migration authority need real backend corrections. A navigation rename alone cannot fix them.

The target experience is: describe an interest, confirm scope, find and approve sources, start monitoring immediately, understand what changed, ask what the evidence supports, and inspect exact provenance. Home answers “What changed?” and “Does anything need me?” Research is the durable workspace. Settings contains ordinary preferences.

## Authority and reading order

This directory is the authoritative **rework product design and implementation sequence**, superseding conflicting product-work ordering in `plan/astra`. It does not supersede evidence invariants, frozen trial protocols, deployment qualification, or historical records. Do not execute Astra's next queued task merely because its queue is older than this plan. Question-first setup and model-only source recommendations already exist in the working tree.

1. [PRODUCT_MODEL.md](PRODUCT_MODEL.md): vocabulary, modes, invariants.
2. [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md): what exists, evidence, limitations.
3. [ADVERSARIAL_REVIEW_2026-09-14.md](ADVERSARIAL_REVIEW_2026-09-14.md): binding full-codebase review delta, production failure modes, simplification and value gates.
4. [RESEARCH_AND_PROVENANCE_ARCHITECTURE.md](RESEARCH_AND_PROVENANCE_ARCHITECTURE.md): binding backend contracts and migration rationale.
5. [UX_AND_INFORMATION_ARCHITECTURE.md](UX_AND_INFORMATION_ARCHITECTURE.md): screens, routes, interactions, states.
6. [EXECUTION_PLAN.md](EXECUTION_PLAN.md): canonical incremental sequence and progress ledger.
7. [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md): repeatable acceptance gates.
8. [DECISIONS.md](DECISIONS.md) and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md): decision record and remaining qualification work.

Resolve conflicts by explicit owner decisions, product invariants, append-only decisions, the adversarial-review delta, architecture contracts, then execution details. Verified new code evidence may invalidate implementation assumptions; record a superseding decision instead of silently changing the product contract.

## Delivery boundary

Both manual/basic local and AI-assisted setup enter the same architecture. No credentials are required for manual setup, safe URL inspection, monitoring, or available local evidence functions. Full semantic interpretation and external Source Scout require a capable configured service; zero-paid mode is not promised equivalent intelligence. A clean-install guided acceptance fixture explicitly includes configured, authorized fake AI/search services. A separate clean-install fixture proves manual operation with no credentials.

MVP includes shared-source correctness, linked article retrieval from feeds, durable historical membership, explicit checks, Research-scoped outputs, Source Profiles and overrides. “No evidence-backed result” is an honest outcome. Useful real-world results require a separate content-quality acceptance gate; green mock tests do not establish usefulness.

Non-goals: new Research root entity; Topic→Watch navigation hierarchy; independently scheduled Focus areas; new scheduler, report system, frontend framework, or local model platform; unbounded crawling; background paid work without authorization; team accounts, publishing, newsletters, native mobile apps; Claim Diff/Belief History/Time Machine UI; destructive purge; redesigning the entire design system.

## Future execution discipline

Implementation starts only after explicit owner authorization. Start with the managed-migration authority prerequisite recorded in the adversarial review, then M0.1 scope/membership history; M0.2 observations, M0.3 contextual processing, M0.4 projection, M0.5 shared-Source integration and M0.6 recovery each have a mandatory review stop. Recheck the working tree and current schema before editing. Preserve unrelated changes. Test against disposable databases outside the repository; do not contact the active trial root or port 8127. No production deployment, trial reset, paid live validation, or merge is implied by this plan.

For each milestone, update Progress, Surprises, Decisions, and Outcomes in the ExecPlan with exact commit/working-tree identity, commands and results. Update affected contracts and acceptance cases together. Keep decision history append-only. Record unknowns honestly; never fabricate historical membership or convert a missing observation into “no change.” Allocate migration numbers only at implementation time. Do not repeatedly reopen settled architecture for routine frontend work.
