# User experience and onboarding contract

This is a source-grounded UX audit and desired experience, not a new browser acceptance report. Relevant implementation is App.tsx, AppShell, AuthView, WatchManagementView, InboxView, AdminViews, ReportsView, AlertsView, StoryEvidenceView, EvidenceView, AskView, WorkbenchView, styles.css and public/sw.js. Paths below are repository-relative.

## Current journey findings

| Surface | Observed implementation | Consequence | Owning tasks |
|---|---|---|---|
| Auth → Home | login mode first, setup toggle; inbox after auth | no welcome/first actionable Watch | AST-24 |
| Watches | target type/ID, separate policy; seeded UAP name | users must know domain structure; example looks configured | AST-23–27 |
| Sources | mostly list/inspect; corpus-only discovery | empty-corpus bootstrap dead end | AST-25,30–32 |
| Vocabulary | approve/reject/edit proposals and query plan | useful boundary, but no semantic default suggestions | AST-28–29 |
| Home | manual daily briefing, six attention rows, render-time Last checked | weak returning-user summary; timestamp overstates collection | AST-27,33–34 |
| Reports | canonical target ID; manual generate | no contextual setup or briefing cadence | AST-36–38 |
| Alerts | ≥0.85 fetch; rules use ≥0.5; global default scope | some matching alerts hidden; scope/noise control unclear | AST-39 |
| Evidence/Stories | exact excerpts, provenance and correction structures | signature feature exists but cross-screen navigation needs proof | AST-35,40 |
| Research/Ask | question form exists; research advanced, Ask object IDs | question-first journey and follow-up context disconnected | AST-41–42,52–55 |
| Settings/status | raw budget/config; main liveness overclaims health | owner cannot configure providers/recover confidently | AST-05–11,43–44 |
| Phone/PWA | responsive CSS and shell; fixed cache, HTML fallback for misses | source inspection cannot certify layout/update correctness | AST-45–46 |

Simple navigation remains Home, Watches, Stories, Reports, Ask, with Settings. Expose Sources through Watches and Settings; Research through Watch/Story context plus Advanced. Preserve existing hash links, Saved, History and Workbench access. Simple/Advanced changes presentation only. Avoid a whole routing rewrite; add context selection using current route/state patterns with reload-safe identifiers where needed.

## First run: eight steps

1. **Welcome.** After workspace authentication: “Newsroom follows what you care about and shows what changed—with the sources behind each claim.” Primary: Create your first Watch. Secondary: Explore existing intelligence if present. Returning users never get trapped in onboarding. Explain local workspace credentials in normal language; auth failure and API unavailable are distinct.
2. **What do you want Newsroom to watch?** Enter natural language and a short editable name. Default to a Topic behind the scenes; offer Person/organization, Developing story and Question as optional choices. Existing objects use searchable named selection. AST-23/24 first deliver Topic setup; AST-41/52/53 extend target creation. Require one editable user-approved primary term for basic local scope: a Topic name alone does not populate topic_terms. No invented remote semantic interpretation. Internal IDs never need typing. Save paused setup and recover it after failure; creating a duplicate on retry is forbidden.
3. **Help Newsroom understand.** Show primary terms, aliases, synonyms, acronyms/expansions, related entities and excluded meanings with rationale and origin. Allow edit/approve/reject; optional region/time scope appears behind “Narrow this Watch.” Distinguish an entity's aliases from merely related organizations. Do not preapprove generated suggestions. Manual terms work when AI is unavailable; explain the limitation. Future jobs use newly approved scope; already acquired versions retain pinned scope. Geographic/date constraints need structured semantics and tests (AST-50/51), never misleading free-text chips.
4. **Choose Sources.** Tabs/choices: Recommended, Search, Add URL/feed, Existing. On an empty corpus show Add URL immediately and explain when recommendations are unavailable. Cards show title/domain, page versus feed, why suggested, how found, limitations and unverified status. Approval attaches a per-Watch Source Monitor; rejection stays rejected. Bad URLs show inline explanation. Shared Source edits warn about other Watch usage; detaching only removes this Watch relationship. AI-proposed URLs are candidates until validated, not evidence.
5. **How often?** Default hourly; several-times-daily, daily and bounded custom intervals. Show next expected check and source/channel limits. Offer faster cadence only when supported; do not say instant. Paid cap remains zero unless deliberately configured. Shared policies must not be silently edited; create/select an independent policy or disclose shared impact. Pause/resume preserves approved sources/history.
6. **What would you like to receive?** Default important in-app updates and an evolving evidence view. Periodic briefing, living report and unanswered-question tracking are opt-ins with sane defaults; unsupported choices are clearly unavailable until their tasks land. No default email/push promise. Explain local versus enhanced Article Analysis and estimated cost separately from cadence.
7. **Review and start.** Show interest, approved terms/exclusions, sources, schedule, reporting/alerts and effective cost mode. Back/edit retains entries. Start monitoring is one explicit action; require at least one approved usable source. Repeated clicks/reload converge on the same Watch and schedules. A saved paused Watch is not labeled collecting.
8. **First value.** Watch detail shows waiting for next check → collecting → processing → ready, derived from persisted facts, not a timed animation. No change, irrelevant content, no accepted claims, failed source, paused and unavailable runtime each have different copy/actions. Offer source/term refinement and explain what happens next; no evidence-free starter summary. When an article is relevant but Story assignment is deferred, show analyzed material and the reason, not an apparently broken empty Story list.

```text
Start Newsroom → workspace setup/sign-in → Welcome
  → interest → terminology → sources → cadence/preferences → review → Start
  → Watch overview: latest change | next check | evidence | report | questions
  → Home on return: since last visit | needs attention | other updates
```

## Daily intelligence workspace

Home: top section answers “Since your last visit” using a stored review boundary, with counts and newest/oldest range. Separate urgent attention from lower-priority updates; never discard unseen items by slicing a list without a More path. Show newest successful collection time per Watch and data freshness, not current clock as Last checked. Empty home with no Watches points to Create Watch. A quiet configured Watch says when it last checked and what it found.

Watch detail: header has name, paused/collecting/needs-attention status, next check and Edit. Main area shows recent analyzed material/Stories and a report preview; secondary tabs hold Sources, terms/scope, questions and activity. Technical Jobs are Advanced. A broad page with no useful Story can be refined without lowering provenance or saturation safeguards.

Stories: timeline distinguishes publication time, retrieval time and knowledge/recording time. Show new Claims, corrections and source disagreement; preserve merge/split lineage. Corrections preview consequences and retain append-only history. Summary sentences link to Claims, exact excerpts, source identity, DocumentVersion and analysis provenance. “Supported by source” never becomes “verified true.” Syndicated copies count as related evidence, not independent corroboration. Missing historic content is explained honestly.

Reports: create from a named Watch/Story context; map to existing supported canonical report target, not a new unsupported Watch report type. Show latest immutable revision, what changed and cited Claims. Failed/no-evidence generation preserves the last successful revision and labels freshness. Briefing cadence is distinct from acquisition cadence and living-report revision triggers. Timezone and daylight-saving behavior are explicit. Exports identify time range, sources and portability limits.

Alerts: important by default, with All/history and threshold/scope controls. Explain material cause and link to affected Claim/Story/report. Acknowledge and snooze persist; quiet periods never erase history. Browser delivery is optional and permission denial leaves in-app delivery intact. No OS push claim when closed.

Research: begin from a question or convert a visible gap; show what evidence is missing, bounded pursuit status, attempts and next review. Hypotheses are notes, not Claims. An unsuccessful search does not close a gap. Ask preselects current context with named selectors and displays evidence/refusal, effective route and limits.

Settings: Watch defaults, AI Providers & cost, notifications, backup/recovery, appearance and Advanced diagnostics. Provider controls show supported capability and effective generation; configure/test/enable are distinct. No raw keys in responses/storage. Status/recovery describes failure and safe action first, components on expansion. If API is unreachable, direct the user to Start Newsroom; a browser button cannot restart an unreachable server. Restore is a separate explicit owner action with backup identity and data-loss consequences.

## State, accessibility and responsive acceptance

Every future UI task must capture entry, populated success, loading, empty, error and recovery at desktop and 390px; 200% zoom and keyboard-only traversal are required. Use labels, visible focus, semantic headings/buttons, focus return after dialogs, field-linked errors and polite status announcements. Loading must not erase a saved draft; stale responses must not select a prior object. Disable duplicate mutation buttons without leaving controls permanently locked after failure. Lists paginate or expose More; long titles/URLs wrap without covering neighboring controls. Check component boundaries, not only page overflow. Preserve dark tokens and validate contrast; a new light palette is not required.

Offline means cached shell only unless separately implemented. Do not cache authenticated API bodies; asset failures cannot return HTML masquerading as JavaScript. Distinguish browser network state, API reachability and collection health. Updates should offer a recoverable reload path with artifact identity and no mixed-version state. Physical phone qualification remains separate from emulated viewport screenshots.
