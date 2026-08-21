# Phase 22 — Verified Evidence and Claims Automation

## Status — implemented (2026-08-20)

Automatic processing invokes `ArticleAnalysisPromotionService` after a
relevant V2 `ArticleAnalysis`. The service treats every candidate as untrusted,
runs the canonical Phase 21H.2 provenance validator, reconstructs only the
exact analyzed slice, and requires a unique verbatim match before persisting an
immutable verified EvidenceSpan, pending canonical Claim, and ClaimEvidence in
one transaction. Model offsets are ignored; ambiguous matches fail closed.
Manual/legacy EvidenceSpans retain NULL automatic provenance and are never
reinterpreted as verified. Migration 0021 supplies the minimum provenance,
identity, outcome, uniqueness, and immutability schema. Automatic processing
stops after Claim/Evidence; Story, Report, and Alert automation remain Phase 23.

## Objective

Make automatically generated EvidenceSpans verifiably anchored to immutable
normalized content before Claims can become accepted.

## Why this phase exists

Current EvidenceSpan creation validates an excerpt and locator structurally but
does not prove that the excerpt exists in the owning acquired version.

## Current-state gap

The manual ledger and AI vertical slice can persist caller/model-supplied
excerpts against a DocumentVersion. Acquisition now needs a durable artifact,
and Phase 21 will produce candidates that must be checked before persistence.

## Scope

- Verify artifact hash and content availability.
- Require exact excerpt membership in normalized content.
- Store deterministic offsets or locators plus excerpt/hash.
- Reject fabricated, ambiguous, or mismatched excerpts.
- Ingest candidate Claims only after EvidenceSpan verification.
- Apply entailment, support/contradiction, confidence, state, provenance,
  duplicate, and idempotency rules.

## Non-goals

- No Story matching, report generation, or browser notification.
- No acceptance of unsupported Claims merely because a model is confident.
- No raw article-body expansion beyond Phase 18 policy.

## Existing components to reuse

`EvidenceService`, `evidence_span_hash`, Claim state transitions,
`AIVerticalSliceService`, AI entailment contracts, Phase 18 artifacts, and
Phase 21 analysis records.

## Required implementation

Create a verification boundary between model output and the evidence ledger.
The verifier loads the immutable artifact, confirms its hash, finds the exact
normalized excerpt, validates locator/offset consistency, and only then creates
the EvidenceSpan and Claim relationship. A fabricated excerpt must fail the
transaction and leave no partial Claim.

## Data model/migration expectations

Extend EvidenceSpan provenance only as needed to store deterministic offsets,
artifact identity/hash, and verification status. Preserve immutable historical
spans and distinguish legacy/manual spans from automatically verified spans if
their provenance cannot be upgraded.

## Runtime integration

Phase 21 analysis results are consumed by a bounded verification step in the
processing workflow. Duplicate processing of the same version/result is
idempotent. Failure is visible as a processing outcome and never becomes a
false `no_change`.

## Security/privacy considerations

Do not trust model-provided offsets or excerpts. Recompute them from the local
artifact, bound scan work, prevent content-derived SQL or HTML execution, and
keep source text out of logs and exported operational metadata.

## Tests

- Exact excerpt and locator are accepted.
- Fabricated excerpt is rejected.
- Hash mismatch and missing artifact are rejected.
- Duplicate evidence and repeated processing are idempotent.
- Contradiction/support/unknown entailment states remain correct.
- Unaccepted or disputed Claims cannot enter report-accepted sets.

## Acceptance criteria

```text
analysis output
  → verified EvidenceSpan
  → Claim
  → evidence relationship
```

The fabricated-excerpt negative test must fail closed.

## Live-test gate

Live Test B may be rerun with evidence verification enabled. Live Test C is
permitted only after Phase 23 connects Stories, Reports, and Alerts.

## Dependencies

Phases 18, 20, and 21.

## Phase 21H design constraints — Phase 22 not started

The following constraints are prerequisites, not implementation work in this
phase:

- Use Unicode/Python `str` codepoint offsets against one canonical normalized
  evidence view. Never use byte offsets or trust model-provided offsets.
- Define and persist the canonical evidence view used for verification. HTML
  and text artifacts use the exact normalized artifact text.
- Feed artifacts require a deterministic evidence projection from the
  persisted feed-entry metadata, including projection version and field path;
  feed metadata must not be treated as raw HTML/text implicitly.
- Require a passing Phase 21H full provenance validation before any
  EvidenceSpan or Claim write.
- Treat the durable Phase 21H paid invocation/reservation state as a
  prerequisite. Evidence retries must not create another paid analysis call.

## Phase 21H.1 — evidence-coordinate specification (binding for Phase 22)

This section fixes a deterministic coordinate contract for the Phase 22
evidence verifier. The next implementation agent MUST implement these rules
exactly; they are not design suggestions. No Phase 22 runtime exists yet and
nothing below authorizes evidence promotion in this checkpoint.

### 1. Canonical evidence text views

Every evidence excerpt is verified against exactly one canonical FINITE text
view derived from the Phase 18 immutable ContentArtifact. There are exactly
two view families:

- `artifact_view`: HTML/text/fallback artifacts (`content_kind` in
  `{"visible_text", "fallback_text"}`). The
  canonical evidence view IS the artifact's exact stored
  `normalized_text` — the same byte-for-byte text whose
  `normalized_content_hash` and `text_length` were verified by the Phase 18
  loader. No re-normalization, no whitespace repair, no entity decoding, no
  case folding. The view identity is the ``artifact_id``.
- `feed_entry_view`: feed-metadata artifacts (`content_kind ==
  "feed_metadata"`). The evidence view is a deterministic projection of the
  exact persisted metadata JSON. The view identity is the triple
  ``(artifact_id, view_version, field_path)``. Feed metadata is NEVER treated
  as raw HTML/text and NEVER passed through artifact normalization.

### 2. Feed-entry evidence view (`feed_entry_projection_v1`)

The projection contract `feed_entry_projection_v1` over the persisted metadata
JSON (an object) is:

- field path = `["title", "summary"]`;
- exclusions: `link`, `guid`, `id`, `updated`, `published`, `author`,
  `content_html`, `content_text` (and any other structural/foreign-key field)
  never participate in evidence text;
- view text is always `title + "\n" + summary`, including when either exact
  JSON-decoded string is empty;
- separator: exactly one `"\n"` (U+000A), never conditionally removed;
- each part is the exact stored JSON string value after JSON unescaping
  (Python `json.loads` semantics), verbatim — no HTML/A markup parsing, no
  whitespace folding;
- missing values are treated as empty strings, so empty title and summary have
  the canonical representation `"\n"`; because both underlying fields contain
  no meaningful text, the record is separately ineligible for analysis or
  evidence promotion;
- projection version `"feed_entry_projection_v1"` and field path
  `"title;summary"` are persisted with the resulting EvidenceSpan.

Historical rule: once a feed-entry EvidenceSpan is persisted, later changes
to the projection rules do NOT retroactively alter existing spans; a new
projection version creates a NEW view identity. Feed entries without a stored
metadata artifact record have no evidence view and every verification fails.

### 3. View hashing

The verifier first rehashes the exact artifact `normalized_text` and verifies
that hash and length against `normalized_content_hash` / `text_length`. It then
derives the canonical view and hashes that distinct representation with
`sha256(view_text.encode("utf-8")).hexdigest()`. For artifact views the two
hashes are equal. For feed views the artifact hash covers the immutable metadata
JSON while the view hash covers the deterministic title/summary projection, so
they are intentionally distinct. The EvidenceSpan never stores the view text;
it stores the excerpt, code-point offsets, artifact identity/hash, view
identity/version, and view hash.

### 3.a Analysis-input truncation bound

Only analyses with a complete Phase 21H.2 input contract are automatically
promotable. The verifier must reconstruct and validate `input_view_version`,
`input_content_hash`, `analyzed_content_hash`, `input_char_count`,
`analyzed_char_count`, and `truncated` through the full provenance validator.
If `article_analyses.analyzed_char_count < article_analyses.input_char_count`
(the model saw a truncated suffix of the input text), a candidate excerpt may
only be verified against the first `analyzed_char_count` code points of the
canonical view: the excerpt must be fully inside that prefix, and its
recomputed offset must satisfy `end <= analyzed_char_count`. No accepted
excerpt content is expanded beyond what the model actually saw, and never
beyond the Phase 18 artifact text.

### 3.b Candidate provenance on the span

Every automatically promoted span stores
`{ "analysis_id", "candidate_claim_index", "candidate_excerpt_index" }` in
its provenance JSON so Phase 22+ can trace exactly which model proposal
became verified.

### 4. Unicode code-point offsets

All offsets stored and compared are Python `str` code-point offsets (0-based)
over the canonical view text:

- `start`: smallest code-point index of the first matched character;
- `end`: one-past-the-last matched character's index (`excerpt == view[start:end]`).

Model-supplied offsets are NEVER accepted; the excerpt and all offsets are
always recomputed locally from the canonical view.

### 5. Exact excerpt matching

- The candidate excerpt is matched as an EXACT substring of the canonical
  view: `view.find(excerpt)`. No normalization, no fuzzy/`difflib` matching,
  no token overlap, no sentence restitching.
- A candidate excerpt may be a truncated suffix of a model-produced sentence,
  as long as it is an exact verbatim substring.
- Empty excerpts fail. Excerpts whose length or code-point span exceeds the
  Phase 18 view bounds fail.
- 5.c Index-resolved occurrence (unique-resolution rule): when the candidate
  excerpt carries `locator_type == "candidate_excerpt_index"`, the verifier
  reads the analysis record's `candidate_evidence_excerpts` array, takes the
  exact stored excerpt string at `candidate_excerpt_index`, and matches THAT
  string verbatim. If it still occurs more than once, the evidence is
  rejected as ambiguous (rule 7). No positional tie-breaking or partial
  locator tolerance is permitted.

### 6. Zero-match rejection

- If the excerpt does not occur in the view (`find` returns `-1`), the
  evidence is rejected; the transaction aborts and no EvidenceSpan, Claim,
  ClaimEvidence, or state change is persisted for that candidate.

### 7. Ambiguous multiple-match rejection

- If the excerpt occurs more than once in the view, the evidence is AMBIGUOUS
  and rejected unless a uniqueness rule deterministically resolves it. The
  ONLY permitted resolution is the index-annotated excerpt in 5.c:
  `locator_type == "candidate_excerpt_index"` with the analysis JSON's
  candidate excerpt string as the excerpt — if THAT exact string still occurs
  more than once, the evidence is rejected. No tie-breaking by position,
  length, or any other heuristic is permitted with accepting ambiguity.
- The verifier returns a distinct outcome code, e.g. `ambiguous_evidence`,
  so operators can re-examine the candidate — the excerpt still never becomes
  an EvidenceSpan.

### 8. Locally recomputed offsets

- The verifier ALWAYS recomputes `start`/`end`/`excerpt_hash` from the
  canonical view + stored excerpt candidates. Stored or model-supplied locator
  values are treated as input hints only and are validated against the real
  recomputed match, unless the index-resolved occurrence rule says the match
  is exact and complete.

### 9. Artifact/view provenance

- Every automatically created EvidenceSpan must persist:
  - `document_version_id` FK (owner);
  - `artifact_id` (the immutable content row);
  - `artifact_content_hash` (`normalized_content_hash`);
  - `view_content_hash` (SHA-256 of the canonical evidence view);
  - `view_kind` ∈ `{"artifact", "feed"}`;
  - `view_version` (`"artifact_norm_v1"` or `"feed_entry_projection_v1"`);
  - `field_path` (`null` for artifact views, `"title;summary"` for feed);

### 10. Atomic promotion

- The EvidenceSpan row, the canonical Claim row, and the `claim_evidence`
  relationship are created in ONE SQLite write transaction, or none of them
  are. A failed excerpt/ambiguity/hash/migration check rolls the whole
  promotion back: no EvidenceSpan, no Claim, no ClaimEvidence and no state
  change.
- The verifier runs inside the same job that owns the analysis invocation;
  a failed promotion is a FAILED processing outcome visible to the queue,
  never a silent `no_change`.

### 11. Deterministic promotion identity

- `evidence_span_hash(excerpt, locator_type, locator_value)` (existing)
  determines EvidenceSpan identity; `locator_type`/`locator_value` are the
  deterministic recomputed `view_kind` + `start`/`end` (e.g.
  `locator_type="codepoint_offset"`, locator_value `"start;end"`).
- A candidate Claim is promoted once per canonical (document_version,
  artifact, candidate_claim_index) triple: the `claims` identity is the
  existing canonical form (proposition + originating `story_id`), and the
  `claim_evidence` relationship references `claims.id` + `evidence_spans.id`
  with the existing relationship vocabulary. Duplicate promotion attempts are
  idempotent (UNIQUE indexes + existing-select), never duplicated.

### 12. Source membership vs logical support — never conflated

- Membership: the exact excerpt occurs in the artifact/view (proof of
  presence in the acquired content).
- Logical support: entailment/claims/contradiction relationships between a
  canonical Claim and the evidence span. These are separate since Phase 22
  does not use prompt/output as evidence: verified membership is necessary but
  NOT sufficient for acceptance — the Claim's state machines and support/
  contradiction/CAUTION classification are unchanged and remain closed-world.
  The verifier creates Claims/EvidenceSpans from verified excerpts when (and
  only when) all the rules in this section plus the full Phase 21H provenance
  chain hold; a member excerpt of a story that was NOT active through the
  chain (run/no entity, missing Story lineage, no relevant canonical Claim) is
  still not acceptable evidence.

Phase 22 has not started and no evidence-promotion runtime is authorized by
this note.

## Exit criteria

Every automatically generated EvidenceSpan is content-verified and every
automatically ingested Claim has immutable, queryable provenance. Phase 23 may
connect verified intelligence to Stories and Reports.
