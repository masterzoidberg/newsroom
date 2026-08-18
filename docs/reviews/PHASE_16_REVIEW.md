# Phase 16 Review — Mature Product Release Acceptance

## Verdict

**Not approved for production promotion.** The application and deployment path
pass the local and clean-room checks that can be run in this workspace, but the
release gate remains open until an operator creates the accepted checkpoint,
registers the Windows tasks, configures private Tailscale Serve, and completes
the physical-device acceptance matrix.

This is an honest deployment boundary: the current source worktree is dirty,
and the deployment script refuses to install it as production.

## Review rerun — 2026-08-17

The Phase 16 gates were rerun against the current checkout. Results were
unchanged: `python -m pytest --tb=short` passed with 293 tests, compilation,
the 30-case corpus validation, frontend typecheck/build, high-severity npm
audit, and `git diff --check` passed. The deployment guard exited 0 in
validation-only mode and made no install, runtime, task, or Tailscale changes.
The current worktree remains dirty, `Newsroom-API`/`Newsroom-Worker`/
`Newsroom-Scheduler` task count remains 0, and the Tailscale CLI remains
uninstalled. No new Critical or Required application finding was identified;
the existing production-promotion blockers remain open.

## Post-audit reconciliation — 2026-08-18

The independent post-audit review supersedes the verification counts and
runtime-completeness assumptions above while preserving them as historical
Phase 16 evidence. The current published implementation checkpoint is
`fe8be60b79780d2be9183121486fa5c846081120`; the worktree remains dirty because
local artifacts are still untracked and the Phase 17–28 plan revision is now in
progress.

The current backend baseline collects 381 tests. A full run produced 380 passes
and one failure in
`tests/test_monitor_runtime_acceptance.py::test_production_composition_source_monitor_lifecycle_aaa_to_b`;
an isolated rerun passed. The failure is a nondeterministic assertion caused by
same-second timestamps and random-ID ordering, and must be reconciled in Phase
17 before the suite is a release gate.

The current schema includes migration 0014/schema version 14. The clean-room
migration-0013 result documented below remains valid only as historical
rehearsal evidence and is not the current schema claim.

### Post-audit reconciliation resolved by Phase 17 — 2026-08-18

The nondeterministic acceptance assertion identified above was repaired in
Phase 17: `test_monitor_runtime_acceptance.py` now identifies the first created
DocumentVersion by the value persisted at the first acquisition step and
compares the second version by set membership instead of positional
`ORDER BY retrieved_at, id` ordering. The full backend suite (382 tests,
including new accepted-but-unsupported Monitor target coverage) passes
repeatedly, and frontend typecheck/build pass. This review's verdict remains
unchanged: Phase 16 was a deployment rehearsal, not final product promotion;
approval stays blocked on the Phase 17+ gates and operator acceptance steps.

## Release identity

| Identity | Result |
|---|---|
| Current repository HEAD | `fe8be60b79780d2be9183121486fa5c846081120` |
| Current worktree | Dirty; not eligible for promotion |
| Clean-room rehearsal commit | `e78a5d521d75326e8235d2d341b68fd1fd71d690` |
| Clean-room installed artifact digest | `fa6bc215f30dd4276b7099f8cbbeccc89be02643f3d65a31d22855c60cfa1c92` |
| Runtime root used in rehearsal | Temporary `%TEMP%` `runtime\prod` root outside the repository |
| Persistent Windows tasks | None registered |
| Tailscale CLI | Not installed on this workstation |

The clean-room commit and installed digest are rehearsal evidence only; they are
not the final accepted source checkpoint.

## Severity-ranked findings

### Required — operator acceptance remains incomplete

1. **No accepted clean source checkpoint.** `git status --short` reports the
   Phase 13–16 changes and the repository correctly reports
   `worktree_clean: false`. The installer refuses `-Mode Install` for this
   state. Create and review one local checkpoint commit containing the accepted
   product, then rerun the deployment script from that clean checkout.
2. **Windows auto-start and private ingress were not activated.** The machine
   has no `Newsroom-API`, `Newsroom-Worker`, or `Newsroom-Scheduler` scheduled
   tasks, and `tailscale.exe` is unavailable. Run the opt-in installer switches
   on the target Windows host, verify the restart bounds and task identity, then
   verify that Tailscale Serve exposes only `127.0.0.1` through the tailnet.
3. **Physical production acceptance was not executable here.** Desktop,
   laptop, phone, tablet, PWA update, notification permission, private mobile
   access, reboot/power-loss, and provider-outage checks need the target host,
   browsers, and operator credentials. Existing automated and Phase 12 evidence
   covers the application behavior, but not those external deployment facts.
4. **The final quality thresholds are not represented by a standalone scored
   acceptance corpus.** Frozen evolution replay proves zero false merges in its
   covered cases, and Ask/report fixtures prove resolvable evidence citations
   and closed-world generation. A full standalone citation-correctness score
   and important-Claim recall score are not currently emitted; the required
   `0.95` and `0.85` release thresholds therefore cannot be asserted.

### No Critical application findings

No new Critical security, data-loss, authorization, or integrity finding was
found in this review. Phase 15's security, privacy, telemetry, backup, restore,
and recovery controls remain covered by the full suite and runbooks.

## Implemented deployment controls

- `newsroom/release.py` creates deterministic source/artifact identities and
  verifies installed file hashes, rejects path traversal in manifests, ignores
  runtime databases/secrets/build caches, and detects dirty Git state.
- `newsroom/runtime.py` provides explicit `api`, `worker`, and `scheduler`
  processes. All require `--environment` and `--root`; production API binding is
  limited to loopback, migrations run before process start, and process logs use
  a five-file, 10 MiB rotating handler.
- `scripts/phase16_windows_deploy.ps1` provides read-only validation by default,
  refuses dirty production installs and non-empty overwrite targets, copies only
  manifest-listed artifacts, writes launchers and `release-manifest.json`, and
  optionally registers bounded Task Scheduler tasks or configures Tailscale.
- `docs/OPERATIONS_RUNBOOK.md` and `docs/RECOVERY_RUNBOOK.md` document explicit
  roots, secrets, health/readiness, backups, retention, stop/start, restore,
  upgrade, and failure procedures.

## Verification evidence

### Repository and application checks

| Check | Result |
|---|---|
| `python -m pytest --tb=short` | **293 passed**, 33 existing HTTPX deprecation warnings |
| `python -m compileall -q newsroom scripts tests` | Pass |
| `python -m newsroom.evals validate` | Corpus valid, 30 cases |
| `npm.cmd run typecheck` | Pass |
| `npm.cmd run build` | Pass; JS 210.68 kB / 62.77 kB gzip, CSS 18.69 kB |
| `npm.cmd audit --audit-level=high` | 0 vulnerabilities |
| `git diff --check` | Pass; existing LF/CRLF normalization warnings only |
| `scripts/phase16_windows_deploy.ps1 -Mode Validate` | Pass; no install/tasks/Tailscale changes |

The repository has no configured `poetry` or `pnpm` format/lint/type wrappers;
the direct configured checks above are the evidence used by prior reviews.

### Clean-room production-root rehearsal

Using the isolated clean-room commit listed above:

- the deployment script copied the exact manifest-listed application and PWA
  artifacts outside the source repository;
- migrations 1 through 13 applied to the explicit `prod` runtime root;
- operator `verify` returned `integrity: ok`, `schema_version: 13`, and all
  contiguous schema versions;
- the installed API returned healthy `/api/v1/health`, ready
  `/api/v1/readiness`, and a 200 same-origin PWA shell;
- online backup, logical export, restore, and post-restore integrity verification
  all returned success;
- the API process stopped cleanly and did not leave a registered task or public
  listener.

### Intelligence-loop coverage

The complete logical loop remains covered across the passed Phase 08–14
integration tests: monitor scope and scheduling, local worker execution,
evidence-bound Story evolution, Living Report revision, durable gap/Question
follow-up, alert creation/deduplication/delivery state, and evidence-grounded
Ask Newsroom citations and refusal paths. The clean-room runtime smoke tested
deployment plumbing, but did not manufacture production data or claim a physical
mobile loop that was not run.

The post-audit trace narrows that statement: those tests exercise separate
service/API capabilities and manual compositions. The actual scheduled Source
Monitor path currently ends after acquisition and DocumentVersion persistence;
automatic relevance, article analysis, Evidence/Claims ingestion, Story
evolution, report revision, and alert emission are not proven in one production
workflow. Phase 23 is the revised unattended-loop gate.

## Acceptance metrics and known limitations

- Frozen Story evolution cases: false-merge count **0** in the covered corpus;
  false-split behavior is separately tested and remains reviewable.
- Phase 14 fixture: every returned Ask citation was resolvable; unsupported or
  prompt-injected requests were refused. This is fixture evidence, not a full
  corpus-wide citation score.
- Closed-world report generation rejects unsupported propositions
  transactionally; a standalone synthesized-proposition aggregate is not yet
  emitted by the evaluation harness.
- Local-first provider routing remains the default. No paid provider was enabled
  during acceptance, so live provider-outage behavior is represented by bounded
  failure/cost-cap tests rather than an external provider run.
- Browser notification state preserves in-app alerts when permission is denied;
  permission prompts and mobile push behavior still require target-browser
  confirmation.
- The process-local request limiter is intentionally single-process; this
  release does not support multi-user or multi-worker scale.

## Required finalization sequence

1. Create/review the local accepted checkpoint; do not deploy from the dirty
   worktree.
2. From that clean checkout, run `phase16_windows_deploy.ps1 -Mode Validate`,
   then `-Mode Install -RegisterTasks` against the chosen production roots.
3. Confirm `release-manifest.json`, migration/integrity output, task restart
   bounds, API/PWA same-origin behavior, and application authentication.
4. Configure and inspect private Tailscale Serve; do not enable Funnel.
5. Run the physical-device acceptance matrix and record the standalone corpus
   citation/important-Claim metrics.
6. Update this review to **Approved**, record the final accepted commit, and
   update the Phase 16 completion record.
