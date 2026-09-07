# AI provider settings architecture

## Existing execution map

| Path | Construction and effective capability |
|---|---|
| Changed document | `runtime.build_worker_handlers` → `DocumentProcessingExecutionService` → `ArticleAnalysisService`; `AnalysisProviderConfig.from_env` captured in service construction |
| Article Analysis remote | `OpenAICompatibleArticleAnalysisProvider` uses existing `openai` SDK, chat completions + JSON-schema response format, configured model/base URL/timeouts; exact input/provenance retained |
| Local AI | `CapabilityBundle.local_defaults` supplies deterministic heuristics, not a local language-model server; vocabulary returns no suggestions and research planner an empty plan for deterministic fallback |
| Watch vocabulary | API `WatchService` and worker `WatchMaintenanceService` construct local bundles; no global remote provider setting |
| Research planning | runtime explicitly constructs a local research router; optional planner injection is not in-app provider integration |
| Relevance | `monitoring.RelevanceCascade` remains explicitly deterministic/local; do not casually replace its approved-scope semantics |
| Ask | normal frontend sends `provider_mode: local`; default `AskService(hosted_enabled=False)`; injectable synthesis path and eval provider exist but are not a supported product paid path |
| Synthesis/extraction/ranking/etc. | capability interfaces and local implementations exist; production paid coverage is not inferred from interfaces |

Current selection requires `NEWSROOM_ANALYSIS_PROVIDER=openai`, Newsroom-specific API key or `OPENAI_API_KEY`, and `budget.paid_enabled`. Analysis uses durable paid invocation reservations; `AIRouter` additionally has instance-local counters, which are insufficient as a cross-process authority for new paid routes. Actual billing cost is unavailable from the current adapter; token counts and estimated reservation cost are different facts. `_resolve_route` raises when remote is selected but credentials/paid permission are absent: graceful local fallback is a design change, not current behavior.

## One coherent configuration authority

Retain SQLite for **public metadata only** and add a small typed provider/config service. Existing generic settings reject sensitive key names and return values; never use them for secrets. Do not add an encrypted key column to SQLite: full database backups would still carry the credential blob.

Proposed additive schema (allocate next migration only after checking current ledger; audit baseline is 36):

- `ai_connections`: stable ID, display name, adapter kind (`openai_compatible`), normalized base URL, model, enabled flag, credential reference/version (opaque non-secret), credential requirement, output/input bounds, created/updated timestamps, validation result/code/time tied to exact config revision.
- `ai_capability_routes`: capability primary key, connection ID or local, fallback policy, revision. Unsupported capabilities cannot be assigned. “Set default” applies only to supported capabilities and previews the affected list.
- One monotonic configuration generation, updated transactionally with route/connection changes. Reuse existing budget settings/limits and durable `BudgetService`; do not create a second spending switch in provider rows.

Names/URLs/model strings are validated and length bounded. Reject embedded URL credentials, secret query strings, fragments, unsupported schemes and ambiguous authorities. An opaque credential reference is never a credential value or a recoverable key fragment.

## Credential storage decision

Recommend the trusted Python **keyring abstraction with an explicitly selected approved OS backend**: Windows Credential Manager on Windows, macOS Keychain and Linux Secret Service when available. This is one justified dependency, to be added only in AST-07 after a packaging/security review. No generic auto-selected plaintext, third-party fallback, null-success or arbitrary plugin backend is acceptable. Unsupported/headless environments remain local-only; tests use an injected in-memory fake. No silent `.env` fallback.

Windows target namespace: `Newsroom/<installation-uuid>/<connection-id>/<credential-version>`, bound to the runtime owner's account. API performs create/replace/delete; workers and API execution services read just in time under that same owner. Scheduler has no need to read provider secrets. An API on another Windows account must report unavailable credentials rather than copy them.

[Microsoft CredWriteW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew) associates credentials with the current token's logon session; this is why startup identity and credential qualification belong together. [Keyring documentation](https://keyring.readthedocs.io/en/latest/index.html) describes OS backends and security considerations; explicitly test the packaged backend rather than trusting development defaults.

Alternative: current-user DPAPI in a separate restricted file. It avoids a Python abstraction but adds blob lifecycle, filesystem ACL, exclusion and platform-specific code. [Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) normally binds decryption to matching user credentials/computer; machine-wide protection is inappropriate here. Prefer Credential Manager because no app-managed credential file enters the backup path. Neither protects against malicious code already running as the same user; do not promise application-exclusive isolation or Python memory zeroization.

## Save, rotate and remove safely

Key store and SQLite do not share a transaction. Write a new versioned secret first; commit its reference and new generation only if that succeeds. On DB failure, remove the new orphan or record a safe cleanup obligation; the prior reference remains authoritative. On successful rotation, retire the old version after in-flight work releases it. Never overwrite an active secret in place while callers could resolve a stale configuration revision.

Removal first disables/reroutes new calls transactionally and advances generation, then deletes the secret. Failed deletion is shown as “disabled; credential removal needs retry,” not falsely reported as removed. Connection metadata may remain as a tombstone where audit foreign keys require it. Existing analysis/history must retain provider/model identity. Deleting a connection never deletes evidence, analyses or paid invocation history.

## Reload and process ownership

At every new AI operation/job boundary, resolve one immutable generation snapshot. Pin connection/model/prompt/capability/generation into invocation identity. Build clients lazily and retire obsolete clients after in-flight operations. All API and worker paths use the same resolver; no construction-time unrelated environment authority remains.

Edits apply to new work without process restart. Running work completes under the old snapshot and displays that fact; “applied” must not claim to revoke a request already sent. A disable takes effect before the next paid reservation, rechecking the authoritative route/paid switch inside the reservation boundary. Report effective and pending generation per component. Backend/runtime updates may require a managed Restart action, but normal provider edits should not.

Environment migration: recognize legacy presence without showing values. Do not import automatically. Provide an explicit one-time import action for the runtime owner, moving secret to the OS store and non-secret config to metadata with paid routing still off until intentionally enabled. Until import, show a clearly labeled legacy configuration source; an explicit managed-config marker prevents environment variables from reactivating a removed provider. Dev-only environment injection may be an explicit mode, but cannot override managed production settings. No writing shell profiles or copying secrets into launch commands.

## Routing and compatibility scope

First completion slice supports Local/Offline and OpenAI-compatible **Article Analysis** through the existing adapter. OpenAI, OpenRouter and other endpoints are connection presets only when the configured endpoint/model passes the specific structured-output contract. Chat-completions syntax alone is not proof of JSON-schema compatibility. Model entry is editable text; model enumeration is optional and never implies every listed model supports the capability.

Loopback local endpoints may be keyless only when explicitly configured; allow HTTP only for deliberate loopback use, never arbitrary private/LAN addresses by default. Hosted URLs require HTTPS. Enforce redirect/destination checks so a base-URL edit cannot forward a stored secret elsewhere; require credential reconfirmation on host change. Do not expose arbitrary headers or provider payload fields in v1. Test DNS/redirect/credential-forwarding behavior with a mock transport. Use existing acquisition security principles without treating article-fetch policy as automatically suitable for trusted loopback AI endpoints.

Direct Anthropic/Gemini SDKs are deferred: different request, tool and output contracts need actual adapters; do not advertise unsupported compatibility. No embedding/entailment/relevance remote switch merely for coverage. Add normal Ask remote synthesis only as the separately gated AST-21 slice after user-value evidence; reuse shared configuration/budget/security contracts. Eval provider injection stays independent and frozen for comparisons.

Fallback: default local when provider is disabled/removed/unconfigured or budget disallows a new call. Clearly label the effective local result and reason. Remote failure may produce a separately identified local fallback only if safe and enabled; it must never fabricate remote success, retry an uncertain billed request, or reuse an old analysis identity with new inputs. In contract-bound evaluation, any fallback invalidates the requested comparison. Local failure stays a truthful failure/refusal; no new paid permission is inferred.

## API and frontend contracts

All routes below are proposed under `/api/v1`, use existing session/CSRF guards for writes, restrictive validation, safe error codes, `Cache-Control: no-store`, and no request-body logging.

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

Settings → AI Providers explains offline operation and the precise improvement (structured Article Analysis initially). Add/Edit/Test/Enable/Disable/Model/Remove credential/Set default controls, masked fixed placeholder, configured state, validation timestamp and generation, effective routing, paid switch, limits, estimated versus actual usage, safe failure explanation. Raw key exists only in the password input/request until submission; clear it afterward, never persist it in browser storage or global state. Server validation errors must not echo input; Pydantic's raw `input` details require special handling for these request models. Shared Settings loading failures must not hide the entire provider state.

## Acceptance — Add AI Provider

In an isolated installed runtime: Settings → AI Providers → Add compatible connection → enter test credential → configure model → test explicitly → enable paid routing intentionally within a small cap → process a relevant document and verify the worker's effective connection/model/generation plus durable invocation. Inspect browser responses/storage, DB, logs, telemetry, logical export, full backup and frontend build for a sentinel credential: absent everywhere except the submitted request and OS store. Then disable/delete, process new work locally, verify no new remote call and a clear local fallback reason. Reopen/restart and repeat; removal remains effective despite legacy environment variables. Use fake providers in CI; an actual paid end-to-end trial needs separate explicit authorization.
