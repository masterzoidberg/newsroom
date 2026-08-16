# ADR-001 — Fully Standalone / Hermes Reference Only

- **Status:** Accepted
- **Date:** 2026-08-16
- **Deciders:** Standalone Newsroom implementation lead

## Context

The completed Hermes Newsroom (v1) is a successful internal/reference
implementation hosted inside the Hermes agent runtime. It depends on Hermes for
plugin registration, Dashboard SDK, session tokens, Cron bridging, model tools,
skills, and `HERMES_HOME` profile semantics.

The standalone product must be independently installable, deployable, and
maintainable without Hermes.

## Decision

Standalone Newsroom is a fully independent application. Hermes Newsroom is
retained as a **reference implementation, benchmark, and source of proven
deterministic logic only**. It is not a runtime dependency, deployment
dependency, authentication boundary, scheduler, research runtime, or data owner.

## Consequences

- No production code imports Hermes modules or honors `HERMES_HOME`.
- The standalone runtime uses its own explicit roots (`%LOCALAPPDATA%\Newsroom\{dev,prod}`).
- Proven deterministic v1 modules (URL normalization, headline similarity,
  event-signature helpers, conservative dedupe, SQLite storage patterns) were
  copied unchanged or adapted, each justified in `docs/PORTING_AUDIT.md`.
- v1 data is treated as evaluation material (read-only) and a potential optional
  import source, never as the standalone database.
- The v1 baseline in `newsroom.evals.baseline` scores v1's *actual* behavior
  against human gold labels to quantify what the standalone product must beat.
