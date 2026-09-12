import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiFetch, formatDate, jsonBody, shortId } from "../lib/api";
import type { Claim, DuplicateSuggestion, Story, StoryCorrection, StoryEvidenceResponse, StoryLineage, StoryNavigationContext, Timeline } from "../lib/types";
import { EvidenceView } from "../components/EvidenceView";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";
import { queueDocumentNavigation } from "./DocumentView";

type Corroboration = { publication_count?: number; distinct_source_count?: number; dependency_group_count?: number; largest_group_share?: number; dependency_groups?: Array<Record<string, unknown>> };
type PreviewClaim = { id: string; proposition: string; importance: string; state: string };
type PreviewDocument = { id: string; title: string; source_id: string; source_name: string; published_at?: string | null; retrieved_at?: string | null; first_retrieved_at?: string | null };
type PreviewEntity = { id: string; canonical_name: string };
type MergePreview = { source: Story & { headline?: string }; destination: Story & { headline?: string }; source_claim_count: number; destination_claim_count: number; source_claims?: PreviewClaim[]; destination_claims?: PreviewClaim[]; source_documents: string[]; destination_documents: string[]; source_document_records?: PreviewDocument[]; destination_document_records?: PreviewDocument[]; source_entity_records?: PreviewEntity[]; destination_entity_records?: PreviewEntity[]; expected_claim_moves: string[]; watch_consequences: Array<{ id: string; kind: string; name: string }>; expected_current_state_fingerprint?: string };
type SplitPreview = { source: Story & { headline?: string }; claims: PreviewClaim[]; expected_claim_ids: string[]; current_document_ids: string[]; current_document_records?: PreviewDocument[]; current_entity_ids: string[]; current_entity_records?: PreviewEntity[]; watch_consequences?: Array<{ id: string; kind: string; name: string }> };
type TimelineEvent = Record<string, unknown> & { id?: string; document_id?: string; update_class?: string; event_type?: string; material_change?: boolean; created_at?: string; decision?: Record<string, unknown>; document?: { id?: string; title?: string; source_name?: string; canonical_url?: string } };
type DocumentContext = { publishedAt?: string | null; latestRetrievedAt?: string | null; firstRetrievedAt?: string | null; title?: string; sourceName?: string };

const STORY_NAVIGATION_KEY = "newsroom.story.inspect.v1";

export function queueStoryNavigation(context: StoryNavigationContext) {
  const storyId = context.storyId.trim();
  if (!storyId) return;
  try {
    window.sessionStorage.setItem(STORY_NAVIGATION_KEY, JSON.stringify({
      storyId,
      ...(context.claimId?.trim() ? { claimId: context.claimId.trim() } : {}),
    }));
  } catch { /* The Story ID remains available in the current view. */ }
}

function readStoryNavigation(): StoryNavigationContext | null {
  try {
    const raw = window.sessionStorage.getItem(STORY_NAVIGATION_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as Partial<StoryNavigationContext>;
    if (typeof saved.storyId !== "string" || !saved.storyId.trim()) return null;
    return {
      storyId: saved.storyId.trim(),
      ...(typeof saved.claimId === "string" && saved.claimId.trim() ? { claimId: saved.claimId.trim() } : {}),
    };
  } catch { return null; }
}

function contextualError(caught: unknown, label: string, identifier: string): unknown {
  if (caught instanceof ApiError && caught.status === 404) {
    return new Error(`${label} ${shortId(identifier)} is unavailable. The link may be stale or the record may have been deleted; no evidence is shown as verified.`);
  }
  return caught;
}

function asTimelineEvents(timeline: Timeline | null): TimelineEvent[] {
  return (timeline?.events ?? []) as TimelineEvent[];
}

function timelineClaimId(event: TimelineEvent): string | null {
  const automatic = event.decision?.automatic_story_stage;
  if (!automatic || typeof automatic !== "object") return null;
  const claimId = (automatic as Record<string, unknown>).claim_id;
  return typeof claimId === "string" ? claimId : null;
}

function timelineDocumentId(event: TimelineEvent): string | null {
  if (typeof event.document_id === "string") return event.document_id;
  return typeof event.document?.id === "string" ? event.document.id : null;
}

function readableUpdateClass(event: TimelineEvent): string {
  return String(event.update_class ?? event.event_type ?? "Story event").replace(/_/g, " ");
}

function previewStoryName(story: Story & { headline?: string }): string {
  return story.headline?.trim() || shortId(story.id);
}

export function StoryEvidenceView() {
  const [initialContext] = useState(readStoryNavigation);
  const [storyId, setStoryId] = useState(initialContext?.storyId ?? "");
  const [story, setStory] = useState<Story | null>(null);
  const [ledger, setLedger] = useState<StoryEvidenceResponse | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [documentContexts, setDocumentContexts] = useState<Record<string, DocumentContext>>({});
  const [corroboration, setCorroboration] = useState<Corroboration | null>(null);
  const [corrections, setCorrections] = useState<StoryCorrection[]>([]);
  const [lineage, setLineage] = useState<StoryLineage | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicateSuggestion[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState(initialContext?.claimId ?? "");
  const [missingClaimId, setMissingClaimId] = useState("");
  const [targetStoryId, setTargetStoryId] = useState("");
  const [mergePreview, setMergePreview] = useState<MergePreview | null>(null);
  const [splitPreview, setSplitPreview] = useState<SplitPreview | null>(null);
  const [splitGroups, setSplitGroups] = useState("");
  const [extractHeadline, setExtractHeadline] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState(false);

  async function load(identifier: string, requestedClaimId = "") {
    setLoading(true); setError(null); setMergePreview(null); setSplitPreview(null); setDocumentContexts({});
    setMissingClaimId("");
    try {
      const encoded = encodeURIComponent(identifier);
      const [storyResult, evidenceResult, timelineResult, corroborationResult, correctionResult, lineageResult] = await Promise.all([
        apiFetch<Story>(`/stories/${encoded}`),
        apiFetch<StoryEvidenceResponse>(`/stories/${encoded}/evidence`),
        apiFetch<Timeline>(`/stories/${encoded}/timeline`),
        apiFetch<Corroboration>(`/stories/${encoded}/corroboration`),
        apiFetch<{ items: StoryCorrection[] }>(`/stories/${encoded}/corrections`),
        apiFetch<StoryLineage>(`/stories/${encoded}/lineage`),
      ]);
      const documentIds = [...new Set([
        ...asTimelineEvents(timelineResult).map(timelineDocumentId),
      ].filter((value): value is string => Boolean(value)))];
      const contextEntries: Array<[string, DocumentContext] | null> = await Promise.all(documentIds.map(async (documentId) => {
        try {
          const [document, versions] = await Promise.all([
            apiFetch<{ title?: string; published_at?: string | null }>(`/documents/${encodeURIComponent(documentId)}`),
            apiFetch<{ items?: Array<{ retrieved_at?: string | null }> }>(`/documents/${encodeURIComponent(documentId)}/versions?page_size=100`),
          ]);
          const retrieved = (versions.items ?? []).map((item) => item.retrieved_at).filter((value): value is string => Boolean(value)).sort();
          return [documentId, { publishedAt: document.published_at, latestRetrievedAt: retrieved[retrieved.length - 1], firstRetrievedAt: retrieved[0], title: document.title }] as [string, DocumentContext];
        } catch {
          return null;
        }
      }));
      const requestedClaimExists = requestedClaimId.length > 0 && evidenceResult.claims.some((claim) => claim.id === requestedClaimId);
      const nextClaimId = requestedClaimExists ? requestedClaimId : evidenceResult.claims[0]?.id ?? "";
      setStory(storyResult); setLedger(evidenceResult); setTimeline(timelineResult); setCorroboration(corroborationResult); setCorrections(correctionResult.items); setLineage(lineageResult);
      setDocumentContexts(Object.fromEntries(contextEntries.filter((entry) => entry !== null)));
      setStoryId(identifier);
      setSelectedClaimId(nextClaimId);
      if (requestedClaimId && !requestedClaimExists) setMissingClaimId(requestedClaimId);
      queueStoryNavigation({ storyId: storyResult.id, claimId: requestedClaimId || nextClaimId || undefined });
      if (storyResult.lifecycle !== "archived") {
        try { setDuplicates((await apiFetch<{ items: DuplicateSuggestion[] }>(`/stories/${encoded}/duplicates`)).items); } catch { setDuplicates([]); }
      } else setDuplicates([]);
    } catch (caught) {
      setStory(null); setLedger(null); setTimeline(null); setCorroboration(null); setCorrections([]); setLineage(null); setDuplicates([]);
      setError(contextualError(caught, "Story", identifier));
    }
    finally { setLoading(false); }
  }

  useEffect(() => {
    if (initialContext?.storyId) void load(initialContext.storyId, initialContext.claimId ?? "");
  }, []);

  async function inspect(event: FormEvent) { event.preventDefault(); const identifier = storyId.trim(); if (!identifier) { setError(new Error("Enter a Story ID to inspect.")); return; } await load(identifier); }

  async function runCorrection(action: () => Promise<unknown>) {
    setWorking(true); setError(null);
    try { await action(); if (story) await load(story.id, selectedClaimId); }
    catch (caught) { setError(caught); }
    finally { setWorking(false); }
  }

  function selectClaim(claimId: string) {
    setSelectedClaimId(claimId);
    if (story) queueStoryNavigation({ storyId: story.id, claimId });
    window.requestAnimationFrame(() => document.getElementById(`claim-${claimId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  function openEvidence(claim: Claim, evidence: Claim["evidence"][number]) {
    if (!story) return;
    queueStoryNavigation({ storyId: story.id, claimId: claim.id });
    queueDocumentNavigation(evidence.document.id, {
      documentVersionId: evidence.document_version.id,
      evidenceSpanId: evidence.evidence_span_id,
      returnStoryId: story.id,
      returnClaimId: claim.id,
    });
    window.location.hash = "documents";
  }

  async function reassign() {
    if (!selectedClaimId || !targetStoryId.trim()) return;
    await runCorrection(() => apiFetch(`/claims/${encodeURIComponent(selectedClaimId)}/reassign`, { method: "POST", body: jsonBody({ story_id: targetStoryId.trim(), expected_from_story_id: story?.id, reason }) }));
  }

  async function unassign() {
    if (!selectedClaimId) return;
    await runCorrection(() => apiFetch(`/claims/${encodeURIComponent(selectedClaimId)}/unassign`, { method: "POST", body: jsonBody({ expected_from_story_id: story?.id, reason }) }));
  }

  async function extract() {
    if (!selectedClaimId || !story || !extractHeadline.trim()) return;
    await runCorrection(() => apiFetch(`/stories/${encodeURIComponent(story.id)}/extract`, { method: "POST", body: jsonBody({ claim_ids: [selectedClaimId], story: { headline: extractHeadline.trim() }, reason }) }));
  }

  async function previewMerge() {
    if (!story || !targetStoryId.trim()) return;
    setWorking(true); setError(null); setMergePreview(null);
    try { setMergePreview(await apiFetch<MergePreview>(`/stories/${encodeURIComponent(story.id)}/merge-preview`, { method: "POST", body: jsonBody({ destination_story_id: targetStoryId.trim() }) })); }
    catch (caught) { setError(caught); }
    finally { setWorking(false); }
  }

  async function merge() {
    if (!story || !targetStoryId.trim() || !mergePreview) return;
    await runCorrection(() => apiFetch(`/stories/${encodeURIComponent(story.id)}/merge`, { method: "POST", body: jsonBody({ destination_story_id: targetStoryId.trim(), expected_source_updated_at: mergePreview.source.updated_at, expected_current_state_fingerprint: mergePreview.expected_current_state_fingerprint, reason, metadata_decisions: {} }) }));
  }

  async function previewSplit() {
    if (!story) return;
    setWorking(true); setError(null); setSplitPreview(null); setSplitGroups("");
    try { setSplitPreview(await apiFetch<SplitPreview>(`/stories/${encodeURIComponent(story.id)}/split-preview`)); }
    catch (caught) { setError(caught); }
    finally { setWorking(false); }
  }

  async function split() {
    if (!story || !splitPreview) return;
    const groups = splitGroups.split("\n").map((line) => line.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean)).filter((group) => group.length);
    if (groups.length < 2) { setError(new Error("Enter at least two Claim groups, one group per line.")); return; }
    await runCorrection(() => apiFetch(`/stories/${encodeURIComponent(story.id)}/split`, { method: "POST", body: jsonBody({ groups, expected_claim_ids: splitPreview.expected_claim_ids, expected_source_updated_at: splitPreview.source.updated_at, reason }) }));
  }

  const headline = story?.current_revision?.headline ?? story?.headline ?? "Story";
  const summary = story?.current_revision?.summary ?? story?.summary ?? "No summary recorded.";
  const timelineEvents = asTimelineEvents(timeline);
  const timelineClaimIds = new Set(timelineEvents.map(timelineClaimId).filter((value): value is string => Boolean(value)));
  const newClaims = ledger?.claims.filter((claim) => timelineClaimIds.has(claim.id)) ?? [];
  const conflictingClaims = ledger?.claims.filter((claim) => claim.evidence.some((item) => item.relationship === "contradicts")) ?? [];
  return <>
    <PageHeader eyebrow="Review / provenance" title="Story & evidence" description="Inspect Claims, exact spans, corrections, lineage, and current Story membership." />
    <SectionCard title="Open a Story" description="Home, Watch results, and saved review context can open this path without re-entering an ID. Manual entry remains available for recovery.">
      <form className="inline-form" onSubmit={inspect}><label htmlFor="story-id">Story ID</label><input id="story-id" name="story_id" autoComplete="off" value={storyId} onChange={(event) => setStoryId(event.target.value)} placeholder="st_…" /><button className="primary-button" type="submit" disabled={loading}>{loading ? "Inspecting…" : "Inspect Story"}</button></form>
    </SectionCard>
    {loading && <LoadingState label="Following provenance" />}{error && <ErrorState error={error} />}
    {story && ledger && <>
      <section className="story-summary"><div><p className="eyebrow">{story.lifecycle === "archived" ? "Historical Story" : "Current Story"}</p><h2>{headline}</h2><p>{summary}</p>{ledger.claims.length > 0 && <button className="secondary-button" type="button" onClick={() => selectClaim(selectedClaimId || ledger.claims[0].id)}>Review summary Claims</button>}</div><div className="story-summary-meta"><Badge tone={story.lifecycle === "developing" ? "amber" : "mint"}>{story.lifecycle}</Badge><span>{shortId(story.id)}</span></div></section>
      <div className="stat-grid"><div className="stat-card"><span>Current Claims</span><strong>{ledger.claims.length}</strong></div><div className="stat-card stat-mint"><span>Accepted</span><strong>{ledger.claims.filter((claim) => claim.accepted).length}</strong></div><div className="stat-card stat-coral"><span>Contradictions</span><strong>{ledger.claims.flatMap((claim) => claim.evidence).filter((item) => item.relationship === "contradicts").length}</strong></div><div className="stat-card"><span>Distinct Sources</span><strong>{corroboration?.distinct_source_count ?? "—"}</strong><small>{corroboration?.dependency_group_count ?? "—"} known dependency groups</small></div></div>

      <SectionCard title="Changes and disagreements" description="New Claims are identified only when a durable Story timeline event names them. Contradictions below are exact EvidenceSpan relationships, not model summaries.">
        <div className="content-grid">
          <div><h3>New Claims in the Story timeline</h3>{newClaims.length ? <ul className="compact-list">{newClaims.map((claim) => <li key={claim.id}><Badge tone="mint">New Claim</Badge> <strong>{claim.proposition}</strong> · {shortId(claim.id)} · {claim.evidence.length} EvidenceSpan{claim.evidence.length === 1 ? "" : "s"}</li>)}</ul> : <p className="muted">No timeline event currently names a new Claim. Current Claims remain listed below; no newness is inferred from ordering alone.</p>}</div>
          <div><h3>Conflicting evidence</h3>{conflictingClaims.length ? <div className="resource-list">{conflictingClaims.map((claim) => <div key={claim.id}><div className="resource-row"><span><strong>{claim.proposition}</strong><small>{shortId(claim.id)} · {claim.evidence.filter((item) => item.relationship === "contradicts").length} contradictory EvidenceSpan{claim.evidence.filter((item) => item.relationship === "contradicts").length === 1 ? "" : "s"}</small></span></div><ul className="compact-list">{claim.evidence.filter((item) => item.relationship === "contradicts").map((item) => <li key={item.id}><Badge tone="coral">Contradicts</Badge> {item.source.name} · {item.document.title}: “{item.excerpt}” <button className="quiet-button" type="button" onClick={() => openEvidence(claim, item)}>Inspect exact span</button></li>)}</ul></div>)}</div> : <p className="muted">No contradictory EvidenceSpans are linked to the current Claims.</p>}</div>
        </div>
      </SectionCard>

      <SectionCard title="Claims and exact spans" description="Current membership is distinct from historical Story Document observations.">{missingClaimId && <p className="status-note" role="status">Claim {shortId(missingClaimId)} is no longer in this Story’s current evidence ledger. The stale link is retained for explanation, not treated as verified.</p>}<EvidenceView ledger={ledger} selectedClaimId={selectedClaimId} dependencyGroupCount={corroboration?.dependency_group_count} onSelectClaim={selectClaim} onOpenEvidence={openEvidence} /></SectionCard>

      <SectionCard title="Story correction actions" description="Human corrections require an expected current Story when moving Claims, so stale approvals are rejected.">
        <div className="stack-form"><label htmlFor="correction-claim">Claim</label><select id="correction-claim" value={selectedClaimId} onChange={(event) => setSelectedClaimId(event.target.value)}><option value="">Select a Claim</option>{ledger.claims.map((claim) => <option value={claim.id} key={claim.id}>{shortId(claim.id)} · {claim.proposition}</option>)}</select><label htmlFor="correction-target">Destination Story ID</label><input id="correction-target" value={targetStoryId} onChange={(event) => setTargetStoryId(event.target.value)} placeholder="st_…" /><label htmlFor="correction-reason">Reason</label><input id="correction-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why is this correction needed?" /><div className="button-row"><button className="secondary-button" type="button" onClick={() => void reassign()} disabled={working || !selectedClaimId || !targetStoryId.trim()}>Move Claim</button><button className="quiet-button" type="button" onClick={() => void unassign()} disabled={working || !selectedClaimId}>Unassign Claim</button></div><label htmlFor="extract-headline">Extract selected Claim into new Story</label><input id="extract-headline" value={extractHeadline} onChange={(event) => setExtractHeadline(event.target.value)} placeholder="New Story headline" /><button className="secondary-button" type="button" onClick={() => void extract()} disabled={working || !selectedClaimId || !extractHeadline.trim()}>Extract Claim</button></div>
        <div className="content-grid">
          <div><h3>Merge</h3><p className="muted">The destination becomes canonical; the source remains historical.</p><button className="quiet-button" type="button" onClick={() => void previewMerge()} disabled={working || !targetStoryId.trim()}>Preview merge</button>{mergePreview && <div className="resource-list" role="status"><p className="status-note">Preview only — no Story, Claim, Watch, or Monitor records have changed.</p><div className="resource-row"><span><strong>Source: {previewStoryName(mergePreview.source)}</strong><small>{shortId(mergePreview.source.id)} · becomes historical · {mergePreview.source_claim_count} Claim{mergePreview.source_claim_count === 1 ? "" : "s"}</small></span></div><div className="resource-row"><span><strong>Destination: {previewStoryName(mergePreview.destination)}</strong><small>{shortId(mergePreview.destination.id)} · remains canonical · {mergePreview.destination_claim_count} current Claim{mergePreview.destination_claim_count === 1 ? "" : "s"}</small></span></div><div><strong>Claims to move</strong>{mergePreview.source_claims?.length ? <ul className="compact-list">{mergePreview.source_claims.map((claim) => <li key={claim.id}>{claim.proposition} · {shortId(claim.id)}</li>)}</ul> : <p className="muted">{mergePreview.expected_claim_moves.length} Claim ID{mergePreview.expected_claim_moves.length === 1 ? "" : "s"} recorded for movement.</p>}</div>{mergePreview.source_document_records?.length ? <div><strong>Source Documents retained in lineage</strong><ul className="compact-list">{mergePreview.source_document_records.map((document) => <li key={document.id}>{document.title} · {document.source_name} · published {formatDate(document.published_at)} · retrieved {formatDate(document.retrieved_at)} · {shortId(document.id)}</li>)}</ul></div> : null}{mergePreview.watch_consequences.length > 0 && <div><strong>Watch/Monitor effects</strong><ul className="compact-list">{mergePreview.watch_consequences.map((item) => <li key={`${item.kind}:${item.id}`}>{item.kind} · {item.name} · {shortId(item.id)}</li>)}</ul></div>}<div className="button-row"><button className="secondary-button" type="button" onClick={() => void merge()} disabled={working}>Approve merge</button><button className="quiet-button" type="button" onClick={() => setMergePreview(null)} disabled={working}>Cancel preview</button></div></div>}</div>
          <div><h3>Split</h3><p className="muted">Enter complete Claim groups, one group per line. The source retires and children become current.</p><button className="quiet-button" type="button" onClick={() => void previewSplit()} disabled={working}>Load split preview</button>{splitPreview && <div className="resource-list" role="status"><p className="status-note">Preview only — no Story, Claim, Watch, or Monitor records have changed.</p><div className="resource-row"><span><strong>Source: {previewStoryName(splitPreview.source)}</strong><small>{shortId(splitPreview.source.id)} · becomes historical</small></span></div><div><strong>Claims available to split</strong><ul className="compact-list">{splitPreview.claims.map((claim) => <li key={claim.id}>{claim.proposition} · {shortId(claim.id)} · {claim.state}</li>)}</ul></div>{splitPreview.current_document_records?.length ? <div><strong>Current Documents</strong><ul className="compact-list">{splitPreview.current_document_records.map((document) => <li key={document.id}>{document.title} · {document.source_name} · {shortId(document.id)}</li>)}</ul></div> : <p className="muted">{splitPreview.current_document_ids.length} current Document ID{splitPreview.current_document_ids.length === 1 ? "" : "s"} recorded.</p>}{splitPreview.current_entity_records?.length ? <div><strong>Effective Entities</strong><ul className="compact-list">{splitPreview.current_entity_records.map((entity) => <li key={entity.id}>{entity.canonical_name} · {shortId(entity.id)}</li>)}</ul></div> : null}{splitPreview.watch_consequences?.length ? <div><strong>Watch/Monitor effects</strong><ul className="compact-list">{splitPreview.watch_consequences.map((item) => <li key={`${item.kind}:${item.id}`}>{item.kind} · {item.name} · {shortId(item.id)}</li>)}</ul></div> : null}<label htmlFor="split-groups">Claim groups</label><textarea id="split-groups" rows={3} value={splitGroups} onChange={(event) => setSplitGroups(event.target.value)} placeholder="claim_id_1, claim_id_2\nclaim_id_3" /><div className="button-row"><button className="secondary-button" type="button" onClick={() => void split()} disabled={working}>Approve split</button><button className="quiet-button" type="button" onClick={() => { setSplitPreview(null); setSplitGroups(""); }} disabled={working}>Cancel preview</button></div></div>}</div>
        </div>
      </SectionCard>

      <div className="content-grid"><SectionCard title="Correction history" description="Append-only organizational decisions, not new factual evidence. Confirmed actions retain their Claim transitions and Story lineage here.">{corrections.length ? <ol className="timeline-list">{corrections.map((item) => <li key={item.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{item.operation_type.replace(/_/g, " ")}</strong><p>{item.reason || "No reason supplied."}</p><small>{item.origin} · {item.cause_class} · {formatDate(item.occurred_at)} · {shortId(item.id)}</small>{item.transitions?.length ? <ul className="compact-list">{item.transitions.map((transition) => <li key={`${item.id}:${transition.claim_id}`}><Badge tone="neutral">Claim transition</Badge> {shortId(transition.claim_id)}: {shortId(transition.from_story_id)} → {shortId(transition.to_story_id)}</li>)}</ul> : null}{item.lineage?.length ? <ul className="compact-list">{item.lineage.map((edge) => <li key={`${edge.source_story_id}:${edge.target_story_id}`}><Badge tone="neutral">Lineage</Badge> {edge.relationship.replace(/_/g, " ")}: {shortId(edge.source_story_id)} → {shortId(edge.target_story_id)}</li>)}</ul> : null}</div></li>)}</ol> : <EmptyState title="No corrections" description="This Story has no recorded correction decisions." />}</SectionCard><SectionCard title="Story lineage" description="Merged sources resolve to a canonical destination; split sources remain historical with explicit children."><p><Badge tone={lineage?.resolution.resolution === "active" ? "mint" : "amber"}>{lineage?.resolution.resolution ?? "unknown"}</Badge>{lineage?.resolution.canonical_story_id ? ` · canonical ${shortId(lineage.resolution.canonical_story_id)}` : ""}</p>{lineage?.incoming.concat(lineage.outgoing).length ? <ul className="compact-list">{lineage.incoming.concat(lineage.outgoing).map((edge) => <li key={edge.id}><Badge tone="neutral">{edge.relationship.replace(/_/g, " ")}</Badge> {shortId(edge.source_story_id)} → {shortId(edge.target_story_id)}</li>)}</ul> : <p className="muted">No lineage edges.</p>}</SectionCard></div>

      {story.lifecycle !== "archived" && <SectionCard title="Duplicate review" description="Suggestions are bounded and dismissals are durable negative decisions. Approval uses the canonical merge service.">{duplicates.length ? <div className="resource-list">{duplicates.map((item) => <div className="resource-row" key={item.evidence_hash}><span><strong>{shortId(item.source_story_id)} ↔ {shortId(item.destination_story_id)}</strong><small>similarity {item.score.toFixed(2)} · {shortId(item.evidence_hash)}</small></span><div className="button-row"><button className="secondary-button" type="button" onClick={() => void runCorrection(() => apiFetch(`/stories/${encodeURIComponent(item.source_story_id)}/duplicates/approve`, { method: "POST", body: jsonBody({ destination_story_id: item.destination_story_id, evidence_hash: item.evidence_hash, reason: "Approved from duplicate review" }) }))} disabled={working}>Approve merge</button><button className="quiet-button" type="button" onClick={() => void runCorrection(() => apiFetch(`/stories/${encodeURIComponent(item.source_story_id)}/duplicates/dismiss`, { method: "POST", body: jsonBody({ destination_story_id: item.destination_story_id, evidence_hash: item.evidence_hash, reason: "Dismissed from duplicate review" }) }))} disabled={working}>Dismiss</button></div></div>)}</div> : <EmptyState title="No duplicate suggestions" description="No bounded duplicate candidate is ready for review." />}</SectionCard>}

      <div className="content-grid"><SectionCard title="Timeline" description="Immutable Story evolution and revision links."><p className="status-note">Time semantics: Recorded/known at is when Newsroom stored the Story event; published is the publisher’s timestamp when supplied; retrieved is when that DocumentVersion was fetched. These times are not interchangeable, and missing publication dates stay missing.</p>{timelineEvents.length ? <ol className="timeline-list">{timelineEvents.map((event, index) => { const documentId = timelineDocumentId(event); const context = documentId ? documentContexts[documentId] : undefined; const evidence = documentId ? ledger.claims.flatMap((claim) => claim.evidence).find((item) => item.document.id === documentId) : undefined; const documentTitle = context?.title ?? event.document?.title ?? (documentId ? shortId(documentId) : "Document unavailable"); const sourceName = event.document?.source_name ?? evidence?.source.name ?? "Source unavailable"; const claimId = timelineClaimId(event); return <li key={String(event.id ?? `${documentId ?? "event"}:${index}`)}><span className="timeline-dot" aria-hidden="true" /><div><strong>{readableUpdateClass(event)} {event.material_change ? <Badge tone="amber">material</Badge> : null}</strong><p>{claimId ? `Claim ${shortId(claimId)} entered this Story through this event.` : event.material_change ? "This event was recorded as a material Story change." : "Story evidence observation recorded."}</p><small>Recorded/known at {formatDate(event.created_at)} · published {formatDate(context?.publishedAt)} · retrieved {formatDate(context?.latestRetrievedAt ?? evidence?.document_version.retrieved_at)}</small><small>{documentTitle} · {sourceName} · {shortId(documentId)}</small></div></li>})}</ol> : <EmptyState title="No timeline events" description="Story evolution will appear here when recorded." />}</SectionCard><SectionCard title="Revision history" description="Saved revisions remain inspectable and immutable.">{ledger.revisions.length ? <div className="resource-list">{ledger.revisions.map((revision) => <div className="resource-row" key={revision.id}><span><strong>Revision {revision.revision_number}</strong><small>{revision.headline} · {revision.claim_ids.length} Claims</small></span><code>{shortId(revision.claim_set_hash)}</code></div>)}</div> : <EmptyState title="No revisions" description="No Story revisions are recorded." />}</SectionCard></div>
    </>}
  </>;
}
