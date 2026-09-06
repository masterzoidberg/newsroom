# Phase 29 trial readiness

Date: 2026-09-06
Scope: A2 only — one approved UAP/UFO Watch and its operational substrate
Verdict: **ready to begin unattended observation after the operator starts the documented processes**

This record does not claim that the four-week observation window has started.
It also does not certify the downstream A3 evidence pipeline, article-analysis
quality, Story/Report/Alert automation, Full-vs-Lite value, or intelligence
value.

## Starting state

- Branch: `main`.
- Accepted baseline ancestor: `e0d626cf88b06e1aa3b7a0af2b41558e7662932a`
  (`Establish Phase 29 authoritative baseline`).
- Schema: 36.
- Baseline backend result: 838 tests passing, as recorded by the accepted
  baseline; not represented here as a newly run check.
- Pre-existing worktree state was preserved: the unrelated deleted
  `plan/phases/` files and pre-existing untracked `.kilo/`, ZIP, planning,
  review, and `plan/phases-v2` artifacts were not staged or changed.

## Runtime identity

The runtime uses the supported explicit Windows `prod` root outside the
repository:

| Item | Value |
|---|---|
| Logical identity | `phase29-trial/prod` |
| Runtime root | `C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod` |
| Database | `C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod\data\newsroom.db` |
| Backup directory | `C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod\backups` |
| Logs/cache | `...\prod\logs`, `...\prod\cache` |
| Restore proof root | `C:\Users\nicol\AppData\Local\Newsroom\phase29-trial-restore\prod` |
| Schema after initialization | 36, contiguous versions 1–36 |
| Acquired content | Same trial DB: 1 Document, 1 DocumentVersion, 1 content artifact |
| Release identity | `e0d626cf88b06e1aa3b7a0af2b41558e7662932a` plus this bounded documentation commit |

No runtime database, fetched content, log, credential, or backup is in source
control.

## Persisted Watch configuration

| Object | ID / value |
|---|---|
| Category | `cat_e582196ed34fdc433284c1b80c468c64` — Aerospace and anomalous phenomena |
| Topic / target | `top_c22007a2f9159a3fc2f69b3e3da70955` — UAP / UFO disclosure and sightings |
| Monitoring policy | `pol_c57d4f9e71e4be5e943ea21b2d77de3b` |
| Watch | `watch_ccc9898ad4bf9cbd8787fc9331123698` — active, high priority |
| Topic vocabulary | 18 active include terms; see `docs/DOGFOOD_CONTRACT.md` |
| Discovery | Disabled for the bounded initial run; pending source candidates: 0 |
| Approved Sources | 8 |
| Associated Monitors | 8, all enabled and pinned to `need_type=topic` and the Topic ID above |
| Cadence | Base 21,600 seconds (6 hours); minimum 10,800 (3 hours); maximum 86,400 (24 hours) |

### Approved Sources and Monitors

Every candidate was added through `WatchService.add_source_candidate` and
approved through `WatchService.review_source_candidate` by
`phase29-trial-operator`. The product resolved each candidate to a Source and
created the Source-targeted Monitor; no direct SQL creation was used.

| Source ID | Source / class | Reviewed URL | Monitor ID |
|---|---|---|---|
| `src_1c705924c464e02b1cb040ccf1f5da5b` | AARO UAP Report Documents — official / primary | [aaro.mil report documents](https://www.aaro.mil/Next-AARO-Home-redesign/Next-Parent/Next-UAP-Report-Documents/) | `mon_5a5eae7da1a4e05d5919949a8a4c35ab` |
| `src_ff286a4fb5cc0c420ff3b48c7efd5815` | AARO Congressional and Press Products — official / primary | [aaro.mil press products](https://www.aaro.mil/Next-AARO-Home-redesign/Next-Parent/Next-AARO-Congressional-Press-Products/) | `mon_e61913bc78f4ad7a53f55cb4b25b0511` |
| `src_c92eb515089d2046bdfd6571cb828361` | NASA UAP — official / primary | [NASA UAP](https://science.nasa.gov/uap/) | `mon_1a8699c948d7bfe7755f1a25628007ad` |
| `src_467b7d8fd9a0c16ea0b7bb68e01c0f85` | FAA General Statements — official / primary | [FAA general statements](https://www.faa.gov/newsroom/statements/general-statements) | `mon_09f3abacb990d8556c8196777e0f2065` |
| `src_274017189152c4db48b41c4638ab26b9` | U.S. Department of Defense News — official / primary | [DoD News](https://www.defense.gov/News/) | `mon_73795c9d6d682fefc3489e6251d97389` |
| `src_93133db716c5b5db09a83d950beec57d` | AP News — reputable secondary | [AP News](https://apnews.com/) | `mon_865901edf9e915ff627e8ce8a0403d70` |
| `src_c5263247190ceaace3aa28564c5ebbfe` | The Debrief Analysis — specialist secondary | [The Debrief analysis](https://thedebrief.org/category/analysis/) | `mon_5f73ee5a8b38267e7dc33a0ba32cb6ec` |
| `src_9412e17c0380319b2300bf4783ecc4c1` | The Black Vault UFO Files Search — specialist archive | [Black Vault UFO files search](https://www.theblackvault.com/documentarchive/ufo-files-search-engine/) | `mon_fb14612bc666f2f442fe8f8770778681` |

All eight use the configured `direct_http` acquisition path. The policy also
allows `rss` for future source changes, but no feed URL is configured in this
initial set.

## Provider and spend configuration

- Watch policy: `allowed_channels=["rss", "direct_http"]`,
  `paid_budget_usd=0.0`, `local_model_budget=0`, `query_budget=4`.
- Runtime setting: `budget.paid_enabled=0`.
- Global lifetime caps: `paid_requests=0` and `usd=0.0`.
- Environment inspection: `NEWSROOM_ANALYSIS_PROVIDER` was unset; an
  `OPENAI_API_KEY` was present in the host environment but was not used or
  persisted.
- Effective acquisition provider: free direct HTTP.
- Effective relevance path: deterministic local cascade.
- Article analysis was not part of A2 acceptance. It was naturally enqueued
  after the successful NASA acquisition, attempted the local route, and ended
  with `AIProviderError`; the paid route was recorded as `paid_disabled`.
  No paid call occurred.
- Ask/research were not exercised. No general-purpose local LLM is claimed;
  the product's deterministic local implementations are described as such.

## API, worker, scheduler, and Watch-health proof

The supported processes were started against the exact trial root:

```powershell
python -m newsroom.runtime api --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --host 127.0.0.1 --port 8127
python -m newsroom.runtime worker --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --worker-id phase29-trial-worker --interval 1
python -m newsroom.runtime scheduler --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --interval 5
```

Proof results:

- API PID `20660` started and `GET http://127.0.0.1:8127/api/v1/health`
  returned HTTP 200 with `{"service":"newsroom","status":"ok"}`.
- Worker PID `56176` consumed the scheduled `monitor_check` Job
  `job_2beacc24b606c8e8597a126ca8d5224d` successfully.
- Scheduler PID `37320` recognized the due Monitor and created that durable
  Job without a duplicate. The five-second interval was only a proof shortcut;
  the Watch policy remained six hours.
- Watch health after proof: `status=active`, 8 attached/active Sources, 0
  pending candidates, 0 pending vocabulary suggestions, last success at
  `2026-09-06T20:33:25Z`, next normal run approximately six hours later.
- One AARO Monitor has `last_error=monitor_error` because its public page
  returned HTTP 403 to the acquisition client. This is an explicit degraded
  Source limitation, not a hidden success claim; the other approved Sources
  remain enabled.
- The three processes were stopped after proof so the backup/restore check
  could run with no active writers. The documented start commands remain the
  unattended operating procedure.

Authenticated API management routes retain the existing session/CSRF
requirements. The public health endpoint was sufficient for process proof; no
password or session secret was written to this record.

## Acquisition proof

The operator temporarily set the NASA Monitor's `next_check_at` to the current
time using `MonitorService.update`; the configured six-hour policy was not
changed. Scheduler and worker then ran the ordinary source-targeted path.

- Successful source: NASA UAP, Source
  `src_c92eb515089d2046bdfd6571cb828361`.
- Monitor: `mon_1a8699c948d7bfe7755f1a25628007ad`.
- Monitor Job: `job_2beacc24b606c8e8597a126ca8d5224d`, status `succeeded`,
  `paid_used=false`.
- Persisted Document: `doc_ba68c9f2803bc3cf3ba5f1a2e7671212`, title `UAP - NASA
  Science`.
- Persisted DocumentVersion: `dv_9e3c5a38dec61e14a19b9e7427d8e8ac`.
- Persisted content artifact: `art_9a0cd170343a3351ddaa1aaf7314c4c0`, 13,395
  normalized text characters.
- The unchanged-duplicate behavior was not broadly certified in A2; the
  acquisition used the normal canonical URL/content-hash path and created one
  Document and one version for the first fetch.
- Negative check: the AARO Press Products Monitor produced a durable failed
  `monitor_check` Job with `AcquisitionError`, matching the observed 403.

## Backup and restore proof

Backup used the supported CLI and online SQLite backup path:

```powershell
python -m newsroom.cli backup --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --destination C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod\backups\phase29-trial-20260906.db
```

Result: `verified=true`; backup SHA-256
`C2A5F09F4EADC43CD6084077EC929B565FDAF1BD0E42237DF8023C0C0B32A9EE`.

The backup was verified, restored into the different explicit
`C:\Users\nicol\AppData\Local\Newsroom\phase29-trial-restore\prod` root, and
verified again. The restore reported schema 36, contiguous migration versions
1–36, SQLite integrity `ok`, application integrity `ok`, and preserved:

- 1 Watch;
- 8 Sources;
- 8 Monitors;
- 1 Document;
- 1 DocumentVersion;
- 1 content artifact; and
- 3 historical Jobs.

The original trial DB SHA-256 was
`C2686C79C5D3BE63178E49F7F504DCA704F5E9A2668A034041BD74ED81287073` both
before backup and after restore. The restore did not alter the original.

## Readiness gate and remaining limitations

**Unattended observation may now begin after the operator starts the API,
worker, and scheduler using the documented procedure.** The A2 substrate is
configured, isolated, recoverable, and has collected one real approved Source.
The four-week window has not been started by this setup.

Known limitations for A3:

1. AARO's public page returned 403 to the acquisition client; source-specific
   access handling and alternate official endpoints should be tested.
2. DoD and several other sources are broad page monitors rather than feeds;
   relevance, duplicate handling, and useful article retrieval need observation.
3. The natural downstream document-processing Job reached local article
   analysis and failed with `AIProviderError`; paid escalation was blocked.
   A3 should test this bounded provider-failure behavior and any local analysis
   requirements without enabling paid calls by accident.
4. This record does not evaluate evidence-span verification, Claims, Stories,
   Reports, Alerts, research automation, or Full-vs-Lite comparative value.
