# Audit evidence and limits

## Repository identity

- HEAD: `aad7d17ec91b56b68e1252c70bdf6521060c0bd1` (`Sync current planning and review artifacts`), branch main.
- Audit began 2026-09-06 local; UTC had crossed into September 7. No commits or application changes made.
- Initial untracked state: `.kilo/`, `Newsroom -v2.zip`. `plan/astra` existed and was empty. Those unrelated files were untouched.
- Recent sequence: baseline `e0d626c`; approved Watch `6fefa65`; A3 repairs/rehearsal `9dea309`; frozen protocol `8a3caab`; short checkpoint `1c24e9d`; current artifact sync `aad7d17`.
- Current migration baseline: 36. Fresh temporary test databases exercise it; the live production database was not opened/migrated by this audit.

## Checks executed

| Check | Result | Limit |
|---|---|---|
| `python -m pytest -q` | PASS exit 0; full suite, 46 HTTPX deprecation warnings | quiet configuration suppresses count summary; separate collection confirmed 844 |
| `python -m pytest --collect-only -q -o addopts=` | 844 tests collected | collection is count confirmation, not execution evidence by itself |
| `ruff check newsroom tests` | PASS | configured E4/E7/E9 rules, not full security review |
| `python -m compileall -q newsroom tests` | PASS | syntax compilation only |
| `npm run build` in frontend | PASS, tsc no-emit and Vite 6.4.3, 42 modules | no standalone frontend lint rules; no clean dependency reinstall |
| `python -m newsroom.evals validate` | PASS, 46 cases | schema/corpus validity only |
| `python -m newsroom.evals lite-contract` | PASS, 20 questions | explicitly results not run |
| `python -m newsroom.evals baseline` | PASS exit 0, 20 cases | non-perfect baseline metrics; not Full-vs-Lite verdict |
| `git diff --check` | PASS during audit; final plan validation repeated | does not validate untracked Markdown semantics by itself |
| Read-only listener/process query | 8127 → Python API PID 48036; matching trial worker/scheduler present | process presence is not heartbeat/job-progress qualification |
| Public `/api/v1/health` on 8127 | HTTP success; Newsroom/ok/0.1.0-dev | liveness only; no authenticated production operations |
| Scheduled task query `Newsroom*` | no matching tasks returned | no claim that all hosts/accounts have no installations |
| Isolated Playwright Chromium | 16 settled routes × 2 widths, no page exceptions/error panels/page overflow | empty-state audit only; internal Settings overlap observed visually |

Browser audit used a fresh external temporary dev root, separate explicit port 18127, synthetic login and no worker/scheduler/network acquisition. Provider environment was forced local. Only that audit API was terminated afterward. The first pass was loading-state reconnaissance and was repeated with explicit `aria-busy` completion before settled assertions.

Final screenshots were produced outside the repository under `%TEMP%/newsroom-astra-audit-mzk6jiog`; temporary files are not durable release evidence. Findings are preserved here and in UX_AND_APPEARANCE. Login, desktop Watches and phone Settings were visually inspected. No source/private production content was copied into the plan.

## Inspection map

This was a cross-subsystem audit with targeted execution-path inspection, not a claim that every line of every historical file received manual review. Concrete findings reference actual symbols below; unresolved real-world behavior remains explicitly unknown.

| Area | Inspected evidence |
|---|---|
| Product/history | README; product spec/master/completion plan structure and relevant sections; phases-v2 README, Phase 28.5/29/29.6, architecture reconciliation memo; phases-old index; current git history |
| Acceptance | baseline acceptance, dogfood contract, trial readiness, A3 pipeline rehearsal, observation checkpoint, evaluation protocol/decision rule; prospective experiment authority |
| Runtime/deploy | full runtime/config/worker/scheduler; release manifest helpers; deployment task/launcher paths; operations/recovery runbooks |
| API/auth | create_app/middleware/health/readiness; domain router construction/settings/Ask routes; AuthService/security interfaces and authentication tests |
| Schema/ops | migration application/version/history handling; storage-backed jobs/metadata; operations backup/restore/export allowlist and recovery procedures |
| AI | capability bundle/local article provider/router execution; AnalysisProviderConfig/compatible adapter/reservation/route/persistence; Ask construction and injected synthesis; production router construction |
| Core chain | acquisition interface/security/body handling, document-processing transaction and promotion path; evidence-promotion/resolution/stage service interfaces and regression suites; monitoring/source discovery/research planner construction |
| UX | App, AppShell, auth, primitives, AdminViews, WatchManagement, Ask, CSS/manifest/service worker; all view inventory and settled browser routes |
| Tests/tooling | test inventory/conftest, frontend source/build tests and browser harness; CI, pyproject/frontend package; eval commands; recent repair regressions |
| Simplification | legacy/compatibility searches, removed-projection plan, tag bridge, budget history, missing-artifact compatibility, phase-specific runtime comments/scripts |

## Highest-confidence findings

- `runtime.py:_run_api` blindly binds; current listener independently identified as Newsroom. No ownership/reuse authority exists.
- `domain_api.py` constructs local Watch router; runtime local research router; `AskView.tsx` explicitly chooses local. The only normal real provider adapter is Article Analysis.
- `ArticleAnalysisService` holds configuration set at construction; `_resolve_route` can raise when paid is disabled, so default fallback behavior needs deliberate implementation.
- `domain.py:set_setting/list_settings` is not secret storage; secret-like keys are rejected/filtered and normal values are returned. Full backups include database state, making a secret SQLite column unsuitable.
- `ai.py:LocalArticleAnalysisProvider` now caps entity candidates at 100; A3 fixed the prior 444-entity error. Do not report that bug as current.
- A3 full-page Story deferral and metadata-only downstream positive path are explicitly documented; checkpoint proves no post-boundary value yet, not pipeline absence.
- `frontend/src/styles.css` lacks generic `.content-grid` mobile collapse; settled phone Settings screenshot confirms internal overlap.
- Ubuntu backend CI plus hard-coded `npm.cmd` in backend-collected test is a concrete configuration mismatch. No remote Actions run was queried, so this is a source-supported CI defect rather than an observed current hosted-run result.

## Not performed / not claimed

No paid-provider calls, live acquisition, production data inspection/mutation, process restarts, scheduled-task changes, installs/upgrades/restores, physical-phone test, full accessibility audit, populated browser journey, external market comparison, human usefulness scoring, four-week observation completion or release publication. Public health GET may generate ordinary service telemetry, but no application data/configuration was changed. No local secrets or full process command lines were printed.

Technical external verification was limited to Microsoft credential/DPAPI/task logon documentation and Python keyring documentation, linked next to the relevant architecture claims. Commercial scores are explicitly hypotheses/judgments rather than external market evidence.
