# Newsroom v2 — project assessment and completion plan

Assessment date: 2026-09-06  
Repository: `G:\Projects\Newsroom -v2`  
Inspected branch: `main`  
Inspected HEAD: `04e7f7ab50602b48b53cee5a9b3f25e047231c57` — Close Phase 29.6 Story time-semantics baseline

## 1. Where the project is

Newsroom is a substantial implemented application at the **Phase 29.6 engineering-closure stage, awaiting Phase 29 real-use and comparative acceptance**. It is beyond an MVP scaffold. The primary remaining work is to establish that it produces useful intelligence in unattended real use, resolve the practical product gaps that trial exposes, and qualify a reproducible private Windows release.

Do not restart earlier phases or turn every historical roadmap item into a release requirement. Follow `phases-v2/README.md`, `Phase 29.md`, `Phase 29.5.md`, and `Phase 29.6.md`, subject to the product invariants in `STANDALONE_NEWSROOM_PRODUCT_SPEC.md`. Phase 30 shipping scope must follow the Phase 29 value decision.

Assumption: “complete” means a dependable first release of the existing standalone, personal news-intelligence product: Windows runtime, private browser/phone access, approved sources, evidence-grounded research, bounded costs, and recoverable data. A public multi-tenant service, subscriptions, and a broad connector marketplace are outside this plan.

### Implemented capability map

Paths below are repository-relative.

| Area | Evidence in current code | Assessment |
|---|---|---|
| Standalone runtime | `newsroom/app.py`, `runtime.py`, `storage.py`, `migrations.py` | FastAPI, SQLite, separate API/worker/scheduler processes; migrations through 0036. No Hermes runtime dependency. |
| Authentication and operations | `auth.py`, `security.py`, `operations.py`, `release.py`, `cli.py` | Sessions/CSRF, request controls, backup/restore, integrity, export, and release identity already exist. Installed-system qualification remains necessary. |
| Watches and acquisition | `intelligent_monitoring.py`, `monitoring.py`, `acquisition.py`, `scheduler.py`, `jobs.py` | Watches, approved vocabulary/source candidates, source monitors, bounded acquisition, durable jobs, and scheduling are present. |
| Automatic evidence pipeline | `content_artifacts.py`, `document_processing.py`, `article_analysis.py`, `evidence_promotion.py` | Durable content, relevance, structured analysis, exact verified evidence, and candidate Claims are connected. Real analysis provider is opt-in. |
| Stories, Reports, Alerts | `automatic_story_resolution.py`, `story_automation.py`, `report_automation.py`, `alert_automation.py` | Downstream automation, exact causes, replay/recovery handling, and in-app delivery exist. |
| Research and corrections | `research_questions.py`, `story_corrections.py`, `source_robustness.py`, `hypotheses.py` | Bounded research, canonical evidence reevaluation, corrections, and lineage-derived dependency analysis exist. Real-world usefulness is unproven. |
| Temporal truth and Ask | `temporal.py`, `ask.py`, `tests/test_phase29_temporal.py`, `tests/test_phase296_story_time_semantics.py` | Knowledge-time reads, historical Ask, exact-cause reports, and stable source-time matching are implemented with regression coverage. |
| Product UI | `frontend/src/App.tsx`, `components/AppShell.tsx`, `views/` | React/TypeScript interface; five Simple navigation entries and nine Advanced entries. Build succeeds. Browser usability is a separate gate. |
| Comparative evaluation | `newsroom/evals/benchmark.py`, `benchmark_provider.py`, `benchmark_contract.py`, `lite.py` | Real Full/Lite runners and fail-closed contract checks exist. Contract validation is not a completed comparative experiment. |

### Verification performed for this assessment

| Check | Result |
|---|---|
| `ruff check newsroom tests` | PASS. |
| `npm run build` in `frontend` | PASS; runs TypeScript checking followed by Vite production build. |
| `python -m newsroom.evals validate` | PASS; 46 valid cases. |
| `python -m newsroom.evals lite-contract` | PASS; 20 questions, `newsroom-lite-20q-v1`, OpenAI/gpt-4o-mini, cutoff 2026-08-25. Explicitly reports results not run. |
| `python -m newsroom.evals baseline` | Completed with exit 0; reports 20 baseline/semantic cases. Non-perfect metrics are present; successful execution is not proof that product thresholds are met. |
| `python -m pytest -q` | PASS; all 838 tests finished with exit 0 (collection count independently checked). Warnings concern the deprecated httpx `app` shortcut. |
| `python -m compileall -q newsroom tests` | PASS. |
| `npm run lint` / `npm run typecheck` in `frontend` | Both PASS. |
| `git diff --check` | PASS for tracked changes; the new plan was also reviewed separately. |

`npm run lint` and `npm run typecheck` are both `tsc --noEmit`; they are not independent JavaScript lint checks. CI runs backend Ruff/tests and frontend checks; mypy is explicitly informational. Phase 29.6 records 238 historical mypy errors, but that count was not independently remeasured here.

This assessment did not launch a production installation, inspect a private runtime database, call paid providers, conduct phone/browser acceptance, or run a real observation window. Existing deployment and browser tests include source-level checks; a green suite must not be represented as fresh installed-system acceptance.

## 2. Confirmed gaps and decisions

### A. The value-acceptance artifacts are missing

`docs/DOGFOOD_CONTRACT.md` explicitly says no approved subject/source set or dedicated trial profile has been configured. `docs/reviews/PHASE_29_HUMAN_USEFULNESS_LOG_TEMPLATE.md` is an empty template. No `docs/reviews/PHASE_29_INTELLIGENCE_VALUE_REPORT.md` is present in the inspected tree.

The code may be engineering-ready, but the repository does not establish a completed trial, blinded comparison, or intelligence-value verdict. External evidence may exist elsewhere; link and validate it before repeating work. Do not infer approval of a subject from the UI's hard-coded “UAP disclosure” default.

### B. Product onboarding still exposes implementation details

`frontend/src/views/WatchManagementView.tsx` requires a canonical Target ID and separately selected policy. Some advanced research/hypothesis actions also require IDs. This is workable for an operator, but first-use setup still assumes knowledge of the database model.

Recommended release approach: keep the current Watch model and add selection/creation affordances to the existing flow. Avoid a new onboarding subsystem. Operator-assisted setup is sufficient to begin Phase 29; polished self-service onboarding belongs after the value gate unless setup actually prevents the trial.

### C. Watch support and direct Monitor support differ

`MonitorExecutionService.handle()` in `newsroom/monitoring.py` rejects non-`source` monitor targets with `unsupported_target`. This is a real limitation, but topic/subject Watches are not therefore broken: `intelligent_monitoring.py` connects approved Sources through ordinary source-targeted Monitors and associates the information need.

Recommended release approach: use that existing Watch-to-source-Monitor path. Clearly explain or prevent unsupported direct monitor configurations at creation time while preserving compatibility for existing records. Do not build four speculative target adapters just to make the schema's accepted values look complete.

### D. Real AI capability is not uniformly wired into the product

The application has an opt-in real article-analysis provider. Local providers in `newsroom/ai.py` are deterministic implementations; they should not be confused with a deployed general-purpose local LLM. The normal API constructs `AskService(service.db_path)` without a synthesis router. Hosted mode falls back to local when hosted synthesis is unavailable. The Full benchmark explicitly supplies a contract-bound hosted router.

Consequently, a strong benchmark result does not automatically establish that the normal UI offers the same synthesis experience. Before trial, record the actual provider behavior for analysis, Ask, and research. Before release, either retain and clearly describe the local product behavior or connect the existing synthesis capability through the normal API with the existing budget, citation, refusal, and telemetry controls. Decide from trial evidence; do not add multiple providers by default.

### E. Evaluation tooling exists, but the operational experiment needs closure

The evaluation CLI exposes validation and baseline commands, but no end-to-end paired-run command. Python runner APIs are already available. A small operator wrapper may be warranted for snapshot binding, run output, blinding, scoring, and reproducibility.

Resolve an important experiment-design question before collecting scores: the frozen 20-question contract references fixed corpus cases and an August 25 cutoff, while the proposed dogfood observation window is still pending. Map each question and each of the five decision categories to eligible evidence. Do not bind an unrelated later corpus and assume this is a valid useful comparison. Preserve the frozen contract; if a distinct prospective experiment is required, version and preregister it separately before its results exist. Insufficient category coverage means inconclusive evidence, not a manufactured pass.

### F. Documentation and release provenance have drifted

The root README still calls Phase 28.875 active and Phase 29 blocked, and contains conflicting live-provider status statements. `frontend/README.md` still describes the UI in future tense. The worktree contains existing deleted `plan/phases/` files, untracked replacements in `plan/phases-old/` and `plan/phases-v2/`, an untracked review document, `.kilo/`, and a Phase 29.6 ZIP.

Preserve this work. Before release, reconcile intended documentation moves and artifact inclusion into an accepted clean commit. `scripts/create_review_snapshot.py` uses `git ls-files`; untracked planning authority is excluded and tracked missing paths are skipped. An existing ZIP is not sufficient release provenance.

## 3. Ordered completion work

Task estimates describe focused work packages, not guaranteed delivery dates. Runtime data, logs, snapshots, and benchmark output remain outside the repository. Store only reviewed summaries and safe references in project documentation.

### Phase A — establish trial readiness

#### A1. Record one authoritative baseline — Small

**Dependencies:** None.

**Work/files:** Reconcile the current-state sections of `README.md`, `frontend/README.md`, and `plan/phases-v2/README.md`. Add a concise acceptance record under `docs/reviews/` with the actual commit, test results, and remaining gates. Account for the existing documentation moves without deleting unrelated work or committing it indiscriminately.

**Acceptance:**
- [ ] Documentation consistently says Phase 29.6 engineering closure / Phase 29 value acceptance pending.
- [ ] Current check results and limitations are recorded; historical reports are clearly historical.
- [ ] The intended release/review file set includes required authority documents.

**Verification:** Run the engineering matrix in section 5; inspect `git status --short`, `git diff --check`, and the generated tracked-file manifest when preparing a checkpoint.

#### A2. Configure one approved trial Watch — Small

**Dependencies:** A1; user supplies subject, approved Sources, runtime location, and spending choice.

**Work/files:** Fill `docs/DOGFOOD_CONTRACT.md` with approved configuration and owners. Use existing runtime/Watch APIs and `docs/OPERATIONS_RUNBOOK.md`; provision a dedicated database outside the repository. No new profile framework is needed.

**Acceptance:**
- [ ] Subject, approved Source IDs/classes, semantic scope, cadence, provider behavior, budget ceiling, start date, and minimum four-week window are explicit.
- [ ] API, worker, and scheduler have a named uptime owner and restart procedure.
- [ ] A backup restores successfully into a different explicit temporary runtime root.

**Verification:** Inspect Watch health and queued jobs; acquire from an approved Source; verify the restored database and confirm the developer/prod databases were not substituted.

#### A3. Rehearse the complete installed pipeline — Medium

**Dependencies:** A2.

**Work/files:** Use `runtime.py`, `document_processing.py`, the existing Phase 23 automation services, and existing acceptance tests. Write a trial-readiness record. Change only the responsible code/test pair for each demonstrated blocker, in separate focused fixes.

**Acceptance:**
- [ ] Approved Source change produces version/artifact, explainable relevance, analysis, verified spans/Claims, Story, Report revision, and exact-cause in-app Alert where rules warrant them.
- [ ] Irrelevant content, unchanged content, absent qualifying evidence, and unavailable providers produce truthful bounded outcomes.
- [ ] Restart/retry does not duplicate accepted Claims, report revisions, or alerts; citations resolve to the actual acquired version.

**Verification:** Run the real API/worker/scheduler against the dedicated runtime, exercise restart and retry, then run focused regression tests for any changes. Include an actual article-body check: feed metadata alone must not be mistaken for fetched full text.

#### A4. Freeze the evaluation procedure before results — Medium

**Dependencies:** A1; A2 defines the prospective subject/corpus.

**Work/files:** Review `evals/lite/20q_contract.json`, `newsroom/evals/lite.py`, `benchmark.py`, and `docs/reviews/PHASE_29_DECISION_RULE.md`. Write a bounded execution protocol under `docs/reviews/`. If necessary, add one small script using existing runner APIs plus targeted tests; do not introduce a new benchmark framework.

**Acceptance:**
- [ ] Contract cutoff, question/case suitability, snapshot selection, category mapping, rubric, scorer, blinding method/seed, and provider budget are settled before outcomes are scored.
- [ ] All 20 paired runs can produce resumable/auditable outputs; partial or invalid runs cannot be labeled a valid comparison.
- [ ] Snapshot hash/binding, effective provider/model/settings, refusal outcomes, latency, and actual cost are recorded; controlled fallback/configuration mismatches fail closed.

**Verification:** Use existing controlled provider integration tests in `tests/test_eval_lite.py`; perform a non-scored rehearsal. Contract-only validation is insufficient. Keep the original snapshot immutable; account for Ask audit writes using an explicitly identified execution copy with the same frozen corpus.

**Checkpoint A:** Engineering baseline green, one approved Watch works unattended, restore succeeds, and the evaluation method is fixed. Begin observation as soon as A2/A3 permit; A4 must finish before evaluation outcomes are collected/scored.

### Phase B — prove value and decide what ships

#### B1. Run the minimum four-week observation window — Ongoing operator work

**Dependencies:** A2/A3.

**Work/files:** Use the existing human-usefulness template and canonical product telemetry. Keep trial records outside source control; reference them in the eventual value report.

**Acceptance:**
- [ ] At least four weeks of observation with recorded uptime, source/corpus mix, outages, and configuration/version changes.
- [ ] Reviewed Attention, Alerts, Ask answers/refusals, Reports, and Research results have honest usefulness/correction notes.
- [ ] Report useful/not-useful rates with denominators, research yield, correction burden, time-to-first-value, cost, and backup health; record missing observations rather than filling them in.

**Verification:** Weekly reconcile a sample of log entries to canonical object IDs and telemetry. Record trial fixes and any comparability impact. Extend observation if volume is too low; calendar duration alone does not prove value.

#### B2. Execute and blind-score Full versus Lite — Medium plus human scoring

**Dependencies:** A4 and a sufficient B1 window.

**Work/files:** Use `freeze_corpus_snapshot`, `bind_contract`, `FullBenchmarkRunner`, `LiteHarness`, and `PairedBenchmarkOrchestrator`. Preserve inputs, raw envelopes, validity failures, blind labels, and scoring separately from the live database.

**Acceptance:**
- [ ] Every scored pair shares the approved frozen evidence basis and verified effective execution conditions; no test-double output is counted as real evidence.
- [ ] Scoring is completed before revealing Full/Lite identities; unsupported answers, bad citations, honest refusals, and both-system failures remain visible.
- [ ] Publish category-level results and concrete cases alongside latency/cost; run the agreed v1/human-labeled comparison needed by the product contract as well.

**Verification:** Recompute snapshot/corpus identity and pairing validity, audit citations and score mappings, then apply the unchanged decision rule. A zero-exit baseline command alone does not establish superiority over v1.

#### B3. Issue the intelligence-value verdict — Small

**Dependencies:** B1/B2.

**Work/files:** Create `docs/reviews/PHASE_29_INTELLIGENCE_VALUE_REPORT.md` and a bounded `plan/phases-v2/Phase 30.md` only if the decision supports shipping.

**Acceptance:**
- [ ] Apply the existing rule: clear Full advantage in at least three of five architecture-dependent categories, without a material trustworthiness regression.
- [ ] Choose the documented verdict: proven; partially proven with one bounded validation tranche; Lite-equivalent with simplification; or core value not proven.
- [ ] Assign KEEP / SIMPLIFY / CONTEXTUALIZE / DEFER / REMOVE to capabilities and derive the release scope from evidence.

**Verification:** Each conclusion links to trial observations and scored cases. An inconclusive result stays inconclusive. Do not proceed to broad Phase 30 work by relabeling engineering success as product value.

### Phase C — finish the accepted product, conditional on B3

#### C1. Make first-use Watch setup usable — Medium

**Dependencies:** B3.

**Likely files:** `frontend/src/views/WatchManagementView.tsx`, the existing API/type helpers if needed, and focused browser coverage.

**Acceptance:**
- [ ] A new user can select/create the intended target and approve Sources without looking up canonical IDs manually.
- [ ] Empty-state and health messages explain the next action, missing Sources/scope, and acquisition-only behavior.
- [ ] Setup reaches the first evidence-backed result through existing policies and jobs; no silent source activation or new top-level navigation.

**Verification:** Fresh-account browser walkthrough on desktop and phone-sized viewport; create, pause, resume, and inspect one Watch.

#### C2. Resolve the normal Ask provider experience — Medium, only if retained

**Dependencies:** B3; use the capability decision identified in gap D.

**Likely files:** `newsroom/domain_api.py`, `ask.py`, existing AI configuration/router code, and `tests/test_phase14_ask.py` or focused API coverage.

**Acceptance:**
- [ ] Normal API/UI behavior and provider labeling match the documented release contract; hosted mode does not imply a hosted answer when it fell back locally.
- [ ] If hosted synthesis is required, reuse the provider-neutral router with bounded spend and exact citation/refusal checks on current and historical Ask.
- [ ] Disabled credentials/provider failure remain useful in local mode and cannot produce ungrounded answers or uncontrolled paid work.

**Verification:** Test through the actual authenticated HTTP route, including no credentials, budget exhaustion, fallback, historical cutoff, and insufficient evidence. Benchmark-only injection is not an API integration test.

#### C3. Close measured workflow friction — Small independent fixes

**Dependencies:** B3/B1 findings.

**Likely files:** Only the affected view and service/test, for example `ReportsView.tsx`, `StoryEvidenceView.tsx`, `AdminViews.tsx`, or `InboxView.tsx`.

**Acceptance:**
- [ ] Each fix names an observed trial problem and a measurable before/after user outcome.
- [ ] Core review flow makes changed conclusions, evidence, corrections, and uncertainty understandable.
- [ ] Any remaining source/notification limitations are explicit; optional connectors, backfill, and external delivery are deferred unless evidence makes them necessary.

**Verification:** Replay the affected trial scenario in the browser, then run the relevant regression suite. Split unrelated fixes into separate tasks.

**Checkpoint C:** A new user can reach and understand useful output; retained capabilities match the accepted value report; no speculative features have entered the release.

### Phase D — qualify and release

#### D1. Refresh real browser/PWA acceptance — Medium

**Dependencies:** Accepted Phase C changes.

**Likely files:** `scripts/phase12_browser_smoke.py`, relevant frontend tests, and only proven UI defects. The legacy smoke script still expects an “Inbox” heading; reconcile it with current Home/navigation before relying on it.

**Acceptance:**
- [ ] Fresh setup/login/logout, Watch creation, Story/evidence inspection, current/historical Ask, Reports, and Research work in the current browser build.
- [ ] Actual phone/private-origin access, PWA install/update/offline fallback, keyboard use, and recovery from API failures are checked.
- [ ] No stale smoke assertions or source-string checks are represented as end-to-end acceptance.

**Verification:** Run an actual browser against the installed build using isolated data; record build identity and concise evidence. Add automation for critical regressions, not a wholesale frontend tooling rewrite.

#### D2. Rehearse Windows installation, upgrade, and recovery — Medium

**Dependencies:** B3 and a candidate build.

**Likely files:** `scripts/phase16_windows_deploy.ps1`, `newsroom/release.py`, `docs/OPERATIONS_RUNBOOK.md`, `docs/RECOVERY_RUNBOOK.md`; fix only demonstrated release issues.

**Acceptance:**
- [ ] Accepted source produces a self-contained installed layout with built frontend assets, recorded dependency versions, and verified release manifest, without requiring the development checkout at runtime.
- [ ] API/worker/scheduler start after reboot; interrupted jobs recover; private HTTPS phone access and authentication work.
- [ ] Fresh install, upgrade from the supported prior database, repeated migration, integrity checks, full backup/restore, and rollback using a compatible backup all pass outside the repository.

**Verification:** Perform the actual PowerShell rehearsal on isolated install/runtime roots. Verify citations/content artifacts after full restore. Logical export intentionally omits some article content and cannot substitute for a full recovery backup. Do not down-migrate a live database to roll back.

#### D3. Publish a bounded release acceptance record — Small

**Dependencies:** B3, C, D1/D2.

**Likely files:** Release/readme documentation and a final review record under `docs/reviews/`; use the existing manifest tooling.

**Acceptance:**
- [ ] All ten product release conditions in section 16 of `STANDALONE_NEWSROOM_PRODUCT_SPEC.md` have linked evidence or an explicit unresolved blocker.
- [ ] The release is tied to a clean accepted commit; intended files and build assets are present, unrelated runtime/user artifacts excluded.
- [ ] Setup, provider/cost defaults, supported Source paths, limitations, maintenance, restore, and rollback are documented and reproducible.

**Verification:** Re-run the final engineering matrix once after the last changes, verify the installed artifact manifest, and perform a final first-use smoke test. Production promotion is a separate deliberate action after this evidence exists.

## 4. Critical path and scope control

```text
A1 baseline -> A2 approved setup -> A3 runtime rehearsal -> B1 four-week trial
           -> A4 fixed comparison procedure ---------------------> B2 scoring
B1 + B2 -> B3 value verdict -> C accepted product fixes -> D release acceptance
```

The trial duration is the minimum calendar constraint. Start it promptly after readiness instead of adding more speculative phases. Four weeks is not a total-project estimate: setup, low event volume, scoring, necessary fixes, and release qualification add time. There is not enough operational evidence to give a defensible percentage-complete or fixed finish date.

Do not add a vector/graph database, PostgreSQL migration, event bus, generic temporal framework, new Evidence Family/Coverage/Fragility subsystem, provider catalog, or extensive connector program. Preserve FastAPI, SQLite, the existing worker queue, and React/Vite. Mypy cleanup is follow-up debt unless a specific error reveals a real release defect; do not expand the completion effort into a mass refactor.

## 5. Engineering and release verification matrix

Run from the repository root unless noted:

```powershell
python -m compileall -q newsroom tests
python -m pytest -q
ruff check newsroom tests
python -m newsroom.evals validate
python -m newsroom.evals lite-contract
python -m newsroom.evals baseline
git diff --check
```

Run from `frontend`:

```powershell
npm run lint
npm run typecheck
npm run build
```

Use the existing targeted tests for temporal reads, Phase 29.6 source-time semantics, evidence promotion, Story/Report/Alert retry isolation, research-worker execution, budgets, and operations. Record `mypy newsroom` as informational under the existing policy. Do not report a skipped command as passing.

Outside the unit suite, require actual fresh/upgrade migration rehearsal, `PRAGMA foreign_key_check`, application integrity, logical export/import for preserved Class A/B state, full backup/restore including content, concurrent queue load, restart/interruption recovery, paid-budget refusal, browser/PWA acceptance, and the real Full/Lite experiment. Record measured performance at the intended trial/release workload rather than inventing scale requirements.

Before scoring/release, explicitly record the product-contract thresholds for citation correctness, unsupported synthesis, false merges, and improvement over the reference. Preserve any previously agreed thresholds; if absent, agree them before seeing final evaluation results.

## 6. Inputs needed to execute this plan

Only trial execution needs these choices; writing this plan does not require them:

1. Approved investigation subject and initial Source set.
2. Dedicated runtime root, machine/uptime owner, backup owner, and trial start date.
3. Actual provider/model configuration and permitted spend for trial and evaluation.
4. Human usefulness-log owner and blinded scorer.
5. Confirmation that the first release remains a private Windows application, if a broader distribution model is intended.

**Next action:** establish the authoritative baseline, obtain the trial configuration, and start one dependable Watch. The main route to completion is real-use evidence, a defensible value verdict, and a small qualified release—not another broad architecture phase.
