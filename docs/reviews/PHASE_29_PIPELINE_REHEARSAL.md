# Phase 29 automatic pipeline rehearsal

Date: 2026-09-06
Scope: A3 — installed automatic evidence pipeline rehearsal for the Phase 29 UAP / UFO Watch
Verdict: **ready for evaluation-procedure freeze and observation start**

This record covers the pre-observation rehearsal only. It does not start the
four-week observation window, run Full-vs-Lite scoring, or establish the
Phase 29 intelligence-value verdict.

## Repository identity

- Branch: `main`.
- Starting HEAD: `6fefa65441087fc2ba52536ab9741526e0d757be`.
- Final HEAD: recorded in the completion response after the bounded A3 commit.
- Starting HEAD is based on the accepted Phase 29 baseline
  `e0d626cf88b06e1aa3b7a0af2b41558e7662932a`.
- Schema: 36, contiguous migrations 1–36.
- Pre-existing unrelated worktree state was preserved: deleted
  `plan/phases/` files, `.kilo/`, the Phase 29.6 ZIP, planning/review files,
  and `plan/phases-old/` and `plan/phases-v2/` artifacts were not staged or
  changed.

## Runtime identity and execution map

The rehearsal used the dedicated runtime outside the repository:

| Item | Value |
|---|---|
| Runtime root | `C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod` |
| Database | `C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod\data\newsroom.db` |
| Approved Watch | `watch_ccc9898ad4bf9cbd8787fc9331123698` |
| Topic | `top_c22007a2f9159a3fc2f69b3e3da70955` |
| NASA Source | `src_c92eb515089d2046bdfd6571cb828361` |
| NASA Monitor | `mon_1a8699c948d7bfe7755f1a25628007ad` |
| Paid routing | disabled; global lifetime caps remain `paid_requests=0`, `usd=0.0` |

The installed execution map observed in the runtime was:

```text
SchedulerProcess
  -> monitor_check Job
  -> MonitorExecutionService
  -> AcquisitionService
  -> Document / DocumentVersion / ContentArtifact
  -> document_version_process Job
  -> relevance decision
  -> ArticleAnalysisService / AIRouter
  -> ArticleAnalysis
  -> verified EvidenceSpan + Claim promotion
  -> automatic_story_stage Job
  -> automatic_report_stage Job
  -> automatic_alert_stage Job
```

Each queue boundary persisted an idempotency key. Completion hooks created the
next stage only after the prior stage succeeded. The ordinary API, worker, and
scheduler processes were started against the exact runtime root during the
rehearsal; no runtime database was copied into the repository.

## Reproduced A2 failure

The A2 NASA page was the exact reproduction target:

- Document: `doc_ba68c9f2803bc3cf3ba5f1a2e7671212`.
- DocumentVersion: `dv_9e3c5a38dec61e14a19b9e7427d8e8ac`.
- Content artifact: `art_9a0cd170343a3351ddaa1aaf7314c4c0`.
- Artifact: `visible_text`, `artifact_norm_v1`, 13,395 normalized characters.
- Relevance: `rel_ef4b7da3d33a08466e026ff3fe497066`, `relevant=true`, exact
  `UAP` match, score `1.0`.
- Processing Job: `job_49d8caa76fd0e27ed6157525024e78d1`.
- Job result: `failed`, one attempt, `AIProviderError`; no downstream
  ArticleAnalysis, EvidenceSpan, or Claim had been persisted at failure time.

`NEWSROOM_ANALYSIS_PROVIDER` was unset. The requested and effective normal
route was the deterministic local `LocalArticleAnalysisProvider` with model
`local`. The router recorded a second attempted route as
`provider=unavailable`, `request_type=ai:paid`, `status=blocked`,
`error_code=paid_disabled`, `escalation_reason=local_failure`. No paid call
occurred.

The direct provider reproduction against the exact artifact failed
deterministically with:

```text
ValidationError: ArticleAnalysisOutput.entities
List should have at most 100 items after validation, not 444
```

The local provider collected capitalized-word entity candidates without
stopping at the already-declared schema maximum. This was an application code
defect, not a provider-routing defect, paid-provider requirement, or malformed
artifact.

## Implementation changes

Two demonstrated defects were corrected with focused tests:

- `newsroom/ai.py`: stop local entity extraction at the
  `ArticleAnalysisOutput.entities` maximum of 100. This keeps broad real pages
  inside the existing structured-output contract.
- `newsroom/jobs.py`: blocked paid telemetry is not paid usage. The budget
  ledger now reads the persisted outcome and returns zero usage for
  `status=blocked` before counting a paid request. This preserves the zero
  paid-request cap without allowing a refused paid fallback to poison later
  zero-cost local work.
- `tests/test_phase21_article_analysis.py`: regression test for broad-page
  local entity bounding and Pydantic revalidation.
- `tests/test_phase07_jobs.py`: regression test proving blocked paid telemetry
  does not consume a zero-paid-request cap for a zero-cost job.

The first corrected rerun exposed the budget-accounting defect in the real
runtime: `job_ecca09150d3cc1e6d6a69b9b538463a4` was refused at reservation with
`failure_cause=budget_exhausted`, before the document handler ran. After the
budget fix, rerunning the same failed work created
`job_f7e0fda91bb139af0d0d634a185454c4`, which completed successfully through
analysis and Claim promotion with no paid usage.

## Real installed positive paths

### Full acquired NASA page: body, analysis, evidence, and truthful deferral

The repaired installed worker processed the real NASA page above:

- Successful rerun Job: `job_f7e0fda91bb139af0d0d634a185454c4`.
- Analysis: `ana_2ce75ed994657de83c87160cb9422bb8`, provider `local`, model
  `local`, paid `false`, exact artifact/version hash, 13,395 analyzed
  characters, `truncated=false`.
- Verified promotions: 10; each produced an exact EvidenceSpan and supported
  Claim. Example Claim: `claim_b4b8c36ea821e2c76d379be82e548c7d`, with
  EvidenceSpan `span_9e0010dff11dea197290b06c3e7a6e86`.
- Automatic Story-stage Jobs all completed safely as `stage_status=deferred`
  with `reason_code=retrieval_terms_saturated`. No Story, Report, or Alert was
  fabricated from the page's navigation-heavy entity set.

This is the expected bounded behavior for the deterministic local provider on
this broad page: the content advanced through relevance, analysis, exact
evidence, and Claims, then stopped at a saturated Story retrieval boundary.

### Qualifying same-Source metadata result: Story, Report, and Alert

To exercise the installed downstream stages without manufacturing database
rows, a small real response from the already approved NASA host was acquired
through the ordinary `AcquisitionService` and processed by the ordinary worker.
It was deliberately recorded as metadata-only: the DocumentVersion is
`content_kind=excerpt`, the artifact is `fallback_text`, and the exact 78-byte
artifact contains a NASA UAP search-result title rather than an article body.

The first metadata result established the Story:

```text
Source       src_c92eb515089d2046bdfd6571cb828361
Monitor      mon_1a8699c948d7bfe7755f1a25628007ad
Document     doc_35028a2cea9b22c733066d55800c0b80
Version      dv_ccf6e5662da21b075c972ba47bf05304
Artifact     art_e1115d301329b3ebced3af325356f8cc
Relevance    rel_e78205fd8edde58f1a397ab9bc28ec98 (exact UAP, score 1.0)
Analysis     ana_477b2589713a91fc690db4ef41a9cd89 (local/local, paid=false)
Evidence     span_06d5167b9f7f71c80d766fdb12840193
Claim        claim_d14ad699696c03fc1a3db1ccf1db90aa
Promotion    promo_4cd9e2360bd63e01a8d4c40352d51344
Story        st_215577a622bd30d4e9884b650916a2ce
Story Job    job_bc532891264161a1e7286d654d03fa87
Report       report_754c1032f00a59a421d1056d095c908a
Report rev   rptrev_b0a46af9bc998981bd1182d2cf2b34c0
Report Job   job_86aae213a333b88f8ba6d6c913c4d1f8
```

The same-source second result was new content about the same UAP search result
and matched the existing Story rather than creating a second Story:

- DocumentVersion: `dv_6a3fe60bf3065bbada3976d3fd7eef03`.
- Artifact: `art_a320bd784944b422e6c26d58077cf330`.
- Analysis: `ana_43384155b41fb85c0e2cbe62139d6b0d`.
- EvidenceSpan: `span_6d484d0f30efc6f78f32ebccc3097fa8`.
- Claim: `claim_74c0ddb7c2c9c5dce3f20674aea53e2b`.
- Promotion: `promo_2848b97d63e0901a81e8f4a8c0309ea1`.
- Story-stage Job: `job_9fbc94b09b799aa4c015861c454b40aa`,
  `story_resolution=matched_existing`, `time_compatible=true`.
- Report revision: `rptrev_91e01c919bab47f723dab99d49470cd9`, material change
  caused by `new_primary_evidence`.
- Alert rule: `alertrule_b6c060f3a5f2f49d541bb5eccf42d4cb`, created through
  `AlertService` for this rehearsal Story.
- Alert-stage Job: `job_ee4cbaf38ae56a439d65ae737a58b422`.
- Alert: `alert_e3d9101a20f6c78bde0dfcf56a8e6587`, exact cause references the
  Claim, EvidenceSpan, Document, Story, Report revision, and cause ID
  `cause_ba7af40a23f11991a49795ef11c79a8f`.
- In-app delivery: `delivery_ed6f0fb564e71d454971f4264d3bc141`, status `sent`,
  one attempt.

The first report-stage run had no matching alert rule and correctly produced
`reason_code=no_active_rule_matched`; the later configured rule produced one
alert. This proves both the no-noise and warranted-alert branches.

## Negative and failure paths

- **Irrelevant/weak content:** approved NASA-host search result
  `dv_a15ed97e46f7d4aaac5342996e6d0908`, artifact
  `art_2495c3303287e54a5bbf22d78aadc281`, Job
  `job_5daf32e57a382a61f0955d477fec5787` completed acquisition and relevance
  with `relevant=false`, `matched_terms=[]`, `stage=none`, score `0.75`.
  No ArticleAnalysis, EvidenceSpan, Claim, Story, Report, or Alert was
  created.
- **Unchanged content:** reacquiring the exact metadata URL produced
  `outcome=unchanged` in event `acq_3b95f9400a64537b616a7ba7b2eeb02f` for the
  existing DocumentVersion `dv_ccf6e5662da21b075c972ba47bf05304`. Counts for
  Documents, Versions, analyses, EvidenceSpans, Claims, Stories, Report
  revisions, and Alerts were unchanged.
- **Acquisition failure:** AARO remained isolated at
  `job_35501e0280f013efe8792cf884c37600`, `AcquisitionError`, HTTP 403. Other
  source work continued; the NASA positive path was unaffected.
- **Provider failure:** the historical A2 `job_49d8caa76fd0e27ed6157525024e78d1`
  retained a durable `AIProviderError` and did not fabricate downstream
  evidence. The repair was verified by a bounded rerun rather than by enabling
  paid fallback.
- **Budget refusal:** paid routing remained disabled and the global caps
  remained zero. The blocked paid telemetry was persisted as
  `provider=unavailable`, `status=blocked`, `error_code=paid_disabled`; no
  paid provider call was made. The temporary `budget_exhausted` refusal of the
  first rerun exposed the accounting defect and was corrected with a focused
  test.

## Restart, retry, and duplicate rehearsal

- The API, worker, and scheduler were stopped and restarted across the A2
  failure, repaired rerun, downstream stage work, and negative-path work.
- A supported rerun of the qualifying document Job was
  `job_4573a5f7f4bd812686d305c8b2fedf7f`; it reused analysis
  `ana_43384155b41fb85c0e2cbe62139d6b0d` and did not increase downstream
  object counts.
- A controlled crash boundary claimed `job_0dfed19631ecc388af5adc38134aa579`
  and left it running. `JobService.recover_expired` moved it to queued with
  `failure_cause=lease_expired`; a restarted worker identity reclaimed it as
  attempt 2 and completed it successfully. The handler reused the existing
  analysis and one promotion; no duplicate Story, Report revision, or Alert
  resulted.
- The same underlying metadata result reacquired unchanged produced no new
  DocumentVersion. New metadata about the same Story produced one additional
  Claim and one material Report revision, not a duplicate Story.

## Provenance audit

- The full NASA page used the persisted `visible_text_v1` artifact tied to
  `dv_9e3c5a38dec61e14a19b9e7427d8e8ac`; analysis recorded the same artifact
  ID and normalized content hash, with 13,395 input/analyzed characters.
- The metadata positive path is explicitly not claimed as an article body:
  its DocumentVersion is `excerpt` and its artifact is `fallback_text`.
- Evidence spans were created by exact analyzed-slice verification. For the
  positive Story path, `span_06d5167b9f7f71c80d766fdb12840193` resolves to
  codepoint offsets `0;78` in `art_e1115d301329b3ebced3af325356f8cc` and its
  excerpt exactly matches the artifact text.
- The second Report revision audit passed with no unsupported propositions or
  unsupported changes. Its exact-cause Alert references the corresponding
  Claim, EvidenceSpan, Document, Story, and Report revision.
- The restored baseline database passed both SQLite and application integrity
  checks after rehearsal.

## Runtime cleanliness and observation boundary

All rehearsal state was preserved in verified external backups:

- `...\backups\phase29-a3-rehearsal-final-20260906.db` contains the complete
  A3 evidence and was verified before restoration.
- The original trial runtime was then restored from the verified
  `...\backups\phase29-a3-prechange-20260906.db`, preserving the approved
  Watch, 8 Sources, 8 Monitors, the original NASA acquisition, and schema 36.
- A post-restore verified baseline backup is
  `...\backups\phase29-observation-baseline-20260906.db`.

The exact future observation boundary is `2026-09-06T21:20:48Z`. The restored
runtime has one historical A2 DocumentVersion and its failure telemetry, but
zero ArticleAnalyses, EvidenceSpans, Claims, Stories, Reports, Report
revisions, Alerts, or Alert deliveries. Future observation records must be
identified by timestamps at or after this boundary; the A3 rehearsal backup is
the forensic record for all pre-boundary downstream objects.

## Verification performed

Focused defect workflow:

```text
python -m pytest -q tests/test_phase21_article_analysis.py -k "deterministic_local_provider"
  2 passed
ruff check newsroom/ai.py tests/test_phase21_article_analysis.py
  All checks passed
python -m pytest -q tests/test_phase07_jobs.py -k "blocked_paid_telemetry or enqueue_is_idempotent or expired_lease"
  3 passed
python -m pytest -q tests/test_phase21_article_analysis.py -k "deterministic_local_provider or budget_exhaustion or provider_disabled or restart_acceptance"
  5 passed
ruff check newsroom/jobs.py tests/test_phase07_jobs.py newsroom/ai.py tests/test_phase21_article_analysis.py
  All checks passed
```

The full repository suite collected 840 tests and passed with exit code 0.
The broad A3-focused suite covering content artifacts, processing jobs,
article analysis, evidence promotion, Story/Report/Alert automation, jobs,
temporal semantics, and Phase 29 closed-loop behavior passed at 100%:

```text
python -m pytest -q tests/test_phase18_content_artifacts.py tests/test_phase19_document_processing_jobs.py tests/test_phase21_article_analysis.py tests/test_phase21h_hardening.py tests/test_phase22_1_hardening.py tests/test_phase22_3_trust_boundary.py tests/test_phase22_evidence_promotion.py tests/test_phase23a_story_resolution.py tests/test_phase23b_story_automation.py tests/test_phase23c_report_automation.py tests/test_phase23d_alert_automation.py tests/test_phase23e_compatibility.py tests/test_phase24_intelligent_monitoring.py tests/test_phase07_jobs.py tests/test_phase09_story_evolution.py tests/test_phase11_reports_briefings_alerts.py tests/test_phase29_closed_loop.py tests/test_phase29_temporal.py tests/test_phase296_story_time_semantics.py
  exit 0; 100% passed; only existing httpx deprecation warnings
```

Runtime/operator checks passed:

```text
python -m newsroom.cli backup ... --destination ...\phase29-a3-rehearsal-final-20260906.db
  verified=true
python -m newsroom.cli verify ... --database ...\phase29-a3-prechange-20260906.db
  ok=true; schema_version=36; integrity=ok
python -m newsroom.cli restore ... --backup ...\phase29-a3-prechange-20260906.db
  verified=true
python -m newsroom.cli status --environment prod --root ...
  versions 1–36
python -m newsroom.cli integrity --environment prod --root ...
  ok=true; issues=[]
python -m newsroom.cli backup ... --destination ...\phase29-observation-baseline-20260906.db
  verified=true
python -m compileall -q newsroom tests
  exit 0
python -m pytest -q
  exit 0; 840 tests passed; existing httpx deprecation warnings only
ruff check newsroom tests
  All checks passed
python -m newsroom.evals validate
  corpus VALID: 46 case(s)
python -m newsroom.evals lite-contract
  Lite contract VALID: newsroom-lite-20q-v1; 20 questions; results not run
git diff --check
  exit 0
```

No frontend files changed, so frontend lint/typecheck/build was not applicable.

## Remaining gates

1. Freeze the comparative Full-vs-Lite evaluation procedure.
2. Confirm the observation operator procedure and use the exact boundary above.
3. Start the four-week Phase 29 observation window.

The remaining gates belong to observation/evaluation. The intelligence-value
verdict is intentionally not made in this rehearsal.
