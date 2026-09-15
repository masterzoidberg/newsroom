# Newsroom repository contract

This file is the operating map for Codex. Product detail belongs in the
authoritative documents below; do not copy those specifications into this
file.

## Authority and current direction

1. `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md` — product contract and
   invariants.
2. `plan/README.md` and the current execution plan named by `plan/ACTIVE.md` —
   currently
   `plan/rework-v2/EXECUTION_PLAN.md`.
3. The binding design, review, and decision documents linked by that plan —
   currently the other documents in `plan/rework-v2/`.
4. `docs/adr/`, `docs/ARCHITECTURE.md`, and verified review/evaluation records
   — implementation evidence and durable decisions.
5. Current code and tests — evidence of what is actually implemented, not a
   substitute for an unresolved product decision.
6. `plan/astra/`, `plan/phases-v2/`, `plan/plan-rework/`, and older root plans
   — historical evidence unless `plan/ACTIVE.md` explicitly promotes one.

When sources conflict, preserve product invariants, follow the active plan,
and record a superseding decision. Never treat a filename, task number, or
older README as authority by itself.

## Plan-driven execution

When the user asks Codex to implement, execute, complete, or continue a plan,
the named plan or phase is the unit of work. Checklist items and individual
files are not normal stopping points.

Before editing:

1. Read the active plan and its linked authority documents.
2. Inspect the current branch, status, upstream relationship, recent commits,
   relevant code, and relevant tests.
3. Identify completed work from code, tests, and durable plan evidence; do not
   reimplement it.

During execution, repeatedly identify the next incomplete coherent requirement,
implement it, verify it, repair regressions caused by it, update tests and the
execution cursor, and continue automatically. Stop at the plan's explicit
review gate or exit gate, not after an ordinary subtask.

A phase is complete only when its applicable requirements and acceptance
criteria pass, relevant checks have been run, failures have been investigated,
and limitations are recorded in the active plan and `plan/ACTIVE.md`.

Stop and ask the user only for a materially unspecified product decision,
irreconcilable authority conflict, destructive or irreversible action,
missing credentials/external infrastructure, an explicit plan gate, or a
genuine blocker that safe local engineering cannot resolve. Routine reversible
engineering choices must not create a "continue" handoff.

## Repository and safety rules

- Inspect local state before comparing with or fetching remote state. The
  local checkout, tracked changes, untracked files, and local commits are
  evidence and must be preserved.
- Do not reset, clean, delete, force-push, rewrite history, or check out over
  local work. Do not make `origin/main` authoritative over the current branch.
- Preserve `.kilo/`, `.tmp/`, ZIP snapshots, runtime artifacts, and historical
  plans unless the user explicitly requests a separately justified cleanup.
- Use disposable databases and runtime roots outside the repository. Do not
  contact the active trial root or port 8127, make paid calls, deploy, merge,
  or change trial boundaries without explicit authorization.
- Keep migrations additive and preserve applied migration history. Never put
  secrets, runtime databases, downloaded article bodies, or credentials in the
  repository.
- Keep changes surgical and within the active plan. Record useful unrelated
  improvements as follow-up work.
- Do not commit or push unless the user explicitly asks or the active plan's
  accepted checkpoint explicitly requires a local commit. Never push as a
  side effect of verification.

## Repository-specific verification

Run only checks applicable to the changed surface, then the plan's exit-gate
checks. The commands supported by this repository are:

- Backend tests: `python -m pytest -q`
- Backend lint: `ruff check newsroom tests`
- Python syntax/import compilation: `python -m compileall -q newsroom tests`
- Evaluation validation: `python -m newsroom.evals validate`
- Evaluation contract/baseline checks: `python -m newsroom.evals lite-contract`
  and `python -m newsroom.evals baseline`
- Frontend checks from `frontend`: `npm run lint`, `npm run typecheck`, and
  `npm run build`
- Change whitespace check: `git diff --check`
- Informational typing baseline: `mypy newsroom` (do not report it as a
  release gate; the existing annotation backlog is documented in
  `docs/TOOLING.md`)

Browser, Windows, live-provider, trial, and deployment scripts under `scripts/`
are gated checks. Run them only when the active plan explicitly requires them
and their authorization/fixture prerequisites are satisfied.

## Durable state and resumption

`plan/ACTIVE.md` is the small execution cursor. Keep it honest and update it
at plan changes, milestone gates, and checkpoints with the current plan,
completed work, current requirement, next requirement, blockers, discoveries,
decisions, and last verification. It is a pointer, not a second specification.

After a normal implementation increment, resume from the first incomplete
requirement in the named ExecPlan. A future Codex session must be able to
reconstruct the next safe action from repository files without this chat.
