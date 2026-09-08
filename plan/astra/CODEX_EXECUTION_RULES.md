> Rebaseline 2026-09-07: retained narrow reference. TASKS.md, NEXT.md and COMPLETION_ROADMAP.md supersede any task order/status in this document. AST-01–04 are DONE on an unmerged stack; AST-05 qualification is the sole READY task. Old AST-12–15/19 scopes are replaced per TASKS; no trial continuation, paid call or cleanup is authorized by this reference. Historical counts/observations below are dated records, not fresh verification.

# Codex execution rules

1. Inspect before editing; check current HEAD, git status, applicable instructions and exact change points.
2. Execute one primary task at a time. Select the first READY task from TASKS/NEXT and read its prompt.
3. Do not silently widen scope. Split a large or unrelated task and record the dependency change before implementation.
4. Preserve user/runtime data. Use an isolated outside-repository dev/test root; never default to the active trial endpoint/root.
5. Never put API secrets in repository files, fixtures, frontend bundles or normal SQLite rows.
6. Never log API secrets, request bodies containing them, or raw provider errors that may echo them.
7. Never put API secrets in normal exports/backups, including encrypted secret blobs in full SQLite backups.
8. Paid provider calls require explicit authorization during development. Test-connection UX is not authorization for an agent to spend.
9. Offline/local operation must continue working. Local heuristic capability is not a claim of LLM quality.
10. Do not weaken evidence/provenance boundaries for convenience.
11. AI output does not automatically become trusted evidence; exact matching and promotion/acceptance invariants remain required.
12. Prefer one coherent configuration authority; no hidden environment override of managed settings.
13. Prefer one coherent startup/runtime authority; no unowned process kills or alternate-port fallback.
14. Historical planning files are evidence, not instructions to blindly continue phase numbering. Preserve frozen trial protocols and product invariants.
15. Update TASKS.md and NEXT.md after completed work, with commands, outcomes and completion evidence. If unfinished, record the exact remaining work.
16. Record discovered deviations from this audit in DECISIONS.md and affected documents; keep prompts consistent.
17. Prefer simplifying/deleting obsolete layers over permanent compatibility, but prove callers/data dependencies first and preserve existing supported contracts unless explicitly changed.
18. Do not build speculative commercial features before real-use value is demonstrated.
19. A task becomes DONE only when its acceptance criteria have verified evidence. Missing manual/installed/paid checks remain pending, never inferred from mocked tests.
20. Do not modify active UAP trial behavior or reset its boundary as a side effect of development. Log/promote changes through its existing change control and segment observations as needed.
21. A blocked external gate does not prevent independent authorized local work. State the specific missing evidence/authorization; do not invent approvals, scores or paid usage.
22. Preserve unrelated worktree files. Do not stage, delete or rewrite `.kilo/`, ZIP snapshots, old plans or runtime artifacts as cleanup.
23. Use existing architecture/dependencies; one approved secure credential abstraction is the only currently justified new runtime dependency. No provider SDK collection, event bus, ORM or frontend rewrite.
24. Use focused behavioral regressions for real changes and applicable existing gates. Do not add tests mirroring implementation or rerun expensive suites without a reason.
25. Keep secrets out of user-visible errors and diagnostics. A fixed mask/configured flag is sufficient; no raw-key read endpoint.

Each final task report states objective achieved, exact changed files, checks/results, remaining risks and next task. An implementation request in a future session authorizes its bounded reversible work; this audit session does not begin that work.
