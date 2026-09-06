# Phase 29 authoritative baseline acceptance

## Repository identity

- Branch: `main`
- HEAD at verification: `04e7f7ab50602b48b53cee5a9b3f25e047231c57`
  (`Close Phase 29.6 Story time-semantics baseline`)
- Applied schema: migration `0036`, schema version `36`
- Verification date: 2026-09-06

This record establishes the engineering baseline only. It does not convert
engineering closure into a Phase 29 product-value acceptance result.

## Verified engineering checks

The following commands were run from the repository root after the baseline
documentation update:

```text
python -m compileall -q newsroom tests
python -m pytest -q
ruff check newsroom tests
python -m newsroom.evals validate
python -m newsroom.evals lite-contract
python -m newsroom.evals baseline
git diff --check
```

From `frontend`:

```text
npm run lint
npm run typecheck
npm run build
```

Observed outcomes:

- `python -m compileall -q newsroom tests` — PASS, exit 0, no output.
- `python -m pytest -q` — PASS, 838 tests passed, 46 known HTTPX deprecation
  warnings, no failures.
- `ruff check newsroom tests` — PASS, `All checks passed!`.
- `python -m newsroom.evals validate` — PASS, 46 corpus cases valid.
- `python -m newsroom.evals lite-contract` — PASS, 20 questions validated for
  `newsroom-lite-20q-v1`; results explicitly not run.
- `python -m newsroom.evals baseline` — PASS, exit 0; 20 baseline/semantic
  cases executed. Its non-perfect metrics are not a product verdict.
- `git diff --check` — PASS, exit 0.
- `npm run lint` from `frontend` — PASS, TypeScript no-emit check.
- `npm run typecheck` from `frontend` — PASS, TypeScript no-emit check.
- `npm run build` from `frontend` — PASS; TypeScript check and Vite production
  build completed, transforming 42 modules.

No non-zero command is represented as passing.

## Explicit non-claims

This record does not establish:

- four-week real-use usefulness;
- Full superiority over Lite;
- superiority over v1;
- production installation acceptance;
- Windows upgrade or recovery qualification;
- phone/PWA acceptance;
- paid-provider behavior unless specifically exercised; or
- intelligence-value approval.

Contract validation and a successful baseline command are not comparative
evaluation results. No paid provider calls or real monitoring were performed
for this baseline.

## Remaining Phase 29 gates

The remaining work is to configure one approved trial Watch, rehearse the
installed automatic pipeline, freeze the comparative evaluation procedure,
begin the real observation window, log human usefulness, execute the
Full-vs-Lite comparison, and issue the Phase 29 intelligence-value verdict.
Phase 30 remains conditional on that verdict.

## Worktree and provenance note

At verification, the checkout contained pre-existing unrelated state: tracked
deletions under `plan/phases/`; untracked `.kilo/`, `plan/phases-old/`, several
`plan/phases-v2` continuation documents, `plan/PROJECT_COMPLETION_PLAN.md`,
`docs/reviews/PHASE_29_PRE_IMPLEMENTATION_ADVERSARIAL_REVIEW.md`, and a Phase
29.6 ZIP snapshot. These files were preserved and were not treated as release
evidence. No runtime database, credentials, user data, trial data, generated
benchmark result, or paid-provider output was changed.

`scripts/create_review_snapshot.py` builds from `git ls-files`, so untracked
planning/review documents are excluded and tracked paths missing from disk are
skipped. The existing ZIP is therefore a review artifact, not release
provenance. The bounded baseline files are kept separate from those unrelated
worktree changes.

## Authority

Implementation behavior is authoritative in the current code and migrations.
For product invariants and Phase 29 continuation, use
`plan/STANDALONE_NEWSROOM_PRODUCT_SPEC.md`, `plan/phases-v2/README.md`,
`plan/phases-v2/Phase 29.md`, `plan/phases-v2/Phase 29.5.md`, and
`plan/phases-v2/Phase 29.6.md`. The dogfood contract, human-usefulness log
template, and preregistered decision rule remain the governing acceptance
artifacts; this record does not duplicate them.
