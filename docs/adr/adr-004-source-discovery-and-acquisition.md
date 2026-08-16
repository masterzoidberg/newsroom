# ADR-004 — Bounded source discovery and acquisition

## Status

Accepted for Phase 06.

## Context

Newsroom needs cheap, repeatable source monitoring without turning retrieval into
an open-ended crawler or storing unreviewed article bodies. Retrieval must be
observable, conditional where possible, safe against malformed input, and
connected to the existing immutable `DocumentVersion` and Evidence Ledger
boundaries.

## Decision

Phase 06 implements a narrow acquisition service in `newsroom.acquisition`:

- RSS and Atom feeds are parsed offline with the standard-library XML parser.
  Links are canonicalized through the existing URL normalizer and feed entries
  become metadata-only `DocumentVersion` records.
- Direct HTTP and explicit page acquisition use a replaceable `HttpTransport`.
  The default transport follows only a bounded number of redirects, applies
  domain allow/deny policy to the request and final URL, enforces response byte
  and timeout limits, rejects literal private/loopback/local targets, and never
  executes browser JavaScript.
- ETag and Last-Modified values are persisted in acquisition provenance and
  replayed as conditional request headers. A 304 creates an observation but no
  new version. A changed body creates a new immutable `DocumentVersion`; an
  unchanged body creates only an `unchanged` observation.
- Raw and normalized content hashes identify retrieval and normalized content
  separately. HTML is reduced to bounded title/text metadata by a parser that
  drops active or embedded content. Article bodies are not copied into the
  normalized metadata JSON.
- `acquisition_events` is append-only and records request/final URLs, channel,
  response status, conditional metadata, hashes, size, outcome, and bounded
  failure information. A failed or blocked retrieval cannot partially create a
  document version.
- `source_profiles` stores separate dimensions for source type, coverage,
  acquisition methods, activity, failures, duplication behavior, and observed
  usefulness. It deliberately does not compute a universal trust score.
- `source_suggestions` remains pending until an authenticated user explicitly
  approves or rejects it. Approval does not automatically create a Source.

The default policy is suitable for local/offline fixtures and can be injected
for tests or a deployment-specific allowlist. Network work is invoked manually
through the authenticated API in this phase; durable scheduling is deferred.

## Consequences

Normal monitoring can use feeds and bounded HTTP with no third-party client or
browser dependency. Repeated polling avoids reprocessing unchanged material,
while provenance remains sufficient to explain what was requested and observed.
The system intentionally retains only bounded metadata at this layer; exact
article excerpts must be explicitly selected into the Evidence Ledger by a
later workflow. Source quality remains multidimensional and reviewable instead
of collapsing coverage and reliability into an unsupported score.

The standard-library parser and lexical normalization are conservative. They do
not provide browser-rendered content, JavaScript execution, or semantic source
quality judgments. Durable jobs, retries/backoff, and richer page monitoring
remain later phases.

## Evidence

Offline tests cover RSS, Atom, malformed and hostile XML, safe HTML extraction,
oversized responses, redirects, conditional 304 responses, changed and
unchanged content, failure provenance, profile counters, suggestion review, API
authorization, and append-only acquisition events:

```powershell
python -m pytest -q tests/test_phase06_acquisition.py
```
