# AI provider settings architecture

## Existing execution map

| Path | Construction and effective capability |
|---|---|
| Changed document | `runtime.build_worker_handlers` → `DocumentProcessingExecutionService` → `ArticleAnalysisService`; shared `AIConfigurationResolver` snapshots managed configuration at each operation boundary |
| Article Analysis remote | `OpenAICompatibleArticleAnalysisProvider` uses existing `openai` SDK, chat completions + JSON-schema response format, configured model/base URL/timeouts; exact input/provenance retained |
| Local AI | `CapabilityBundle.local_defaults` supplies deterministic heuristics, not a local language-model server; local vocabulary returns no provider suggestions and research planner an empty plan for deterministic fallback |
| Watch vocabulary | API `WatchService` and worker `WatchMaintenanceService` resolve the shared authority per operation; the configured `vocabulary` route uses the structured OpenAI-compatible adapter with durable paid admission, while local/manual derivation remains the safe fallback |
| Watch source recommendations | AST-31 implements the bounded `source_discovery` capability on the same structured OpenAI-compatible adapter; owner setup/recovery presentation is AST-32, and no external search adapter is part of the contract |
| Research planning | production worker uses the deterministic local path; optional planner injection remains test/integration-only and is not in-app provider integration |
| Relevance | `monitoring.RelevanceCascade` remains explicitly deterministic/local; do not casually replace its approved-scope semantics |
| Ask | normal frontend sends `provider_mode: local`; default `AskService(hosted_enabled=False)`; injectable synthesis path and eval provider exist but are not a supported product paid path |
| Synthesis/extraction/ranking/etc. | capability interfaces and local implementations exist; production paid coverage is not inferred from interfaces |

Managed selection now uses the shared `AIConfigurationResolver`: it reads the current metadata generation, obtains the selected vault credential just in time, and resolves unavailable, disabled, removed, or budget-blocked routes to an explicitly labeled local result for new work. An untouched installation may use `NEWSROOM_ANALYSIS_PROVIDER=openai` with `NEWSROOM_ANALYSIS_API_KEY` or `OPENAI_API_KEY`, but that source is explicitly labeled and is never allowed to reactivate after managed configuration exists. Article Analysis uses durable paid invocation reservations. AST-08 adds durable generic paid-capability reservations through `BudgetService` and the existing `provider_usage` ledger; `AIRouter` instance-local counters remain only a compatibility fallback when no durable authority is supplied. Actual billing cost is unavailable from the current adapter; token counts and estimated reservation cost are different facts. Explicit `AnalysisProviderConfig` injection remains a compatibility/test override and may still report a terminal configuration error rather than silently changing its requested route.

AST-28 adds the first non-Article-Analysis managed capability: `VocabularyRequest` carries bounded approved target and Watch terms, `OpenAICompatibleVocabularyProvider` requests a structured `VocabularyOutput`, and every suggestion is persisted as review-only (`suggested`, disabled). A synchronous run receives a distinct durable work identity when the caller does not supply one; queued worker retries use the durable job ID. Provider failures, malformed or low-confidence output, disabled paid mode, and unavailable credentials leave the deterministic/manual configuration intact. Rejection rows are retained by the existing Watch vocabulary uniqueness contract and are not resurrected by later runs.

AST-29 adds the owner-facing terminology boundary in Watch setup. Suggested, approved and rejected terms are separate visible states; approve/reject actions call the authenticated review route; edited suggestions become explicit approved owner terms while the original suggestion is rejected; and manual terms remain available when managed routing is disabled or unavailable. This UI does not make a provider call while typing and does not treat a suggestion as monitoring scope before server review.

AST-30 freezes the fresh-corpus source boundary below, AST-31 implements it without changing the existing candidate schema or adding a second provider configuration store, and AST-32 completes the setup presentation and source-health/recovery connection.

## One coherent configuration authority

Retain SQLite for **public metadata only** and add a small typed provider/config service. Existing generic settings reject sensitive key names and return values; never use them for secrets. Do not add an encrypted key column to SQLite: full database backups would still carry the credential blob.

Implemented additive schema (migrations 0038–0039; the audit baseline was 36):

- `ai_connections`: stable ID, display name, adapter kind (`openai_compatible`), normalized base URL, model, enabled flag, credential reference/version (opaque non-secret), credential requirement, output/input bounds, created/updated timestamps, validation result/code/time tied to exact config revision.
- `ai_capability_routes`: capability primary key, connection ID or local, fallback policy, revision. Unsupported capabilities cannot be assigned. “Set default” applies only to supported capabilities and previews the affected list.
- One monotonic configuration generation, updated transactionally with route/connection changes. Reuse existing budget settings/limits and durable `BudgetService`; do not create a second spending switch in provider rows.

Names/URLs/model strings are validated and length bounded. Reject embedded URL credentials, secret query strings, fragments, unsupported schemes and ambiguous authorities. An opaque credential reference is never a credential value or a recoverable key fragment.

## Credential storage decision

AST-07 implements the trusted Python **keyring abstraction with an explicitly selected approved OS backend**: Windows Credential Manager on Windows, macOS Keychain and Linux Secret Service when available. This is the one approved credential dependency. No generic auto-selected plaintext, third-party fallback, null-success or arbitrary plugin backend is acceptable. Unsupported/headless environments remain local-only; tests use an injected in-memory fake. There is no silent `.env` fallback.

Windows target namespace: `Newsroom/<installation-uuid>/<connection-id>/<credential-version>`, bound to the runtime owner's account. API performs create/replace/delete; workers and API execution services read just in time under that same owner. Scheduler has no need to read provider secrets. An API on another Windows account must report unavailable credentials rather than copy them.

[Microsoft CredWriteW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew) associates credentials with the current token's logon session; this is why startup identity and credential qualification belong together. [Keyring documentation](https://keyring.readthedocs.io/en/latest/index.html) describes OS backends and security considerations; explicitly test the packaged backend rather than trusting development defaults.

Alternative: current-user DPAPI in a separate restricted file. It avoids a Python abstraction but adds blob lifecycle, filesystem ACL, exclusion and platform-specific code. [Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) normally binds decryption to matching user credentials/computer; machine-wide protection is inappropriate here. Prefer Credential Manager because no app-managed credential file enters the backup path. Neither protects against malicious code already running as the same user; do not promise application-exclusive isolation or Python memory zeroization.

## Save, rotate and remove safely

Key store and SQLite do not share a transaction. AST-07 writes a new versioned secret while holding the SQLite reservation lock, commits its reference and new generation only if that succeeds, and on DB failure removes the new orphan or records a safe cleanup obligation; the prior reference remains authoritative. On successful rotation, it retires the old version after the metadata commit. Never overwrite an active secret in place while callers could resolve a stale configuration revision.

Removal first disables/reroutes new calls transactionally and advances generation, then deletes the secret. Failed deletion is shown as “disabled; credential removal needs retry,” not falsely reported as removed. Migration 0039 retains a non-secret cleanup version so retries can recover even after a process failure. Connection metadata may remain as a tombstone where audit foreign keys require it. Existing analysis/history must retain provider/model identity. Deleting a connection never deletes evidence, analyses or paid invocation history.

## Reload and process ownership

At every new AI operation/job boundary, resolve one immutable generation snapshot. Pin connection/model/prompt/capability/generation into invocation identity. Build clients lazily and retire obsolete clients after in-flight operations. All API and worker paths use the same resolver; no construction-time unrelated environment authority remains.

Edits apply to new work without process restart. Running work completes under the old snapshot and displays that fact; “applied” must not claim to revoke a request already sent. A disable takes effect before the next paid reservation, rechecking the authoritative route/paid switch inside the reservation boundary. Report effective and pending generation per component. Backend/runtime updates may require a managed Restart action, but normal provider edits should not.

Environment migration: recognize legacy presence without showing values. Do not import automatically. Provide an explicit one-time import action for the runtime owner, moving secret to the OS store and non-secret config to metadata with paid routing still off until intentionally enabled. Until import, show a clearly labeled legacy configuration source; an explicit managed-config marker prevents environment variables from reactivating a removed provider. Dev-only environment injection may be an explicit mode, but cannot override managed production settings. No writing shell profiles or copying secrets into launch commands.

## Routing and compatibility scope

The current managed surface supports Local/Offline, OpenAI-compatible **Article Analysis**, the bounded Watch vocabulary route, and AST-31's bounded Watch `source_discovery` route through the existing adapter. `source_discovery` uses the same OpenAI-compatible adapter, credential boundary, operation-generation snapshot and durable budget authority, but it does not reuse the vocabulary schema or silently inherit its meaning. OpenAI, OpenRouter and other endpoints are connection presets only when the configured endpoint/model passes the specific structured-output contract for the requested capability. Chat-completions syntax alone is not proof of JSON-schema compatibility. Model entry is editable text; model enumeration is optional and never implies every listed model supports a capability.

Loopback local endpoints may be keyless only when explicitly configured; allow HTTP only for deliberate loopback use, never arbitrary private/LAN addresses by default. Hosted URLs require HTTPS. Enforce redirect/destination checks so a base-URL edit cannot forward a stored secret elsewhere; require credential reconfirmation on host change. Do not expose arbitrary headers or provider payload fields in v1. Test DNS/redirect/credential-forwarding behavior with a mock transport. Use existing acquisition security principles without treating article-fetch policy as automatically suitable for trusted loopback AI endpoints.

Direct Anthropic/Gemini SDKs are deferred: different request, tool and output contracts need actual adapters; do not advertise unsupported compatibility. No embedding/entailment/relevance remote switch merely for coverage. Add normal Ask remote synthesis only as the separately gated AST-21 slice after user-value evidence; reuse shared configuration/budget/security contracts. Eval provider injection stays independent and frozen for comparisons.

Fallback: default local when provider is disabled/removed/unconfigured or budget disallows a new call. Clearly label the effective local result and reason. Remote failure may produce a separately identified local fallback only if safe and enabled; it must never fabricate remote success, retry an uncertain billed request, or reuse an old analysis identity with new inputs. In contract-bound evaluation, any fallback invalidates the requested comparison. Local failure stays a truthful failure/refusal; no new paid permission is inferred.

## AST-30 — Fresh-corpus source recommendation contract

This is the frozen implementation boundary for AST-31. It is intentionally a
bounded recommendation lane, not autonomous web discovery. The source
recommendation result is configuration input for a human review queue; it is
never a Claim, Evidence, Document, or proof that a publication is authoritative.

### Capability and trigger

- The logical capability name is **`source_discovery`**. It is distinct from
  `vocabulary`, `article_analysis`, `research_plan`, and acquisition.
- AST-31 uses the existing OpenAI-compatible chat-completions adapter with a
  strict JSON-schema response. It adds no SDK, crawler, metasearch engine,
  search index, or second credential/budget authority.
- The assistance lane is eligible only for a Watch with an information-need
  target (`topic`, `subject`, `story`, or `research_question`) whose bounded
  deterministic corpus query has no proposal to offer. A `source` Watch is
  acquisition-only and remains manual/corpus-only. Existing corpus proposals
  are returned without a model call; a model call is not a way to refresh or
  replace observed provenance.
- “Empty corpus” means no confirmed `relevant=1` DocumentVersion joined to
  one of this Watch's own `watch_sources.monitor_id` rows. No raw document
  body, candidate URL, provider response, credential, or internal target ID is
  sent to the provider. The bounded Watch name and approved positive/excluded
  terms are the only semantic context.

### Request and output schema

AST-31 implements these provider-neutral shapes in `newsroom/ai.py` with
strict extra-field rejection and bounded strings. The server, not the model,
owns candidate provenance.

```json
{
  "watch_name": "string, 1..200",
  "target_type": "topic|subject|story|research_question",
  "approved_terms": ["at most 100 strings, each 1..300"],
  "excluded_terms": ["at most 100 strings, each 1..300"],
  "max_candidates": "integer, 1..10"
}
```

The structured output is:

```json
{
  "candidates": [
    {
      "name": "string, 1..200",
      "homepage_url": "HTTP(S) string, optional, max 2048",
      "feed_url": "HTTP(S) string, optional, max 2048",
      "rationale": "string, 1..2000",
      "authority_context": "string, max 2000",
      "limitations": "string, 1..2000"
    }
  ]
}
```

At least one of `homepage_url` and `feed_url` is required per item; at most
10 items may be returned by one provider call and the existing hard
`MAX_CANDIDATES_PER_RUN` cap remains the outer limit. `authority_context` and
`rationale` are model hypotheses, not verification. The provider must not
claim that it visited a URL, saw current content, established official status,
or found independent evidence. `limitations` must explicitly preserve the
unverified nature of a model-proposed URL when the provider does not supply a
stronger bounded explanation.

No confidence threshold is treated as trust. A high model confidence cannot
override URL policy, human review, acquisition health, or the Evidence
promotion boundary.

### Candidate persistence and provenance

AST-31 reuses the existing `source_candidates` columns and does not add a
migration:

| Field | Frozen meaning |
|---|---|
| `discovery_method` | `ai_suggestion` for model-proposed candidates; `existing_source`, `document_link`, and `feed_discovery` remain corpus-observed lanes; `manual` remains owner input; `web_search` is reserved for existing research workflows and is not emitted by this Watch lane |
| `status` | `suggested` on creation, `approved` or `rejected` only after the explicit authenticated review action |
| `source_id` | `NULL` for a new model-proposed Source, or a matching existing Source identity if canonical URL matching safely finds one; either case remains unattached until review |
| `normalized_url` | Canonical homepage identity for the per-Watch uniqueness key. If only a feed is supplied, the feed is also the candidate homepage identity and remains in `feed_url` |
| `rationale` / `authority_context` / `limitations` | Bounded, visible explanation. Model text is not upgraded to a verified fact; the server adds the unverified limitation when needed |
| `provenance_json` | Server-owned bounded metadata such as `kind=ai_suggestion`, `capability=source_discovery`, trigger `empty_corpus`, provider route/provider/model, configuration generation and work identity. Never store the raw prompt, response body, credential, secret, or search snippet |

Candidate identity is `(watch_id, normalized_url)`. Repeating a canonical URL
returns the retained row without changing its rationale, provenance, or
rejected status. Rejected rows remain retained and are never resurrected or
auto-approved by a later run. A matching existing Source is reused rather than
copied, but reuse never creates a `watch_sources` relationship by itself.

### URL, feed, and transport validation

Validation is staged and each stage has a narrow meaning:

1. Before candidate persistence, normalize each supplied URL and apply the
   existing structural `AcquisitionPolicy.check_url` rules: HTTP(S) only,
   bounded length, valid host, no literal loopback/private/local destination,
   and deployment allow/deny policy where configured. A malformed homepage or
   feed rejects the entire candidate; silently keeping a second unsafe URL is
   not allowed.
2. Candidate creation and review do not fetch a homepage, follow a redirect,
   resolve DNS, or parse a feed. A structurally valid URL is still visibly
   **unverified**.
3. On the first and every later acquisition request, the existing bounded
   transport applies `check_resolved_url`, public connected-peer verification,
   response bounds, and redirect-destination checks for each hop. A previous
   DNS result is never cached as permanent source verification. A feed is not
   labeled valid until the normal feed poll parses it successfully.
4. A blocked, private, redirecting-to-private, malformed, unavailable, or
   hallucinated URL can therefore never produce a `DocumentVersion`, Claim, or
   Evidence. Acquisition records the bounded failure/health outcome instead.

Approval is explicit and remains the only attachment gate for Watch
`source_candidates`. Approval may create the ordinary Source and per-Watch
Monitor relationship through `review_source_candidate`, but it does not make a
network request or create Evidence. This Watch-specific behavior is separate
from the older global `source_suggestions` workflow described in ADR-004,
whose approval contract remains unchanged.

### API and run result

Reuse the existing authenticated, CSRF-protected routes; do not add a second
source-recommendation API:

- `POST /watches/{identifier}/discover-sources` remains the synchronous
  bounded run.
- `POST /watches/{identifier}/discovery-runs` remains the `202` durable Job
  request. Its idempotency/retry identity remains per requested run, not a
  permanent per-Watch key.
- `GET /watches/{identifier}/source-candidates` continues to expose the
  retained candidate row and provenance. AST-32 may derive an
  `unverified` display label from `discovery_method=ai_suggestion` and
  `provenance.unverified=true`; it must not infer approval from that label.

The existing result keys remain backward compatible. AST-31 may add bounded
metadata fields:

```json
{
  "watch_id": "...",
  "ran_at": "...",
  "outcome": "completed|manual_fallback",
  "corpus_state": "populated|empty",
  "methods": ["existing_source", "document_link", "feed_discovery", "ai_suggestion"],
  "candidates": [],
  "candidate_count": 0,
  "external_requests": 0,
  "provider_requests": 0,
  "fallback_reason": "paid_disabled|route_unavailable|budget_exhausted|provider_failed|no_candidates|null"
}
```

`external_requests` continues to count source/web acquisition requests and is
zero for recommendation. A remote model call is counted separately as one
`provider_requests` attempt and in `provider_usage` under the
`source_discovery` capability.

### Cost, fallback, and cancellation

- Local `source_discovery` returns no model candidates; deterministic corpus
  proposals and manual entry remain available at zero cost.
- A remote call is attempted only when the owner has explicitly configured a
  `source_discovery` connection route, the global paid switch is on, the Watch
  policy has sufficient paid budget, and the operation obtains one durable
  reservation. The reservation is bounded to one call and the Watch ceiling
  is the minimum of global, connection, and policy limits.
- Disabled, missing, unconfigured, credential-unavailable, budget-blocked, or
  low-capability routes return `manual_fallback` with a safe reason and no
  provider call where no call was attempted. The run is not reported as a
  successful recommendation merely because a local empty result exists.
- A sent call that times out, fails, or returns invalid structured output is
  finalized in durable usage and is not silently retried by the same run or
  by automatic Job retry. The user may request a new bounded run. No provider
  error or raw response is copied into candidate text or user-visible errors.
- Cancellation before candidate commit leaves no candidate, Source, Monitor,
  acquisition, Claim, or Evidence mutation. If a paid request was already
  sent, its durable reservation/uncertain outcome remains counted.

### External search decision

An external search adapter is **not necessary for AST-31**. The empty-corpus
capability is a model-only, review-only recommendation lane backed by a fake
provider in offline tests; it does not promise exhaustive discovery or URL
verification. `web_search` remains a compatibility value for the existing
Research Question path, not a license to add a search engine here. If real-use
evidence later shows model-only recommendations are insufficient, a separate
task must freeze exactly one search provider, transport/SSRF policy, cost and
human preference before implementation. That decision is outside AST-30/31.

## API and frontend contracts

The backend routes below are implemented under `/api/v1`; they use existing session/CSRF guards for writes, restrictive validation, safe error codes, `Cache-Control: no-store`, and no request-body logging. AST-11 now consumes these contracts through a functional Settings UI; the domain/API surface itself was unchanged by that frontend slice.

| Endpoint | Contract |
|---|---|
| `GET /ai/providers` | metadata, supported capabilities, effective route/generation, configured/unavailable status; no secret, suffix or provider response bodies |
| `POST /ai/providers` | create disabled connection metadata; optional write-only credential, never echoed |
| `PATCH /ai/providers/{id}` | metadata edit with expected revision; stale update → 409; host changes invalidate validation and require credential handling |
| `PUT /ai/providers/{id}/credential` | replace write-only secret; return configured status/revision only |
| `DELETE /ai/providers/{id}/credential` | disable/reroute, remove secret, truthful partial-failure status |
| `DELETE /ai/providers/{id}` | disable, remove credential, preserve historical audit identity |
| `POST /ai/providers/{id}/test` | explicit bounded validation request; known configured model and response-schema probe; safe result/time/capability status |
| `PUT /ai/routes/{capability}` | assign supported route/fallback with expected generation; reject unsupported capability |
| `GET /ai/status` | effective model, generation, last validation/failure, usage and existing budget summary |

Use existing budget APIs for spending limits; no second limit ledger. Test connection may incur cost: explicit UI action explains this, requires a bounded authorized test reservation even while background paid routing is off, and never enables background spending. No validation on typing, page open, periodic refresh or migration. Count failed/uncertain sent requests conservatively; distinguish free local tests. Never treat a models-list request alone as a schema-capability pass.

AST-11 Settings → AI Providers explains offline operation and the precise improvement (structured Article Analysis initially). It owns Add/Edit/Test/Enable/Disable/Model/Remove credential/Set default controls, a fixed masked/configured state, validation timestamp and generation, effective routing, paid switch, limits, estimated versus actual usage, and safe failure recovery. Raw key exists only in the password input/request until submission; the UI clears it afterward and never persists it in browser storage or global state. Server validation errors must not echo input; Pydantic's raw `input` details require special handling for these request models. Shared Settings loading failures must not hide the entire provider state. The isolated browser acceptance covers the fake API surface, while actual paid-provider authorization and installed lifecycle remain separately gated.

## Acceptance — Add AI Provider

The AST-11 isolated acceptance runs Settings → AI Providers → Add compatible connection → submit a synthetic credential → test explicitly → enable paid routing within a small synthetic cap → route Article Analysis → edit/recover → remove/delete and verify local fallback. It inspects browser DOM/storage and fixture responses for the sentinel (absent after submission except in the submitted request), checks no external provider call, and records desktop/390px screenshots. Existing phase21 tests exercise the configured managed worker authority and durable invocation contracts. This evidence does not certify an actual paid provider, installed runtime, OS-vault artifact audit or physical lifecycle; those require separate authorization/qualification.
