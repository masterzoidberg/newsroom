# Immediate execution queue

Updated 2026-09-12 after AST-07 completed on `astra/AST-25-27-first-watch` at implementation commit `00ee0fb`. AST-05 engineering, AST-23/24, AST-25/26/27, AST-33, AST-34, AST-35, AST-36, AST-37, AST-38, AST-39, AST-40, AST-06 and AST-07 are accepted on the branch; AST-07 credential lifecycle, migration, export-policy, full-suite, evaluation, frontend-build and disposable same-user Windows vault qualification passed. Physical reboot/sign-in and lock/sleep/wake evidence remains a release gate; it does not block isolated product development.

**AST-07 — Store credentials in an approved operating-system vault is DONE. The next queued task is AST-08 — Make paid admission durable across processes and reloads; it is READY.**

AST-40, AST-06 and AST-07 are complete. The public AI metadata authority now has a schema-39 generation counter, typed connection metadata, supported Article Analysis routing, local/fail effective-route reporting, authenticated API boundaries, secret-free logical export, and versioned credentials in an explicitly selected OS vault with durable cleanup recovery. AST-41 is not READY because it depends on AST-29, which is not started; the independent managed-AI lane continues at AST-08.

Run 1 used an isolated checkout descended from `astra/AST-05-windows-runtime-cleanup` at accepted head `18c5ee8`, cherry-picked planning commit `b20fd79`, and completed one bounded commit per AST task without merging or rewriting history. Do not begin Run 2 in this session.

Following queue, AST-08 is next and all future tasks remain NOT_STARTED unless separately classified below:

1. AST-08 — Make paid admission durable across processes and reloads (Tier 3/high), after AST-07.

Then AST-07–11 complete managed AI configuration before AST-28–32 add assisted terminology/discovery. This removes the older artificial dependency of basic local onboarding on a finished paid-provider settings screen.

Release blockers: AST-05 still needs physical reboot/sign-in and lock/sleep/wake evidence; hosted automation cannot imply those manual checks. AST-16/17/18 remain blocked external value gates. These gates do not block AST-25 engineering and do not authorize runtime contact, paid execution, merge or deployment.

## Gate 0 disposition

Engineering passed with physical evidence pending. Integrated head `18c5ee8` preserves the corrected AST-24 ancestry and fixes the shared spawned-child publication race. Run 1 C1 passed on the descendant branch with full local backend/frontend qualification and first-Watch browser/state evidence. Final release qualification must still retain evidence from a physical reboot/sign-in and lock/sleep/wake cycle.

Do not start AST-08 early, broad superseded AST-12–15/19, speculative external discovery before AST-30, paid Ask, commercial pilot, or any trial promotion/merge/deployment. Do not contact port 8127 or active `phase29-trial` roots, recreate the Watch, reset the observation boundary or start an automation. Recorded boundary and limitations are in CURRENT_STATE.
