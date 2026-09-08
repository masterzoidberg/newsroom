# Model and prompt strategy

| Class | Use | Default reasoning |
|---|---|---|
| TIER 1 — ROUTINE | Known-pattern docs/fixtures and mechanical bounded changes | low |
| TIER 2 — IMPLEMENTATION | Default frontend/service/test slices with decided behavior | medium |
| TIER 3 — COMPLEX IMPLEMENTATION | Transaction, concurrency, security or lifecycle interactions with a fixed contract | high |
| TIER A — ASTRA | Architecture/product decisions, repository-wide audit, adversarial review and conflicting acceptance evidence | high |

These are capability classes, not price claims or fixed commercial model names. Use the lowest class likely to meet the task; importance alone is not a reason for Astra. The next six prompts freeze product decisions and relevant files so implementation models need not re-audit the repository. Do not resend the entire master rebaseline request with every task.

Each prompt supplies one outcome, dependencies, read set, allowed surface, non-goals, UI states, invariants, acceptance, minimal tests and a stop condition. The ledger owns status even when a prompt exists. Historical templates remain available but must not execute unchanged. Generate a new dedicated prompt only as a future task enters the 3–6 task horizon; inspect landed dependencies first.

Escalate when schema work exceeds the explicitly anticipated slice, a public behavior conflicts with the contract, a prerequisite is absent, paid execution is necessary, a source-discovery provider cannot satisfy the decided contract, or an unrelated subsystem needs redesign. Return exact evidence and the smallest decision needed, not a generic request for Astra to implement everything. Tier A reviews the boundary and returns a repaired small task.

Routine operation keeps paid routing off by default. Heuristic local analysis is useful plumbing but not a local LLM. Semantic assistance is a separately displayed supported capability; paid use always requires deliberate opt-in and the durable admission mechanism. Tests use local fixtures/fakes. Estimates remain labeled; uncertain billed invocations are never invisibly retried. Trial and frozen eval provider routing stay separate from future product configuration.

At milestones, review the actual user journey and trust/cost boundaries. Re-run only affected checks unless a named release gate requires a full suite. Browser evidence is required for UI tasks; source assertions and TypeScript compilation cannot establish visual success.
