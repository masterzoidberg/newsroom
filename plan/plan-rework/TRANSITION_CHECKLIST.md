# Transition checklist

Use this once the active backend-acceptance chat finishes. Do not fill outcomes from assumptions.

## 1. Reconcile current state

- [x] Record main branch and exact head: `main` at `6e772a6c1895bc404987dc1a4e397514bd603981` before this ledger transition.
- [x] Record AST-05 lifecycle/physical branch and exact head: `astra/AST-05-windows-runtime-cleanup` at `18c5ee8bdf56a44218af4ecd6d7e8d9ead68f8c0`.
- [x] Record AST-23 and AST-24 heads and prove ancestry: `2ab4715` and corrected `0df1c1d` are ancestors of accepted `18c5ee8` (both `git merge-base --is-ancestor` exit 0).
- [x] Record the backend command and result: `python -m pytest -q`, exit 0, retained `backend-acceptance` artifact in CI run 34412730096 attempt 2.
- [x] Record whether physical sign-in/wake qualification was actually performed: not performed; reboot/sign-in and lock/sleep/wake remain pending.
- [x] Inspect involved worktrees for tracked changes; planning edits are isolated on main and unrelated `.kilo/`, ZIP and `.artifacts/` files remain untouched.

## 2. Classify Gate 0

Choose exactly one:

- [ ] `GATE 0 PASSED`: retained full backend exit 0, corrected AST-24 behavior valid, required AST-05 installed evidence complete.
- [x] `ENGINEERING PASSED / PHYSICAL EVIDENCE PENDING`: full backend and corrected behavior pass; only explicitly identified human/physical lifecycle evidence remains.
- [ ] `GATE 0 FAILED`: a reproducible engineering failure remains; record its owner and bounded next fix.

Do not promote AST-25 from `GATE 0 FAILED`. If only physical evidence is pending, an explicit owner decision may allow isolated product development while release qualification remains blocked; record that decision rather than silently weakening AST-05.

## 3. Adopt the reworked authority

- [ ] Preserve the existing Astra ledger as historical evidence or mark it clearly superseded; do not maintain two competing NEXT files.
- [ ] Create/update one canonical task ledger with the classifications in `REWORKED_COMPLETION_PLAN.md`.
- [ ] Apply the dependency corrections exactly, validating that the graph remains acyclic.
- [ ] Keep AST-20–22 optional and AST-55 outside the critical path.
- [ ] Convert AST-47 and AST-48 descriptions to bounded qualification checkpoints.
- [ ] Split AST-48 reporting into engineering-complete and value-qualified outcomes.
- [x] Select exactly one READY implementation task: AST-25.
- [ ] Generate one prompt for the next autonomous run from `AUTONOMOUS_EXECUTION_RUNBOOK.md`; do not pre-author dozens of stale task prompts.

## 4. Validate the adopted plan

- [ ] Every required capability maps to a CORE or ASSISTED owner.
- [ ] Every task has testable acceptance, verification, dependencies and bounded files.
- [ ] No optional/external/checkpoint record inflates implementation remaining counts.
- [ ] Full-suite runs occur at milestone boundaries; focused checks remain per task.
- [ ] Markdown links and machine-readable mirror agree.
- [ ] Dependency validation and `git diff --check` pass.
- [ ] Planning changes do not overwrite backend implementation or retained evidence.

## 5. Start execution

After adoption, begin Run 1 in `AUTONOMOUS_EXECUTION_RUNBOOK.md`. A green C1 permits automatic continuation to Run 2; stop only under the runbook’s mandatory stop conditions or at a user-requested boundary.
