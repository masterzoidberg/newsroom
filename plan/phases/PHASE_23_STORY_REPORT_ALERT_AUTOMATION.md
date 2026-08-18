# Phase 23 — Story, Living Report, and Alert Automation

## Objective

Connect verified analysis into one unattended Story → Report → in-app Alert
workflow.

## Why this phase exists

Story evolution, Living Reports, and AlertService are implemented but isolated.
Current monitored changes do not invoke them automatically.

## Current-state gap

`StoryEvolutionService.process()` and `LivingReportService.generate()` are
manual/API paths. Alert emission is invoked from the report-generation route,
not from a completed processing pipeline.

## Scope

- Build idempotent downstream orchestration after verified Claims.
- Resolve/create/update Stories and record chronology/evolution events.
- Apply contradiction, correction, corroboration, novelty, and materiality
  rules.
- Generate a Living Report revision only when warranted.
- Emit durable in-app Alerts with evidence causes and deduplication.
- Preserve job/retry/recovery/cancellation semantics.

## Non-goals

- No browser Push implementation; Phase 28 owns delivery.
- No external research or Source discovery.
- No free-standing report prose outside accepted Claims.

## Existing components to reuse

`StoryEvolutionService`, `LivingReportService`, `AlertService`, Evidence/Claim
closed-world checks, JobService completion hooks, processing records, and
existing dedupe keys.

## Required implementation

Consume one verified processing result at a time. Resolve Story identity,
record an immutable observation/evolution event, determine materiality, and
conditionally generate a report revision. Alert causes must reference the exact
report revision, Story event, Claim, EvidenceSpan, and DocumentVersion that
caused the alert. Replays must not duplicate any durable object.

## Data model/migration expectations

Reuse existing Story, report, cause, alert, and delivery tables. Add an
orchestration/audit record or unique idempotency key only if existing records
cannot prove completion. Do not mutate immutable historical revisions.

## Runtime integration

The processing workflow invokes this phase only after Phase 22 verification.
Failures must leave the processing result retryable or partial and must not
advance the monitor to a false success state.

## Security/privacy considerations

Reports remain closed-world and evidence-bound. Alert content must avoid
unnecessary sensitive source text. Preserve authorization and deduplication;
never publish externally.

## Tests

- New Story, corroboration, correction, contradiction, and material update.
- Idempotent replay of the same processing result.
- Report revision only for material changes.
- Exact cause chain to EvidenceSpan and DocumentVersion.
- Alert deduplication and durable in-app delivery.
- Processing retry/recovery does not duplicate Stories, revisions, or alerts.

## Acceptance criteria

```text
static Source change
  → Monitor → acquisition → processing → relevance → analysis
  → verified Evidence/Claims → Story → report revision → in-app Alert
```

After initial Monitor setup, no manual API calls are permitted.

## Live-test gate

After Phase 23, Live Test C is permitted against a controlled public Source or
fixture: the full loop must reach an in-app alert without manual intervention.

## Dependencies

Phases 18–22.

## Exit criteria

The first true unattended Source-to-Report acceptance test passes with a
complete evidence cause chain. Phase 24 may expand discovery and vocabulary.
