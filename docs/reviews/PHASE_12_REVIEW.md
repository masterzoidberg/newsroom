# Phase 12 Review — Story Intelligence Through Product UI

## Verdict

**Approved.** No Critical or Required findings remain. Phase 13 may begin.

Accepted implementation checkpoint:
`8ca018fe01a2e77dfc6817b47b285febe9f57283`.

Reviewed range: Phase 09 Story evolution and lineage, Phase 10 Research
Questions, Phase 11 Reports/Briefings/Alerts, and Phase 12 product UI/PWA,
integrated with the accepted monitoring system.

## Findings

### Required — resolved in the accepted checkpoint

1. **Exact-identity Story resolution depended on caller order.** When multiple
   candidates shared a URL or document identity, the resolver returned the
   first input. Candidates are now ordered by stable Story ID before identity
   and score evaluation. Reversed-input regression coverage proves the same
   winner and resolution path.
2. **Alert-rule dedupe windows were persisted but not enforced.** A repeated
   material observation could create an equivalent alert from a later report
   revision. Alert evaluation now compares bounded semantic cause identities
   within the configured window while retaining exact revision retry
   idempotency. Regression coverage confirms one durable alert.
3. **Product report generation did not evaluate alert rules.** The UI generated
   evidence-bound revisions, but alert emission was reachable only by direct
   service calls. The authenticated generation API now evaluates rules after a
   successful revision, with deduplication protecting retries. API and browser
   tests prove the durable in-app alert appears.
4. **Structured report values could overflow the viewport.** Long evidence
   strength records expanded the report beyond desktop and responsive bounds.
   Report sections now allow grid shrinkage and wrap long values. Regenerated
   desktop/tablet/phone screenshots confirm containment.

### Required — previously resolved and reverified

1. The service worker caches successful same-origin static assets, bypasses all
   `/api/` requests, and falls back to the cached shell for offline navigation.
2. Primary navigation uses links, `aria-current`, a named navigation landmark,
   a skip link, hash deep links, and visible keyboard focus.
3. Saved Stories render the API's nested current-revision shape without
   conflating review state with `new_update` attention.

### Optional / non-blocking

1. The phone menu intentionally overlays the workspace. It remains keyboard
   reachable and exposes expanded state; a backdrop and outside-click close can
   be added later.
2. The manifest uses the local SVG mark. Distribution-specific raster icons can
   be added if a target platform requires explicit 192px/512px PNG assets.

## Logical review

### Story correctness and lineage

- Frozen false-merge/false-split fixtures, ambiguous candidates, temporal
  compatibility, corrections, mutable documents, event exclusions, shared
  Claims, and deterministic tie ordering pass. Exact URL/document identity is
  deterministic; unresolved ambiguity splits to a new Story.
- Duplicate, corroboration, contradiction, qualification, correction, material
  update, and new-Story classifications remain evidence-derived. Syndication,
  wire propagation, rewrites, citations, and common-primary-document lineage
  are inspectable and do not inflate independent corroboration.
- Immutable Story evolution events and revision-document links preserve the
  evidence trail. Saved/dismissed state remains independent from material-update
  resurfacing.

### Research and report integrity

- Gap detection derives from stored Claim state, support/contradiction links,
  missing primary evidence, and lineage-aware independence. Question lifecycle,
  immutable history, evidence links, schedules, and attempt/query/model/cost
  budgets survive retries; hypotheses remain notes and never become Claims.
- Living Report propositions resolve only to the exact accepted supported Claim
  set. Material-change explanations require accepted Claim and Evidence Span
  provenance; unsupported content aborts generation transactionally.
- Report revisions are immutable. Current status, changes, Stories, evidence
  strength, contradictions, unresolved Questions, and investigations remain
  auditable against the stored ledger.

### Importance and alerts

- Briefing windows validate IANA timezones and deduplicate daily/weekly periods.
  Ranking uses material evidence causes rather than article or keyword volume.
- Alert rules enforce target, event, importance, and bounded semantic dedupe
  windows. Exact retries and equivalent later revisions do not create storms.
  Acknowledgement and delivery attempts retain durable state.
- Permission denial, browser disablement, offline delivery, and failure never
  remove the in-app record. Browser delivery remains opt-in and no notification
  payload is dispatched beyond the stored delivery policy/state in this phase.

### UI, security, accessibility, and performance

- Product surfaces use canonical authenticated same-origin APIs. Mutations send
  CSRF tokens; destructive report archival requires confirmation. React output
  encoding is preserved and no raw HTML injection path was introduced.
- Loading, empty, error, stale/update, permission, and offline states are
  explicit. Story evidence provides direct source navigation and exact locators.
- Desktop, tablet, and phone layouts, keyboard navigation, focus visibility,
  semantic headings/forms/tables, reduced motion, PWA registration, offline
  workspace state, and cached-shell reload were exercised.
- List APIs use bounded pagination. Story/report collection queries are bounded;
  alert dedupe inspection is capped at 1,000 recent rule/report records. The
  production bundle is 196.43 kB JavaScript (59.15 kB gzip) with no new runtime
  dependency and no high-severity npm vulnerability.

## End-to-end evidence

- [Login — desktop](phase12-screenshots/01-login-desktop.png)
- [Story and exact evidence — desktop](phase12-screenshots/02-story-evidence-desktop.png)
- [Bounded Research Question — desktop](phase12-screenshots/03-question-desktop.png)
- [Closed-world Living Report — desktop](phase12-screenshots/04-report-desktop.png)
- [Durable Alert — desktop](phase12-screenshots/05-alert-desktop.png)
- [Alert layout — tablet](phase12-screenshots/06-alert-tablet.png)
- [Alert and navigation — phone](phase12-screenshots/07-alert-phone.png)
- [Offline workspace — phone](phase12-screenshots/08-offline-workspace-phone.png)
- [Cached offline shell reload — phone](phase12-screenshots/09-offline-shell-phone.png)

The browser run creates an accepted Claim and exact Evidence Span, inspects its
Story, creates a bounded Question, creates an alert rule and Living Report,
generates an audited revision, verifies the resulting in-app alert, exercises
responsive layouts, verifies an active service worker, then reloads offline.
No unexpected browser console errors remain.

## Verification

- `python -m pytest --tb=short` — **270 passed**, 29 HTTPX deprecation warnings;
- `python -m compileall -q newsroom scripts` — pass;
- `python -m newsroom.evals validate` — corpus valid, 30 cases;
- `npm.cmd run typecheck` — pass;
- `npm.cmd run build` — pass;
- `npm.cmd audit --audit-level=high` — 0 vulnerabilities;
- production same-origin browser workflow through `with_server.py` — pass;
- desktop/tablet/phone/offline screenshots — captured and visually inspected;
- `git diff --check` — pass.

The prescribed `poetry run format`, `poetry run test`, `pnpm format`, `pnpm
lint`, and `pnpm types` wrappers were attempted but are unavailable or
misconfigured in this repository. The direct project gates above pass.
