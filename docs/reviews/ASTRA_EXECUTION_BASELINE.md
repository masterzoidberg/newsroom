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

Before AST-01, `tests/test_phase12_frontend.py` invoked `npm.cmd run build`. That is a Windows executable name and caused the Ubuntu backend pytest path to fail before the frontend contract assertions could run. The backend job also intentionally installs only Python dependencies.

AST-01 separates responsibilities instead of duplicating frontend installation in the backend job:

- backend pytest validates source-level PWA/product contract invariants without spawning npm;
- the existing frontend CI job owns `npm ci`, TypeScript checks, and the production Vite build on Ubuntu.

This preserves both contract coverage and real build coverage while removing the Windows-only backend dependency.

## Verification evidence

A supplied repository snapshot was used only as an isolated verification copy. For the affected paths, its Git blob hashes matched current GitHub `main` exactly before modification:

- `tests/test_phase12_frontend.py`: `6ed7cb3026d28a883b351c785ee57b3880585ed0`
- `newsroom/config.py`: `7d3840a76782d592214f525d5a24eebb3c32db4a`
- `.github/workflows/ci.yml`: `1e227ce182febf242be2525ea6475e080ed7b11b`
- `frontend/package.json`: `1336caaaa7b52d454ebf2b532ca60de22368821d`

Observed local/container checks on that isolated snapshot:

| Check | Result |
|---|---|
| `python -m pytest -q tests/test_phase12_frontend.py tests/test_runtime_config.py` before correction | **FAIL as expected**: frontend test raised `FileNotFoundError` for `npm.cmd`; the five runtime-config tests passed |
| Same targeted command after the source-contract refactor | **PASS**: 6 passed |
| `python -m newsroom.evals validate` | **PASS**: 46 corpus cases valid |
| `python -m newsroom.evals lite-contract` | **PASS**: 20-question contract valid; results intentionally not run |
| `python -m newsroom.evals baseline` | **PASS**: 20 baseline/semantic cases executed; metrics are diagnostic, not a value verdict |
| Full `python -m pytest -q` in the container | **UNVERIFIED locally**: execution exceeded the bounded local tool window after reaching 21%; no pass is claimed |
| Ruff in the container | **UNVERIFIED locally**: Ruff is not installed in the container |
| `npm run build` against bundled snapshot `node_modules` | **UNVERIFIED locally**: the uploaded dependencies are Windows-shaped and lack Rollup's Linux optional binary; this is not treated as a repository build failure |

The draft PR's clean GitHub Actions Ubuntu jobs are the authoritative full backend/Ruff/frontend-build verification for this branch. Their exact run result is recorded in `plan/astra/TASKS.md` when AST-01 is closed.

## Non-claims and preservation

- No real paid provider call was made.
- No production/trial process was started, stopped, restarted, or contacted.
- No runtime database, backup, logs, acquired content, credentials, or private trial artifacts were modified.
- No migration or application runtime behavior changed.
- Historical Phase 29 acceptance and dogfood records remain unchanged.
