# Autonomous execution runbook

## Goal

Minimize handoffs without turning the entire roadmap into one unsafe, context-heavy session. The efficient unit is one coherent run containing several bounded tasks, one commit per task, focused verification after each commit, and a full checkpoint at the end.

Default cadence: one Codex chat per run. A chat may continue into the next run automatically when context is healthy and the checkpoint is green. It must preserve a durable handoff report before context becomes unreliable.

## Continue and stop policy

Codex continues without asking between tasks when:

- the next dependency is satisfied;
- the task contract and acceptance are already explicit;
- changes stay within the named files/subsystem;
- focused verification passes;
- no paid call, production/trial contact, deployment, destructive operation or new product decision is required.

Codex must stop only when:

- a test or acceptance gate remains failed after focused root-cause diagnosis;
- a product decision changes user-visible semantics or data contracts and the plan does not already decide it;
- physical wake/sign-in/phone evidence or human scoring is required;
- authorization is required for paid execution, trial access, deployment, merge or destructive action;
- unrelated tracked changes overlap the required edit;
- the next change would exceed the task boundary or require a new dependency/service;
- remaining context is insufficient to execute safely after writing a durable handoff.

A checkpoint failure does not authorize broad cleanup. Preserve the failed output, create one bounded defect task, fix it, rerun focused proof, then rerun only the invalidated checkpoint.

## Commit and evidence policy

For every AST task inside a run:

1. Confirm dependency head and clean owned surface.
2. Implement only that task.
3. Run focused tests and static checks relevant to changed files.
4. Commit with the AST ID.
5. Append compact evidence: head, files, commands, results, limitations.
6. Continue to the next task automatically.

Do not update the canonical ledger after every small commit. Update it atomically at the end of the run, marking only tasks with complete evidence. This removes repetitive planning churn while keeping rollback points.

## Optimized run sequence

### Run 0 — Foundation reconciliation

**Includes:** current backend/lifecycle job, AST-05 evidence reconciliation, AST-23/24 acceptance reconciliation, adoption of the reworked ledger.

**Execution:** Sequential. Do not duplicate work still running in another chat.

**Exit:** Exact heads/ancestry recorded; retained full backend result classified; physical evidence truthfully classified; one canonical ledger; AST-25 READY only if permitted by Gate 0.

**Mandatory stop:** Any remaining engineering backend failure. Physical-only evidence may remain a release blocker while product development continues only if the owner explicitly records that decision.

### Run 1 — Complete the first Watch

**Includes:** AST-25 → AST-26 → AST-27 → C1.

**Why grouped:** Same setup view/state machine and direct dependency chain. Separate chats would repeatedly reload identical context.

**Commit boundaries:** One commit each for Sources, cadence, and Review/Start. Do not combine them into one unreviewable diff.

**Checkpoint:** Full backend; frontend typecheck/build; one deterministic empty-to-first-result browser journey at desktop and measured 390 CSS pixels; server-state/idempotency assertions.

**Exit:** First Watch accepted. Continue automatically to Run 2 when green.

### Run 2 — Returning-value spine

**Includes:** AST-33 → AST-34 → AST-35.

**Why grouped:** These form the data-to-UI spine needed by reports, alerts, Story changes, search and questions.

**Commit boundaries:** Review cursor; since-visit Home; exact evidence navigation.

**Checkpoint:** Late-arrival/timezone/pagination tests plus returning-user browser journey and exact Claim/span/source traversal.

**Exit:** Freeze the AST-35 API/navigation contract. This is the synchronization point for Run 3.

### Run 3 — Core capability waves

Start from the accepted AST-35 head. Parallelize only the first wave and use separate worktrees/branches with declared file ownership.

#### Wave 3A — Safe parallel work

- **Workstream A:** AST-36 Living Reports, then AST-40 Story changes. Their primary frontend/backend files are distinct after the AST-35 contract is frozen.
- **Workstream B:** AST-42 search/history. Owns Workbench/Ask/ReviewViews/knowledge surfaces only.
- **Workstream C:** AST-43 → AST-44 recovery. This may start earlier after Gate 0, but must integrate here at latest.

Each workstream runs its focused tests and produces one commit per AST task. Do not allow concurrent edits to shared types, navigation or central API files without assigning one integration owner.

#### Wave 3B — Integrate, then alerts

1. Integrate A/B/C sequentially onto the accepted spine.
2. Run focused integration tests after each integration.
3. Execute AST-39 after AST-36 is integrated because both may touch reporting domain code.

**Checkpoint:** Lane-level journeys for reports, Story corrections, alerts, search and recovery; then one combined backend/frontend checkpoint.

**Exit:** Core capabilities integrated with no overlapping uncommitted work.

### Run 4 — Local Core Release

**Includes:** AST-45 bounded Core audit → AST-46 → AST-49 → AST-47 Core checkpoint → AST-48 engineering checkpoint.

**Important:** AST-45, AST-47 and AST-48 are evidence checkpoints. They may open bounded defect tasks but must not become refactor buckets. AST-49 documents only qualified behavior.

**Checkpoint:** Named isolated artifact; journeys A/C/E/F; installed lifecycle; backup/restore/update; desktop/phone viewport; PWA cache/update; accessibility; full quality suite; retained hashes/results.

**Exit:** Local Core Release candidate. If green, continue to Run 5 unless the user requested a release review stop. Physical-device actions that Codex cannot perform are reported as the only remaining items, without blocking unrelated assisted implementation.

### Run 5 — Managed AI security boundary

**Includes:** AST-06 → 07 → 08 → 09 → 10 → 11 → C3.

**Why one run:** The metadata, vault, admission, resolver, validation API and settings UI are one security protocol. Repeated handoffs increase the chance of inconsistent assumptions.

**Commit boundaries:** One commit per AST task. Run migration/security/failure tests after each backend task. Do not wait until AST-11 to test secret leakage or concurrent admission.

**Checkpoint:** Full provider safety matrix with fake transport and sentinel; database upgrade/backup/export checks; actual worker reload behavior; Settings browser journey. No real provider call.

**Mandatory stop:** Any unplanned provider, credential backend, schema or spending-policy decision.

### Run 6 — Assisted intelligence waves

#### Wave 6A — Vocabulary and candidate Sources

AST-28 → 29 → AST-30 decision checkpoint → 31 → 32.

AST-30 is time-boxed. If existing adapters suffice, decide and continue in the same run. Stop only if a new paid search provider, service or materially different data contract is required.

#### Wave 6B — Alternate Watch intents

After their reworked dependencies are present, AST-52 and AST-53 can run independently of Wave 6A. AST-41 can run from AST-35/27. Integrate these before AST-54.

#### Wave 6C — Scope and Ask

AST-50 decision checkpoint → AST-51; AST-54 after AST-41/42.

Parallel execution is permitted only when worktrees do not share `WatchManagementView`, `domain_api.py` or shared frontend types. Because several tasks do share those files, default to two coordinated workstreams, not one agent per task:

- Workstream 1 owns terminology/source/scope changes.
- Workstream 2 owns target types/question/Ask changes.

Integrate one workstream completely before resolving the other’s shared-file changes.

**Checkpoint:** Journeys A–D with fake providers, manual fallback, ambiguity, rejection, refusal, unsafe URL and immutable scope history.

**Exit:** Assisted setup accepted.

### Run 7 — Briefings and engineering completion

**Includes:** AST-37 → AST-38, post-Core accessibility regression for new surfaces, AST-47 full checkpoint, AST-49 assisted documentation update, AST-48 final engineering checkpoint.

**Checkpoint:** Journeys A–F; schedule concurrency/DST/wake/retry; reports/briefings/alerts/questions/search; full backend/frontend/migration/security/recovery/browser suites; named artifact and retained evidence.

**Exit:** Engineering-complete app. AST-55 remains an enhancement and does not block completion.

### Run 8 — External value qualification

**Includes:** AST-16, AST-17 and AST-18 only when their real observation, eligible inputs, paid authorization and human scoring are available.

This is not an autonomous coding run. Codex may prepare or analyze authorized evidence, but must stop for unavailable human or external inputs. Append the verdict to release evidence without rerunning unrelated engineering checks unless the artifact or requirements changed.

## Expected handoff reduction

The old operating pattern could require a new chat for nearly every one of 30+ records. This runbook reduces normal engineering coordination to approximately eight durable runs:

1. foundation reconciliation;
2. first Watch;
3. returning-value spine;
4. core capability waves;
5. Local Core qualification;
6. managed AI foundation;
7. assisted intelligence waves;
8. briefings/final engineering qualification.

External value qualification remains separate by design. Parallel work can shorten Runs 3 and 6, but excessive concurrency around shared frontend/API files will create more integration work than it saves.

## Prompt template for each run

```text
Execute Run <N> from:
G:\Projects\Newsroom -v2\plan\plan-rework\AUTONOMOUS_EXECUTION_RUNBOOK.md

Read the reworked completion plan, transition state, canonical ledger, relevant AST task contracts, repository instructions and current Git/worktree state first.

Continue autonomously across every task in this run. Make one bounded commit per AST task, run focused verification after each, retain evidence, and update the ledger atomically at the run checkpoint. Do not stop merely to ask whether to continue when the next dependency is satisfied and the checkpoint remains green.

Stop only for the runbook’s mandatory stop conditions. Do not widen scope, weaken acceptance, make paid calls, contact the active trial, deploy, merge to main, perform destructive cleanup or manufacture physical/human evidence.

At completion report exact heads, commits, changed files, focused and checkpoint results, retained artifacts, unresolved risks, statuses and the next run.
```
