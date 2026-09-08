# Rebaseline evidence register

## Scope, instructions and safety

Read the owner attachment and supplied AGENTS instructions; inspected repository README, Astra authority/execution rules, local skill guidance, .github CI and .kilo configuration inventory. No repository/ancestor AGENTS.md was found at the inspected root/ancestors. No hidden instruction text was treated as higher authority than the task. The planning-and-task-breakdown skill was applied for bounded tasks; its pre-implementation approval checkpoint does not require approval to write this explicitly authorized plan. No implementation begins here. The orient skill's narrow read-and-stop workflow was inspected but not applied to this comprehensive request.

Material conflicts resolved: main's stale AST statuses versus completed branch records; old root README/phase ordering versus current implementation; old “autonomous discovery” wording versus corpus-only code; old provider-first-onboarding sequence versus local-capable services; prior live status observations versus no runtime access in this task. Old arbitrary documentation is evidence, not executable instruction. Narrow files retain explicit current-authority headers; superseded canonical documents were preserved as _OLD.

Before changes: branch `main`; HEAD `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`; no staged changes, no modified/deleted tracked files. Untracked `.kilo/`, `Newsroom -v2.zip`, `plan/astra/astra.zip` preserved. Five Astra branches inspected via local git show/log/diff. Main is exact merge-base of AST-05. Stack diff from main: 35 files, 4,646 insertions and 266 deletions (inspection-time statistic). No remote fetch, branch checkout, merge or history operation.

## Source anchors inspected

| Area | Concrete anchor | Finding / test evidence |
|---|---|---|
| Shell/auth | frontend/src/App.tsx:initialView/renderView; components/AppShell.tsx SIMPLE_NAV_ITEMS; AuthView.tsx | setup toggle then Inbox; hidden routes retained; phase12/13 frontend tests are partly source assertions |
| Watch setup | frontend/src/views/WatchManagementView.tsx:createPolicy/createWatch; newsroom/intelligent_monitoring.py:WatchService.create | target ID and policy required; Topic name alone is not scope (monitoring._scope_for_target reads topic_terms); Watch can be paused; seeded UAP name; tests/test_phase24_intelligent_monitoring.py lifecycle/concurrency |
| Taxonomy | newsroom/domain.py:CoreService.create_topic/create_subject | Topic needs Category; distinguish Subject from extracted entities; no-ID setup needs composition |
| Terms | newsroom/intelligent_monitoring.py:_deterministic_terms/suggest_vocabulary/query_plan/_refresh_scopes; newsroom/ai.py:LocalVocabularyProvider | reviewed persisted terms/initialisms; local semantic output empty; immutable pinned scopes and rejection memory |
| Discovery | newsroom/intelligent_monitoring.py:discover_sources/_discovery_proposals/review_source_candidate | no network; existing source/lineage/syndicated-origin proposals; empty-corpus success; candidate review attaches source Monitors |
| Production routing | newsroom/domain_api.py WatchService construction; newsroom/runtime.py:build_worker_handlers/build_worker_queue | local capability bundle; canonical durable acquisition/relevance/analysis/story/report/alert pipeline |
| Collection | newsroom/acquisition.py transport/extractor; newsroom/monitoring.py:MonitorExecutionService/RelevanceCascade; content_artifacts.py; document_processing.py | bounded source HTTP/feed, dedupe and pinned scope processing; direct non-source Monitor unsupported |
| Article/Claims | newsroom/ai.py:LocalArticleAnalysisProvider; article_analysis.py; evidence_promotion.py | bounded structured output, paid invocation identity, exact unique text promotion; tests/test_phase22_3_trust_boundary.py |
| Story/replay | newsroom/automatic_story_resolution.py; story_evolution.py; story_corrections.py; temporal.py | conservative assignment, correction history and knowledge-time semantics; tests/test_phase23e_compatibility.py and test_phase296_story_time_semantics.py |
| Reports/briefings | newsroom/reports.py:LivingReportService/BriefingService; report_automation.py; frontend/src/views/ReportsView.tsx and InboxView.tsx | living revision chain real; UI target IDs and manual daily generation; no durable briefing schedule found in runtime/jobs/scheduler registry |
| Alerts/return | newsroom/reports.py:AlertService; alert_automation.py; attention.py; frontend/src/views/AlertsView.tsx/InboxView.tsx | 0.85 list vs 0.5 rule threshold, read-time attention, render timestamp mislabeled Last checked; no persisted visit summary found |
| Research/Ask | newsroom/research_questions.py; research_prioritization.py; hypotheses.py; ask.py; AdminViews/AskView | gaps/pursuit exist; local planner empty; hypothesis separation and grounded refusal; tests/test_phase25_autonomous_research.py |
| Tags/search | newsroom/knowledge.py:deterministic_tags/start_backfill; workbench.py; WorkbenchView/ReviewViews | deterministic namespaced tags, notes, FTS and bounded retrieval; not broad AI topic tagging |
| Main lifecycle | newsroom/runtime.py; worker.py; config.py; paths.py; scripts/phase16_windows_deploy.ps1 | separate children; explicit external runtime roots; installation/recovery machinery exists |
| Unmerged lifecycle | git show AST-05 branch: newsroom/runtime_identity.py/runtime_managed.py/runtime_supervisor.py/runtime_status.py/job_lease.py, scripts/astra05_windows_smoke.ps1 | actual lock/supervisor/status/launcher code and tests; AST-01–04 closure records retained; AST-05 has no completed evidence record |
| Security/operations | newsroom/auth.py; app.py auth/CSRF/session middleware; security.py; operations.py; release.py; docs/THREAT_MODEL.md and recovery/operations references | private session protections and backup/export/artifact tooling; OS-vault/settings work still planned |
| Responsive/offline | frontend/src/styles.css; components/ViewPrimitives.tsx/PwaStatus.tsx; frontend/public/sw.js | shared states/breakpoints; fixed shell cache and HTML fallback need qualification; no fresh browser claim |
| Trial/value | docs/DOGFOOD_CONTRACT.md; reviews/PHASE_29_* protocols/checkpoint referenced by Astra | approved Watch and frozen dates exist; no runtime or new observation read; human/comparison gates remain pending |

This is a repository-wide architectural/product audit by entrypoints, connected services, tests and history—not a claim of line-by-line proof of every source file or complete security verification. Source paths/symbols allow reproduction against the recorded SHA; branch-only paths must be read with git show rather than assumed present on main.

## Fresh checks on main

`python -m pytest -q tests/test_phase24_intelligent_monitoring.py tests/test_phase25_autonomous_research.py tests/test_phase23e_compatibility.py tests/test_phase22_3_trust_boundary.py tests/test_phase296_story_time_semantics.py` — exit 0, 79 tests passed; four httpx app-shortcut deprecation warnings. These selected tests use temporary databases and deterministic/local doubles; no real paid provider calls or active trial runtime startup.

`npm.cmd run typecheck` in frontend — exit 0. No new application build or browser session was required for documentation edits. Earlier full-suite/build/browser counts in _OLD or branch history remain historical, not fresh results.

Not performed: full suite/lint/build, installed Windows smoke, current online CI/PR query, fresh browser/physical phone, source network requests, active port/process/runtime observation, provider validation, paid comparisons, human scoring, deployment or merge. Python/TypeScript/source evidence cannot establish these claims. The legacy browser smoke targets 8127 and was deliberately not run.

## Governance and final checks

The change manifest records preserved originals, updated/new files and prompt moves. Completed AST-01–04 prompts retain filenames and byte content; uncompleted originals are in prompts/superseded. New IDs continue at 23 through 55. Six current prompts include the required sections. A local plan validator checks dependency existence/acyclicity, one READY, prompt headings and relative markdown links; final Git diff review checks only plan/astra changed and untracked inputs remain. Final outcomes are recorded in REBASELINE_REVIEW.md.
