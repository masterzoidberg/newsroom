# Verification strategy

## Existing evidence

Current offline backend suite passes: 844 collected tests, full run exit 0, 46 HTTPX deprecation warnings. Ruff passes. Frontend `npm run build` passes TypeScript no-emit plus Vite production compilation. `lint` and `typecheck` scripts are the same TypeScript command; repeating them adds no independent frontend lint coverage. CI mypy is explicitly informational (`|| true`); green CI would not mean type-clean Python.

Strong existing suites cover artifacts, acquisition policy/SSRF boundaries, auth/CSRF, idempotent queues/coalescing, durable paid analysis, exact promotion integrity, Story/report/alert replay and corrections, temporal truth, grounded refusal and evaluation contracts. Keep those regressions. Many frontend tests inspect strings/build output; the legacy Playwright harness is fixed to 8127, creates data and expects older navigation. Do not run it unchanged on the active application.

No need for another broad test framework or hundreds of phase-labeled tests. Add focused behavior tests for the following gaps. Prefer one reusable safe browser harness parameterized by explicit test URL/root over copying the legacy script.

## Minimal additional matrix

| Area | Minimum useful proof | Task |
|---|---|---|
| Startup singleton | two concurrent launchers, identical/different root, stale PID creation time, mismatched release | AST-02/03 |
| Port collision | matching healthy API, foreign listener, unknown owner, race between preflight and bind, no random port/no kill | AST-02 |
| Crash/restart | each child crashes; supervisor crashes with child alive; bounded retry exhaustion; no duplicate downstream objects | AST-03 |
| Long work | handler exceeds existing lease, second claim/recovery attempt, cooperative stop/cancel, paid call uncertain | AST-03/08 |
| Process health | process alive but heartbeat stale, scheduler stopped, worker stopped, API unavailable, no work due | AST-04 |
| Install/sign-in | clean user profile, shortcut, browser closed, lock/wake, reboot/sign-in, same-user credential availability | AST-05/19 |
| Settings persistence | fresh/upgrade DB, expected revision conflict, no-secret schema, restart persistence | AST-06 |
| Credential lifecycle | approved OS backend, wrong user/locked store, rotate two-store failure, remove failure, no plaintext fallback | AST-07 |
| Secret redaction | sentinel through request validation, returned errors, logs, telemetry, repr, DB, full backup, logical export and browser storage | AST-07/10/11 |
| Provider tests | fake timeout/auth/schema/JSON/model errors; explicit bounded reservation; no calls on typing/list/save | AST-10 |
| Destination security | HTTPS enforcement, keyless loopback, userinfo/query secret rejection, DNS/redirect/host edit, no cross-host credential forwarding | AST-10 |
| Budget | multi-process reservations, restarts/reloads, disabled/blocked/failed/uncertain invocation, retry bounds and test-call spending | AST-08 |
| Reload | long-lived worker sees next generation, in-flight pinned generation, disable race and no env resurrection | AST-09 |
| Fallback | disabled/deleted/no budget chooses labeled local for new work; local failure remains failure; uncertain paid not silently retried | AST-09 |
| Settings UX | complete Add AI Provider journey with real local worker + fake remote transport, no returned key, safe stale-edit errors | AST-11 |
| Onboarding | fresh empty DB → first named Watch/source → due fixture → useful inspection, scoped Ask/refusal; no raw IDs | AST-12 |
| Theme/mobile | component bounds as well as document overflow, Settings two-column overlap regression, contrast/focus/zoom, all user states | AST-13 |
| Backup/update | verified round trip, corrupted backup rejection, disk/write failure, stopped writers, compatible rollback, secret exclusion | AST-14/19 |
| Real-use chain | body vs metadata quality, broad navigation, blocked access, unchanged/saturation/refusal, qualifying downstream output and replay | AST-15 |
| Evidence value | real owner usefulness entries, active interval/denominators, unchanged comparison protocol and blinded human scoring | AST-16–18 |
| PWA | first load vs cached load, offline API, missing asset, upgrade from old shell, recovery from failed response, supported physical phone | AST-19 |

## Commands and execution discipline

From repository root, after checking no test resolves production paths:

```powershell
python -m pytest -q
ruff check newsroom tests
python -m newsroom.evals validate
python -m newsroom.evals lite-contract
python -m newsroom.evals baseline
git diff --check
```

From `frontend`: `npm run build`. For focused implementation run the affected existing test modules first. Full paid comparisons/live_test_b are not included. Corpus validate and lite-contract verify definitions, not superiority. Baseline's non-perfect results are diagnostic, not an accepted product verdict.

AST-01 must fix the concrete CI portability/setup gap: `tests/test_phase12_frontend.py` executes `npm.cmd`, while backend CI runs Ubuntu and installs only Python dependencies. Do not infer a remote CI failure result from this source inspection; verify the corrected workflow on its target platform. Ruff's narrow configured rule set is not a complete security/style audit.

## Evidence standards

Record command, runtime/platform/tool version, HEAD/artifact identity, exit code, test count or checked cases, and what was not exercised. Use fixtures/fake keys; never check in real keys or private data. OS vault tests use disposable namespaced entries and remove only those entries afterward. Paid live provider qualification needs explicit approval and a bounded budget; mocked tests cannot be called paid-provider certification.

Full real-use smoke: install → one-action launch → account setup → named topic/source/Watch → due acquisition → relevance → Article Analysis → exact Evidence/Claim → qualified Story → Report → material Alert → inspect citation → Ask grounded question and no-evidence refusal → disable provider/local run → verified backup → restart/upgrade/recovery → phone/PWA and offline-state check. Use a source/body fixture that actually qualifies; test deferral separately rather than treating it as chain completion.
