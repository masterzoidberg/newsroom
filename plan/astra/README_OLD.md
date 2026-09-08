# Astra completion plan

Audit baseline: `aad7d17ec91b56b68e1252c70bdf6521060c0bd1`, branch `main`, 2026-09-06 America/New_York (work continued after midnight UTC). Scope: audit and planning only. No application implementation is included.

This directory is the canonical new completion layer requested by the owner. It supersedes historical task ordering, not evidence/provenance invariants, migration history, or frozen trial protocols. `plan/astra` existed but was empty when inspected. Unrelated `.kilo/` and `Newsroom -v2.zip` were preserved.

## Start here

1. Read [EXECUTIVE_AUDIT.md](EXECUTIVE_AUDIT.md) and [CURRENT_STATE.md](CURRENT_STATE.md).
2. Read [CODEX_EXECUTION_RULES.md](CODEX_EXECUTION_RULES.md), [DECISIONS.md](DECISIONS.md), and [NEXT.md](NEXT.md).
3. Execute the first READY task in [TASKS.md](TASKS.md), using its matching [prompt](prompts/README.md). Revalidate dependencies and current HEAD first.
4. Record evidence, update task status and the immediate queue, and stop after the primary task. No task is DONE merely because its code exists.

## Planning map

| Document | Purpose |
|---|---|
| [MASTER_PLAN.md](MASTER_PLAN.md) | Milestones, dependency order, fastest reliable path |
| [STARTUP_AND_RUNTIME.md](STARTUP_AND_RUNTIME.md) | Port 8127 finding, launcher, lifecycle, installation |
| [AI_PROVIDER_SETTINGS.md](AI_PROVIDER_SETTINGS.md) | Configuration authority, credential boundary, routing contracts |
| [UX_AND_APPEARANCE.md](UX_AND_APPEARANCE.md) | Per-surface review, onboarding, dark theme, mobile |
| [PRODUCT_READINESS.md](PRODUCT_READINESS.md) | Daily-use and commercial-pilot acceptance |
| [COMMERCIAL_THESIS.md](COMMERCIAL_THESIS.md) | Product thesis, scores, hypotheses, falsification |
| [TEST_STRATEGY.md](TEST_STRATEGY.md) | Existing coverage and minimal additional verification |
| [DELETE_DEFER_KEEP.md](DELETE_DEFER_KEEP.md) | Safe simplification decisions |
| [AUDIT_EVIDENCE.md](AUDIT_EVIDENCE.md) | Checks, limitations, source map, current observations |

Future-session instruction: **Read plan/astra and execute the current READY task.** This audit itself does not authorize paid calls, changing the frozen trial, publishing a release, or beginning implementation during the audit session.
