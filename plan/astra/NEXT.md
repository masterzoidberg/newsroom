# Immediate execution queue

Updated 2026-09-09 from the retained AST-24 backend run. This is a planning-only update: no task status is promoted, no merge is authorized, and AST-05 remains the sole READY task. See [BACKEND_ACCEPTANCE_AND_COMPLETION_PLAN](BACKEND_ACCEPTANCE_AND_COMPLETION_PLAN.md).

**Exactly one next task: AST-05 — Qualify the existing Start Newsroom launcher. Status: READY. TIER 3 — COMPLEX IMPLEMENTATION; reasoning high.**

Prompt: [AST-05-qualify-existing-launcher](prompts/AST-05-qualify-existing-launcher.md).

Main `3d7f9cf` lacks completed AST-01–04. Use an isolated checkout descended from the existing AST-05 stack (`astra/AST-05-start-newsroom`, inspected at `cddad09`), bringing only this current planning authority into that checkout after checking for newer work. Do not replay old implementation prompts or merge the stack as a side effect. Current planning changes are uncommitted on main; preserve them and unrelated work.

Following queue, all NOT_STARTED:

1. AST-23 — paused, retry-safe Watch setup contract (Tier 3/high), after AST-05.
2. AST-24 — Welcome and no-ID interest entry plus bounded correction gate (Tier 2/medium), after AST-23.
3. AST-25 — manual/existing Watch Sources (Tier 2/medium), only after AST-24 corrections and complete backend verification are accepted.
4. AST-26 — understandable cadence (Tier 2/medium), after AST-25.
5. AST-27 — review/Start and truthful first value (Tier 2/medium), after AST-26.

Then AST-06–11 complete managed AI configuration before AST-28–32 add assisted terminology/discovery. This removes the older artificial dependency of basic local onboarding on a finished paid-provider settings screen.

Blockers: AST-05 still needs installed qualification evidence, including supported sign-in/wake checks; a harness/CI pass cannot imply unperformed manual checks. AST-16/17/18 are blocked external value gates with the unchanged observation/eligible comparison/human input and separately authorized paid execution requirements. They do not authorize runtime contact now.

## AST-24 review disposition

The candidate review at head `93c80b564485f8a864b085af190f8b888b0a9f98` against AST-23 base `2ab4715ff1c267d8476a88bcd997380d16976d9d` found two P1 and two P2 issues. Commits through `0df1c1d39b93b47306d2093cf506599fc44888ef` address those four corrections, but AST-24 remains unaccepted and AST-25 is held because the retained full backend run failed. Preserve the corrected behavior and close these remaining gates:

1. fix the Windows runtime-supervisor portability and heartbeat-cleanup failures in the AST-05 lifecycle-owned surface;
2. incorporate that fix into the AST-24 descendant without breaking ancestry or the four corrected Watch behaviors; and
3. rerun the full backend suite and retain a passing final result and exit code.

The retained run at `0df1c1d` reached 100% but exited 1 with three `tests/test_runtime_supervisor.py` failures: two Windows-incompatible `signal.SIGKILL` uses and one heartbeat cleanup `WinError 32`. Hosted CI success is supporting evidence only. Do not mark AST-24 DONE, start AST-25, advance the canonical ledger, or begin AST-25-related implementation until the bounded fix and passing retained full run exist.

Do not start AST-06 early, broad superseded AST-12–15/19, speculative external discovery before AST-30, paid Ask, commercial pilot, any implementation in this audit session, or any trial promotion/merge/deployment. Do not contact port 8127 or active `phase29-trial` roots, recreate the Watch, reset the observation boundary or start an automation. Recorded boundary and limitations are in CURRENT_STATE.
