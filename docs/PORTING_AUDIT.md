# Hermes Newsroom v1 -> Standalone Newsroom Porting Audit

## Source inspected

Uploaded v1 repository Git HEAD:

`76a0be19ea3e0978743024d9283433a827c9e901`

The implementation report records Stage-A application acceptance at:

`2620fe0e94dc73b935bbc61697dbbc7c0fb0c22e`

The uploaded ZIP preserved the Git repository. Some extracted files appeared as
modified because of line-ending / Unicode filename extraction behavior, so the
bootstrap copies below were taken from canonical `git show HEAD:<path>` content,
not blindly from the extracted working tree.

## Port now — copied as proven deterministic baseline

### `newsroom/url_norm.py`

Why: pure URL canonicalization/fingerprinting behavior with extensive tests; no
Hermes dependency.

Disposition: copied unchanged from v1 HEAD. Treat as a baseline and extend only
with tests for newly encountered tracking/canonicalization cases.

### `newsroom/similarity.py`

Why: deterministic headline normalization/similarity is still useful as a cheap
candidate filter before embeddings or model adjudication.

Disposition: copied unchanged from v1 HEAD.

### `newsroom/event_sig.py`

Why: compact deterministic event-signature helpers remain valuable as one signal
in conservative candidate Story resolution.

Disposition: copied unchanged from v1 HEAD. It must not become sole event
identity in v2.

### `newsroom/dedupe.py`

Why: embodies the proven "false merge is worse" policy and useful URL/time/topic
safeguards.

Disposition: copied unchanged as the initial deterministic baseline. The v2
Story resolver will eventually wrap/replace portions with Subject/entity,
embedding, Document, and revision-aware candidate retrieval, but regression tests
must preserve conservative behavior.

### Core tests

Copied from v1 HEAD:

- `tests/test_url_norm.py`
- `tests/test_similarity.py`
- `tests/test_event_sig.py`
- `tests/test_dedupe.py`

These provide an immediate regression floor.

## Port with adaptation — implemented in bootstrap

### SQLite storage pattern

V1 strengths retained:

- short-lived connections;
- `foreign_keys=ON`;
- WAL;
- `busy_timeout=5000`;
- `synchronous=NORMAL`;
- explicit `BEGIN IMMEDIATE` write transactions;
- online SQLite backup;
- integrity check.

Hermes path resolution was removed. Standalone `newsroom/paths.py` uses a
standalone runtime root and supports explicit test/runtime configuration.

## Port conceptually, not by copying code

### Taxonomy invariants

Reuse:

- Category -> Topic hierarchy;
- stable slugs;
- Category/Topic soft deletion;
- include/alias/entity/exclude terms;
- term weights;
- per-Topic caps/priorities;
- disabled Category effectively disables collection without mutating child
  Topic enabled state.

Reason not copied wholesale: v2 adds Subjects and Monitor policies and should not
be constrained by the old service/schema layout.

### Review semantics

Reuse:

- saved;
- dismissed/remove as neutral review state;
- not useful as negative feedback;
- restore semantics;
- tags do not influence collection;
- reviewed state persists when new source material is merged.

Extend for v2:

- last reviewed Story revision;
- material-update resurfacing without destroying review state.

### Operational patterns

Reuse conceptually:

- online backup, not live file copying;
- restore without stale WAL/SHM;
- explicit integrity/migration verification;
- streamed logical export;
- scale fixture testing;
- source/runtime data separation;
- exact accepted commit as release source.

### API semantics

Reuse conceptually:

- canonical structured error envelope;
- deterministic pagination/order;
- omitted vs explicit-null PATCH handling;
- semantic validation separated from HTTP shape validation;
- atomic feedback + state mutation.

Do not copy Hermes plugin routing/auth assumptions.

## Reference only — do not port as production implementation

### `newsroom/migrations.py`

V1 schema is an excellent behavior reference but lacks v2 first-class concepts:
Subjects, Monitors, Policies, Jobs, Documents, DocumentVersions, StoryRevisions,
Claims, EvidenceSpans, ClaimEvidence, ClaimStateHistory, and ResearchQuestions.
Build a new migration 0001 for standalone.

### `newsroom/models.py`, `schemas.py`, `api_models.py`

Useful for enums/validation patterns, but v1 places claim status at Story level
and has Hermes-era transport assumptions. Recreate from the standalone product
contract.

### `newsroom/service.py`

Contains proven CRUD/run/ingestion behavior but is a large v1 orchestration
module organized around Hermes collector boundaries and the v1 schema. Mine it
for tests/invariants; do not transplant it wholesale.

### Dashboard source

The v1 UI provides interaction/design lessons (Inbox, Saved, History, Topics,
Runs) but depends on the Hermes Dashboard SDK and global runtime. Recreate the
frontend in normal React/TypeScript. Copy interaction semantics, not host code.

### `scoring.py` / `test_evidence.py`

Primary-source preference and separation of source quality from claim certainty
are useful ideas. The v1 story-level `claim_status` logic is not the v2 Evidence
Ledger, so do not copy it as authoritative claim evaluation code.

## Discard for standalone runtime

Do not port:

- `newsroom/plugin.yaml`
- plugin `__init__.py` registration
- `newsroom/tools.py`
- collector skill / Hermes skill wiring
- `newsroom/scheduler.py`
- Hermes dashboard `plugin_api.py`
- Hermes dashboard SDK bundle contract
- Hermes `HERMES_HOME` / profile paths
- Hermes plugin install/uninstall/verify scripts
- Hermes cron bridge and cron job provisioning
- Hermes session-token authentication

These solved host-integration problems that the standalone product no longer has.

## Recommended next port candidates after v2 schema exists

1. Stable-slug tests and taxonomy service invariants.
2. Review/tag transaction tests.
3. Streamed export generator patterns.
4. Backup/restore verification tests.
5. Scale-fixture generation approach.
6. Selected v1 real Story/Source data transformed into evaluation cases.

Port only after the corresponding standalone schema/service boundary exists.
