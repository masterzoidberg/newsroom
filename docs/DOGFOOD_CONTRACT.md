# Phase 29 → dogfood start contract

Status: **A2 configuration record; A4 observation protocol frozen and official
observation boundary recorded in `docs/reviews/PHASE_29_OBSERVATION_PROTOCOL.md`.**

This contract records the one approved Phase 29 trial configuration created on
2026-09-06. It is intentionally narrow and uses the existing Topic, Watch,
Source-candidate, Monitor, scheduler, worker, acquisition, and recovery paths.
It does not certify the downstream A3 evidence pipeline or intelligence value.

## Subject

**UAP / UFO disclosure and sightings**.

The intended information need covers documented UAP/UFO incidents; government
investigations and disclosures; hearings and official statements; military and
aviation reports; released records; scientific analysis; credible evidence
investigations; material corrections or rebuttals; and testimony from directly
relevant officials or witnesses. The Watch does not assume that UAP claims are
true or false; it monitors evidence and developments.

## Approved semantic scope

The Topic has these 18 active include terms, managed through the existing Topic
vocabulary mechanism:

`UAP`, `unidentified anomalous phenomena`, `unidentified aerial phenomena`,
`UFO`, `unidentified flying object`, `flying saucer`, `flying saucers`, `NHI`,
`non-human intelligence`, `anomalous craft`, `UAP disclosure`, `UFO disclosure`,
`UAP sightings`, `UFO sightings`, `UAP investigation`, `UAP evidence`,
`UAP hearing`, and `UAP report`.

The scope is not a literal requirement to match every occurrence. Broad pages
remain subject to the product's scope, relevance, and later human review.

## Approved Sources

The initial set is deliberately bounded at eight manually reviewed Sources.
Candidates were not auto-approved. All are direct-HTTP sources in this trial;
none has a feed URL configured.

| Source | Class | Inclusion reason | Limitation |
|---|---|---|---|
| AARO UAP Report Documents | Official / primary | U.S. government repository for AARO UAP report documents. | Page access may be blocked; individual document links can change. |
| AARO Congressional and Press Products | Official / primary | AARO congressional and press materials, briefings, and statements. | Page access may be blocked; product links can change. |
| NASA UAP | Official / primary | NASA scientific context and public UAP material. | Not a rolling incident-news feed; updates may be infrequent. |
| FAA General Statements | Official / primary | Aviation-regulator statements and relevant aviation context. | Broad page; UAP items are a subset. |
| U.S. Department of Defense News | Official / primary | Military, aviation, and AARO-related official releases. | Broad newsroom; semantic filtering is required. |
| AP News | Reputable secondary | National reporting and public-record coverage. | Broad homepage; news-volume and syndicated-copy noise are possible. |
| The Debrief Analysis | Specialist secondary | UAP-relevant reporting and document analysis. | Claims require corroboration; not a primary authority. |
| The Black Vault UFO Files Search | Specialist archive | Searchable released/FOIA document index. | The archive is not the issuing authority; originals require checking. |

The operator record at
`docs/reviews/PHASE_29_TRIAL_READINESS.md` contains the persisted Source and
Monitor IDs and the reviewed URLs. Material Source changes during observation
must be logged.

## Watch and cadence

- Watch: `Phase 29 UAP / UFO disclosure and sightings trial`.
- Target: Topic `UAP / UFO disclosure and sightings`.
- Discovery: disabled for the initial run. Source discovery remains available
  through the existing candidate path, but this trial starts from the bounded
  manually reviewed set and does not silently expand it.
- Policy: six-hour base cadence, three-hour minimum, 24-hour maximum.
- Scheduler behavior: the process polls the durable queue; it does not change
  the Watch cadence. The normal documented scheduler interval is 30 seconds.
- Backoff: the policy uses the existing bounded error/no-change backoff with a
  multiplier of 2.0. In the proof run, the successful NASA Monitor advanced by
  six hours and the failed AARO Monitor advanced by twelve hours.
- Retry: durable Jobs use the existing bounded retry/lease behavior. A2 does
  not certify every downstream retry or idempotency path.

## Dedicated runtime

The logical runtime identity is `phase29-trial/prod`, separate from the
repository and the existing developer runtime. The operator-specific Windows
root for this contract is:

`C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod`

- Database: `...\prod\data\newsroom.db`.
- Backups: `...\prod\backups\`.
- Logs: `...\prod\logs\`.
- Cache: `...\prod\cache\`.
- Acquired content/artifacts: persisted in the trial database's document,
  document-version, and content-artifact tables; no repository path is used.
- Schema: 36.
- Release identity: repository commit
  `e0d626cf88b06e1aa3b7a0af2b41558e7662932a` and the bounded documentation
  commit recorded in the readiness review.

Runtime commands always pass `--environment prod --root` explicitly. Never use
the repository directory or the developer database for this Watch.

## Provider behavior and budget

- Acquisition: direct HTTP, cost `$0`.
- Watch relevance path: deterministic local cascade, cost `$0`.
- Article analysis: the requested default is local/free. The runtime
  environment had `NEWSROOM_ANALYSIS_PROVIDER` unset, so the effective route
  is local. The existing `OPENAI_API_KEY` was not used. A naturally enqueued
  downstream analysis attempt failed locally; paid escalation was recorded as
  blocked and is outside this A2 acceptance.
- Ask/research: not exercised by this A2 setup; the product's local
  deterministic defaults remain the effective default unless explicitly
  changed later.
- Monitor policy: `paid_budget_usd=0.0`, `local_model_budget=0`.
- Runtime budget: `budget.paid_enabled=0`, global lifetime paid-request cap `0`,
  and global lifetime paid-USD cap `0.0`.
- No paid provider call was made. Any future provider/model or budget change
  requires a logged contract change before observation comparability is
  claimed.

## Observation period

The minimum Phase 29 observation window is four weeks. This A2 readiness record
stopped the processes after operational and recovery proof and did not claim
that the window had started. The A4 observation protocol subsequently verified
the restored clean baseline and established the official boundary
`2026-09-06T21:20:48Z`; its earliest four-week boundary is
`2026-10-04T21:20:48Z`. This contract still does not claim a four-week result.

## Operators and ownership

The project is currently operated by one user. Names are intentionally not
invented. That operator fills these roles unless delegated and recorded:

- uptime owner;
- restart and incident owner;
- backup and restore owner;
- human usefulness-log owner; and
- blinded scorer.

The usefulness log and any scoring protocol must be created and dated before
the observation evidence is interpreted.

## Change control

During the observation period, log every material change to the Source set,
semantic scope, provider/model behavior, budget, or core monitoring behavior.
Do not silently change those variables and then compare results as if the trial
were unchanged. The readiness record is the configuration baseline; the
runtime database and backups remain outside source control.

## Start procedure

From the repository root, start the three supported processes against the
dedicated root:

```powershell
python -m newsroom.runtime api --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --host 127.0.0.1 --port 8127
python -m newsroom.runtime worker --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --worker-id phase29-trial-worker
python -m newsroom.runtime scheduler --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod
```

`GET /api/v1/health` is public and is the startup check. Authenticated API
management routes require the existing session and CSRF behavior. Stop writers
before restore or upgrade, following `docs/RECOVERY_RUNBOOK.md`.

## A2 boundary

This contract permits the installed-pipeline rehearsal in A3 to begin after
the operator starts the runtime. It does not certify relevance quality,
structured article analysis, evidence spans, Claims, Stories, Reports, Alerts,
research automation, Full-vs-Lite value, or the four-week intelligence-value
verdict.
