# Phase 18 — Durable Normalized Content Artifact

## Objective

Persist the exact bounded normalized content represented by each acquired
DocumentVersion so downstream workers can reload and verify immutable source
material.

## Why this phase exists

Acquisition currently extracts visible text in memory and persists hashes and
metadata only. This prevents reliable downstream processing and prevents
EvidenceSpan membership verification.

## Current-state gap

`AcquisitionService` returns an in-memory extracted document, while
`document_versions.normalized_json` contains metadata such as hash, title, and
text length. A worker cannot reload the exact normalized text from a version.

## Scope

- Define the raw-versus-normalized content policy.
- Choose a bounded local artifact representation: SQLite, a content-addressed
  filesystem store, or another local-first store.
- Persist visible normalized text with content type, hash, length, and immutable
  provenance.
- Associate exactly one verified artifact with a DocumentVersion.
- Reuse artifacts when content hashes match.
- Expose a worker-safe read/verify operation.

## Non-goals

- No relevance or AI calls.
- No automatic Claims, Stories, Reports, or alerts.
- No arbitrary raw HTML archive or unbounded crawler cache.
- No distributed object storage.

## Existing components to reuse

`AcquisitionService._extract_response`, `SafeHTMLExtractor`, content hashing,
`DocumentVersion`, `storage.py`, backup/restore in `operations.py`, and the
existing acquisition provenance events.

## Required implementation

Define a stable artifact identity and lifecycle. On successful acquisition,
normalize visible content once, hash the exact stored representation, and write
the artifact and DocumentVersion reference transactionally. A reload must verify
the stored bytes/text against the recorded hash and fail closed on mismatch.

## Data model/migration expectations

A migration is expected only if the existing schema cannot represent an
immutable artifact reference safely. The logical model must include artifact
identity, content hash, content kind, byte/character length, storage location or
payload, created time, and retention eligibility. Existing versions must remain
readable and historical metadata-only versions must be handled explicitly.

## Runtime integration

`AcquisitionService.acquire_document()` and feed persistence create or reuse the
artifact. `MonitorExecutionService` remains acquisition-only. No processing Job
is created in this phase.

## Security/privacy considerations

Keep response-size and normalized-text bounds. Do not persist active HTML,
scripts, embedded content, credentials, cookies, or arbitrary response bytes.
Ensure backups, exports, retention, and logs respect the content policy. Do not
expose artifact paths or raw content through unauthenticated routes.

## Tests

- Retrieve and reload an HTML normalized artifact byte-for-byte.
- Verify hash mismatch and missing-artifact failures.
- Verify unchanged acquisition creates no duplicate version or artifact.
- Verify feed metadata behavior remains bounded.
- Verify backup/restore and export behavior for artifacts.
- Verify oversized and hostile content remains blocked.

## Acceptance criteria

- Every newly acquired DocumentVersion references a durable immutable normalized
  content artifact.
- Reloading a version returns and verifies the exact normalized content.
- Same-content acquisition reuses the existing version/artifact.
- Retention, backup, restore, export, and size limits are documented and tested.

## Live-test gate

After Phase 18, real RSS/HTML canaries may verify durable content persistence,
but no semantic interpretation or Claims promotion is permitted.

## Dependencies

Phase 17 and the existing acquisition safety implementation.

## Exit criteria

Workers can obtain immutable, hash-verified normalized content for a
DocumentVersion without reading transient transport state. Phase 19 may add the
processing Job.

## Completion Record — 2026-08-18

Implemented by Kilo against the post-audit roadmap. Overall verdict: **PASS**.

### Storage architecture (chosen)

**SQLite content table** (`content_artifacts`) with a nullable
`document_versions.artifact_id` FK reference, rather than a filesystem
content-addressed store.

Rationale, in the phase's own comparison terms:

- **Transactional integrity:** artifact creation and the DocumentVersion row
  commit in the same `BEGIN IMMEDIATE` write transaction, so a failed artifact
  write can never leave a falsely successful acquisition.
- **Backup/restore:** the existing `storage.online_backup` /
  `operations.backup_database` path captures the artifact table automatically;
  no sidecar files can drift from the SQLite state.
- **Corruption detection:** `PRAGMA integrity_check`, `foreign_key_check`, and
  the Phase 18 hash re-verification all operate on one file.
- **Portability/Windows:** single-file runtime DB matches the existing
  deployment layout exactly; no new paths or file-permission concerns.
- **Deduplication:** `normalized_content_hash UNIQUE` gives exact
  content-addressing with zero extra design.
- **Scale:** Newsroom's personal/local-first scope keeps artifact text bounded
  below 200k chars per `AcquisitionPolicy.max_html_text_chars`; SQLite handles
  this trivially.

No object storage, Redis, external database, or distributed queue was
introduced.

### Normalization contract

The canonical normalized content is defined once by the acquisition path and
the persisted text IS the text that was hashed:

- **HTML and text/plain:** `SafeHTMLExtractor(...).text` (bounded visible
  text) → artifact `content_kind='visible_text'`,
  `norm_version='visible_text_v1'`. The extractor's safety semantics
  (script/style/iframe stripping, node and char bounds) are unchanged.
- **RSS/Atom entries:** the exact feed-entry metadata JSON currently persisted
  in `document_versions.normalized_json` (title, summary, url, published_at)
  → `content_kind='feed_metadata'`, `norm_version='feed_metadata_v1'`. Feed
  XML itself is NOT treated as article body; only what acquisition actually
  associated with the entry is stored.
- **Other (non-extractable) content types:** the exact fallback normalization
  `_normalized_text(body.decode('utf-8', errors='replace'))` that
  `normalized_content_hash` already used → `content_kind='fallback_text'`,
  `norm_version='fallback_text_v1'`. If that normalized text would exceed
  `max_html_text_chars`, acquisition truthfully fails with
  `AcquisitionTooLarge` (existing safety bound reused, not bypassed).

Invariant proven by tests:

    sha256(artifact.normalized_text)
        == artifact.normalized_content_hash

and the artifact hash equals the `acquisition_events.normalized_content_hash`
recorded for the same version. The hash is computed with
`normalized_text_hash()` over the exact bytes of the persisted text; a separate
normalization is never hashed.

### Schema / migration

- Migration **0015**; schema version becomes **15**.
- New table `content_artifacts`:
  `id, normalized_content_hash UNIQUE, content_kind CHECK, norm_version,
  normalized_text, text_length CHECK >= 0, retention_eligible CHECK IN (0,1),
  created_at`.
- `ALTER TABLE document_versions ADD COLUMN artifact_id TEXT REFERENCES
  content_artifacts(id)` + `document_versions_artifact_idx(artifact_id)`.
- Immutability trigger `content_artifacts_immutable_content` blocks any UPDATE
  of the content-bearing columns (`normalized_content_hash`, `content_kind`,
  `norm_version`, `normalized_text`, `text_length`); the FK forbids deleting a
  referenced artifact.
- **Legacy behavior:** pre-Phase-18 `document_versions` have
  `artifact_id = NULL` and stay fully readable as historical metadata.
  `ContentArtifactService.load_normalized_content()` returns
  `{"available": False, "reason": "legacy_version_without_artifact"}` and the
  strict `load_verified_text()` raises `LegacyVersionWithoutArtifact`. No
  content is manufactured and no remote re-fetch is attempted for history.
- Existing databases migrate idempotently through the normal framework
  (`apply_migrations` reruns are no-ops; schema-14 DBs upgrade to 15 with
  historical rows preserved).

### Acquisition integration

```
HTTP response / feed poll
  → bounded normalized text (canonical contract above)
  → artifact create-or-reuse (same write tx)
  → DocumentVersion INSERT with artifact_id
  → acquisition_event (same tx)
```

`AcquisitionService` holds one `storage.write_tx` across artifact +
`document_versions` + `acquisition_events`, so the association is atomic.
Network fetch happens before the transaction opens. Unchanged acquisition
returns the existing version (no new version and no new artifact).

### Immutability & deduplication

- Artifact rows can never be mutated (DB trigger) and cannot be deleted while
  referenced (FK).
- Artifact dedup key: exact `sha256(normalized_text)`.
- DocumentVersion dedup is unchanged: same `content_hash` short-circuits;
  304 records `not_modified` without a new version.

### Integrity verification

- `ContentArtifactService.verify(artifact_id)` recomputes sha256 and length
  and raises `ArtifactHashMismatch` / `ArtifactLengthMismatch` on any mismatch
  (fail closed, never silent corruption).
- `ContentArtifactService.load_normalized_content(version_id)` /
  `load_verified_text(version_id)` are the worker-ready loaders, also exposed
  through `EvidenceService.load_document_version_content` for Phase 22
  consumption.
- `integrity.check_database()` now reports `missing_content_artifact`,
  `content_artifact_hash_mismatch`, and `content_artifact_length_mismatch`
  issues; legacy NULL versions are not flagged.

### Backup / restore / export / privacy

- SQLite online backup includes content_artifacts automatically; a test backs
  up, restores, and re-verifies the artifact to prove it.
- Logical export allow-list deliberately does NOT include `content_artifacts`;
  `document_versions` export columns add only the `artifact_id` reference —
  normalized article text never leaves the runtime root through exports.
- No public API route returns artifact text; existing
  `get_document_version` views expose artifact_id only as a reference.

### Tests

`tests/test_phase18_content_artifacts.py` — 20 tests covering: HTML artifact
persistence + reload equality + hash correspondence; DB close/reopen
durability; unchanged 304/200 dedup; changed content new version + artifact;
feed entry metadata artifacts + unchanged feed dedup; content-addressed shared
artifact + immutability trigger; crafted hash/length mismatch detection
(loader + integrity); missing referenced artifact; legacy version truthful
unavailability (metadata still readable); backup/restore preserves artifacts
and references; export excludes artifact text; oversized direct artifact input
rejected; production-composition acceptance (Scheduler → Job → Worker →
artifact load after object teardown); migration 0015 fresh + schema-14 upgrade
preserving historical rows + idempotency; Live Test A redirect regression.

Existing suites updated for migration 15: phase02 foundation (expected tables,
versions, schema_version), phase06, phase07 jobs, phase08 monitors (upgrade
test now expects (14, 15)), phase15 hardening operations (range 1..16).

### Commands and exact results

| Command | Result |
|---|---|
| `python -m pytest -q tests/test_phase18_content_artifacts.py` | **20 passed** |
| `python -m pytest -q tests/test_monitor_runtime_acceptance.py` | **14 passed** |
| `python -m pytest -q tests/test_phase06_acquisition.py` | **15 passed** |
| `python -m pytest -q tests/test_phase02_foundation.py` | **7 passed** |
| focused phase15 hardening (backup/restore/export) | passed |
| full backend suite run 1 | **403 passed, 37 warnings** |
| full backend suite run 2 | **403 passed, 37 warnings** |
| `python -m pytest --collect-only -q` | 403 collected |
| `python -m compileall -q newsroom scripts tests` | exit 0 |
| frontend typecheck/build | not run — no frontend or shared API change |
| `git diff --check` | pass (pre-existing LF/CRLF advisory only) |

Phase 18 changes are backend-only: `newsroom/acquisition.py`,
`newsroom/content_artifacts.py`, `newsroom/integrity.py`,
`newsroom/evidence.py`, `newsroom/migrations.py`, `newsroom/operations.py`. No
existing API response shape changed (existing document-version views expose the
new `artifact_id` reference since they select `dv.*`, but no content text is
exposed), and no frontend workflow was modified, so frontend checks were not
required.

### Bounded live smoke test

Performed once (acquisition persistence changed materially). Used
`scripts/live_test_a.py`-style production composition against real public
services with disposable SQLite databases. Artifacts were verifiably present
for:

- RSS: `https://feeds.npr.org/1001/rss.xml` — retrieved, versions + artifacts
  persisted, repeat poll no_change without duplicates.
- HTML: `https://example.com/` — retrieved with artifact; repeat 304
  not_modified without a new version/artifact.
- Official/government: `https://www.usa.gov/` — redirected bare→www (the
  Live Test A redirect fix remains intact), retrieved with artifact persisted.

The full Live Test A suite was not re-run; the bounded smoke proves the
artifact path against real public services using the production composition.

### Remaining known limitations

- Legacy pre-Phase-18 versions intentionally have no artifact and truthfully
  report `unavailable`; no backfill is performed (no fabricated provenance).
- The manual/admin vertical-slice fixture path
  (`EvidenceService.create_document_version`, `run_manual`) creates
  metadata-only versions without artifacts — acquisition is the only Phase 18
  artifact producer by design.
- `retention_eligible` is stored but no retention policy/job exists yet;
  retention remains future operator work.
- `check_database()` re-hashes every artifact; fine at Newsroom's
  single-user scale, worth reviewing if the corpus grows multi-million row.
- Fallback-text artifacts are bounded by `max_html_text_chars`; oversized
  non-extractable responses that previously succeeded as hash-only now fail
  with `AcquisitionTooLarge` — a deliberate Phase 18 bound, not a silent
  regression.
