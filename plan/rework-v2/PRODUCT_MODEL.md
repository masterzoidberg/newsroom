# Product model

## Core objects

| User concept | Meaning | Existing machinery / required extension |
|---|---|---|
| Research | Durable user intent and accumulated research history, with its own scope, monitoring state and cost boundary | `watches.id`; retain target pointer to Topic, ResearchQuestion, or another supported legacy target |
| Focus area | User-approved organization, matching explanation and source-coverage category | Versioned Watch scope metadata; no independent Monitor/policy/schedule |
| Update | An evidence-backed development relevant to this Research | Scoped projection of Story events/revisions and eligible Claims; never an unfiltered global Story summary |
| Briefing | Automatically maintained current intelligence for this Research | Watch-owned existing LivingReport, immutable report revisions; scheduled backend Briefings remain delivery digests |
| Source | Identifiable publisher/origin from which material is obtained | Existing Source plus explicit endpoints; origin may differ from discovering feed |
| Source Profile | Explainable identity, role, authority, independence, controls, transparency, strengths and limitations | Append-only detected/AI/user assertions, plus Research relevance and Focus coverage; distinct from operational `source_profiles` |
| Ask | Question answering over the Research's accumulated eligible evidence | Existing Ask with Watch scope and strict evidence closure |
| Evidence | Exact preserved material supporting, contradicting or contextualizing a statement | Existing EvidenceSpan→DocumentVersion→artifact provenance, including feed fidelity and discovery path |
| Open question | A useful unresolved question, not a fact | Existing ResearchQuestion/Gap where applicable, or clearly labeled presentation of unresolved scoped evidence |
| Source approval | Permission to monitor the reviewed endpoint and bounded linked-publication policy in this Research | Candidate review plus historical membership interval; not a factual endorsement |
| User override | User-authored effective assessment that AI cannot replace | Versioned assertion with actor/time/optional reason; clearing is an explicit user action |
| Source health | Whether acquisition works | Per-endpoint attempts and Research check results, using existing acquisition/profile services |

Research identity does not change when its display name, scope, sources or target presentation changes. MVP adds no user-facing retarget operation. Existing Story correction workflows may change target binding while retaining Watch identity and immutable binding history (D20). Question-first Research uses the existing question composition path; users are not forced to choose a backend target type. A question may also remain an open question inside a Topic-backed Research. Do not automatically create a Watch for every question.

## Modes and authority

Manual/basic local: preserve prose, let the user edit name/Focus areas/terms/exclusions, inspect and approve URLs, then monitor. Require a user-confirmed positive matching term before Start; never infer approved scope from a text substring. Local summaries/Ask must disclose their limitations and may refuse for insufficient evidence.

AI-assisted: propose an interpretation, coverage plan, terminology, exclusions and Source assessments. Zero clarification questions for clear intent; one or two only for material ambiguity. The user confirms a structured diff. Capable local providers can later implement the same contracts. Setup never exposes routing IDs.

An AI response, a reachable website, a feed, a source role and a verified quotation are different facts. Verification establishes provenance and the implemented support relationship, not universal truth. “Official source” establishes who stated something, not the truth of everything stated. No numeric truth/reliability score is introduced.

## Invariants

| ID | Binding invariant |
|---|---|
| I01 | Canonical acquisition can be shared; each eligible Research gets its own pinned-scope processing obligation, including on unchanged content. |
| I02 | Detach stops future monitoring for this Research and preserves admitted historical knowledge and source membership history. Reattach opens a new interval. |
| I03 | AI proposals remain proposals; explicit user overrides win and their predecessors remain auditable. |
| I04 | Source reputation/role never mechanically sets Claim truth, acceptance or support state. |
| I05 | Start/Check now schedule bounded durable work through existing scheduler, jobs, retries, leases and budgets. |
| I06 | Ask, Updates, Briefing, explanations and citations obey the same Research evidence boundary; Source/Story membership alone is insufficient. |
| I07 | Scope edits apply to future observations. Historical scope snapshots, evidence and report revisions are not silently rewritten. |
| I08 | Paid/external work needs the applicable explicit authorization and current budget admission; retry, fallback and configuration changes cannot expand it. |
| I09 | Suggestion/inspection never creates accepted Evidence, Claims, active monitoring or hidden article acquisition. |
| I10 | Feed summary/full-feed content/retrieved article are distinguishable evidence representations; later retrieval never alters an older citation. |
| I11 | This check has an immutable expected-work set and durable causal outcomes. Old failures cannot determine its result. Processing is not a terminal outcome. |
| I12 | Pause/detach suppress work not yet admitted to a network/provider operation; already admitted observations may finish under their captured scope and authorization. UI discloses in-flight work. |
| I13 | Global network deduplication never creates uncharged per-Research paid analysis or attribution to paused/unsubscribed Researches. |
| I14 | Replays preserve evidence/analysis/report identities. Historical unknowns remain unknown; migration does not invent prior approval or relevance. |
| I15 | Existing exact-match promotion, correction histories, closed-world synthesis and manual authority checks remain intact. |
| I16 | Normal operation requires no internal IDs; Research/view/evidence locations survive reload, Back and new tabs. |

## Terminology disposition

| Existing term | Disposition | Ordinary presentation |
|---|---|---|
| Watch | Rename in ordinary UI | Research |
| Topic | Hide as setup hierarchy; contextualize in scope | Research subject/interest |
| Subject / Entity | Advanced-only as objects | Recognizable person/company name in content |
| Monitor | Advanced-only | Source checking / monitoring |
| MonitoringPolicy | Hide raw fields | Frequency, cost limit, linked-article permission |
| Source | Keep | Source |
| Source candidate / suggestion | Contextualize | Suggested source; unverified until inspected |
| Source Profile | Keep | Source profile, editable assessment |
| Document | Contextualize | Article, page, report, publication or feed material |
| DocumentVersion / content artifact | Audit-only | Retrieved version; exact content |
| EvidenceSpan | Rename ordinary UI | Evidence / exact excerpt |
| Claim | Contextualize | Statement and support state; Claim in audit |
| Story | Rename ordinary UI | Update / development |
| Story merge/split/event lineage | Advanced-only | Correction explanation where relevant |
| ResearchQuestion / Gap | Contextualize | Open question / missing evidence |
| LivingReport | Hide backend noun | Research Briefing |
| Backend Briefing | Contextualize | Daily/weekly delivery digest |
| Run / Job / attempt / lease | Advanced-only | Check / checking / retrying |
| Attention / review boundary | Contextualize | Needs attention / since last review / mark reviewed |
| Saved / history / workbench | Advanced or contextual | Saved material and provenance when needed |
| Provider / route / capability | Advanced configuration | AI assistance available, basic local analysis, AI & cost |
| Simple / Advanced experience | Keep preference | Advanced tools; not a security boundary |
| Raw settings key/value dump | Remove from ordinary UI | Named preferences only |
| Pending / verified / accepted | Contextualize precisely | Proposed; exact excerpt verified; accepted for synthesis; never “proven true” |

## Coverage and feedback

Coverage counts approved Sources explicitly mapped to Focus areas, not independent confirmations. Show “2 sources; 1 currently unhealthy,” and mark coverage mapping as user-approved or suggested. Do not resurrect the removed coverage ontology. “Not useful” records Research + Update/event + reason + time; it does not automatically change vocabulary, suppress evidence, or retrain anything. Source-wide role overrides are shared across Researches; relevance/coverage overrides are Research-specific, clearly distinguished in the editor.
