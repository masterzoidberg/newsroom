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
