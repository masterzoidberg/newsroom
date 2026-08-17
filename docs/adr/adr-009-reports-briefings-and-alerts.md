# ADR-009 — Evidence-Bound Reports, Briefings, and Alerts

## Status

Accepted in Phase 11.

## Decision

Persist Living Reports as versioned projections over accepted Claims. Every
revision records its exact Claim-set hash, propositions, required report
sections, closed-world audit result, and immutable causes for material change.
An explanation is valid only when it resolves to accepted supporting evidence;
Story evolution events are eligible only when they link back to that evidence.

Generate daily and weekly briefings from current material report revisions for
selected Monitors. Use an IANA timezone for local period boundaries and a
unique period key for deterministic regeneration. Rank by the strongest
evidence, contradiction, correction, corroboration, or material-update cause,
not article or keyword volume.

Persist alert rules and alerts in SQLite. Rules may target all reports, one
report, one Monitor, or one Story and may filter event types and minimum
importance. Each alert has a stable dedupe key, acknowledgement state, and
per-channel delivery records. In-app delivery is always durable; browser
delivery is optional and records permission denial, offline state, or failure
without affecting the in-app alert. Email, SMS, public publishing, and raw
article-volume alerts remain out of scope.

## Consequences

- Restarting or regenerating a report, briefing, or alert does not erase its
  audit trail or create duplicate material notifications.
- Report prose remains bounded by the accepted evidence ledger and can be
  rejected transactionally when a proposition or change cause is unsupported.
- Browser/PWA delivery can be added at the client boundary without coupling
  the core to a push provider.
- A future report renderer can replace the stored section serializer only if it
  preserves immutable Claim/evidence references and the closed-world audit.
