# Verified current state

Baseline and checks: [AUDIT_EVIDENCE.md](AUDIT_EVIDENCE.md). Status describes the subsystem at this HEAD, not a blanket release certification. DONE means production-usable within the stated narrow contract; MOSTLY DONE means substantial implementation with qualification gaps; PARTIAL means an important user/operational path is absent; UNKNOWN / NEEDS REAL-WORLD VERIFICATION means code/test evidence cannot settle the claim.

## Runtime and operations

| Subsystem | Status | Evidence and remaining boundary |
|---|---|---|
| API | MOSTLY DONE | `app.py:create_app`, `runtime.py:_run_api`; authenticated same-origin workspace, public liveness; live 8127 health returned Newsroom/ok; no ownership-aware reuse |
| Worker | MOSTLY DONE | `runtime.py:build_worker_handlers`, `worker.py`; complete production handler registry and durable outcomes; whole-process health/singleton missing |
| Scheduler | MOSTLY DONE | `scheduler.py`, `jobs.py:SchedulerService`; persisted ticks/coalescing and due research; heartbeat is not a full service supervisor |
| Jobs/retry/leases | MOSTLY DONE | `jobs.py`, coalescing/research worker tests; bounded recovery and reservations; test long handlers vs 120-second job lease before adding restart behavior |
| Process lifecycle | PARTIAL | `_stop_event` supports cooperative worker/scheduler exit; no aggregate ownership/stop handshake |
| Startup/port handling | PARTIAL | direct Uvicorn bind, no listener diagnosis or root identity |
| Shutdown/restart | PARTIAL | per-process signals and runbook Task commands; no application-level drain/control |
| Health | PARTIAL | `/health` liveness and `/readiness` DB integrity; UI polls on mount/network changes, not continuous component health |
| Runtime roots | DONE | `config.py`, `paths.py`, `test_runtime_config.py`; explicit dev/prod, root outside repository, root suffix checks |
| Windows install | MOSTLY DONE | `phase16_windows_deploy.ps1`, `release.py`; artifact identity and separate install/runtime roots, operator ceremony remains |
| Task Scheduler | PARTIAL | three fixed-name tasks, AtStartup/S4U, IgnoreNew per task; cannot prevent manually launched duplicates; no matching tasks returned during audit |
| Upgrade/migrations | MOSTLY DONE | `migrations.py`, `operations.py`, `cli.py`; contiguous schema 36, integrity checks, rehearsal tools; coordinated writer shutdown is manual |
| Backup/restore | MOSTLY DONE | `operations.py`, `storage.py`, phase15 tests; verified SQLite backup/restore, not effortless owner UX |
| Logical export/import | MOSTLY DONE | explicit `_EXPORT_COLUMNS`, round-trip/integrity tests; bounded logical reconstruction is not full database recovery |
| Logs/telemetry | MOSTLY DONE | rotating runtime logs, `telemetry.py`, AI telemetry; no cohesive user diagnostics/recovery screen |
| Release identity | MOSTLY DONE | manifest hash verification in `release.py`; dirty worktree is recorded, not automatically a distributable release |
| Tests | MOSTLY DONE | broad offline regression suite, trust-boundary/coalescing/temporal coverage; browser source checks do not replace journey tests |
| CI | PARTIAL | Linux backend and frontend jobs; backend test invokes `npm.cmd`, while backend job has no frontend npm install; Windows/runtime/keyring checks absent |

## Core product

| Subsystem | Status | Evidence and remaining boundary |
|---|---|---|
| Acquisition | MOSTLY DONE | `acquisition.py` bounded HTTP/feed parsing, redirect/peer checks, immutable artifacts; JS-heavy/blocked pages and broad homepages remain quality risks |
| Sources | MOSTLY DONE | Source profiles, reviewed suggestions and Watch candidates; collection UI insufficient for first creation |
| Watches/Monitors | MOSTLY DONE | `intelligent_monitoring.py`, `monitoring.py`; Watch targets create source Monitors; direct non-source Monitor execution reports unsupported_target |
| Source discovery | PARTIAL | deterministic existing-source/document-link/feed-origin proposals with approval; not a general autonomous discovery engine |
| Relevance | MOSTLY DONE | `RelevanceCascade`, `document_processing.py`; pinned scope, persisted decision, deterministic matching; semantic quality on broad content unproven |
| Article Analysis | MOSTLY DONE | local and OpenAI-compatible structured route; real-page entity bound fixed; quality differs substantially by route |
| Evidence promotion | DONE | `evidence_promotion.py`, phase22 trust tests; exact unique matches, full provenance, atomic immutable evidence/Claim proposals; no truth guarantee |
| Claims | MOSTLY DONE | `evidence.py`, `story_automation.py`; acceptance and evidence histories; operator explanation of supported vs true needs care |
| Story resolution/evolution | MOSTLY DONE | `automatic_story_resolution.py`, `story_evolution.py`, `story_corrections.py`; conservative deferral/correction/time semantics; representative yield unknown |
| Reports | MOSTLY DONE | `reports.py`, `report_automation.py`; evidence-bound revisions and correction propagation; real user usefulness pending |
| Alerts | MOSTLY DONE | `alert_automation.py`, report causes and in-app delivery/dedupe; optional browser delivery is not OS push while app is closed |
| Research Questions | MOSTLY DONE | `research_questions.py`, durable pursuit/reassessment, hypotheses/gaps; manual ID-heavy UI and sparse real-use evidence |
| Autonomous research | PARTIAL | bounded candidate/retrieval workflows and budgets exist; local planner is intentionally empty, external discovery is constrained |
| Ask | PARTIAL | `ask.py`, `AskView.tsx`; evidence-grounded local answers/refusal and historical contracts; normal UI explicitly sends provider_mode=local |
| Workbench | MOSTLY DONE | `workbench.py`, `WorkbenchView.tsx`; notes/tags/search/compare/diagnostics; dense advanced surface |
| Search/knowledge | MOSTLY DONE | `knowledge.py`, `workbench.py`, phase26 tests/benchmark; FTS and bounded retrieval; large real corpus performance needs qualification |
| Notifications | PARTIAL | in-app authoritative, browser permission/preferences implemented; no general background push delivery proof |
| Daily intelligence value | UNKNOWN / NEEDS REAL-WORLD VERIFICATION | A3 repaired full body → Claims, broad-page Story deferral; metadata positive chain; short checkpoint insufficient |

## AI configuration

| Subsystem | Status | Evidence and remaining boundary |
|---|---|---|
| Local route | MOSTLY DONE | `ai.py:CapabilityBundle.local_defaults`; heuristic embedding/ranking/entailment/extraction/synthesis; not an installed local LLM |
| Remote route | MOSTLY DONE | `OpenAICompatibleArticleAnalysisProvider`; JSON-schema chat completions required, bounded SDK; endpoint compatibility must be tested |
| Provider selection | PARTIAL | `AnalysisProviderConfig.from_env`; selection is analysis-specific, not coherent product settings |
| Credential persistence/UI | NOT STARTED | no OS credential-store implementation or provider management UI found; ordinary settings reject sensitive key names |
| Budgets | MOSTLY DONE | `BudgetService` durable analysis reservations plus router-local counters; extend shared durable enforcement before adding paid capabilities |
| AI telemetry | MOSTLY DONE | `SQLiteTelemetrySink`, invocation identity, token usage; provider billing cost unavailable and estimated cost must remain labeled |
| Model identity | MOSTLY DONE | analysis identity includes model/config/prompt inputs; effective configuration should be surfaced per capability and generation |
| Capability coverage | PARTIAL | remote Article Analysis only in ordinary production; Watch vocabulary and research routers local; normal Ask local; eval remote synthesis is not product integration |
| Failure handling | MOSTLY DONE | safe codes, validation/timeouts, uncertain invocation handling; disabling current remote route can currently raise AIDisabled rather than transparently choose local |
| Dynamic reload | NOT STARTED | analysis service captures config at construction; no shared versioned reload authority |

## Frontend

| Subsystem | Status | Evidence and remaining boundary |
|---|---|---|
| Navigation | MOSTLY DONE | five Simple destinations plus Settings; Advanced adds Documents/Research/Workbench/Alerts; other hash routes retained |
| Settings | PARTIAL | experience and notifications editable; raw settings/budget display, no provider or lifecycle controls |
| Dark appearance | MOSTLY DONE | CSS tokens plus many literals, color-scheme:dark, dark manifest; contrast and populated-state audit still required |
| Responsive/mobile | MOSTLY DONE | breakpoints, wrapping/table containers; isolated desktop/390px empty route checks; physical phone unqualified |
| PWA | PARTIAL | manifest/service worker/install event present; fixed shell cache version and unconditional HTML fallback need update/error verification |
| Offline | PARTIAL | API excluded from service-worker cache; shell only, auth bootstrap may return to login; not an offline evidence reader |
| Onboarding | PARTIAL | setup/login available; no complete first-Watch journey without IDs |
| Loading/empty/error | MOSTLY DONE | shared accessible primitives; generic error text and retry coverage vary, operational recovery still weak |
| Light/System preference | NOT STARTED | not required for first milestone; keep dark-only with coherent theme tokens |

Historical removed coverage/blind-spot/fragility projections: **LEGACY / SHOULD RETIRE** applies to stale documentation and obsolete normal-user script entry points, not to retained migration/history evidence. Do not recreate those projections.
