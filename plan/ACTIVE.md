# Active Execution

## Authority

- Product specification: `plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md`
- Current execution plan: `plan/rework-v2/EXECUTION_PLAN.md`
- Current plan map: `plan/rework-v2/README.md`
- Binding design/review/decision records: the remaining Markdown documents in
  `plan/rework-v2/`
- This file is the durable cursor; it does not override the authorities above.

## Status

IN PROGRESS — workflow instructions are reconciled. Product implementation is
at a partial M0.1 foundation and is not acceptance-complete.

## Completed

- Rework-v2 planning package, architecture review, decision record, and
  acceptance matrix are present.
- Managed migration-authority fencing and schema-readiness verification landed
  in commits `6a7e3e1` through `9d8077c`.
- Additive schema-40 foundation landed: Watch scope/lifecycle history, Source
  endpoints, and historical Watch–Source membership structures.
- Focused migration-authority regression tests pass.

## Current

- M0.1 — finish transactional scope/membership integration and its acceptance
  evidence. The migration scaffold exists, but application services, callers,
  integrity/export handling, and dedicated M0.1 acceptance tests are still
  missing.

## Next

- Reconcile the schema-40 upgrade fixtures, complete M0.1 service/caller
  integration and recovery/integrity/export checks, then stop at the required
  M0.1 review gate.
- Do not begin M0.2 until that gate is explicitly passed.

## Blockers

- Full suite is not green: the latest run had 1,016 passed, 2 failed, and 1
  skipped. The failures are legacy schema-upgrade fixtures whose expected
  migration ranges do not include schema 40.
- `migration_0040_research_membership_overlay.py` is present but is not
  referenced by `newsroom/migrations/__init__.py`; verify its intended role
  before declaring M0.1 complete.

## Important discoveries

- HEAD on `astra/AST-25-27-first-watch` exactly matches its upstream; the
  bootstrap edits in this working tree are intentionally uncommitted. The
  branch is nevertheless divergent from `origin/main` (172 commits ahead and
  4 behind). Do not merge `origin/main` as a bootstrap step.
- `.kilo/`, `.tmp/`, and ZIP snapshots are untracked local artifacts and have
  been preserved.
- Astra and older phase plans remain useful evidence, but rework-v2 is the
  current implementation sequence.

## Decisions / deviations

- This bootstrap does not authorize new product implementation, paid calls,
  trial access, deployment, merge, or push.
- Existing M0.1 commits are recorded as landed evidence, not as proof that the
  milestone's acceptance gate passed.

## Last verification

- `python -m pytest tests/test_rework_d27_migration_authority.py tests/test_runtime_identity_recovery.py` — 6 passed.
- `python -m pytest` — 1,016 passed, 2 failed, 1 skipped; see Blockers.
- `git fetch origin --prune` — completed; current branch remains `0/0` against its upstream.

## Resume instruction

For an explicit implementation request, read the current rework-v2 documents,
then continue from the first incomplete M0.1 requirement. Complete and verify
the milestone, update this cursor and the ExecPlan, and stop at its mandatory
review gate.
