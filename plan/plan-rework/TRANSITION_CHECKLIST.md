# Transition checklist

Use this once the active backend-acceptance chat finishes. Do not fill outcomes from assumptions.

## 1. Reconcile current state

- [ ] Record main branch and exact head.
- [ ] Record AST-05 lifecycle/physical branch and exact head.
- [ ] Record AST-23 and AST-24 branch heads and prove ancestry.
- [ ] Record the backend command, exit code, exact final summary and retained artifact paths.
- [ ] Record whether physical sign-in/wake qualification was actually performed.
- [ ] Inspect every involved worktree for tracked changes and preserve unrelated artifacts.

## 2. Classify Gate 0

Choose exactly one:

- [ ] `GATE 0 PASSED`: retained full backend exit 0, corrected AST-24 behavior valid, required AST-05 installed evidence complete.
- [ ] `ENGINEERING PASSED / PHYSICAL EVIDENCE PENDING`: full backend and corrected behavior pass; only explicitly identified human/physical lifecycle evidence remains.
- [ ] `GATE 0 FAILED`: a reproducible engineering failure remains; record its owner and bounded next fix.

Do not promote AST-25 from `GATE 0 FAILED`. If only physical evidence is pending, an explicit owner decision may allow isolated product development while release qualification remains blocked; record that decision rather than silently weakening AST-05.

## 3. Adopt the reworked authority

- [ ] Preserve the existing Astra ledger as historical evidence or mark it clearly superseded; do not maintain two competing NEXT files.
- [ ] Create/update one canonical task ledger with the classifications in `REWORKED_COMPLETION_PLAN.md`.
- [ ] Apply the dependency corrections exactly, validating that the graph remains acyclic.
- [ ] Keep AST-20–22 optional and AST-55 outside the critical path.
- [ ] Convert AST-47 and AST-48 descriptions to bounded qualification checkpoints.
- [ ] Split AST-48 reporting into engineering-complete and value-qualified outcomes.
- [ ] Select exactly one READY implementation task: normally AST-25 after Gate 0.
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
