# Executive audit

Newsroom has a substantial, tested evidence-intelligence core and an unfinished normal-user operating experience. The fastest reliable path is to finish startup, configuration, onboarding, and recovery around the existing architecture, then evaluate sustained usefulness. A rewrite or another broad autonomy phase would delay the actual product decision.

## Five largest everyday-use blockers

1. **P0 — No single lifecycle authority.** `newsroom/runtime.py` exposes three commands; API startup calls Uvicorn directly. An already-running API produces a socket error on duplicate launch. There is no whole-app stop/restart or ownership-aware reuse protocol.
2. **P0 — No secure in-app provider configuration.** Article Analysis reads environment configuration; other product capabilities are locally constructed. Settings mostly displays raw values and budget JSON. A provider form alone would not change those workers.
3. **P1 — First value requires internal identifiers and setup knowledge.** Watch setup requires a target ID/policy; Topics/Subjects/Sources collection views do not supply complete creation workflows. Scoped Ask asks for object IDs. A green service label does not establish that monitoring is functioning.
4. **P1 — Real content usefulness remains unqualified.** Broad-page local analysis can promote exact text but defer Story resolution due to saturated retrieval terms. The A3 downstream positive path used metadata-only content; that proves plumbing, not useful daily intelligence. The short observation checkpoint has zero post-boundary acquisitions and no reviewed useful output.
5. **P1 — Installed lifecycle, recovery, and phone/PWA qualification remain incomplete.** The deployment/recovery tools are operator-oriented. CI is not installed Windows acceptance; cached shell is not offline access to the knowledge base.

## What is already valuable

Durable normalized content artifacts, exact-span provenance verification, immutable analysis identities, transactional processing obligations, replay-safe downstream stages, correction history, temporal reads, evidence-bound reports, and grounded refusal are real code with meaningful adversarial tests. Keep these boundaries. Exact source quotation proves that a source said something; it does not prove that the statement is true or independently corroborated.

The interface is already dark and reasonably responsive. Improve tokens, contrast and workflow clarity; do not redesign it wholesale or make Light mode a release dependency.

## Material reconciliation with older plans

- `PROJECT_COMPLETION_PLAN.md` says trial configuration/evaluation artifacts are missing. Commits after that assessment include an approved UAP Watch, A3 rehearsal, frozen historical/prospective evaluation protocols, and a recorded observation boundary. Do not repeat A2 or restart the clock.
- README's initial paragraph still says automatic relevance and autonomous discovery are incomplete. Automatic relevance is wired in `document_processing.py`; bounded Watch discovery exists in `intelligent_monitoring.py`. This is not unrestricted web discovery.
- README's later baseline paragraph still describes approval/configuration as pending; the current dogfood contract and checkpoint are newer evidence.
- The old phase index calls Phase 24 next. It is historical. Phase 28.5 subtraction and Phase 29.6 temporal closure are already implemented.
- The local entity-overflow failure and blocked-paid-call accounting defect described in A2 are fixed in `ai.py` and `jobs.py`, with regressions and A3 evidence. They are not new Astra implementation tasks.
- The historical 20-question comparison and prospective UAP experiment are explicitly separate now. Preserve both identities and the preregistered decision rule.
- Phase 30 remains conditional on value; Astra authorizes the requested usability completion sequence without pretending broad feature expansion has passed that gate.

## Verdict

**Promising but unproven**, most plausibly a personal/prosumer analyst workspace. The defensible wedge is longitudinal, inspectable evidence and corrections for a narrow recurring information need. There is no repository evidence of willingness to pay, distribution efficiency, or a durable company moat.

Recommended first task: **AST-01 — Freeze the execution baseline and isolate development from observation**. Then implement ownership-aware startup. No unresolved input prevents isolated engineering work; trial promotion, paid validation and final value acceptance have explicit later gates.
