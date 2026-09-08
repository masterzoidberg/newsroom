# UX and appearance

## Audit boundary and observed defects

Current source was reviewed across every view and shared shell/auth/PWA primitive. A fresh temporary runtime on 18127 loaded all 16 hash routes at 1440px and 390px. After waiting for loading states to finish, each rendered without page exceptions, error panels or document-level horizontal overflow. Login, desktop Watches and phone Settings screenshots were inspected. This is empty-state coverage, not populated workflow, keyboard, offline, physical-phone or contrast certification.

**Confirmed mobile defect:** Settings retains the base two-column `.content-grid` at 390px; the Experience mode buttons extend beyond their narrow card into the adjacent App install column. Document-width overflow checks do not catch this internal overlap. `styles.css` collapses named grids in media queries but not generic `.content-grid`; AST-13 must address the base grid and wrapping buttons. The mobile screenshot also shows tiny low-emphasis explanatory text and unnecessarily tall narrow cards.

## Per-surface assessment

| Surface | Current experience | Smallest useful improvement |
|---|---|---|
| First launch/auth | login default; manual setup-mode switch; failed auth/bootstrap can resemble offline login | server-declared setup availability, plain first-run action, distinguish unreachable API from invalid credentials |
| Shell/navigation | Simple: Home, Stories, Ask, Reports, Watches; Settings persistent; Advanced retains evidence/diagnostics | keep five primary destinations; label Home/Inbox consistently; honest component status; accessible Advanced links to retained operational views |
| Inbox/Home | Attention/material-change review, empty state | first-Watch action when empty; separate “nothing changed” from “nothing observed”; show recent successful collection and due time |
| Stories/evidence | detailed Claim/provenance views and correction concepts | lead with change, reason and source; preserve exact evidence links; explain unresolved/deferred outcomes |
| Documents | version/artifact/analysis inspection | content kind and missing-body reason in plain language; distinguish quoted source support from verified truth |
| Reports | evidence-bound Living Reports | explain prerequisite and next action in empty state; show revision/cause and stale/reconciled state |
| Alerts | in-app review and delivery preferences | keep authoritative in-app state, make material alerts discoverable from Home even in Simple; no push promise when browser is closed |
| Workbench | search/compare/notes/diagnostics combined | keep Advanced, searchable object selectors; do not add another main dashboard |
| Ask | global/scoped questions, normal local route; ID field for scopes | contextual entry from a Story/Document with scope selected, name search for objects, active route label, truthful insufficient-evidence action |
| Topics/Subjects/Sources | table/read/review views, raw identifiers, no complete creation | create/select within Watch setup; collection browsing stays Advanced; never tell ordinary users to “create through the API-backed workflow” |
| Watches/Monitors | target ID, policy creation, trial-specific UAP default | choose/create named topic, add reviewed source, simple cadence preset; advanced policy behind disclosure; blank/example-neutral default |
| Research Questions | useful gaps/tasks/hypothesis primitives; raw Claim/hypothesis IDs | named selectors and contextual actions; keep bounded pursuits and manual approval; no general chat-agent pivot |
| Runs/Jobs | diagnostic type/attempt/ID tables | Advanced status detail with safe Retry/cancel where supported; ordinary user sees collection/processing stage and next action |
| Settings | mode/notifications/install editable; raw settings and budget JSON | sections: General, AI Providers, Usage & limits, Appearance, Status & recovery; typed controls over existing authorities |
| PWA/install | install-event button when browser provides it; shell cache | platform-specific unavailable/install guidance, update/reload state, coherent cached asset versions |
| Offline/mobile | API uncached; new launch may return to login | state clearly “service unavailable; cached shell only”; distinguish internet outage from local server outage; physical phone needs approved secure connection |
| Loading/error/empty | shared roles and retry primitives | avoid generic “could not load” for invalid user action; retain form contents except secrets, prevent double submit, explain recovery |

## Must fix before everyday use

- One-action launch and honest API/worker/scheduler status (AST-02–05).
- Complete first-Watch setup without IDs, terminal commands or paid account (AST-12).
- In-app provider/cost management that actually affects the worker (AST-06–11).
- Fix phone Settings overlap; shared controls must stay inside cards (AST-13).
- Dark defaults and readable contrast; all supported user flows retain provenance links.
- Empty Home/Ask/Reports clearly explain prerequisites and next action.
- Backup/update/recovery actions that wrap existing verified operations, with status after failure (AST-14/19).

## Must fix before commercial pilot

- Populated browser journey and keyboard-only operation at 320/390/768/1440px and 200% zoom.
- Provider form validation/errors do not leak credentials, confuse estimates with billing, or hide active route.
- Physical Windows install/reboot/update/recovery and supported phone browser/PWA acceptance.
- Safe support diagnostics, bounded documented limitations, onboarding time and usefulness measurement.
- Source access and content quality limitations are visible before purchase; no claims of comprehensive monitoring.

## Later polish

Optional Light/System switch, tray icon, visual customization, expanded shortcuts, richer search refinements. Avoid new primary destinations or decorative dashboards.

## Theme decision and implementation contract

Dark-only first milestone; dark remains default. `:root` tokens (`--ink`, `--muted`, `--quiet`, surfaces, accents), `color-scheme: dark`, dark manifest/background and reduced-motion rules are assets. Many literal backgrounds/text/borders remain across `styles.css`; consolidate into semantic background/panel/text/muted/border/focus/status tokens in the existing stylesheet. No parallel design system or pile of tail overrides. Align root/background, browser theme-color, manifest and offline document. Light/System should appear only when an entire alternate palette is qualified.

Measure text contrast against rendered/composited background (target 4.5:1 normal text, 3:1 large text); focus/control boundaries target 3:1. Inspect subdued `--quiet`, code text, disabled/secondary buttons, badges and translucent panels. Do not claim all muted text fails before measurement. Preserve visible focus, labels, live errors, reduced motion, Escape/focus return for overlays and usable touch targets. Avoid color-only meaning.

## Dark-experience acceptance (AST-13/19)

Review login, shell, every main view, settings/provider controls, forms/native selects, tables, dialogs/overlays, loading, errors, empty states, offline fallback, PWA/install chrome and mobile layouts. Use populated fixtures plus invalid/loading/offline states, keyboard and zoom. No unexplained bright surfaces, unreadable text, clipped controls or overlap. Verify body scroll and component bounds; a zero horizontal-overflow assertion alone is insufficient. Keep screenshots and a contrast/focus checklist with artifact identity. This audit did not perform that complete matrix.
