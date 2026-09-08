# Current state at the rebaseline

## Baseline and branch distinction

Main is `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`; merge-base with the AST-05 branch is exactly that SHA. The five Astra branches form a descendant stack, not five alternative implementations. Local refs were inspected; no fetch, checkout, merge or runtime contact occurred.

| Work | Local branch tip | State relative to main | Evidence disposition |
|---|---|---|---|
| AST-01 baseline/CI | `astra/AST-01-baseline` `4dfc950` | implemented, unmerged | DONE under narrow recorded acceptance |
| AST-02 identity/preflight | `astra/AST-02-instance-preflight` `db5d94b` | implemented, unmerged | DONE; installed lifecycle excluded from its contract |
| AST-03 supervisor/lease renewal | `astra/AST-03-supervisor` `85f41e1` | implemented, unmerged | DONE; subprocess/hosted evidence recorded |
| AST-04 status/recovery UI | `astra/AST-04-status-controls` `1000487` | implemented, unmerged | DONE; corrected browser artifact recorded |
| AST-05 launcher | `astra/AST-05-start-newsroom` `cddad09` | implemented, unmerged, qualification incomplete | PARTIAL capability; only READY task, no DONE claim |

The original main ledger incorrectly treats all four completed tasks as future. Their full completion sections are preserved in [history](history/AST-01-04_COMPLETION_RECORD.md). Hosted run/PR state is historical recorded evidence, not freshly queried online status. Later AST-05 launcher commits do not establish clean installed acceptance by themselves.

## Actual current architecture

FastAPI/session authentication serves a same-origin React hash-route workspace. SQLite WAL owns domain data, immutable provenance and a durable job queue. Source acquisition creates immutable content artifacts and DocumentVersions; changed versions enqueue processing with pinned information-need scope. Relevant material receives structured analysis; exact excerpt verification produces pending Claims/Evidence; conservative automatic Story resolution/acceptance feeds immutable reports, exact-cause alerts and in-app delivery. Durable completion hooks and replay identities protect downstream convergence. Schema is 36 on main and the inspected stack.

Watches are durable user intent referencing a Topic, Subject, Story, Source or Research Question. A Watch attaches Sources via per-Watch source Monitors. **Only source Monitors execute acquisition**; direct topic/subject/story/question Monitors are unsupported. This does not mean those Watch targets are unsupported. Do not build parallel Topic acquisition adapters merely to hide this distinction.

Main still launches API/worker/scheduler separately and labels API health as Service online/Synced. The stack adds ownership locks, PID creation identity, bounded supervisor recovery, renewing worker leases, truthful whole-runtime UI and a single launcher. None is present in main yet.

## Product maturity

Substantial evidence-intelligence engine; incomplete owner-facing application. Narrow exact-span verification is complete within its tested trust contract. Acquisition, analysis, Story evolution/corrections, reports, research gaps, search, tags, authentication and backup machinery are implemented with meaningful tests. Their normal-user integration and real-world qualification remain partial. All 30 capability ratings and precise boundaries are in [FEATURE_GAP_ANALYSIS](FEATURE_GAP_ANALYSIS.md).

Setup/login exists; first login lands in Inbox/Home without first-Watch guidance. Watch setup requires target ID and a separately created policy. Source collection is mainly inspection. Report/Ask workflows still expose IDs. Home briefing is manually generated; its Last checked uses render time rather than acquisition success. Alerts request only importance ≥0.85 while rule creation uses 0.5, hiding some matching alerts. Source-reviewed aliases and deterministic initialisms exist, but LocalVocabularyProvider returns an empty semantic suggestion list. Discovery reads only an existing corpus; fresh-install recommendations are absent. Local research planning is similarly empty; bounded deterministic pursuit still exists. Smart tags are persisted deterministic classifications/backfills, not general learned topical tagging.

## Planned, blocked and deferred

Planned: no-ID Watch setup, assisted terminology and source discovery, understandable cadence and first value, connected evidence/report/alert/research workspace, return-since-visit summary, owner recovery and release qualification. These are task contracts, not code changes in this pass.

Blocked external acceptance: unchanged Phase 29 observation sufficiency, eligible frozen Full-vs-Lite inputs, explicit paid execution authorization and actual human scoring. No live state or observation progress was read. The repository records boundary `2026-09-06T21:20:48Z` and earliest four-week point `2026-10-04T21:20:48Z`; time alone does not satisfy the protocol.

Deferred: paid Ask, commercial pilot, speculative broad autonomy, light/system appearance, OS push while closed, pre-login/cloud operation. Backup/logical export exist but are different promises: full SQLite backup contains content artifacts; bounded logical export intentionally excludes article bodies and is not full recovery.

## Fresh evidence and limits

79 focused offline tests passed on main across Watch/research/full-chain/evidence trust/Story time semantics; frontend typecheck passed. Four httpx deprecation warnings were emitted. No full suite, production build, fresh browser, installed Windows, physical phone, online CI, real provider or real-use value qualification was performed. UX observations are source-grounded; historical screenshots/CI artifacts are not relabeled as new visual evidence. See [AUDIT_EVIDENCE](AUDIT_EVIDENCE.md).
