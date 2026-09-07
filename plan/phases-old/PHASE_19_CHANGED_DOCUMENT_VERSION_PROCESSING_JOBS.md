# Phase 19 — Changed DocumentVersion Processing Jobs

## Objective

Create the durable orchestration primitive that connects acquisition to
downstream processing without making MonitorExecutionService synchronous or
AI-coupled.

## Why this phase exists

The current monitor correctly records a changed version and returns. There is no
durable obligation representing the work that should process that version.

## Current-state gap

The production handler registry contains `monitor_check` and
`research_question`, but no DocumentVersion processing job. A changed version
has no restart-safe downstream lifecycle.

## Scope

- Define the explicit job type `document_version_process`.
- Make `document_version_id` the canonical owner and carry Source, Document,
  Monitor, and effective-scope traceability.
- Add idempotent enqueue/coalescing and explicit rerun semantics.
- Add retry, lease recovery, cancellation, budgets, and terminal outcomes.
- Register the handler in the production runtime.
- Add completion/recovery hooks only where state reconciliation requires them.
- Implement a deterministic no-op/test processor only.

## Non-goals

- No relevance, AI provider, semantic extraction, accepted Claims, Story
  updates, Reports, or alerts.
- No synchronous processing inside the acquisition transaction.
- No arbitrary request-controlled handler execution.

## Existing components to reuse

`JobService`, `_active_monitor_check_id_tx`, `WorkerProcess`,
`merge_handlers`, `compose_completion_hooks`, `MonitorExecutionService`,
`runtime.build_worker_handlers`, and the existing budget/recovery patterns.

## Required implementation

When acquisition commits a new or changed DocumentVersion, create at most one
active processing obligation using a stable idempotency key derived from the
version. The enqueue must be transactionally linked to the acquisition outcome
or use a recovery-safe outbox/hand-off mechanism. The no-op processor must load
and verify the Phase 18 artifact and persist a lifecycle result.

## Data model/migration expectations

Use the existing Jobs schema where possible. Add only the ownership/index/state
fields required to query processing obligations by DocumentVersion and status.
Document processing records should preserve job ID, version ID, monitor/source
context, status, attempt, timestamps, and failure cause.

## Runtime integration

The Source Monitor remains responsible for acquisition and truthful monitor
activity. A successful changed acquisition hands off to the durable worker. A
no-change or failed acquisition must not create a processing obligation.

## Security/privacy considerations

Require canonical ownership validation, bounded payloads, allow-listed handler
registration, budget reservation, and safe artifact access. Do not place article
content in Job payload JSON.

## Tests

- Source change creates exactly one processing Job.
- Repeated scheduler ticks do not duplicate it.
- A completed version does not reprocess unless explicitly rerun.
- Lease expiry, retry, cancellation, and worker restart preserve consistency.
- Unknown job types fail safely.
- Monitor and processing failures remain separately observable.

## Acceptance criteria

Production-composition test proves:

```text
Source change → one DocumentVersion → one durable processing Job
               → persisted processing lifecycle
```

No manual API call may be required after Monitor setup.

## Live-test gate

After Phase 19, public-source canaries may verify processing-job creation and
restart behavior, but the processor must remain deterministic and non-semantic.

## Dependencies

Phase 17 baseline and Phase 18 durable content artifacts.

## Exit criteria

Every changed DocumentVersion has a durable, idempotent, restart-safe processing
obligation and a registered worker path. Phase 20 may add automatic relevance.

## Completion Record — 2026-08-18

Implemented by Kilo against the post-audit roadmap. Overall verdict: **PASS**.

### Job type and registration path

Job type: `document_version_process` (`DOCUMENT_VERSION_PROCESS_JOB_TYPE` in
`newsroom/jobs.py`). Registered centrally in the production composition:

- `runtime.build_worker_handlers()` adds
  `DocumentProcessingExecutionService(db_path).handlers()` to the
  `merge_handlers` set;
- `runtime.build_worker_queue()` chains the DocumentVersion rerun factory
  through the new `compose_rerun_factories` helper
  (`document_version_processing_rerun_factory`, registered after
  `research_job_rerun_factory`);
- unknown job types still fail safely (`unknown_job_type`, terminal) and no
  parallel queue architecture was introduced.

### Ownership model

- Canonical owner: the persisted `DocumentVersion` row.
- `jobs.document_version_id` (Migration 0016, `REFERENCES document_versions(id)`)
  is the canonical ownership column — the FK proves the version exists at
  insert time, and an index `(document_version_id, status)` supports
  active-work coalescing and obligation queries.
- Payload carries only canonical IDs for traceability: `document_version_id`,
  `document_id`, `source_id`, originating `monitor_id`. Mutable Source/Monitor
  metadata is never duplicated; handlers resolve persisted rows through
  services.
- `jobs.monitor_id` is deliberately NOT overloaded: it remains the
  monitor_check execution ownership column (coalescing, policy budget scoping,
  monitor completion hooks). Monitor provenance for processing obligations
  lives in payload JSON only. The processing handler validates every payload
  ID against the persisted DocumentVersion/Document/Source/Monitor rows and
  rejects conflicting caller-supplied IDs.
- Eligibility: newly-created/changed DocumentVersions (HTML/text and every new
  feed entry) create obligations; HTTP 304, unchanged re-fetch, acquisition
  error, and disabled Monitor create none.

### Durable handoff (atomicity / crash gap)

Same-transaction enqueue (design A). `enqueue_document_version_processing_tx`
runs inside the exact `BEGIN IMMEDIATE` write transaction that commits the
DocumentVersion and its Phase 18 artifact (`_persist_document` /
`_persist_feed_entries` in `newsroom/acquisition.py`), so a crash between
version commit and obligation commit is impossible — both commit or neither
commits. The crash-gap test injects an obligation-creation failure and proves
the whole version/artifact/event transaction rolls back; no commit state can
retain an eligible changed version while losing its processing obligation.

### Idempotency / coalescing

- Automatic scheduling key: `document:{version_id}` (UNIQUE). An existing
  obligation for the key — queued, running, succeeded, failed, or
  cancelled — blocks any further automatic obligation for that version.
- `JobService.enqueue` additionally rejects any second ACTIVE (queued/running)
  obligation per version regardless of idempotency key
  (`_active_document_version_process_id_tx` inside the enqueue write
  transaction), so API/direct/rerun paths cannot create concurrent duplicate
  work. Transaction serialization (`BEGIN IMMEDIATE`) makes this TOCTOU-free;
  the concurrent two-thread test produces exactly one active obligation.
- Autonomously re-acquiring identical content produces no new version and
  therefore no new obligation; processed versions are never automatically
  reprocessed.

### Rerun behavior

Generic JobService rerun semantics with a domain rerun factory:
- Only terminal obligations may be rerun (existing rule);
- rerun while an ACTIVE processing obligation exists for the same version is
  refused (`JobConflict`) by the central enqueue validation;
- rerun of a terminal obligation creates a fresh obligation (new `rerun:` key)
  preserving canonical `document_version_id` ownership; the historical
  terminal job and its attempts are never mutated;
- rerun of a job whose version no longer exists is refused truthfully.

### Processing handler (what it does and does not do)

`DocumentProcessingExecutionService.handle`:
1. resolves the canonical DocumentVersion (via `jobs.document_version_id`
   + payload) and validates persisted ownership IDs;
2. loads the hash-verified Phase 18 artifact via
   `ContentArtifactService.load_normalized_content`;
3. returns a bounded deterministic result (version/document/source IDs,
   artifact_id, content_hash, normalized_content_hash, content_kind,
   norm_version, content_length, processing_status="completed") persisted in
   `jobs.result_json`;
4. terminalizes as succeeded.

It does NOT invoke RelevanceCascade, AIRouter, extraction, Evidence/Claims,
Story evolution, Living Reports/Alert services, budgets beyond the generic
zero-reservation queue accounting, or any remote re-fetch.

### Artifact consumption

Only the canonical Phase-18 loader path is used: `DocumentVersion →
ContentArtifactService.load_normalized_content → hash-verified text`.
Corruption is fail-closed: missing artifact → `ArtifactNotFound`; hash mismatch
→ `ArtifactHashMismatch`; length mismatch → `ArtifactLengthMismatch`; all
terminal. Legacy pre-Phase-18 artifact-less versions fail terminally and
truthfully (`LegacyVersionWithoutArtifact`) — no fabricated content, no
re-fetch.

### Failure / recovery / cancellation

- Terminal failures (no bounded retry): missing version (`DomainNotFound`),
  legacy artifact-less version, artifact missing/corrupt, ownership conflicts.
- Retryable: transient SQLite conditions are mapped to
  `RetryableJobFailure` (existing bounded retry/backoff).
- Lease expiry/recovery/restart: the repaired generic JobService machinery
  (proved by queue-survival and lease-recovery tests); no independent lease
  system.
- Cancellation: generic behavior; cancelled obligations never report a
  processing success and never mutate the immutable version/artifact.

### Schema / migration

Migration **0016**; schema version becomes **16**. Additive, preserves
schema-15 data unchanged:
- `ALTER TABLE jobs ADD COLUMN document_version_id TEXT REFERENCES
  document_versions(id)`;
- `ALTER TABLE jobs ADD COLUMN result_json TEXT`;
- `CREATE INDEX jobs_document_version_idx ON jobs(document_version_id, status)`.

Rationale: the canonical ownership column + index are required to query
processing obligations by DocumentVersion/status (the phase's data-model
expectation) and the FK is the strongest "no nonexistent version" guarantee;
`result_json` durably persists the deterministic processing result, which the
previous job model could not represent (outcomes only reached in-memory
completion-hook context). Phase 18 artifact semantics are untouched.

### Tests

`tests/test_phase19_document_processing_jobs.py` — 24 tests covering: changed
HTML → exactly one obligation (with canonical payload provenance); feed entries
→ one obligation per entry; HTTP 304 and unchanged feed → no new obligations;
acquisition error and disabled Monitor → none; handler resolve + verified
artifact + deterministic result; handler invokes no relevance/AI/Evidence/
Story/Report/Alert; autonomous duplicate enqueue coalesced; concurrent enqueue
→ one active obligation; direct enqueue cannot bypass canonical-ownership or
active-work validation; rerun rejected while active / fresh obligation on
terminal rerun; missing version, legacy artifact-less version, and corrupt
artifact terminate truthfully; queue survives process-object restart; lease
recovery; cancellation semantics; monitor_check coalescing unchanged;
Research Question jobs unchanged; production-composition acceptance
(Scheduler → monitor_check → Worker → Acquisition → version/artifact →
processing Job → fresh Worker → succeeded processing Job, with exact persisted
counts 1/1/1/1 and result referencing the exact version/artifact); crash-gap
acceptance (injected obligation failure rolls back the whole acquisition
transaction).

Test expectations updated for schema 16: phase02 foundation, phase06
acquisition, phase07 jobs, phase08 monitors (incl. the 14→16 upgrade test),
phase15 hardening, phase18 artifacts (incl. the 14→16 upgrade preserving
historical rows). `test_research_question_worker.py` handler-coverage and
composition assertions now include the third production job family and the
composed rerun factory. `test_phase08_monitors.py` budget-exhaustion test
drains the Phase-19 obligation before asserting claim-time exhaustion.

### Commands and exact results

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_phase19_document_processing_jobs.py` | **24 passed** |
| `python -m pytest -q tests/test_phase18_content_artifacts.py` | **20 passed** |
| `python -m pytest -q tests/test_monitor_runtime_acceptance.py` | **14 passed** |
| `python -m pytest -q tests/test_phase06_acquisition.py` | **15 passed** |
| `python -m pytest -q tests/test_phase07_jobs.py` | **12 passed** |
| `python -m pytest -q tests/test_phase02_foundation.py` | **7 passed** |
| `python -m pytest -q tests/test_phase08_monitors.py` | **25 passed** |
| `python -m pytest -q tests/test_phase15_hardening_operations.py` | passed |
| `python -m pytest --collect-only -q` | **427 collected** |
| full backend suite run 1 | **427 passed, 37 warnings** |
| full backend suite run 2 | **427 passed, 37 warnings** |
| `python -m compileall -q newsroom scripts tests` | exit 0 |
| frontend typecheck/build | not run — no frontend or shared API contract change |
| `git diff --check` | pass (pre-existing LF/CRLF advisory only) |

Frontend checks omitted: the only API surface change is an additive optional
`document_version_id` field on the Job create model; no response shape or
frontend workflow changed.

### Live smoke

Performed after offline acceptance, one bounded real-source canary (details in
the final Phase 19 report): real RSS acquisition → DocumentVersion/artifact →
durable `document_version_process` Job → processing success. No relevance or
AI. Result: PASS.

### Remaining known limitations

- Legacy pre-Phase-18 versions terminate truthfully as unsupported; no backfill
  mechanism exists (by design).
- `jobs.result_json` is write-once at job completion; a rerun creates a new
  obligation row rather than revising the historical result.
- Processing obligations are only automatically created by the acquisition
  path; the manual EvidenceService fixture path (metadata-only versions
  without artifacts) intentionally creates none.
- No retention policy for historical obligations/artifacts yet (future
  operator work).
