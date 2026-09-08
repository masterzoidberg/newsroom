# Startup and runtime contract

Current distinction: main `3d7f9cf` has separate API/worker/scheduler startup; AST-01–04 are complete on the unmerged stack and AST-05 has launcher implementation but incomplete installed qualification. See CURRENT_STATE and history/AST-01-04_COMPLETION_RECORD. Prior endpoint/process observations are preserved in STARTUP_AND_RUNTIME_OLD and are historical only; this audit made no runtime contact.

Retain one per-user supervisor around existing children, explicit fixed endpoint, OS-backed ownership, PID creation identity, bounded retries/reconciliation and cooperative writer drain. Reuse only verified matching installation/root/release ownership. Never kill unmanaged/foreign/unknown owners or silently change ports. Runtime/status code is in the AST-05 branch's runtime_identity.py, runtime_managed.py, runtime_supervisor.py, runtime_status.py and job_lease.py.

AST-05's next action is qualification of existing scripts/phase16_windows_deploy.ps1 and scripts/astra05_windows_smoke.ps1, not another supervisor implementation. Audit the harness first: it registers disposable scheduled tasks and has legacy fixed-name probes, so it must refuse pre-existing real legacy tasks and prove all cleanup targets belong to its test namespace. Never run it against the active trial or ordinary installed tasks.

Supported intended lifecycle is same Windows owner while signed in, browser closed/locked where qualified, safe bounded wake/sign-in catch-up. No pre-login/sleep/power-off collection guarantee. API unavailable means the UI directs the owner to external Start Newsroom; it cannot make an unreachable API restart itself. Status must distinguish connectivity, component health and actual Watch collection success.

Backup/update/restore remains AST-43/44 around existing operations; no live writer overwrite. Final named-artifact Windows/physical-phone proof is AST-48. Preserve old artifact and verified backup; code rollback is not schema downgrade. No trial changes, paid calls, merge or deployment in this planning pass.
