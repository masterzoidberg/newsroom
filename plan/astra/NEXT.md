# Immediate execution queue

1. **AST-02 — READY:** Identify application instances and diagnose port conflicts. Read its [prompt](prompts/AST-02.md), recheck current `main` before branching, and keep all development on the isolated Astra root/endpoint established by AST-01.
2. AST-03 — NOT_STARTED, waits for AST-02: supervise existing components safely.
3. AST-04 — NOT_STARTED, waits for AST-03: expose honest component status and recovery controls.

AST-01 is DONE on draft PR #1. Its implementation established the isolated Astra development target, removed Windows-only frontend-build subprocesses from backend pytest, and passed the clean Ubuntu backend/Ruff/frontend CI gate. The PR remains unmerged.

The UAP trial already has an approved configuration and a recorded boundary `2026-09-06T21:20:48Z`; earliest four-week boundary is `2026-10-04T21:20:48Z`, subject to active-observation/event-volume sufficiency. AST-16 continues that protocol only when explicitly executed. Do not recreate A2, reset the clock, start a monitoring automation, or alter the trial as part of AST-02.

AST-17 remains BLOCKED for actual comparative execution: an eligible frozen snapshot mapping, explicit paid-provider authorization, and human blinded scoring are still needed. Preparation does not authorize spending. AST-21/22 remain DEFERRED until their evidence gates justify them.

Before promoting any implementation to the active trial, record changed artifact/configuration and obtain the required trial change decision; isolated development itself is not blocked. Update this file after every primary task, including failures or changed dependencies.
