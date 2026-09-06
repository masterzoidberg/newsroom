# Phase 29 UAP observation protocol

Status: official observation boundary established; four-week minimum not yet
complete. Frozen 2026-09-06 before outcome interpretation.

## Official boundary and duration

The clean A3 restore remains valid and the official observation start boundary
is preserved as:

```text
2026-09-06T21:20:48Z
```

This is the timestamp after which new runtime objects and observations belong
to the official window. It is not backdated from later output. The minimum
calendar boundary is exactly four weeks later:

```text
2026-10-04T21:20:48Z
```

The window may be extended. Four calendar weeks alone do not establish product
usefulness or a Phase 29 intelligence-value verdict.

## Baseline and runtime identity

The observation runtime is isolated from the repository:

```text
C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod
```

The verified baseline backup is:

```text
C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod\backups\phase29-observation-baseline-20260906.db
```

Before the operator processes were started, the current database SHA-256
matched that backup. Starting the scheduler changed only the expected
`scheduler_state.last_tick_at` / `updated_at` heartbeat; the backup remains
byte-verifiable and all evidence/object counts remain identical. The baseline
has schema 36, one approved Watch, eight approved Sources, eight Monitors, one
historical NASA DocumentVersion/content artifact, three historical Jobs, and no
Stories, Claims, EvidenceSpans, Living Reports, or Alerts from the A3 rehearsal.
The historical A2/A3 state remains understood: NASA acquisition succeeded, an
AARO endpoint returned HTTP 403, local analysis attempted and failed, and paid
fallback was blocked without consuming paid budget. These are pre-boundary
forensic facts, not observation outcomes.

The approved Watch is:

```text
Phase 29 UAP / UFO disclosure and sightings trial
watch_ccc9898ad4bf9cbd8787fc9331123698
top_c22007a2f9159a3fc2f69b3e3da70955
```

Do not use the developer database, repository paths, or A3 rehearsal backups
as the active observation database.

## Runtime operation

Start the three supported processes from the repository root with explicit
environment and root arguments:

```powershell
python -m newsroom.runtime api --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --host 127.0.0.1 --port 8127
python -m newsroom.runtime worker --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod --worker-id phase29-trial-worker
python -m newsroom.runtime scheduler --environment prod --root C:\Users\nicol\AppData\Local\Newsroom\phase29-trial\prod
```

Confirm `GET http://127.0.0.1:8127/api/v1/health` returns HTTP 200 before
considering the runtime up. Keep API, worker, and scheduler logs under the
dedicated runtime `logs` directory. Do not put credentials or acquired runtime
data in Git.

## Uptime, outages, and restarts

At each operator check, record UTC time, process state, health result, and any
queue/lease issue in the external operations log. An outage record includes:

- start and detection time;
- affected process and last successful health check;
- source/jobs affected;
- restart or recovery action;
- end time and recovery verification; and
- whether the interruption reduces coverage or requires an extension.

Restart is allowed for a crashed, hung, or intentionally maintained process.
Use the supported runtime commands and preserve the database. Do not restore,
upgrade, or move the database while writers are active. A Class 1 operational
restart does not reset comparability when code, Source configuration, provider,
cadence, and budget are unchanged.

## Source health

The eight approved Sources remain in the Watch unless a logged Class 2 change
is approved. AARO HTTP 403 is treated as isolated source degradation:

- retain failure telemetry and the affected Monitor;
- do not invent content or mark the acquisition successful;
- continue the other approved Sources;
- record outage duration, affected coverage, and any missed or delayed item;
- do not silently substitute an unrelated Source; and
- if an official endpoint is repaired or changed, record the old/new URL,
  timestamp, reason, commit if applicable, and comparability impact.

Broad DoD, FAA, AP, and specialist pages remain subject to relevance and human
review. A source with low yield is not silently removed because it is noisy.

## Sustainable review and observation logging

Use `docs/reviews/PHASE_29_HUMAN_USEFULNESS_LOG_TEMPLATE.md` for one row per
material object reviewed. The operator does not need to inspect every stored
object:

- Daily or at the next available operator session, review every new Alert and
  Attention item, plus every Ask answer/refusal, Report revision, and Research
  result initiated or surfaced since the prior review.
- For Stories, review every automatic assignment or correction surfaced in
  the session; if volume is high, review all corrections and a deterministic
  sample of unchanged assignments, recording the denominator.
- For low-volume surfaces, record zero rather than inventing a usefulness rate.
- Once per week, reconcile a sample of at least ten reviewed rows (or all rows
  when fewer exist) to canonical object IDs and durable telemetry.

The log must make it possible to report, with denominators where available:

- useful/not useful Attention and Alerts;
- Ask grounded-answer and refusal outcomes;
- Report/Story correction burden and false positives;
- Research attempt yield and Gap closure/change;
- source failures, missed or delayed important developments when identifiable;
- time-to-first-value and rough time saved/time-to-understanding;
- provider route, local/paid behavior, and estimated cost; and
- backup health and restore verification.

Record an observation as unavailable when the system does not measure it
honestly. Do not turn missing telemetry into a zero or a success.

## Backup and verification

Create a supported online backup at least daily after the operator review and
before any maintenance that could affect the runtime. Store it under the
dedicated `prod\backups` directory with UTC timestamp and SHA-256. Verify the
backup with the supported CLI and record schema, SQLite integrity, application
integrity, row/object counts, and hash.

At least weekly, verify one current backup by restoring to a separate explicit
`phase29-trial-restore\prod` root with all writers stopped. Never restore over
the active observation database. Record the restore result and preserve the
original database hash.

## Change-control policy

Every material change records UTC timestamp, operator, reason, exact change,
repository commit when code changed, affected window/segment, and expected
comparability impact.

### Class 1 — operational recovery

Examples: restarting a crashed process, restoring service, or retrying a
failed acquisition with unchanged configuration. Keep the same observation
segment; log downtime and impact.

### Class 2 — Source/configuration adjustment

Examples: repairing a Source URL, temporarily disabling a Source, changing
vocabulary, or changing cadence. Do not silently change the Watch. Segment
observations at the exact effective timestamp and assess whether the affected
category remains comparable. Extend the window if coverage is materially lost.

### Class 3 — product behavior change

Examples: relevance, Claim promotion, Story matching, Reports, Alerts,
provider routing, or core processing changes. Tie the change to a commit and
record before/after behavior, affected objects, and whether pre/post results
can still be compared. A bug fix does not automatically reset all four weeks,
but it does not automatically preserve comparability either. If the fix
fractures the evidence, retain the old segment and extend or start a clearly
identified new segment.

No change may be made because an emerging outcome is inconvenient.

## Provider and cost policy

Dogfood remains free/local by contract:

```text
paid_enabled = 0
paid_requests = 0
usd = 0
```

The controlled Full/Lite provider allowance is separate and is governed by the
evaluation protocol. Do not enable paid calls in the unattended Watch because
the later controlled benchmark may need a hosted provider. Any deliberate
provider/model/budget change is at least Class 2, requires an explicit log
entry, and may require segmenting or extending the observation.

## A3 retrieval-saturation observation target

Carry forward the A3 finding exactly:

> A full acquired NASA page successfully produced relevance, local analysis,
> exact evidence, and Claims, but automatic Story resolution deferred at
> `retrieval_terms_saturated`. The full downstream Story → Report → Alert
> rehearsal was completed using a truthfully labeled metadata/excerpt artifact.

During the trial, record each substantive full-page occurrence that reaches
Claims but fails to become useful Story/Report output because retrieval terms
saturate or another deterministic-local boundary dominates. Record source,
DocumentVersion, Claim/processing IDs, reason code, downstream objects created,
operator usefulness impact, and whether a correction was needed. Do not change
thresholds during this observation merely to create more Stories. Repeated
occurrence is Phase B evidence for KEEP, SIMPLIFY, CONTEXTUALIZE, DEFER, or
REMOVE; it is not a reason to rewrite this protocol.

## Inconclusive or extended trial

Extend the window and preserve the existing segment if any of the following
holds:

- event/output volume is too low for the pre-registered category or usefulness
  denominators;
- important product surfaces receive too few real examples;
- a prolonged source or runtime outage materially reduces coverage;
- a Class 2 or Class 3 change fractures comparability; or
- the clean baseline, backup, or provider/cost telemetry cannot be verified.

Do not define an arbitrary minimum number of UFO events. If evidence remains
insufficient after a documented extension, report the affected conclusion as
inconclusive.
