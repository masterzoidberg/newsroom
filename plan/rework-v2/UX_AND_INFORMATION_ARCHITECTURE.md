# UX and information architecture

## Navigation and addressability

Normal navigation: **Home · Research · Settings**. Advanced tools expose Library (Documents, Sources, Questions), Operations (Monitors, Jobs/Runs, Alerts) and System (providers/routing, diagnostics, backup/recovery/runtime). Advanced changes presentation density, not authentication or data permissions.

Use a small typed hash router; React/Vite stay. Canonical routes:

```text
#/home
#/research
#/research/new
#/research/<watchId>/overview
#/research/<watchId>/updates
#/research/<watchId>/updates/<storyId>?event=<eventId>
#/research/<watchId>/briefing?revision=<revisionId>
#/research/<watchId>/sources
#/research/<watchId>/settings
#/research/<watchId>/ask/<conversationId>
#/research/<watchId>/evidence/<spanId>?version=<versionId>&return=<encodedLocalRoute>
#/settings
#/advanced/<existingView>/<optionalObjectId>
```

Validate route shape/encoding and object ownership server-side. Bad paths show Not found; absent/deleted Research shows a recovery link; unauthorized requests show authentication. Do not silently select a different Research. Preserve intended route across authentication. Opening a citation pushes an addressable overlay route; Back closes it, forward reopens it. A direct evidence route renders full context without requiring an opener. Return routes accept only valid local router values.

Legacy `#inbox`, `#monitors`, `#reports`, etc. map deterministically to Home, Research or advanced collection pages. Legacy storage values may be offered once as “Reopen previous selection,” never required for navigation. Draft form recovery may remain session storage, with a server draft ID after persistence; draft storage is not object routing. No second tab can change another tab's selected Research via localStorage. Use ordinary anchors for open-in-new-tab and notification deep links. Focus moves to page heading on full navigation and restores to citation trigger when closing the drawer. Skip-link fragments must not be interpreted as routes.

## Workspace shape

```text
UAPs and Congress                            Monitoring
Track institutional developments related to UAP oversight.
Checked 18 minutes ago · next check in 42 minutes · 12 sources
[Check now] [Pause]

Overview | Updates | Briefing | Sources & scope | Settings

Current situation
Evidence-backed statements, uncertainty and open questions...

Latest developments                         Monitoring
Committee announces hearing...              11 healthy; 1 needs attention

Ask about UAPs and Congress
[ What does the evidence support?                         ] [Ask]
Using evidence collected for this Research · Basic local analysis
```

Five tabs remain because they answer different questions: status/current situation, chronology, five-minute synthesis, input configuration, operational preferences. Contextual Ask persists across tabs without becoming a global chat workflow. On narrow screens tabs scroll or use a labeled section picker; do not shrink text to fit.

## Screen contracts

Every row defines the user question, actions, data and load/empty/error/success states. Partial data failures remain local to the affected section; they do not erase the rest of a populated workspace.

| Screen | User question / primary action | Secondary actions and data | Loading / empty / error / success |
|---|---|---|---|
| Home | What changed and what needs me? / Read update | Evidence, mark displayed changes reviewed, open affected Research/source; scoped material changes + explicit review cursor + operational attention | Skeleton list; New Research if none, otherwise “No new changes since review”; retry failed section; dated developments grouped by Research |
| Research list | What am I researching? / Open Research | New Research, name search, pause state filter; paginated Watch summaries, current check and next due | List skeleton; concise first-value CTA; retry list; names/intents/status and latest meaningful change, not count dashboard |
| New Research: intent | What should Newsroom follow? / Continue | Manual/AI assistance choice when available; prose draft and capability availability | Save/interpret indicator; one textarea; retain input on provider/save error; persisted draft/proposal |
| Interpretation review | Does this capture my intent? / Confirm scope | Edit name, Focus areas, terminology, exclusions; optional one/two ambiguity questions; original prose + proposed diff + provenance | Proposal pending with cancel; manual editor when no capable service; retry bounded operation without losing edits; approved scope revision |
| Source Scout | Where should we look? / Find sources | Add manually, adjust coverage, review bounded service usage; approved scope + coverage proposal + source candidates | Actual pending job state; honest no suggestions/manual path; provider/quota errors with safe reason; inert candidate cards with provenance |
| Manual source | Can this URL be monitored? / Inspect URL | Existing Source suggestion and advanced corrections; single URL, inspection result | Bounded inspection status; paste URL; blocked/unreachable/unsupported remains editable; endpoint options and duplicate resolution preview |
| Source review | Do I approve this source and method? / Approve source | Edit/override profile, reject, select feed/page, linked-publication permission; endpoint verification time, assessment basis, coverage and costs | Profile assessment may load independently; unknown profile is acceptable; inspection failure cannot claim healthy; approved membership, still paused draft |
| Ready to monitor | What will run and cost? / Start monitoring | Back to sources/scope, choose frequency; confirmed intent/scope, approved endpoints, bounds, cost authorization, immediate first check | Refresh saved review; missing scope/source blockers; stale revision conflict reloads diff; durable check receipt and workspace |
| Check detail | What happened in this check? / View results | Failed-source retry, pause, inspect attempts advanced; expected source items and descendants | Due/checking/processing/preparing/retrying from persisted states; never-run distinct; partial/total failure explicit; terminal result with source/document/evidence counts and next check |
| Overview | What do we know now? / Read latest development | Briefing, open question, Ask, source recovery; current scoped synthesis + latest Updates + concise health | Independent section placeholders; no accepted evidence guidance; stale synthesis labeled; current situation and exact evidence links |
| Updates | What materially changed? / Read update | Focus/time filtering, Why this matched, Not useful; scoped Story events/eligible claims | Pagination state; distinguish quiet/no evidence/current processing; retry page; chronological developments with support/uncertainty |
| Update detail | What happened and why does it matter here? / Inspect evidence | Ask about statement, related in-scope updates, feedback; scoped claims, evidence and event time | Detail skeleton; unavailable/withdrawn update explanation; no fallback to global Story prose; supported development with limitations |
| Briefing | What matters in five minutes? / Read evidence | Previous revisions, contextual Ask, delivery preference; Watch LivingReport revision + current status | Preparing with existing dated revision if any; “Not enough accepted evidence yet”; failed refresh shows last good revision as stale; Bottom line/what changed/supported/unresolved/conflicts/open questions |
| Ask | What does this Research's evidence say? / Ask | Follow-up, citation, stop; Watch-scoped conversation and capability label | Working/cancel from actual request state; example questions; refusal vs transport error distinguished; classified answer with resolvable scoped citations |
| Evidence drawer/page | Show the exact basis / Read excerpt | Open publication, inspect related in-bound support/conflict, expand audit; span/version/source/fidelity/relationship | Excerpt skeleton; missing artifact explicitly unavailable; wrong Research/version rejected; exact quote and provenance, no substitute version |
| Sources & scope | Are we looking in the right places? / Add source or edit scope | Scout, coverage, profile override, stop monitoring source, historical sources; intent revisions, active/former memberships and endpoint health | Sections load independently; no attached sources CTA; save conflict retains edits; approved revision/attachment changes with future-only notice |
| Research settings | How should this Research operate? / Save preferences | Frequency, pause/resume, budget cap, delivery, archived-state access; Watch policy/schedule | Form skeleton; defaults explained; validation preserves input; named confirmation, no raw seconds/IDs |
| Normal Settings | What are my preferences? / Save | General, notifications, delivery defaults, monitoring defaults, privacy/storage summary, AI & cost summary; typed settings | Loading; defaults are usable; section errors; saved values and clear paid-off state |
| Advanced/System | Diagnose or configure machinery / Task-specific action | Existing provider vault UI, routes, jobs, backup/runtime; authenticated existing APIs | Explicit service state; no data does not imply broken service; existing bounded recovery actions; confirmations for consequential actions |

## Creation and Source setup detail

Stages: describe → interpret/edit → confirm → find/add sources → approve → review → Start. A draft can be saved before terms are approved; it cannot monitor until positive scope is confirmed. Reuse idempotent UUID setup composition and uncertain-save retry behavior; do not duplicate a Watch after a timed-out save. Keep existing Question-first selection of known questions in advanced refinement, but ordinary prose can suggest a question interpretation for confirmation. No automatic Topic→Watch→Monitor form hierarchy.

With no credentials, Continue opens manual name/Focus/terms editor and clearly says AI suggestions are unavailable. Default Research display name may derive from prose as a cosmetic label only; it is never approved matching scope. AI setup authorization copy states the service, purpose, maximum request/cost, data sent and one-off nature in concise human language. Changing global paid routing requires the existing explicit settings action, not a setup checkbox side effect.

Source cards separate:

- approval: suggested / approved / rejected;
- endpoint: reachable/feed detected/page-only/unsupported/unreachable, with inspection date;
- monitoring: healthy/needs attention/paused/not yet checked;
- assessment: detected/AI-suggested/user-assessed, with unknown dimensions allowed.

AI profiles do not delay approving a manually inspected Source. “Official primary” is an assessment label with a basis. Strengths/limitations explain authority boundaries. Global role edits say “Applies wherever this Source is used”; relevance/coverage edits say “Only this Research.” Preserve the original suggestion in audit history. Never show fabricated reliability percentages.

Duplicate preview says “Already known: reuse this Source” with its matching endpoint. Conflicting identity asks the user to select/review; it does not merge by slug/domain. A feed shows whether linked articles may be fetched, including public cross-domain publication links and bounds. A homepage without a feed may be watched as that page; it is not falsely described as monitoring every article on the website.

Stop monitoring Source closes membership, preserving Updates/evidence/Briefing history. Former Sources have dates (or “Earlier attachment dates unavailable” for legacy records) and an explicit Reattach action. Scope save copy: “Changes apply to future monitoring. Existing evidence and historical Briefings will not be rewritten.” No purge action in this flow.

## Check states and recovery copy

| State | Copy / action |
|---|---|
| Due | “Your check is due now. Waiting for Newsroom's scheduler.” Show runtime recovery if unavailable. |
| Checking | “Checking 4 of 9 sources.” Only count persisted attempted/completed items. |
| Processing | “5 relevant documents are being analyzed.” Show queued vs retry delay if useful. |
| No change | “9 sources checked successfully. No source changes.” This is success. |
| Irrelevant | “New material was reviewed; none matched this Research.” |
| No accepted evidence | “Processing completed. No evidence-backed Update was produced.” Terminal, not endless processing. |
| Partial failure | “8 sources completed; 1 failed.” Preserve available results; retry failed subset. |
| Total failure | “No sources completed successfully.” Specific safe failure categories and recovery. |
| Paused | “Monitoring is paused. Existing evidence remains available.” If applicable: “Previously started work is finishing.” |
| Bounded/deferred | “10 articles processed; additional items will be checked later.” Show count/cursor/deadline, never imply complete coverage. |

A source retry requests a new bounded failed-subset check; it does not resurrect every historical failed job. Check now while paused offers explicit Resume and check; do not silently resume. Pressing twice reopens the same active check. Ordinary list status stays Monitoring / Paused / Needs attention, with specific check phase underneath.

## Home review, evidence and responsive behavior

Use the existing explicit review boundary. Loading Home does not mark all changes read. Mark reviewed advances to the displayed high-water boundary, preserving changes arriving during review. Date language is “since your last review,” not an inaccurate browser-visit timer. Attention decisions and useful-content review are separate.

Evidence first shows statement, exact excerpt, Source, publication/retrieval time, supports/contradicts/context, and fidelity. “RSS summary; linked article unavailable” is conspicuous. Audit disclosure contains IDs, hashes, scope version, model/promotion/revision lineage. Related evidence within Research remains in scope. An advanced “Open global evidence record” action must be explicitly labeled as leaving Research context.

Retain dark theme, visible keyboard focus, reduced-motion support and current responsive foundations. Body 15–16px, secondary/labels 13–14px, badges 11–12px; verify contrast rather than assume hex colors are adequate. Reduce enormous titles, redundant cards, uppercase microtext and equal-weight buttons. At 390px evidence is a full-screen sheet with accessible close/back; desktop may use a drawer. Test 390/768/1440 widths, 200% zoom, long source names, keyboard-only navigation, focus trap/restore, Escape, screen-reader labels and no horizontal page overflow. No new component library or design-system rewrite.


## Final audit: interaction acceptance refinements

Apply the web interface guidelines to the planned M3/M6 flows: preserve unsaved setup drafts or guard navigation; associate inline errors with inputs and focus the first invalid field on submit. Use named native inputs (including URL type where applicable), allow paste, and keep actions as buttons/navigation as links. Persist selected Research/filter/page state in addressable URLs. Announce asynchronous check outcomes with polite live status without moving focus on background updates. Drawer layouts account for safe areas, bounded scrolling and overscroll; preserve Escape, focus trap/restore and reduced-motion behavior. These refine existing accessibility/navigation gates without adding a framework or broad visual redesign. Question-backed Home labels and event attribution use eligible Watch context, never raw global Story/alert prose.
