# Astra completion authority

Rebaseline: 2026-09-07. Inspected checkout: `main`, `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`. This is an audit and completion plan, not product implementation or release certification.

Read [CURRENT_STATE](CURRENT_STATE.md), [PRODUCT_VISION](PRODUCT_VISION.md), [UX_AND_ONBOARDING](UX_AND_ONBOARDING.md), then [NEXT](NEXT.md) and [TASKS](TASKS.md). **AST-05 is the only READY task**, with a revised qualification prompt. Its code is already on an unmerged stack; do not reimplement it on main.

| Authority | Purpose |
|---|---|
| [FEATURE_GAP_ANALYSIS](FEATURE_GAP_ANALYSIS.md) | All 30 completion capabilities, evidence and task coverage |
| [COMPLETION_ROADMAP](COMPLETION_ROADMAP.md) | Dependency-ordered product milestones and gates |
| [TASKS](TASKS.md) | Sole status authority; completed IDs retained; bounded future contracts |
| [NEXT](NEXT.md) | One primary task and five queued tasks |
| [DECISIONS](DECISIONS.md) | Durable choices, supersessions and unresolved choices |
| [MODEL_AND_PROMPT_STRATEGY](MODEL_AND_PROMPT_STRATEGY.md) | Model classes and escalation rules |
| [AUDIT_EVIDENCE](AUDIT_EVIDENCE.md) | Git state, code anchors, checks and limitations |
| [JOURNEY_VALIDATION](JOURNEY_VALIDATION.md) | Six simulated finished journeys and missing links |
| [PRODUCT_READINESS](PRODUCT_READINESS.md) | Release acceptance gates |
| [BACKEND_ACCEPTANCE_AND_COMPLETION_PLAN](BACKEND_ACCEPTANCE_AND_COMPLETION_PLAN.md) | Retained AST-24 backend failure, bounded Windows lifecycle fix, and adjusted completion order |
| [prompts/README](prompts/README.md) | Six current execution prompts |
| [AI_PROVIDER_SETTINGS](AI_PROVIDER_SETTINGS.md), [STARTUP_AND_RUNTIME](STARTUP_AND_RUNTIME.md), [TEST_STRATEGY](TEST_STRATEGY.md), [CODEX_EXECUTION_RULES](CODEX_EXECUTION_RULES.md) | Narrow technical constraints; ledger owns order |

`*_OLD.md`, `history/`, and `prompts/archive/` are historical evidence and never execution instructions. `prompts/superseded/` contains uncompleted older prompt contracts retained for traceability; being moved there does not mean DONE. COMMERCIAL_THESIS and DELETE_DEFER_KEEP remain narrow references, not completion scope authorities. Legacy MASTER_PLAN, EXECUTIVE_AUDIT and UX_AND_APPEARANCE canonical files now route to this rebaseline.

Execution: validate branch and dependencies; change READY → IN_PROGRESS only when explicitly executing; record commands, artifact/branch, browser evidence and unresolved gates; mark DONE only when all acceptance is established. DONE on an unmerged branch does not mean shipped on main. Promote exactly one eligible successor in TASKS/NEXT/prompts together. Failed qualification remains IN_PROGRESS or BLOCKED with its missing evidence. Stop after one task. No merge is implicit.

Astra owns architecture, product synthesis and conflicting evidence. Tier 2 implementation models execute most slices; Tier 1 handles mechanical documentation; Tier 3 handles bounded transaction/lifecycle interactions. See the strategy. Neither this plan nor a prompt authorizes paid calls, trial access, deployments, runtime promotion or automatic continuation.
