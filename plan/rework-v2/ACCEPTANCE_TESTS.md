# Acceptance tests

Status: specifications, not executed tests of the redesign. Existing audit checks are recorded in TECHNICAL_FINDINGS. Each case below requires an executable assertion and a recorded result before its owning milestone is complete.

## Deterministic harness

Use temporary SQLite DB/artifact roots outside the repository, fixed UTC clock, known UUIDs, fake safe transport, fake AI/search adapters and no credentials/network. Run the real scheduler, JobService/worker handlers and completion hooks against fixtures, not only service mocks. Assert database lineage and final UI responses, not just HTTP 200. Use a transport counter, invocation/usage ledger and canonical IDs to prove dedup and zero-paid behavior.

Fixture A = UAP congressional oversight, B = Boeing safety. Both approve the same Reuters-like fixture feed, with separate Monitor/scope IDs. Documents: A-only, B-only, both, neither, an older relevant version followed by unrelated content, a contradictory B-only Claim linked to a shared global Story, and repeated wire-derived evidence. Transport variants: 200, 304, unchanged body, redirect, unsafe redirect, timeout, malformed feed, full-content Atom, summary RSS, duplicate item URLs, cross-domain origin, oversized body. Freeze clocks to test admission, pause, scope edit and publication vs knowledge times.

Browser testing is justified: routing/drawer focus/staged setup cannot be proved by current source-string pytest assertions. Reuse existing Python Playwright/Chromium smoke pattern and add one maintained rework harness; no second JS test framework or runtime dependency is prescribed. API-route fixtures may support UI failure states, but the primary first-value flow must use a real isolated backend plus fake external services.

## Primary journeys

**AC-North-Star (M7):** clean DB→configure authorized fake interpretation/search/analysis capabilities→New Research→“UAPs and Congress”→review Focus/terms/exclusions→Scout returns useful bounded Sources→inspect feed/site→edit profile→approve→Ready review→Start twice→one durable check→scheduler/worker processes linked article→scoped Update/current Briefing→Ask→exact citation→reload/new tab/Back preserve route. Assert no raw IDs were entered, source/evidence provenance exact, paid authorization never expanded, B-only evidence absent everywhere. Every intermediate state comes from persisted work. Repeat with no changes/irrelevant/partial failure/no accepted evidence.

**AC-Manual (M7):** clean DB, no provider credentials and paid off→plain prose→manual name/Focus/terms/exclusions→single pasted website→feed detection/selection→explicit approval→Start/check→local evidence/Briefing/Ask or honest insufficient-evidence state→citation. Transport may contact approved sources; provider invocation count must be zero. No invented suggestions, semantic equivalence claim or required AI setup. Basic local capability label remains visible.

## Setup, inspection and proposals

| ID | Stimulus | Required assertion |
|---|---|---|
| AC-N01 | Clear prose with capable fake interpreter | Bounded name/Focus/terms/exclusions proposal, zero unnecessary questions; no approved scope mutation |
| AC-N02 | Ambiguous “Mercury” | At most two material questions; answer changes proposal; no premature activation |
| AC-N03 | No provider / paid disabled | Manual completion available; original intent persisted; display name does not become approved matching term |
| AC-N04 | Edit intent after proposal | Old approval cannot apply silently; diff/reconfirmation; scope revision pinned |
| AC-N05 | Save timeout and identical request retry | Same Watch/Topic-or-Question/policy IDs; changed request with same UUID conflicts |
| AC-N06 | Question-first prose/existing Question | Existing composition reused; one Watch per target; no duplicate question hierarchy |
| AC-N07 | Cancel/fail interpreter | Draft/manual edits retained; no Scope/Source activation or hidden paid retry |
| AC-N08 | Save Focus/terms/exclusions | Future Monitor scope versions updated transactionally; existing observations/Briefing revisions unchanged |
| AC-N09 | Empty positive scope or no approved usable endpoint | Start blocked with named action; no jobs/network |
| AC-P01 | Paste raw RSS or Atom | Type/title/endpoint inferred; one-field UX; explicit approval required |
| AC-P02 | Paste website with relative rel=alternate feeds | Safe bounded resolution; offered endpoints correctly associated; multiple choices reviewed |
| AC-P03 | Website without feed / unsupported format | Direct-page option if supported; honest limitation; not “entire site monitored” |
| AC-P04 | Known homepage/feed/redirect alias | Reuse Source only on supported identity match; no duplicate by alternate URL |
| AC-P05 | Same slug/name, different sites; case-sensitive paths | No false merge; identity conflict review; distinct meaningful paths retained |
| AC-P06 | Private address, mixed public/private DNS, unsafe redirect, DNS rebinding, oversized response | Block each applicable hop/peer; bounded error; no evidence/monitoring side effects |
| AC-P07 | Malformed XML / DTD / script metadata / malicious canonical URL | Fail safely or ignore unsafe hint; never execute instructions or fetch unapproved links |
| AC-P08 | AI profile→user override→later AI reassessment | Original AI record retained; user effective value wins; global role vs Watch coverage scope respected |
| AC-P09 | Inspect/approve/reject source while paused | Inspection is preview only; approval opens membership but does not fetch article/start Monitor; rejection retained and not resurrected |
| AC-A01 | Bootstrap empty corpus | Existing model recommendation reused, external search explicitly distinguished; coverage plan + candidate provenance |
| AC-A02 | Populated corpus | Corpus discovery labeled correctly; later explicit external Scout remains possible, no claim corpus means web search |
| AC-A03 | External setup authorization | Exact capability/config generation/max cost/requests/expiry pinned; zero unintended global paid changes |
| AC-A04 | Missing/disabled provider, quota exhausted, expired grant | Manual fallback; no call and safe reason |
| AC-A05 | Concurrent paid admission/retry/ambiguous timeout | No duplicate unauthorized invocation; unknown billing outcome retained; new spend requires a new grant |
| AC-A06 | Provider removed/route changed between enqueue and call | New operation fails closed or requires new authorization; environment does not resurrect provider |
| AC-A07 | Malicious search result/profile suggestion | No automatic authoritative classification, source approval or evidence; prompt injection stays data |
| AC-A08 | Inspect persisted DB/export/logs/frontend/telemetry | No API secrets; bounded allowed proposal context only; unrelated Research evidence never transmitted |

## Shared processing and historical membership

| ID | Stimulus | Required assertion |
|---|---|---|
| AC-I01 | Same Source and version relevant to A and B | One canonical Document/representation; independent A/B relevance and contextual processing; both eligible |
| AC-I02 | A-only material | A relevant; B not relevant; B has truthful processed result, not missing job |
| AC-I03 | B-only material, A acquires first | B gets missing processing even when acquisition is unchanged; A excluded |
| AC-I04 | Irrelevant to both | Both durable negative decisions; no invented Update/evidence-backed success |
| AC-I05 | Different Monitor scope versions | Each decision uses pinned snapshot; differing scopes do not share analysis identity |
| AC-I06 | A paused, B active | B acquires; no new A observation/paid processing; historical A evidence remains |
| AC-I07 | A resumes and sees unchanged/304 version | A gets any missing obligation at current approved scope, without duplicate body download |
| AC-I08 | Concurrent ticks/manual enqueues/reruns | One active job per contextual identity; two contexts are allowed; API/rerun cannot bypass guard |
| AC-I09 | Crash between observation and enqueue / before completion acknowledgement | Atomic observation+obligation or durable reconciliation; retry reuses exact relevance/analysis/promotion |
| AC-I10 | Known successful result observed in later check | Reuse contextual result, record new check-observation link; no false new Update or paid analysis |
| AC-I11 | Legacy acquisition-only job and new contextual job coexist | Legacy version-only guard cannot suppress contextual work; no payload ownership mismatch accepted |
| AC-I12 | Same article discovered via two feed Sources | One canonical article; both discovery edges; no skip due solely to Document.source_id mismatch; attribution preserves origin |
| AC-H01 | Detach A's Source | Close A interval/remove current projection/disable A Monitor atomically; B unaffected; A past evidence still retrievable |
| AC-H02 | Reattach A | New interval, same Source/Monitor identity where applicable; no duplicated old relevance; new admission trace retained |
| AC-H03 | Pause/detach before network or paid admission | Suppress that work; show skipped/cancelled; already admitted work handled per architecture contract |
| AC-H04 | Scope edit after observation before processing | Old observation uses old pinned scope; new observation uses new scope; no rewrite |
| AC-H05 | Legacy detached Monitor with partial ownership proof | Recover only provable Research association; unknown dates labeled; ambiguous rows excluded from ordinary Research outputs and listed for review |

## Check lifecycle and linked publications

| ID | Stimulus | Required assertion |
|---|---|---|
| AC-C01 | Start valid paused draft | Activation + expected source snapshot + due-now timestamps in one transaction; no API synchronous fetch |
| AC-C02 | Duplicate Start/Check UUID and concurrent requests | Same receipt for same inputs; conflict for changed inputs; equivalent active requests coalesce |
| AC-C03 | Scheduler offline | Due state persists through reload; no fake checking animation or success; restart picks it up |
| AC-C04 | Check now while periodic subset active | No duplicate acquisition; all requested sources represented now or explicit queued next check; no dropped obligations |
| AC-C05 | All unchanged | Terminal no_source_change; attempted/succeeded counts exact; missing contextual processing still runs |
| AC-C06 | New material irrelevant | Terminal new_material_irrelevant; distinct from no change |
| AC-C07 | Relevant material queued/analyzing | Processing remains nonterminal with exact descendant counts; no ready claim |
| AC-C08 | Processing returns no accepted evidence | Terminal no_accepted_evidence; not perpetual processing or error merely because no Update |
| AC-C09 | One source fails, others succeed | Terminal partial_failure after descendants settle; successes visible; failed-subset retry only |
| AC-C10 | All sources fail | Terminal failed; concrete safe reasons/retry guidance |
| AC-C11 | Old failure, new successful check | Old job failure cannot contaminate current result; global latest-100 truncation cannot hide this check's work |
| AC-C12 | Child analysis/report retry exhausts | Terminal stage failure/stale Briefing warning; no infinite preparing; existing evidence retained |
| AC-C13 | Crash/lease expiration/concurrent recovery | Same work identity and check links restored; counters not doubled; no busy-wait deadlock with one worker |
| AC-C14 | Check now while paused / no sources / item ceiling hit | Explicit resume or blocker; bounded surplus shown/deferred with cursor; no fake complete coverage |
| AC-F01 | Feed item links to article | Feed discovery→shared article job→exact article version→Research observation lineage resolves |
| AC-F02 | Duplicate item/article URLs in one/two feeds | One compatible concurrent fetch; all discovery origins retained; counters distinguish discoveries/publications |
| AC-F03 | Redirect and canonical URL alias | Safe final identity reused; requested/final chain preserved; canonical tags alone do not merge |
| AC-F04 | Cross-domain linked publication | Safe bounded fetch allowed by reviewed link policy; unknown origin Source not auto-monitored or trusted; processing and promotion verifier resolve membership→feed discovery→article version; forged/missing edges fail closed, old direct Source checks remain |
| AC-F05 | Cross-domain private/unsafe redirect | Blocked, useful feed fallback labeled; no SSRF |
| AC-F06 | Article timeout/unavailable | Summary/full-feed fallback retains correct representation; “article unavailable” visible |
| AC-F07 | Unchanged article with changed feed summary | No article→metadata comparison churn; same article version reused; feed observation separately retained |
| AC-F08 | Full-content Atom/content:encoded | Full feed content preserved with fidelity label and bounded sanitizer; not falsely called fetched article |
| AC-F09 | Summary-only RSS | Evidence explicitly RSS summary; title alone not upgraded to semantic conclusion |
| AC-F10 | Later article retrieval succeeds | New article representation preferred in current view; old feed citation remains exact and usable |
| AC-F11 | A/B share fetch under different analysis budgets | Acquisition billed/attributed once; B cannot inherit A's paid permission; A/B analysis reservations independent |
| AC-F12 | Oversized feed, too many links, publisher restrictions | Time/byte/item/request bounds enforced; deterministic deferred/unavailable outcomes, no access-control bypass |

## Read isolation, synthesis and exact evidence

| ID | Stimulus | Required assertion |
|---|---|---|
| AC-S01 | A Ask with B-only evidence from shared Source | B-only IDs, text, snippets and citations absent |
| AC-S02 | Shared global Story with mixed Claims | A Update/Overview/Ask uses only A-qualified statements, not copied global summary |
| AC-S03 | A-qualified Claim has B-only supporting/contradicting links | Packet and final answer do not expand to B links; support qualification uses A evidence |
| AC-S04 | Document has in-scope old version and out-of-scope latest | Only admitted relevant version used; no document-level version expansion |
| AC-S05 | Detached Source / earlier scope | Historical A evidence still available with old scope/former Source provenance |
| AC-S06 | No sufficient qualifying evidence | Bounded explicit refusal; no global fallback |
| AC-S07 | Question/note/report/entity expansion and corrections | Every expansion/final serialization intersects Research boundary |
| AC-S08 | User injection asks to reveal B / fabricated citation | No out-of-bound retrieval or citation; prompt treated as request, not scope authority |
| AC-S09 | Direct evidence route claims wrong Watch/version | Ownership/version mismatch rejected; never silently substitute latest version |
| AC-S10 | Historical knowledge-time query fixture | No observation, acceptance or revision learned after boundary; published_at alone cannot include later-learned evidence |
| AC-E01 | Citation opens drawer then direct link | Same exact span/version/artifact with relationship and dates |
| AC-E02 | Feed fallback citation | Source fidelity prominent; linked article failure/discovery path inspectable |
| AC-E03 | Artifact hash mismatch / missing span | Fail closed with unavailable explanation; no fabricated excerpt |
| AC-E04 | Multiple syndicated outlets | Known dependency groups labeled; outlet count not independent-confirmation count |
| AC-E05 | Official Source profile edited to high authority | No Claim state/acceptance mutation; “agency said X” not “X proven true” |
| AC-E06 | Corrected/superseded Claim or historical Briefing | Old exact evidence remains; current correction/status shown without rewriting old artifact |
| AC-B01 | First accepted in-scope Claim | One Watch LivingReport ensured; current Briefing refresh via queue; no manual create required |
| AC-B02 | Unchanged scoped input / replay | No duplicate revision or alert/delivery |
| AC-B03 | No accepted evidence | Useful empty/deferred Briefing state; no fabricated synthesis; check can finish |
| AC-B04 | B-only change in shared Story | A Briefing input/hash/output does not change due solely to unrelated B content |
| AC-B05 | Correction of A-qualified evidence | New scoped revision/cause; old revision immutable |
| AC-B06 | Delivery disabled | Current Briefing still generated; no notification |
| AC-B07 | A/B same daily timezone/window | Separate scoped digests; no legacy same-window row reuse mixing content |
| AC-B08 | Legacy Monitor/Topic/Question report | Accessible as legacy/advanced; not certified as Watch-isolated without new scoped projection |
| AC-B09 | Concurrent refreshes and crash after revision commit | Input identity coalesces; valid last revision retained; bounded retry |
| AC-B10 | Stale/failed refresh | Last good revision labeled dated/stale; current error explicit; no silent successful status |

## UI, feedback and upgrade gates

| ID | Stimulus | Required assertion |
|---|---|---|
| AC-U01 | Research/view reload and new tab | Same addressed Research/view; no selected-ID storage dependency |
| AC-U02 | Update→Evidence→Back→Forward | Correct overlay/page history, focus restore and exact evidence identity |
| AC-U03 | Login from deep link, invalid/encoded route, deleted Research | Intended valid route restored; honest invalid/not-found states, no random selection |
| AC-U04 | Legacy hashes / storage disabled | Deterministic compatible landing; new normal workflow works with storage unavailable |
| AC-U05 | 390/768/1440 widths, long text, 200% zoom | No horizontal page overflow/clipped primary actions; legible type and drawer |
| AC-U06 | Keyboard/screen reader/reduced motion | Focus trap/restore, Escape, labeled tabs/buttons/status, skip link unaffected by router |
| AC-U07 | Home review while new event arrives | Only displayed high-water boundary acknowledged; new event remains unread |
| AC-U08 | Section fetch fails among populated sections | Local retry preserves other content and current Research |
| AC-U09 | Normal vs Advanced Settings | No raw key/value dump/operator IDs in normal flow; secure provider controls reachable advanced |
| AC-U10 | Navigation/settings/check actions | No implicit AI call or paid enable; local capability label truthful |
| AC-X01 | Why this matched | Pinned terms/Focus/source/eligible evidence explain match, not current changed scope |
| AC-X02 | Not useful + reason→reload | Append-only Watch+Update/event feedback retained; no automatic ranking/scope mutation |
| AC-X03 | Coverage with unhealthy/former Source | Counts approved active mappings, health separately; former sources not counted as active coverage |
| AC-X04 | AI reassessment vs user override | Review suggestion shown; user value persists |
| AC-X05 | Source role changed | Intellectual profile and operational health/Claim truth remain distinct |
| AC-R01 | Schema39 upgrade with active/terminal legacy jobs | IDs/results preserved; context backfill validated; no mixed old/new writers |
| AC-R02 | Known/unprovable legacy membership | Conservative migration and unresolved report; no invented dates or global corpus assignment |
| AC-R03 | Logical export/import and verified backup/restore | New nonsecret lineage metadata round-trips as explicitly partial archive; unsupported runtime import rejected before mutation. Verified backup restores full evidence/obligations; secrets absent from logical export |
| AC-R04 | Restore matching prior binary/schema in isolated root | Proven rollback; no new-schema database opened by old writer; no production/trial mutation |

## Completion evidence

For each milestone record fixture version, branch/HEAD + dirty status, command, result count, artifact paths and known limitations in EXECUTION_PLAN. Keep failing adversarial fixtures until fixed. Final engineering gate includes full backend suite, applicable static checks, frontend build and real-backend browser journeys. Real-world Source utility, extraction quality, installed runtime and physical phone acceptance remain owner-visible qualification gates. No live paid call is implied by these test specifications.


## Final M0 audit acceptance additions

These are required future tests, not executed implementation results.

| ID | Fixture / action | Required result |
|---|---|---|
| AC-M01 | Story Watch merge, collision, split/resolve | Watch IDs retained; target/lifecycle snapshots explain history; no wrong current-need inference |
| AC-M02 | Topic, Question, Subject, Story and Source-only Watches | Existing behavior compatible; Source-only lacks invented semantic eligibility |
| AC-M03 | Target term edit plus Watch overlay; Focus-only approval | Atomic overlay preservation; Watch revision changes without forcing semantic version; failed transaction leaves no drift |
| AC-M04 | Detach, edit scope, reattach; unknown legacy interval | Reused Monitor gets current scope; old jobs remain pinned; unknown interval not active |
| AC-M05 | Feed 200 then 304 with B newly attached | Exact prior snapshot reused; B pending admission created, no historical Source-wide scan |
| AC-M06 | Page/feed 304 missing cache; same-hash 200 | Bounded recovery or explicit unavailable; unchanged can create missing obligation |
| AC-M07 | Crash during manifest/admission persistence; detach while fetch in flight | No incomplete manifest presented complete; withdrawn subscriber not newly admitted; existing admissions retained |
| AC-M08 | Concurrent contextual enqueue via all API/rerun/recovery paths | One active job per version/Monitor/scope; A/B never suppress one another |
| AC-M09 | Expired lease, stale worker publishes after replacement | Only current lease/attempt can commit result/side effects and complete |
| AC-M10 | Crash after relevance, analysis or promotion before downstream job completion | Stage-wise recovery schedules missing descendants; stable IDs, no duplicated paid invocation or promoted evidence |
| AC-M11 | Shared Story/Claim with mixed support and global summary | A/B projector returns only eligible support and safe text; acceptance not mutated per Watch |
| AC-M12 | Detached and earlier-scope evidence; current target corrected | Historical qualified evidence retained/explained; unresolved history not silently admitted |
| AC-M13 | Concurrent A/B source checks, opposite relevance | One compatible endpoint fetch, two contextual outcomes, no shared semantic decision |
| AC-M14 | Dispatch succeeds before child insertion/completion; failure/cancel/exhaustion | Atomic sealed graph; no early Run success; legacy unscoped finalizer compatible |
| AC-M15 | Duplicate legacy Sources share URL; redirects/mirrors/alternate feeds | All source IDs preserved; conflict labels; transport sharing never establishes publisher authority |
| AC-M16 | Repeated migration with ambiguous detached/corrected history | EXACT/INFERRED/UNKNOWN counts stable; no invented dates, row loss or network calls |
| AC-M17 | RSS guid, Atom id, summary versus full content and old truncated feed | New basis preserved; old missing fidelity unknown; no fabricated retrieved article |
| AC-M18 | Ask task/correction/snippet/citation and report section expansions | M0 projector fixture isolates packets; M4/M5 actual consumers pass same adversarial corpus before release |
| AC-M19 | 100 Watches, one endpoint/version; mid-fanout restore | One compatible fetch, bounded 100 contextual obligations, indexed pagination and no lost subscriber |
| AC-M20 | Metadata export during writes, conflicting import, backup restore and causal deletion | Consistent snapshot, accurate counts/atomic conflicts, partial archive non-runnable, full backup projection equivalent, retained proof not cascaded away |

M4/M6 additionally test Question Watch Home attribution, global event counted once with multiple qualified Research labels, per-Research acknowledgement, and no raw global alert-body leakage. M1/M2 security tests exercise every URL transition, DNS/redirect revalidation, XML entities and bounded response/item limits; safe initial input alone does not pass.
