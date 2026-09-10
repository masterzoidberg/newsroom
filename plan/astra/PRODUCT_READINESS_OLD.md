# Product readiness

## Daily-use definition of done

All gates need linked evidence against a named installed artifact and runtime. Tests passing alone do not satisfy this checklist.

| Gate | Acceptance | Tasks |
|---|---|---|
| Start/use/restart | owner uses one shortcut; required components healthy; repeated/concurrent launch reuses; foreign port gives actionable diagnosis | AST-02–05,19 |
| Background | browser closed, locked desktop, wake and reboot/sign-in recover with no duplicate work; pre-login/sleep limitations disclosed | AST-03–05,19 |
| Status/recovery | owner can identify collection vs processing failure and retry/stop/restart appropriately without terminal | AST-04,14,19 |
| Local operation | no provider configured still permits Watch, collection, local analysis, evidence review, Ask/refusal, reports/alerts when qualifying | AST-09,12,15,19 |
| Configuration | named Watch/source and cadence creation without raw IDs; disable/edit persistence; paid choices explicit | AST-11,12 |
| AI providers | special Add AI Provider test passes end to end with secure store, real worker authority, generation/reload, disable/removal | AST-06–11 |
| Costs | global/work bounds, concurrent/restarted calls, failed/uncertain calls and validation calls counted correctly; estimates labeled | AST-08,10,11 |
| Evidence | source/version/exact excerpt inspectable; AI candidate remains subject to promotion checks; unsupported/no-data states honest | AST-15,19 |
| Daily value | a sustained owner workflow produces reviewed useful changes with denominators and no unacceptable trust regression | AST-16–18 |
| Appearance | complete dark-experience matrix, including phone Settings overlap, focus/contrast/zoom and failure states | AST-13,19 |
| Recovery/data | owner creates verified backup and rehearses restore/update using clear UI; secrets absent from all app backups/exports | AST-07,14,19 |
| Mobile/PWA | supported phone connection/install documented, updates recover, offline shell explicitly limited, no stale mixed-version app | AST-13,19 |

Daily-use engineering candidate can be ready before the frozen observation ends. Do not call it a value-qualified release until AST-18. Earlier trial can continue untouched while isolated improvements are built. A changed runtime/provider/source set starts a documented segment; a product improvement is not permission to contaminate the frozen evaluation.

## Commercial-pilot definition of done

Daily-use gates plus a small, bounded pilot with actual target users:

- A precise audience and promise, supported Windows/browser versions, local-data and account ownership model, source restrictions and offline limitations.
- Participants can install, get a first useful Watch, recover and uninstall without engineering intervention or losing data unexpectedly.
- A measured willingness-to-pay test and retention behavior; no invented traction, price or conversion benchmarks.
- Safe diagnostics export, update/rollback policy, deletion/export and credential-removal behavior, dependency/license/distribution review and security review of provider/lifecycle APIs.
- Explicit treatment of acquisition rights, source terms and privacy claims with appropriate legal review before commercial distribution; do not present this audit as legal advice or clearance.
- A tested support boundary and effort log. If support/onboarding outweigh measured value, simplify or stop.
- Distribution decision based on signed/verified artifact needs and realistic support capacity; no public release in this audit.

No enterprise SSO, teams/RBAC, shared cloud corpus, billing platform, marketplace, broad provider SDK suite or always-on cloud agents are required for the pilot. A manually administered, bounded commercial test is sufficient once real value is established.

## Release verdict vocabulary

Engineering baseline verified ≠ installed candidate qualified ≠ daily-use value accepted ≠ commercial pilot justified. Each has its own evidence. Unknown/no eligible events means inconclusive, not success and not failure.
