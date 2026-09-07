# Active decisions

D01-D13 were established during the 2026-09-06/07 audit. D14 records the runtime-identity decision from AST-02. D15 records the bounded supervisor/lease decision from AST-03. D16 records the authenticated whole-runtime status/control decision from AST-04. Planning decisions remain contracts unless their implementation status is explicitly recorded in CURRENT_STATE/TASKS.

| ID | Decision | Basis / revisit condition |
|---|---|---|
| D01 | Astra is canonical completion ordering; preserve historical plans and product invariants | owner request; history remains evidence |
| D02 | One per-user supervisor, existing three child processes | runtime already has durable queues; smallest way to remove topology from owner UX |
| D03 | Explicit fixed endpoint; reuse only verified matching instance | current healthy Newsroom owns 8127; never kill foreign listener or silently choose another port |
| D04 | Sign-in startup first, same Windows user for API/worker/credentials | simpler than service/S4U credential context; pre-login operation deferred |
| D05 | SQLite metadata plus explicit approved OS keyring backend; no SQLite secret blob | full backups must not contain keys; same-user credential boundaries |
| D06 | Versioned config resolver at operation boundaries | existing constructors capture environment; prevents cosmetic Settings integration |
| D07 | Article Analysis is initial compatible-provider capability | ordinary Ask/research not remotely wired; broader capability claims are false today |
| D08 | Durable shared budget is authoritative; test calls explicit | AIRouter counters are process-local; existing analysis reservations must be preserved |
| D09 | Dark-only with semantic tokens for first completion milestone | already dark; confirmed phone grid defect, no need for alternate palette |
| D10 | Preserve frozen trial and evaluation protocols; separate development runtime | approved Watch/observation already exist; no silent reset or source substitution |
| D11 | Do not reopen A2 fixed defects or relax Story saturation | A3 code/tests fix entity bound and blocked usage; content-quality problem still needs measurement |
| D12 | No broad Phase 30 or commercial platform without value verdict | provenance complexity must earn its place through unchanged decision rule |
| D13 | Test CI portability explicitly; local green is not CI proof | Linux backend workflow meets hard-coded npm.cmd frontend build test |
| D14 | API ownership uses a root-stable installation UUID, OS-held exclusive lock, PID creation token and bounded local identity protocol; matching fixed-port instances may be reused, all unverified owners fail closed | AST-02 behavioral tests and hosted CI; AST-03 may move normal ownership to the supervisor but must preserve these verification/no-kill/no-random-port invariants |
| D15 | Normal managed runtime uses one supervisor over the existing API/worker/scheduler, with a shared root/release/endpoint manifest, OS-held per-role locks, PID creation-token verification, fresh heartbeats, token-bound cooperative stop controls, managed-only migration ownership, bounded per-role restart/backoff and continuous renewal of a running Job lease while the same worker still owns it | AST-03 real subprocess/crash/heartbeat/drain/lease tests plus hosted full CI. Stale/ambiguous/unmanaged roles fail closed and are never killed or replaced. Installed Windows/task registration remains AST-05. |
| D16 | Owner-facing runtime truth comes from authenticated AST-03 ownership/heartbeat state plus lightweight active-job counts, never from `navigator.onLine`, `/health` alone or frequent integrity scans. Recovery is limited to `restart_api`, `restart_worker`, `restart_scheduler` and `stop_newsroom`, protected by session authentication and CSRF and translated only into AST-03 cooperative stop primitives. | AST-04 API/auth/frontend tests, hosted run `34147588347`, and visually reviewed corrected browser artifact `10028215213`. Revisit only if a later launcher/runtime architecture replaces AST-03 ownership semantics; do not add arbitrary commands, public roots/PIDs or force-kill behavior. |

## Deviations and discoveries

- The first browser reconnaissance captured loading states after hash navigation. It was repeated with an explicit busy-state wait; only the settled pass supports empty-state conclusions.
- Settled mobile screenshot exposed internal Settings button/card overlap despite no page-width overflow. AST-13 includes component-boundary acceptance.
- Current test count is 844 at the audited baseline, not the older acceptance record's 838. Historical records refer to different commits and are preserved as such.
- AST-02 was implemented as a stacked draft PR because AST-01 is verified but still unmerged; AST-03 and AST-04 continue the same explicit stacked dependency model rather than pretending stale `main` contains verified prerequisites.
- AST-02 discovered that simultaneous startup can lose its first lock holder before the API becomes ready. The bounded waiting launcher attempts to re-acquire the released OS lock and proceeds only after it owns that lock; it still never kills a process or chooses another port.
- AST-02 also discovered that the installed `release-manifest.json` can exceed the deliberately small runtime-owner metadata limit. Release-manifest parsing therefore uses a separate bounded reader rather than weakening the runtime identity-file bound.
- Windows PID creation-time verification is implemented for the target platform but has not been qualified in a clean installed Windows lifecycle. That remains an explicit installed-platform acceptance boundary for AST-05/AST-19.
- AST-03 confirmed a concrete lease-safety gap: `WorkerProcess` could execute a synchronous handler longer than the existing 120-second Job lease without renewal. The correction renews only the same running Job while the same worker remains lease owner; ownership/status loss stops renewal and prevents that worker from issuing a stale completion.
- AST-03 self-review found that sequential child startup could otherwise spawn a new sibling before discovering an unmanaged role. Startup now preflights all roles first; stale, ambiguous or unmanaged ownership blocks sibling creation. Shutdown sends controls only to verified `supervisor_managed` owners and reports anything else without stopping it.
- AST-03 migration ownership is conservative: the supervisor applies normal managed migrations only when API/worker/scheduler managed locks are all free. A replacement supervisor reconciling surviving same-release children does not write migrations.
- AST-03 uses no process termination in product supervisor logic. Tests deliberately kill fixture processes to prove crash recovery, but production stop/restart is cooperative and a busy worker that misses the deadline is reported rather than force-killed.
- AST-04 confirmed that public API liveness and browser network state are insufficient service truth. The shell now polls authenticated `/runtime/status` with bounded backoff; `/readiness` is not part of the frequent polling path and browser network state remains separately labeled.
- AST-04's first hosted screenshot artifact `10028137244` passed its mechanical smoke step but failed human visual review because the expanded recovery panel escaped the narrow sidebar and overlapped Settings content. The task stayed open, the panel was contained, and corrected artifact `10028215213` on head `371ff0e24d72f1f0de72eb7f08ff8d1a6c74a659` was visually accepted for idle, stale-worker/degraded and API-unavailable states. A green screenshot command alone is therefore not treated as visual acceptance.
- AST-04 returns the 202 control acknowledgement before dispatching the cooperative stop primitive through FastAPI background work. This prevents the API-stop request from closing the endpoint before the browser receives acknowledgement; AST-03 remains the authority for actual drain/restart bounds.
- AST-04 changed no schema migration, provider route, budget authority, evidence/provenance rule or active trial behavior. No paid call was made and port 8127 was not contacted.

Future updates must add date, task, evidence, rationale, compatibility/data impact and any change to dependencies. Do not overwrite historical decisions to conceal changed assumptions.
