# Astra execution baseline

## Identity

- Task: `AST-01 — Freeze the execution baseline and isolate development from observation`.
- Remote `main` HEAD at task start: `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f` (`Add Astra Newsroom completion plan`).
- Task branch: `astra/AST-01-baseline`, created directly from that HEAD.
- Applied schema remains migration `0036` / schema version `36`.
- The remote Git ref is the execution source of truth for this task. A GitHub remote has no staged/unstaged worktree state; no local checkout was cleaned or rewritten by this implementation.

This is an Astra engineering baseline, not a release, value, installed-Windows, paid-provider, or Phase 29 acceptance result. Historical phase acceptance records remain dated evidence rather than being rewritten.

## Frozen observation boundary

The approved Phase 29 trial remains the separate logical runtime `phase29-trial/prod`. Its official observation boundary remains:

`2026-09-06T21:20:48Z`

with earliest four-week boundary:

`2026-10-04T21:20:48Z`

AST-01 does not change its Watch, Sources, semantic scope, provider route, budget, runtime database, runtime root, processes, or port. Port `8127` remains reserved for that observed runtime unless its own change-control procedure explicitly records a change.

## Isolated Astra development target

Astra engineering uses an explicit development identity that cannot be confused with the observation runtime.

### Windows development root

```powershell
$devRoot = Join-Path $env:LOCALAPPDATA "Newsroom\astra-dev\dev"
```

### Windows manual test root

Use a per-run temporary root outside the repository, ending in `dev` so the existing `RuntimeConfig` guard accepts it:

```powershell
$testRoot = Join-Path $env:TEMP "Newsroom\astra-tests\<run-id>\dev"
```

Pytest should continue to prefer its own temporary directories for automated runtime tests.

### Development endpoint

The default documented Astra developer API endpoint is:

`http://127.0.0.1:18127`

Example explicit launch:

```powershell
python -m newsroom.runtime api --environment dev --root $devRoot --host 127.0.0.1 --port 18127
python -m newsroom.runtime worker --environment dev --root $devRoot --worker-id astra-dev-worker
python -m newsroom.runtime scheduler --environment dev --root $devRoot
```

No Astra development or browser test may default to the active trial root or port `8127`. Tests that need a listener should use an ephemeral socket or an explicitly assigned non-trial port.

## Root-safety proof

`newsroom.config.RuntimeConfig` already enforces both requirements needed here:

1. the resolved root name must equal the explicit environment (`dev` or `prod`), and
2. the runtime root cannot be the repository root or any descendant of it.

`tests/test_runtime_config.py` covers distinct dev/prod roots, suffix rejection, source-tree rejection, explicit-environment precedence, and missing-environment rejection. AST-01 adds no alternate root authority.

## CI portability correction

Before AST-01, three backend pytest contract tests for the frontend invoked `npm.cmd run build`: Phase 12, Phase 13, and Phase 14. `npm.cmd` is a Windows executable name, while the Ubuntu backend job intentionally installs only Python dependencies. The Phase 12 instance was identified during initial audit; the first hosted AST-01 run then exposed the two remaining instances in Phase 13 and Phase 14.

AST-01 separates responsibilities instead of duplicating frontend installation in the backend job:

- backend pytest validates source-level PWA/product/workbench/Ask contract invariants without spawning npm;
- the existing frontend CI job owns `npm ci`, TypeScript checks, and the production Vite build on Ubuntu.

This preserves both contract coverage and a real clean frontend build while removing every Windows-only npm dependency from backend pytest.

## Verification evidence

A supplied repository snapshot was used only as an isolated verification copy. For the affected paths, its Git blob hashes matched current GitHub `main` exactly before modification:

- `tests/test_phase12_frontend.py`: `6ed7cb3026d28a883b351c785ee57b3880585ed0`
- `tests/test_phase13_frontend.py`: `d1e587c2a6d78608949f008f8bc906396676483e`
- `tests/test_phase14_frontend.py`: `e772acdca58882c1ccc82fc792e62521ee4e1381`
- `newsroom/config.py`: `7d3840a76782d592214f525d5a24eebb3c32db4a`
- `.github/workflows/ci.yml`: `1e227ce182febf242be2525ea6475e080ed7b11b`
- `frontend/package.json`: `1336caaaa7b52d454ebf2b532ca60de22368821d`

Observed checks:

| Check | Result |
|---|---|
| `python -m pytest -q tests/test_phase12_frontend.py tests/test_runtime_config.py` before correction | **FAIL as expected**: Phase 12 raised `FileNotFoundError` for `npm.cmd`; the five runtime-config tests passed |
| Same targeted command after the first source-contract refactor | **PASS**: 6 passed |
| `python -m pytest -q tests/test_phase12_frontend.py tests/test_phase13_frontend.py tests/test_phase14_frontend.py tests/test_runtime_config.py` after hosted discovery/fix | **PASS**: 8 passed |
| `python -m newsroom.evals validate` | **PASS**: 46 corpus cases valid |
| `python -m newsroom.evals lite-contract` | **PASS**: 20-question contract valid; comparative results intentionally not run |
| `python -m newsroom.evals baseline` | **PASS**: 20 baseline/semantic cases executed; metrics are diagnostic, not a value verdict |
| Full `python -m pytest -q` in the local container | **UNVERIFIED locally**: execution exceeded the bounded local tool window after reaching 21%; no pass is claimed from that attempt |
| Ruff in the local container | **UNVERIFIED locally**: Ruff is not installed in that container |
| `npm run build` against bundled snapshot `node_modules` | **UNVERIFIED locally**: the uploaded dependencies are Windows-shaped and lack Rollup's Linux optional binary; this is not treated as a repository build failure |
| Draft PR run `34076549706` at commit `99aa49c3047f31ccc18b5e6f6a3869811e36abff` | **PARTIAL/FAIL**: frontend and Ruff passed; backend exposed the two remaining Phase 13/14 `npm.cmd` failures |
| Draft PR run `34076899509` at commit `1d22282955c3dfa9057c0c765dd8b4988de58236` | **PASS**: Ubuntu backend pytest, Ruff, frontend dependency install, lint, typecheck, and production build all succeeded |

The hosted clean run is the authoritative full backend/Ruff/frontend-build verification for the implementation code. The final plan-only closure commit is also checked by the draft PR before merge.

## Non-claims and preservation

- No real paid provider call was made.
- No production/trial process was started, stopped, restarted, or contacted.
- No runtime database, backup, logs, acquired content, credentials, or private trial artifacts were modified.
- No migration or application runtime behavior changed.
- Historical Phase 29 acceptance and dogfood records remain unchanged.
