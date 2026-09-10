# Reworked Newsroom completion plan

## Outcome

Deliver completion in three explicit increments:

1. **Local Core Release:** an owner can install, create a Topic Watch without IDs, add Sources, choose cadence, start it, return to useful changes, inspect evidence, search, recover data and use the supported phone/PWA surface.
2. **Assisted Intelligence Release:** managed AI configuration, reviewed terminology and source suggestions, additional Watch types, reports/briefings, questions and scoped Ask work safely and coherently.
3. **Value-qualified Release:** representative content, installed artifact, physical-device and human-value gates pass with retained evidence.

“App complete” means increments 1 and 2 are implemented and the engineering qualification gates pass. “Value-qualified release” additionally requires increment 3 and cannot be manufactured from unit tests or elapsed calendar time.

## Operating rules

- The active backend task is Gate 0. Reconcile its actual result; do not assume it passed.
- Preserve existing AST IDs for traceability. Reclassify or change dependencies; do not renumber historical work.
- One task owns each implementation change. Later qualification checkpoints may report defects but must create small defect records rather than absorbing fixes.
- A Codex run owns a milestone-sized batch, not a single task. It makes one bounded commit per AST task, records focused evidence, and continues automatically while gates remain green.
- Run focused tests per task. Run the complete backend/frontend suite at milestone checkpoints, not redundantly after every unrelated UI edit unless the risk warrants it.
- UI tasks retain desktop, measured 390 CSS-pixel, keyboard, zoom, error/recovery and server-state evidence.
- No paid provider call, active-trial mutation, deployment or merge is implied.

Execution batches and stop rules are authoritative in [AUTONOMOUS_EXECUTION_RUNBOOK](AUTONOMOUS_EXECUTION_RUNBOOK.md). Checkpoints are normally automatic continuation gates, not mandatory chat handoffs.

## Gate 0 — Accept the current foundation

Complete this sequentially before new product work:

1. Finish the Windows runtime-supervisor fix currently in progress.
2. Retain the exact full backend result at the resulting AST-24 descendant head.
3. Finish or explicitly isolate the remaining physical AST-05 sign-in/wake checks.
4. Confirm AST-23 and corrected AST-24 ancestry and evidence.
5. Update the canonical ledger once, using the exact results.

Gate 0 passes only when the full backend result is retrieved with exit code 0 and no failures. If physical wake/sign-in remains human-blocked, mark that evidence gate separately; do not rerun or reopen already accepted AST-24 Watch behavior.

## Scope classifications

| Classification | Meaning | Existing work |
|---|---|---|
| CORE | Required for a coherent local product | AST-25–27, 33–36, 39–40, 42–46, 49 |
| ASSISTED | Required for the full assisted-intelligence vision, but not for the first useful local release | AST-06–11, 28–32, 37–38, 41, 50–54 |
| ENHANCEMENT | Useful but not required to call the primary product complete | AST-55 |
| CHECKPOINT | Evidence aggregation, not a feature implementation bucket | AST-47, AST-48 |
| EXTERNAL_GATE | Cannot be completed through ordinary coding alone | AST-16–18 |
| OPTIONAL | Execute only after a separate decision | AST-20–22 |
| HISTORICAL | Preserve; never execute again | AST-01–04, superseded AST-12–15/19 |

Smart-tag browsing (AST-55) is excluded from the critical path. Paid Ask (AST-21), commercial pilot (AST-22), and obsolete-entry cleanup (AST-20) are not completion requirements.

## Streamlined dependency corrections

Adopt these after Gate 0. All unlisted task dependencies remain unchanged.

| Task | Current dependency | Reworked dependency | Reason |
|---|---|---|---|
| AST-39 Alert triage | AST-38 | AST-35 | Alerts do not require briefing preferences. |
| AST-41 Question-first Watches | AST-29, AST-35 | AST-27, AST-35 | Manual question setup does not require AI terminology. |
| AST-42 Search/history | AST-35, AST-41 | AST-35 | General search does not require question-first setup. |
| AST-43 Backup controls | AST-11, AST-05 | AST-05 | Backup is independent of AI settings; repeat secret-specific checks after AST-11. |
| AST-50 Geography/time decision | AST-29, AST-41 | AST-29 | Scope semantics do not require question-first UI. |
| AST-52 Person/organization Watch | AST-29, AST-23 | AST-24 | Manual Subject selection should not wait for assisted terminology. |
| AST-53 Developing-event Watch | AST-24, AST-35 | AST-27 | Watch creation does not require completed evidence navigation. |
| AST-45 Accessibility audit | thirteen UI dependencies | all CORE UI surfaces completed | It is a bounded cross-surface checkpoint; assisted surfaces are checked in their owning tasks. |
| AST-47 Journey qualification | eleven feature dependencies | relevant release increment completed | Run once per release increment; do not make optional features block core qualification. |
| AST-48 Release qualification | AST-46, AST-47, AST-49, AST-18 | engineering: AST-46, AST-47, AST-49; value-qualified: plus AST-18 | Separate engineering readiness from human-value approval. |

This removes the main artificial chain in which AI terminology blocked questions, questions blocked search, briefing UI blocked alerts, and nearly every enhancement blocked accessibility and release qualification.

## Execution plan

### Phase 1 — Finish the first Watch

Execute sequentially because each extends the same setup state machine:

#### AST-25 — Sources

- Add/reuse/detach a Source by name or URL without IDs.
- Preserve shared-source ownership and explicit approval.
- Verify unsafe URL, retry, partial failure and paused-Watch behavior.

#### AST-26 — Cadence

- Add plain cadence choices over existing scheduler policy.
- Keep policy private to the Watch when edited.
- Verify persistence, bounds, timezone display and shared-policy isolation.

#### AST-27 — Review, Start and truthful progress

- Review saved scope, Sources and cadence, then start idempotently.
- Display persisted scheduled/collecting/processing/no-change/deferred/ready/error states.
- Verify the complete empty-workspace-to-first-result fixture journey.

#### Checkpoint C1 — First Watch accepted

- Full backend and frontend quality commands pass.
- Fresh and returning browser journeys pass at desktop and measured 390 CSS pixels.
- No raw IDs, duplicate Monitors/jobs, network-dependent tests or false “ready” state.

### Phase 2 — Local daily value and recovery

The following lanes may progress according to the dependency waves in the autonomous runbook. They are not all immediately independent: Lane 2B begins only after AST-35, while Lane 2C may start as soon as Gate 0 passes. Use separate worktrees only when file ownership does not overlap.

#### Lane 2A — Returning intelligence

1. AST-33: persist the review boundary.
2. AST-34: named Watch Home and complete since-visit pagination.
3. AST-35: summary → Claim → exact source Evidence navigation.
4. AST-36: create/read one Living Report from named Watch context.
5. AST-40: Story changes, disagreements and correction preview.

#### Lane 2B — Alerts and search

1. AST-39 after AST-35: Important/All/history and scoped alert controls.
2. AST-42 after AST-35: named paged search, saved items and history.

AST-39 and AST-42 do not wait for briefings or question-first setup.

#### Lane 2C — Recovery

1. AST-43 after Gate 0/AST-05: verified backup and redacted diagnostics.
2. AST-44: controlled restore/update recovery and honest export guidance.

#### Checkpoint C2 — Local Core Release candidate

- Run journeys A, C, E and F from `JOURNEY_VALIDATION.md` using deterministic fixtures.
- Perform AST-45 as a bounded audit of the completed CORE surfaces only. Fix only demonstrated cross-surface defects; create separate defect tasks for logic failures.
- Complete AST-46 PWA cache/update recovery.
- Draft/finalize AST-49 owner documentation against the qualified behavior.
- Run AST-47 for the Core increment as evidence aggregation, not feature development.
- Run AST-48 engineering qualification without claiming the AST-18 human-value verdict.

This checkpoint produces an installable Local Core Release even if assisted AI or external human validation is not yet complete. If it passes, continue to the managed-AI run unless the user explicitly requested a core-only stopping point.

### Phase 3 — Managed AI foundation

Execute AST-06–11 sequentially because they form one security boundary:

1. AST-06: public typed provider metadata.
2. AST-07: OS-vault credential lifecycle.
3. AST-08: durable multi-process paid admission.
4. AST-09: operation-boundary configuration resolution.
5. AST-10: bounded provider validation and safe APIs.
6. AST-11: owner provider/cost UI.

#### Checkpoint C3 — Provider safety

- Sentinel is absent from responses, logs, database, browser storage, diagnostics, backups and exports.
- Concurrent/restarted workers cannot overspend.
- Local remains the default and unavailable/disabled paid routing fails safely.
- Re-run AST-43/44 secret-boundary assertions; do not rebuild their UI.

This lane is security-sensitive and must not be compressed into a single large implementation task.

### Phase 4 — Assisted setup and alternate intents

Two lanes can proceed after C3.

#### Lane 4A — Terminology and Sources

1. AST-28: bounded semantic vocabulary adapter.
2. AST-29: terminology review UI.
3. AST-30: short source-recommendation decision checkpoint.
4. AST-31: implement only the approved candidate contract.
5. AST-32: recommendation/source-health UI.
6. AST-50: short geography/time semantics checkpoint.
7. AST-51: implement only the frozen scope contract.

AST-30 and AST-50 are decision checkpoints. Time-box each to producing an explicit contract; they are not implementation phases.

#### Lane 4B — Alternate Watch intents

1. AST-52 after AST-24: person/organization Watch using manual aliases.
2. AST-53 after AST-27: developing-event Watch without inventing a Story.
3. AST-41 after AST-27/35: question-first Watch and bounded research.
4. AST-54 after AST-41/42: named scoped Ask context using the existing local endpoint.

Do not make Lane 4B wait for semantic suggestions unless a specific acceptance case actually requires them.

#### Checkpoint C4 — Assisted setup accepted

- Journeys A–D pass with fake providers, ambiguity/refusal/rejection cases and safe URLs.
- Disabled/unavailable provider paths retain a fully usable manual fallback.
- No suggestion becomes accepted scope, Source, Claim or Evidence without explicit governed review.

### Phase 5 — Briefings and full daily workflow

1. AST-37: durable briefing schedule backend after AST-36.
2. AST-38: briefing preference UI after AST-37.

These no longer gate alert triage. Verify concurrent due ticks, retry, timezone/DST, wake catch-up, pause and zero-paid behavior before the UI task is accepted.

AST-55 smart-tag browsing can be scheduled after core/full release based on user demand. It does not block C2–C5.

#### Checkpoint C5 — Engineering-complete app

- Re-run AST-47 across journeys A–F using the full intended feature set.
- Repeat the cross-surface accessibility audit only for surfaces added after C2.
- Update AST-49 documentation for assisted features.
- Run AST-48 against a named isolated Windows artifact and supported private phone/PWA configuration.
- All applicable backend, frontend, migration, security, recovery and browser suites pass with retained summaries.
- No unresolved P0/P1 engineering defect remains.

At C5, the application is engineering-complete. External value gates remain separately visible.

### Phase 6 — Value qualification

- AST-16: complete the unchanged observation protocol.
- AST-17: execute the frozen comparison only with eligible inputs and explicit paid authorization.
- AST-18: issue the evidence-based value/scope verdict after AST-16, AST-17 and representative journey evidence.

After AST-18, append the value verdict to AST-48’s engineering evidence. Do not rebuild or rerun unrelated features solely because the external gate completed; rerun only checks invalidated by elapsed time, artifact change or discovered defects.

## Verification economy

Use four levels instead of running everything after every task:

| Level | When | Required proof |
|---|---|---|
| Focused | Every implementation task | affected unit/API/browser tests and static checks for touched code |
| Lane | End of a parallel lane | lane integration journey and neighboring regressions |
| Milestone | C1–C5 | full backend, frontend build/typecheck, plan consistency and relevant browser journeys |
| Release | Named artifact | installed lifecycle, recovery, PWA/phone, security, content journey and retained hashes/results |

A failed milestone run is retained once. Diagnose and run focused proof before repeating the entire suite. Hosted CI supplements but does not replace required local/physical evidence.

## Measures of forward progress

Track outcomes rather than raw task count:

| Measure | Target |
|---|---|
| First Watch | fresh owner reaches a truthful first result without IDs |
| Returning value | complete bounded since-visit changes and evidence path |
| Recovery | verified backup/restore/update path without terminal data manipulation |
| Assisted setup | useful reviewed suggestions with safe manual fallback |
| Daily workflow | report, briefing, alert, question and search paths are reachable by name |
| Engineering quality | named artifact passes C5 with no P0/P1 defect |
| Human value | AST-18 verdict supported by actual observation/comparison evidence |

Report CORE, ASSISTED, ENGINEERING and VALUE progress separately. Never calculate one misleading percentage from optional and blocked tasks.

## Risks and controls

| Risk | Control |
|---|---|
| Active backend chat changes heads while this plan is written | Transition checklist records actual heads and results before adoption. |
| Parallel lanes conflict in shared frontend files | Define API/state contracts first; use separate branches and integrate one lane at a time with milestone tests. |
| Qualification tasks become broad cleanup | Checkpoints record evidence and open bounded defects; they do not absorb refactors. |
| Local release is mistaken for value-qualified release | Keep C2/C5 and AST-18 labels distinct in UI/docs/reports. |
| AI work delays basic usefulness | Local Core Release completes before managed AI and remains functional with providers disabled. |
| Optional features delay release | AST-20–22 and AST-55 remain outside the critical path. |
