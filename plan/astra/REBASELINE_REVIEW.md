# Final rebaseline review

Planning pass completed 2026-09-07. No new application implementation, merge, deployment, paid call, trial contact or observation-clock change occurred.

## Repository state

- Branch before/after: `main`.
- HEAD before/after: `3d7f9cfe91b34feeaa5602a5febd9077e1d87b7f`.
- Before: no staged/modified/deleted tracked files; untracked `.kilo/`, `Newsroom -v2.zip`, `plan/astra/astra.zip`.
- After: planning changes only under `plan/astra`, unstaged and uncommitted. Original untracked inputs remain. Old prompt paths appear deleted in unstaged Git status because their preserved destinations are still untracked; this is a move, not loss of prompt content.
- Branch stack is read-only evidence. AST-01–04 narrow completion records are preserved; AST-05 implementation is unmerged and its installed qualification remains open. No current hosted CI/PR status is inferred.

## Deliverables and traceability

The plan defines all 30 requested capabilities, eight onboarding steps, six end-to-end journey simulations, dependency-ordered product milestones, task records through AST-55, and six bounded execution prompts. There are 46 future/external/deferred task records, four completed historical tasks, and five superseded broad tasks. This count is a decomposition ledger, not a completion percentage or requirement to execute optional work.

Authoritative documents: README, PRODUCT_VISION, UX_AND_ONBOARDING, FEATURE_GAP_ANALYSIS, CURRENT_STATE, COMPLETION_ROADMAP, TASKS, NEXT, DECISIONS and MODEL_AND_PROMPT_STRATEGY. JOURNEY_VALIDATION and PRODUCT_READINESS provide cross-journey acceptance. AUDIT_EVIDENCE distinguishes current source/checks from historical and unperformed qualification. MASTER_PLAN, EXECUTIVE_AUDIT and UX_AND_APPEARANCE now route to the new authority. Narrow provider/runtime/test/safety references remain traceable.

Eleven materially superseded canonical originals are preserved byte-for-byte (apart from Git working-tree newline representation) as `_OLD`: README, CURRENT_STATE, TASKS, NEXT, DECISIONS, MASTER_PLAN, EXECUTIVE_AUDIT, UX_AND_APPEARANCE, PRODUCT_READINESS, AUDIT_EVIDENCE and STARTUP_AND_RUNTIME. No existing `_OLD` file was overwritten.

Completed prompts AST-01–04 moved unchanged into `prompts/archive`. Uncompleted original prompts AST-05–22 moved unchanged into `prompts/superseded`; they are not classified as completed. Current prompts are AST-05 launcher qualification and AST-23–27 paused Watch, Welcome/interest, Sources, cadence and first value. Full original completed task sections are retained in `history/AST-01-04_COMPLETION_RECORD.md`.

Exact path inventory: [CHANGE_MANIFEST.json](CHANGE_MANIFEST.json). Machine-readable task mirror: [task-index.json](task-index.json); TASKS remains the sole status authority. Read-only checks: [validate_plan.py](validate_plan.py).

## Consistency checks resolved

| Comparison | Result |
|---|---|
| Vision vs tasks | All 30 capabilities mapped; optional paid Ask/commercial work stays deferred |
| UX vs frontend tasks | Eight-step setup and daily surfaces have task owners and browser/state requirements; person/event/Ask/tag work split |
| Feature gaps vs roadmap | Existing core, absent semantic assistance, corpus-only discovery, briefing cadence and installed gates distinguished |
| Roadmap vs task dependencies | No dependency cycle; explicit stack prerequisite; one primary queue |
| Current state vs code | Main/unmerged separated; no remote semantic vocabulary assumed; source-only Monitor versus multi-target Watch distinction retained |
| NEXT vs prerequisites | Exactly AST-05 READY; AST-23–27 are the following five tasks; later AI work requires managed safeguards |
| Prompts vs ledger | Six existing files with all 20 required sections and matching task/dependency IDs |
| Archive and `_OLD` integrity | All 22 original prompt contents and all 11 preserved canonical originals compared against baseline Git content |
| History/status | AST-01–04 earned evidence retained; AST-05 not falsely closed; AST-12–15/19 superseded, not DONE |
| Model routing | Most UI uses Tier 2/medium; bounded transaction/lifecycle/security uses Tier 3/high; Astra reserved for source/scope design and value conflict review |
| Trust/cost/trial constraints | Inherited in all future tasks and explicit in every current prompt; no implementation performed |

Review also found that `CoreService.create_topic` alone leaves `topic_terms` empty; `_scope_for_target` reads terms rather than Topic name. AST-23/24 now explicitly require user-reviewed primary terms in the atomic paused setup contract. This is a planning correction, not an application fix. AST-50 is design-only and AST-51 implements its frozen scope contract; a cheaper model need not invent date/geography semantics while editing UI.

## Fresh verification

- 79 focused offline tests passed: Watch lifecycle/discovery/research/full-chain replay, exact provenance trust and Story time semantics. Four httpx deprecation warnings; no failure.
- Frontend `npm.cmd run typecheck`: passed.
- `python plan/astra/validate_plan.py`: passed; one READY, six prompts, all dependencies acyclic, 30 capability rows, canonical Markdown links resolved, preserved originals verified, tracked scope restricted to planning and no staged changes.
- `git diff --check`: passed.

No full suite, production build, fresh visual browser, installed Windows smoke, physical phone, online CI/PR query, real source acquisition/provider validation or human value scoring was performed. The source UX audit is evidence for observed code and planned states; it is not visual release certification. Existing historical browser/CI evidence remains dated and attributed.

## Next and remaining decisions

**AST-05 — Qualify the existing Start Newsroom launcher**, Tier 3/high, using [its current prompt](prompts/AST-05-qualify-existing-launcher.md). The future executor must use a safe descendant checkout with the existing AST-01–05 code and this planning authority, preserving newer branch and uncommitted work. Installed/manual gaps remain open if not actually exercised.

Human judgment remains necessary for actual usefulness scoring/value retention, any new paid source-search vendor commitment if AST-30 finds one necessary, and the actual supported device matrix. None blocks this completed planning pass. Technical source-discovery and geographic/time contracts have explicit design tasks before implementation. Trial/evaluation gates remain unchanged, independent and unexecuted here.
