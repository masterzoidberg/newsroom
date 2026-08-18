# Phase 20 — Semantic Scope and Automatic Relevance

## Objective

Automatically evaluate changed DocumentVersions against the actual information
need and Monitor scope.

## Why this phase exists

The relevance cascade exists, but production Source acquisition currently does
not invoke it. Source Monitor scope ownership is also ambiguous when a Source is
being monitored for a Topic or other information need.

## Current-state gap

`candidate_text` supports a manual/unit-test path, while the production path
records `changed` with `relevant_items=0`. Approved vocabulary is persisted, but
there is no automatic changed-version scope handoff.

## Scope

- Define the canonical effective-scope owner for each processing obligation.
- Require a Source Monitor that is intended to represent an information need to
  carry an explicit Topic/information-need association or be classified as
  acquisition-only.
- Snapshot exact terms, approved vocabulary, aliases, acronyms, concepts, and
  exclusions at processing time.
- Run the deterministic `RelevanceCascade` from a processing Job.
- Persist relevant/not-relevant outcome, matched terms, score, scope version,
  and provider signal.

## Non-goals

- No real LLM provider or autonomous vocabulary expansion.
- No accepted Claims or Story/report changes.
- No silent inference of scope from Source name or URL.

## Existing components to reuse

`RelevanceCascade`, `RelevanceScope`, `_scope_for_target`, topic term approval,
`MonitorService` scope history, `AIRouter` local relevance contracts, the Phase
19 processing Job, and Phase 18 artifact access.

## Required implementation

Load and verify normalized content, load the immutable effective scope snapshot,
apply exclusions first, then exact/vocabulary/entity/concept/semantic/local
stages, and persist the result. A non-relevant version must terminate cleanly
without article analysis. A relevant version must produce a stable handoff for
Phase 21.

## Data model/migration expectations

Persist processing scope identity/version and relevance result with enough data
to reproduce the decision. Use existing monitor scope history where possible;
add a migration only if a durable processing-result record is required.

## Runtime integration

The Phase 19 worker calls relevance after loading the artifact. The result is
idempotent by DocumentVersion and scope version. It must not call the manual
`candidate_text` route or make acquisition synchronous.

## Security/privacy considerations

Keep content and scope bounded. Treat acquired text as untrusted input; do not
execute or render it. Preserve exclusion semantics and prevent a source from
silently widening a user's information need.

## Tests

- Changed version loads durable content and evaluates automatically.
- Exact, alias, acronym, concept, semantic, and exclusion paths are covered.
- Scope changes create a new reproducible scope version without mutating history.
- Manual `candidate_text` remains test-only/manual and is not required by Jobs.
- No-change, failed, irrelevant, and relevant outcomes are distinct.

## Acceptance criteria

```text
changed DocumentVersion
  → processing Job
  → durable normalized content
  → deterministic relevance
  → persisted relevant/not-relevant result
```

No manual candidate text is required in the production path.

## Live-test gate

After Phase 20, real public-source relevance canaries may run using the
deterministic/local provider. No model-generated Claims may be accepted.

## Dependencies

Phase 19 and Phase 18; scope ownership must be resolved before implementation.

## Exit criteria

Every changed version receives a reproducible automatic relevance decision tied
to an explicit information need and scope version. Phase 21 may add article
analysis and a real provider.

## Completion Record — 2026-08-18

Implemented by Kilo against the post-audit roadmap. Overall verdict: **PASS**.

### Canonical scope model (the critical design question)

There is no implicit association between a Source Monitor and an information
need in the pre-Phase-20 model: only `source` Monitors acquire, and their
scope (`_scope_for_target('source')`) was source name/slug/domain matching —
exactly what the phase forbids. The Phase 20 plan itself requires the missing
association, so it was added explicitly rather than improvised:

- The **Monitor is the canonical scope owner**. `monitors` gains an optional,
  explicitly approved information-need association (`need_type`/`need_id`,
  Migration 0017) referencing a persisted **Topic, Subject, Story, or
  Research Question** (never another Source). A Source Monitor **with** a need
  is a semantic Monitor; **without** one it is explicitly classified
  **acquisition-only**.
- Scope resolution is the existing approved path
  (`_scope_for_target` over `topic_terms`/`subject_aliases`/latest
  revision/question text) snapshotted into the existing immutable, versioned
  `monitor_scope_history`. Pending/rejected vocabulary suggestions never enter
  the snapshot (Phase 08 invariant preserved). Topic vocabulary approval and
  direct edits refresh need-based Monitors too (`refresh_topic_scopes`).
- Exclusions are first-class: approved `exclude` terms land in
  `RelevanceScope.exclusions` and are evaluated first by the cascade.
- **Historical/current scope semantics: scope-at-acquisition.** The enqueue
  (inside the acquisition write transaction) pins the Monitor's current
  approved `monitor_scope_history` version as payload `scope_version`. The
  processing worker evaluates that exact immutable snapshot, stores it in the
  decision record, and never follows later scope edits. The T0(acquire with
  scope A) → T2(edit scope to B) → T3(process) race resolves to A for that
  version; versions acquired after the edit evaluate B. This is reproducible
  and non-silent: the decision pins its scope version and full snapshot.

### Relevance pipeline

```
DocumentVersion
  → verified Phase 18 artifact (fail-closed loader)
  → evaluation text (exact normalized text; feed entries → title+summary
    extracted from the persisted metadata JSON, never URLs/JSON structure)
  → approved RelevanceScope snapshot (pinned scope_version, immutable)
  → deterministic RelevanceCascade stages:
      excluded → exact → vocabulary → entity → concept
      → semantic (local token-overlap / Jaccard approximation)
      → local classifier (LocalRelevanceProvider token overlap)
  → one canonical persisted decision (idempotent)
  → terminal processing result → STOP before article analysis
```

The existing `RelevanceCascade` was reused unchanged (it already provided the
correct staged evaluation); Phase 20 wires the persisted approved scope into
the processing job. Terminology stays accurate: the "semantic" stage is a
deterministic local token-overlap approximation, never an LLM. `paid_used`
is always `false`; no provider call occurs.

### Persistence model

Migration **0017** adds `document_version_relevance` (schema version **17**):
`id, document_version_id FK, monitor_id FK, job_id FK, scope_version, scope_json
(approved snapshot copy), relevant, stage, score, matched_terms_json, reason,
algorithm='deterministic_relevance_cascade_v1', paid_used=0, created_at`,
UNIQUE `(document_version_id, monitor_id, scope_version)`.

- Identity/idempotency: the unique tuple is the canonical decision. Retries,
  lease recovery, and explicit reruns all reuse it (select-then-insert with
  `BEGIN IMMEDIATE` + IntegrityError re-select); nothing is duplicated or
  silently overwritten; history stays auditable.
- Provenance: monitor_id, pinned scope_version, and the full approved snapshot
  copy make every decision reproducible offline.
- Rerun: terminal rerun creates a fresh job that preserves the acquisition pin
  (`rerun:` key) and references the same canonical decision.
- No article text is stored; no backfill of historical versions occurs.

### Monitor activity / cadence

- `relevant=true` (new canonical record only) → one `relevant_change` activity
  row (`relevant_items=1`) + `monitor.last_result='relevant_change'` + next
  check at the policy **minimum cadence**, all inside the same write
  transaction as the decision (atomic, retry-safe).
- `relevant=false` → no activity write; the acquisition `changed` row remains
  the truthful outcome and cadence stays unchanged (cadence-neutral).
- `not_applicable` → no activity write.
- Regression proven: acquisition-level `changed` alone can never emit
  `relevant_change`; relevant_change/cadence acceleration only ever follow a
  real relevance decision.

### Failure semantics

- Missing scope / empty approved scope (no positive terms) → terminal
  `DomainValidation` (COULD NOT EVALUATE, never `relevant=false`).
- Missing pinned version, malformed persisted snapshot → terminal.
- Missing Monitor provenance → explicit `not_applicable` (succeeded, no
  decision); invalid provenance → terminal rejection.
- Corrupt/legacy artifact → terminal via the Phase 18 fail-closed loader
  before any relevance work.
- Transient SQLite → existing bounded retry/recovery.

### Tests / results

New `tests/test_phase20_relevance_automation.py` (28 tests) covers every task
requirement: relevant HTML, non-relevant HTML, feed entries through the same
pipeline, no candidate_text, exact/alias/acronym participation, pending/
rejected non-participation, exclusion suppression, empty scope truthful
failure, missing vs invalid provenance, corrupt artifact, persisted result
survives reopen, retry/recovery and rerun idempotency, scope-at-acquisition
mutation semantics, relevant_change/cadence behavior (including the
acquisition-changed regression), local-only/zero-paid usage, acquisition-only
monitors, production composition (A relevant + B not), process-restart
acceptance, the UAP/UFO approved-vocabulary fixture (relevant / unrelated /
exclusion), and migration 0017 upgrade preserving schema-16 data.

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_phase20_relevance_automation.py` | **28 passed** |
| `python -m pytest -q tests/test_phase19_document_processing_jobs.py` | **24 passed** |
| `python -m pytest -q tests/test_phase18_content_artifacts.py` | **20 passed** |
| `python -m pytest -q tests/test_phase08_monitors.py` | **25 passed** |
| `python -m pytest -q tests/test_monitor_runtime_acceptance.py` | **14 passed** |
| `python -m pytest -q tests/test_phase06_acquisition.py` | **15 passed** |
| `python -m pytest -q tests/test_phase07_jobs.py` | **12 passed** |
| `python -m pytest -q tests/test_phase02_foundation.py` | **7 passed** |
| jobs/RQ (research_question_worker, coalescing, api, dedupe) | passed |
| `python -m pytest --collect-only` | **455 collected** (was 427) |
| full backend suite run 1 | **455 passed, 37 warnings in 72.99s** |
| full backend suite run 2 | **455 passed, 37 warnings in 70.92s** |
| `python -m compileall -q newsroom scripts tests` | exit 0 |
| `git diff --check` | pass (pre-existing LF/CRLF advisory only) |
| frontend checks | not run — no frontend or shared response-shape change; only additive optional `need_type`/`need_id` fields on the Monitor create/patch models |

### UAP/UFO fixture result

Approved-terms fixture inserted through the current approved-scope path
(`create_vocabulary` for UFO / unidentified flying object / unidentified
anomalous phenomena / flying saucer / non-human intelligence (related concept)
/ hoax (exclude), plus `ScopeSuggestionService` approval for the `UAP` and
`NHI` acronyms). Deterministic results through the full pipeline:

- article containing **UAP** → relevant=true, stage `vocabulary`,
  matched `["UAP"]`; monitor `relevant_change`.
- unrelated article → relevant=false (stage `none`); monitor stays `changed`.
- ambiguity/exclusion article ("UFO photograph is a hoax") → relevant=false,
  stage `excluded`, matched `["hoax"]`; exclusion won over the positive term.

### Live smoke

Performed once offline-bound: real RSS (NPR feed) + real HTML
(`example.com`) with an explicitly configured approved relevance scope using
the production Scheduler → Job → Worker composition; real acquisition →
artifact → processing Job → automatic local relevance → persisted decision
(truthful relevant/not-relevant depending on content; one arbitrary live
source classified not-relevant). Zero remote AI calls, `paid_used=false`
everywhere. Result: PASS.

### Remaining known limitations

- Only `source` Monitors acquire; other target types remain
  `unsupported_target` (unchanged, out of Phase 20 scope).
- Scope edges are snapped to the existing monitor refresh hooks (Topic
  vocabulary approval/edits). Direct Subject alias / Story revision /
  Research Question edits do not currently auto-refresh snapshots (unchanged
  pre-existing Phase 08 behavior); re-snapshotting happens on Monitor
  create/update.
- The "semantic" stage is token-overlap approximation; real model-backed
  analysis is Phase 21.
- Relevance decisions are one per (version, monitor, scope_version); a
  cross-monitor or cross-need aggregation view is future work.
- No retention policy for `document_version_relevance` rows yet (future
  operator work).
