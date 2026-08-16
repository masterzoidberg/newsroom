# Phase 08 Review — AI Through Persistent Monitoring

## Verdict

**Approved.** No Critical or Required findings remain. Phase 09 was not started.

Reviewed range:

- accepted Phase 04 baseline `65f083e` / review record `2d91595`;
- Phase 05 implementation `d7a0885`;
- Phase 06 implementation `0f2e7fb`;
- Phase 07 implementation `c11d125`;
- Phase 08 implementation `3f4621d`;
- review fixes `a71dc7f`.

## Findings

### Required — resolved

1. **Acquisition hostname resolution could bypass the SSRF boundary.**
   URL validation rejected literal private, loopback, link-local, reserved, and
   local hosts, but the standard transport did not validate resolved addresses.
   A hostname resolving to a non-public address could therefore reach an
   internal service. The transport now resolves and rejects any non-public
   address before both the initial request and every redirect. A deterministic
   regression test covers a public-looking hostname resolving to loopback.
   Fixed in `a71dc7f`.

2. **Low-confidence monitor classification could activate relevance.**
   The final local classifier stage accepted `relevant=True` regardless of its
   confidence. It now requires confidence at or above the scope threshold;
   lower-confidence output fails closed as non-relevant. Fixed in `a71dc7f`.

3. **A monitor could be re-enabled after its target was deleted.**
   Creation and scheduler execution validated target availability, but the
   explicit enable path did not. Re-enabling now revalidates the target in the
   same write transaction and rejects unavailable targets. The scheduler's
   existing deletion/disable fallback remains in place. Fixed in `a71dc7f`.

### Optional / non-blocking

1. The local AI defaults are deliberately lexical and templated. ADR-003 and
   the benchmark artifact state those limits; no hosted provider is configured
   in the production API path.
2. The project uses setuptools and has no Poetry `format` or `test` commands.
   The repository's canonical Python, evaluation, frontend, audit, and diff
   checks passed instead.
3. TestClient emits the existing HTTPX `app` shortcut deprecation warning. It
   does not affect the reviewed behavior.

## Logical review

### AI boundaries and evidence safety

- Capability outputs are validated by strict Pydantic models before domain use.
  Malformed output, provider exceptions, timeouts, low confidence, disabled
  routes, paid-disable state, and exhausted route budgets fail safely and write
  bounded telemetry.
- The shipped API constructs only local capability providers. Hosted adapters
  are optional injection points and cannot be selected by request data.
- AI extraction and synthesis produce proposals only. Persistence is delegated
  to the Phase 04 Evidence service, which revalidates Claim state, exact Evidence
  spans, accepted Claim sets, synthesis citations, and immutable revisions in a
  single transaction.
- The offline benchmark is deterministic, uses fixed cases and no network, and
  exactly matches `evals/benchmarks/phase05_ai_benchmark.json`. ADR-003 records
  the selected defaults and their measured limitations.

### Acquisition security and correctness

- Only HTTP(S) is permitted. Canonical URLs remove credentials, fragments,
  default ports, tracking parameters, and trivial path drift before identity
  checks.
- Domain allow/deny rules, literal and resolved-address SSRF checks, redirect
  limits, redirect revalidation, timeouts, declared and streamed byte limits,
  bounded XML entry counts, and bounded HTML node/text extraction are enforced.
- Active/embedded HTML is dropped. Article bodies are not persisted as document
  metadata; acquisition events retain bounded provenance, hashes, response
  metadata, and failure attribution.
- Conditional requests use ETag/Last-Modified. Raw and normalized hashes make
  unchanged retrieval cheap, while changed normalized content creates an
  immutable DocumentVersion with its acquisition provenance.

### Durable concurrency and economics

- Job claims, lease recovery, budget reservation, attempt creation, state
  transition, cancellation, and scheduler ticks use short SQLite write
  transactions. Worker handlers run after the claim transaction closes.
- Claims are serialized with `BEGIN IMMEDIATE`; lease ownership guards
  completion. Expired attempts release reservations and transition to bounded
  backoff, terminal failure, or cancellation according to persisted state.
- Idempotency keys and atomic monitor schedule advancement prevent duplicate
  ticks from creating duplicate work. Retry counts and backoff are bounded.
- Global, policy, Job, and Research Question limits include active reservations
  and attributed provider usage. Paid work is disabled by default, and planned
  paid requests are rejected atomically before dispatch when disabled or over
  cap.

### Monitor scope and relevance

- Topic, Subject, Story, Source, and Research Question targets are validated on
  creation; enable now revalidates; scheduler fallback disables unavailable,
  deleted, disabled, or abandoned targets before enqueue.
- Pending and rejected suggestions never enter Topic vocabulary. Approval is a
  separate authenticated action that appends a visible scope-history version.
- Exclusions win before every positive relevance stage. Exact terms,
  vocabulary, entities, concepts, semantic similarity, and the bounded local
  classifier execute in order; invalid and low-confidence results fail closed.
- Adaptive cadence is derived from append-only activity and remains clamped to
  policy minimum/maximum bounds. Retirement clears the next run and prevents
  further scheduling.

## Verification

- `python -m pytest -q` — pass (248 tests);
- focused Phase 05-08 suite — pass (42 tests);
- `python -m compileall -q newsroom` — pass;
- `python -m newsroom.evals validate` — pass (30 cases);
- `python -m newsroom.evals replay multi-outlet-hermes-v0200` — deterministic
  replay hash `54eeacbd32f04ffc83844b27ad972e075c3075988eb6da82c4dac03d51b55776`;
- `python -m newsroom.ai_benchmark` — pass and exact committed-artifact match;
- `npm run typecheck` — pass;
- `npm run build` — pass;
- `npm audit --audit-level=high` — 0 vulnerabilities;
- `git diff --check` — pass.

The focused suites reproduce offline acquisition, malformed/oversized/redirected
content, unchanged and mutated documents, AI failure/timeout/low-confidence and
local-only behavior, worker crash/lease recovery, retry exhaustion,
cancellation, duplicate scheduler ticks, disabled/deleted monitor targets,
scope approval/rejection, adaptive cadence bounds, and paid budget exhaustion.

## Accepted evidence

The accepted Phase 04 evidence metrics remain unchanged: the 30-case corpus is
valid, the reference replay hash is stable, AI synthesis remains closed-world,
and no automatic merge path was introduced. Phases 05-08 work together with
hosted providers disabled and no network or credentials required for tests.

Accepted implementation commit:
`a71dc7f1de382732c2dc847d77fd9fc27da5f20d`.

