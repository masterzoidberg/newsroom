# Backend acceptance and app completion plan

Updated 2026-09-09 from the retained Windows backend run at AST-24 head `0df1c1d39b93b47306d2093cf506599fc44888ef`. This is planning only. It does not mark AST-05 or AST-24 DONE, authorize AST-25, merge branches, deploy, contact the Phase 29 runtime, or authorize paid calls.

## Objective, constraints and assumptions

Close the failed local backend gate with the smallest portable runtime/test correction, finish the separately pending installed launcher qualification, then resume the existing dependency-ordered product roadmap. Preserve the unmerged AST-01–24 stack and unrelated untracked files. The retained artifacts under `G:\Projects\Newsroom-AST24\.artifacts` are evidence, not source files to commit.

The AST-24 correction commits through `0df1c1d` implement the four prior review findings: approval invalidation, immutable retry payload, tab-isolated recovery, and measured 390 CSS-pixel qualification. Acceptance is still withheld because the required full backend command ended with exit code 1.

## Confirmed backend issue

The retained command `python -m pytest -q` completed at 100% on Python 3.12.0 / pytest 7.4.3 and failed three tests in `tests/test_runtime_supervisor.py`:

1. `test_supervisor_crash_reconciliation_reuses_children_then_child_crash_restarts_one` calls `os.kill(pid, signal.SIGKILL)`. `signal.SIGKILL` does not exist on Windows.
2. `test_bounded_restart_exhaustion_stops_crash_loop` has the same non-portable kill operation.
3. `test_shutdown_reports_busy_worker_deadline_without_force_kill` intermittently starts without a worker owner because a managed child exits while deleting its heartbeat file. `ManagedRoleContext.__exit__` treats Windows sharing violation `WinError 32` as fatal, leaving cleanup/startup state inconsistent.

The focused runtime-supervisor file reproduces all three failures. This is not an AST-24 Watch-domain regression, but it is a real acceptance failure and overlaps AST-05's Windows lifecycle authority. A passing focused rerun alone cannot convert the failed full run into a pass.

## Recommended fix

Keep the correction in the runtime/lifecycle stack and carry it forward into the AST-24 descendant before final acceptance.

### Task BA-1 — Make crash tests portable

**Change:** In `tests/test_runtime_supervisor.py`, use a small test helper that terminates a fixture child through its retained `subprocess.Popen` handle (`process.kill()` and `process.wait()`), rather than referencing `signal.SIGKILL`. Keep the POSIX-only heartbeat suspension test explicitly skipped on Windows.

**Acceptance criteria:**

- Both crash/restart tests exercise the same abrupt-child-loss behavior on Windows and POSIX.
- The helper verifies the process exits and does not broaden production kill behavior.
- No new dependency is introduced.

**Verification:** Run the two exact test nodes on Windows, then the complete `tests/test_runtime_supervisor.py` file.

**Likely file:** `tests/test_runtime_supervisor.py`.

**Dependency:** None. Size S.

### Task BA-2 — Make managed-state cleanup resilient to Windows readers

**Change:** In `ManagedRoleContext.__exit__`, perform bounded retry/backoff for `PermissionError` when removing owner, heartbeat, and control files, using the repository's existing bounded Windows file-operation convention. Join the heartbeat writer before cleanup and never mask the body exception. If retries are exhausted, release the component lock and leave stale metadata for existing identity-aware reconciliation; do not crash an otherwise clean child shutdown or delete another owner's state.

**Acceptance criteria:**

- A transient Windows sharing violation during heartbeat cleanup does not change a managed child's successful exit to code 1.
- Cleanup remains owner-checked and cannot remove replacement-process metadata.
- Persistent cleanup failure is bounded, diagnosable, and does not retain the ownership lock.

**Verification:** Add focused unit coverage that injects transient and persistent `PermissionError`; run the busy-worker test repeatedly; run `tests/test_runtime_managed_state_io.py`, `tests/test_runtime_supervisor.py`, `tests/test_runtime_identity.py`, and `tests/test_runtime_status_api.py`.

**Likely files:** `newsroom/runtime_managed.py` and `tests/test_runtime_managed_state_io.py`.

**Dependency:** BA-1 only for the combined checkpoint. Size S–M.

### Checkpoint BA-A — Focused Windows lifecycle gate

- All runtime lifecycle modules above pass on the AST-05 physical Windows checkout.
- Existing launcher duplicate/reuse/foreign-owner protections remain green.
- No tracked file outside the bounded runtime/test surface changes.
- The fix is committed on the lifecycle branch, then incorporated into the AST-23/24 descendant by an explicit ancestry-preserving merge or cherry-pick; never hand-edit divergent copies.

### Task BA-3 — Re-run and retain exact AST-24 acceptance

After incorporating BA-1/BA-2, record the new exact head and run `python -m pytest -q` once with stdout/stderr redirected to a uniquely named artifact. Record head, timestamp, Python, pytest, worktree and exit code in metadata. Retrieve the final summary after the process terminates.

**Acceptance criteria:**

- Exit code is 0, output reaches 100%, final summary contains no failures, and the output is retained.
- `git status --short --branch` shows no tracked test side effects.
- AST-24 focused frontend/browser evidence remains valid at the new descendant head, or is rerun if the integration changes its source/test inputs.

If the full run fails, preserve it, classify the first failure, fix only the owning task, and repeat the full suite only after focused proof. Never report `LOCAL BACKEND ACCEPTANCE PASSED` from a partial run or a rerun of only the failing file.

**Dependency:** BA-A. Size S verification.

## Remaining issues and adjusted completion order

### Immediate gates

1. **AST-05 installed qualification remains the sole READY task.** Its physical Windows branch is at `dded2ff`; finish actual duplicate launch, browser-closed operation, sign-in/wake, conflict, and recovery checks. BA-1/BA-2 belong here because they are Windows lifecycle defects. A harness pass cannot substitute for physical wake/sign-in evidence.
2. **AST-24 is correction-complete but acceptance-failed.** Preserve `0df1c1d` and the failed retained log as evidence. After the lifecycle fix is incorporated, execute BA-3. Do not reopen the four corrected Watch behaviors unless integration invalidates their evidence.
3. **AST-25 remains held.** Promote it only after AST-05 is accepted, AST-23/24 ancestry is preserved, and AST-24 has a retained full-suite pass.

### Product completion sequence

After those gates, retain the canonical vertical-slice order:

1. AST-25–27: complete Sources, cadence, review/Start, and truthful first result.
2. AST-06–11: managed provider metadata, vault, durable budgets, routing, validation, and owner UI before any paid-provider feature.
3. AST-28–32 and AST-50–53: assisted terminology/discovery and explicit geography/time contracts.
4. AST-33–42 and AST-54–55: returning-user intelligence, reports, briefings, alerts, questions, and search.
5. AST-43–49: backup/restore, update, accessibility/mobile/PWA, real-use content qualification, installed candidate, and owner documentation.
6. AST-16–18: complete the unchanged observation/comparison/human-value gates. These remain external blockers; elapsed time alone is not evidence.
7. AST-48/release acceptance: only after its dependencies and human-value gate pass. Optional AST-21/22 remain deferred unless separately authorized.

### Cross-cutting issues that must remain visible

- Main does not contain the unmerged Astra implementation stack. Every execution checkout must prove dependency ancestry; DONE on a branch does not mean shipped.
- The frontend has build/typecheck coverage but limited behavioral browser coverage. Each UI slice must retain server-state assertions and measured viewport/accessibility evidence rather than source-string checks alone.
- Python type checking is informational in current CI. Do not treat green CI as proof of Python type cleanliness; hardening that policy requires a separate bounded task, not scope creep in backend acceptance.
- Real source quality, private phone/PWA behavior, backup/update recovery, and human usefulness are not established by deterministic unit tests.
- Paid calls, live discovery, trial mutation, merge, deployment, and release promotion require their existing explicit gates and authorization.

## Final completion checkpoint

The app is complete only when every gate in `PRODUCT_READINESS.md` has an exact branch/artifact, commands, results, browser or physical evidence where required, and named remaining limitations; the plan validator and full local quality suites pass; the implementation stack is deliberately integrated; and the owner documentation matches the qualified artifact. No single backend pass, hosted CI run, or implemented feature branch is sufficient by itself.
