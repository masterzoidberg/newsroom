# ADR-006 — Persistent monitors and semantic relevance

## Status

Accepted for Phase 08.

## Context

Persistent monitoring needs a durable policy, a validated target, and a clear
record of what scope was active when each check ran. Scope suggestions must not
turn into new work merely because a local or AI-assisted heuristic proposed
them. Relevance also needs a predictable local path before any future paid or
provider-specific classifier.

## Decision

Phase 08 adds migration 0007 and the `newsroom.monitoring` service boundary:

- `MonitoringPolicyService` validates allowed channels, cadence bounds,
  acquisition/local-model/paid budgets, backoff rules, and retirement criteria.
- `MonitorService` validates live Topic, Subject, Story, Source, and Research
  Question targets, stores an immutable initial scope snapshot, records
  immutable activity, and adapts cadence only within policy bounds. Consecutive
  errors can retire a monitor. The durable scheduler suppresses unavailable or
  disabled targets before inserting work and copies only the policy budget into
  the monitor job.
- `ScopeSuggestionService` stores typed pending candidates for terms, synonyms,
  acronyms, aliases, broader/narrower/related concepts, ambiguity, and
  exclusions. Only explicit approval can add an activating `topic_terms` row;
  rejected and informational ambiguity suggestions remain inert.
- `RelevanceCascade` evaluates explicit exclusions first, followed by exact
  terms, vocabulary, entities, concepts, local semantic similarity, and finally
  a local relevance classifier. The cascade has no paid fallback and returns a
  reviewable stage, score, and matched-term record.

## Consequences

Monitoring survives process restarts and produces user-visible scope and
activity history. Quiet monitors back off, relevant monitors accelerate, and
repeated errors can retire without an unbounded retry loop. Scope changes are
auditable, but a pending or rejected suggestion cannot broaden a monitor.
Alerts, reporting, recursive research work, and external provider execution
remain later-phase concerns.

## Evidence

Offline tests cover migration idempotence, target validation, pending/rejected/
approved suggestions, immutable scope and activity history, every relevance
cascade level, bounded cadence, retirement, disabled-target suppression, and
authenticated API access:

```powershell
python -m pytest -q tests/test_phase08_monitors.py
```
