# Active decisions

D01-D13 were established during the 2026-09-06/07 audit. D14 records the first implemented runtime-identity decision from AST-02. Planning decisions remain contracts unless their implementation status is explicitly recorded in CURRENT_STATE/TASKS.

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

## Deviations and discoveries

- The first browser reconnaissance captured loading states after hash navigation. It was repeated with an explicit busy-state wait; only the settled pass supports empty-state conclusions.
- Settled mobile screenshot exposed internal Settings button/card overlap despite no page-width overflow. AST-13 includes component-boundary acceptance.
- Current test count is 844, not the older acceptance record's 838. Both refer to different commits; preserve historical records.
- AST-02 was implemented as a stacked draft PR because AST-01 is verified but still unmerged; the stack makes the dependency explicit rather than rebasing the task onto stale `main`.
- AST-02 discovered that simultaneous startup can lose its first lock holder before the API becomes ready. The bounded waiting launcher now attempts to re-acquire the released OS lock and proceeds only after it owns that lock; it still never kills a process or chooses another port.
- AST-02 also discovered that the installed `release-manifest.json` can exceed the deliberately small runtime-owner metadata limit. Release-manifest parsing therefore uses a separate bounded reader rather than weakening the runtime identity-file bound.
- Windows PID creation-time verification is implemented for the target platform but has not been qualified in a clean installed Windows lifecycle in AST-02. That remains an explicit installed-platform acceptance boundary for AST-05/AST-19, not a reason to infer failure of the cross-platform ownership contract.
- AST-02 changed no schema, provider route, budget authority, evidence/provenance rule or active trial behavior. No paid call was made and port 8127 was not contacted.

Future updates must add date, task, evidence, rationale, compatibility/data impact and any change to dependencies. Do not overwrite historical decisions to conceal changed assumptions.
