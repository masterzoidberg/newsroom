import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiFetch, formatDate, jsonBody, shortId } from "../lib/api";
import type { Claim, DuplicateSuggestion, Story, StoryCorrection, StoryEvidenceResponse, StoryLineage, StoryNavigationContext, Timeline } from "../lib/types";
import { EvidenceView } from "../components/EvidenceView";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";
import { queueDocumentNavigation } from "./DocumentView";

type Corroboration = { publication_count?: number; distinct_source_count?: number; dependency_group_count?: number; largest_group_share?: number; dependency_groups?: Array<Record<string, unknown>> };
type MergePreview = { source: Story; destination: Story; source_claim_count: number; destination_claim_count: number; expected_claim_moves: string[]; watch_consequences: Array<{ id: string; kind: string; name: string }>; expected_current_state_fingerprint?: string };
type SplitPreview = { source: Story; claims: Array<{ id: string; proposition: string; importance: string; state: string }>; expected_claim_ids: string[]; current_document_ids: string[]; current_entity_ids: string[] };

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

export function StoryEvidenceView() {
  const [initialContext] = useState(readStoryNavigation);
  const [storyId, setStoryId] = useState(initialContext?.storyId ?? "");
  const [story, setStory] = useState<Story | null>(null);
  const [ledger, setLedger] = useState<StoryEvidenceResponse | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
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
    setLoading(true); setError(null); setMergePreview(null); setSplitPreview(null);
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
      const requestedClaimExists = requestedClaimId.length > 0 && evidenceResult.claims.some((claim) => claim.id === requestedClaimId);
      const nextClaimId = requestedClaimExists ? requestedClaimId : evidenceResult.claims[0]?.id ?? "";
      setStory(storyResult); setLedger(evidenceResult); setTimeline(timelineResult); setCorroboration(corroborationResult); setCorrections(correctionResult.items); setLineage(lineageResult);
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
    setWorking(true); setError(null);
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
    setWorking(true); setError(null);
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
  return <>
    <PageHeader eyebrow="Review / provenance" title="Story & evidence" description="Inspect Claims, exact spans, corrections, lineage, and current Story membership." />
    <SectionCard title="Open a Story" description="Home, Watch results, and saved review context can open this path without re-entering an ID. Manual entry remains available for recovery.">
      <form className="inline-form" onSubmit={inspect}><label htmlFor="story-id">Story ID</label><input id="story-id" name="story_id" autoComplete="off" value={storyId} onChange={(event) => setStoryId(event.target.value)} placeholder="st_…" /><button className="primary-button" type="submit" disabled={loading}>{loading ? "Inspecting…" : "Inspect Story"}</button></form>
    </SectionCard>
    {loading && <LoadingState label="Following provenance" />}{error && <ErrorState error={error} />}
    {story && ledger && <>
      <section className="story-summary"><div><p className="eyebrow">{story.lifecycle === "archived" ? "Historical Story" : "Current Story"}</p><h2>{headline}</h2><p>{summary}</p>{ledger.claims.length > 0 && <button className="secondary-button" type="button" onClick={() => selectClaim(selectedClaimId || ledger.claims[0].id)}>Review summary Claims</button>}</div><div className="story-summary-meta"><Badge tone={story.lifecycle === "developing" ? "amber" : "mint"}>{story.lifecycle}</Badge><span>{shortId(story.id)}</span></div></section>
      <div className="stat-grid"><div className="stat-card"><span>Current Claims</span><strong>{ledger.claims.length}</strong></div><div className="stat-card stat-mint"><span>Accepted</span><strong>{ledger.claims.filter((claim) => claim.accepted).length}</strong></div><div className="stat-card stat-coral"><span>Contradictions</span><strong>{ledger.claims.flatMap((claim) => claim.evidence).filter((item) => item.relationship === "contradicts").length}</strong></div><div className="stat-card"><span>Distinct Sources</span><strong>{corroboration?.distinct_source_count ?? "—"}</strong><small>{corroboration?.dependency_group_count ?? "—"} known dependency groups</small></div></div>

      <SectionCard title="Claims and exact spans" description="Current membership is distinct from historical Story Document observations.">{missingClaimId && <p className="status-note" role="status">Claim {shortId(missingClaimId)} is no longer in this Story’s current evidence ledger. The stale link is retained for explanation, not treated as verified.</p>}<EvidenceView ledger={ledger} selectedClaimId={selectedClaimId} dependencyGroupCount={corroboration?.dependency_group_count} onSelectClaim={selectClaim} onOpenEvidence={openEvidence} /></SectionCard>

      <SectionCard title="Story correction actions" description="Human corrections require an expected current Story when moving Claims, so stale approvals are rejected.">
        <div className="stack-form"><label htmlFor="correction-claim">Claim</label><select id="correction-claim" value={selectedClaimId} onChange={(event) => setSelectedClaimId(event.target.value)}><option value="">Select a Claim</option>{ledger.claims.map((claim) => <option value={claim.id} key={claim.id}>{shortId(claim.id)} · {claim.proposition}</option>)}</select><label htmlFor="correction-target">Destination Story ID</label><input id="correction-target" value={targetStoryId} onChange={(event) => setTargetStoryId(event.target.value)} placeholder="st_…" /><label htmlFor="correction-reason">Reason</label><input id="correction-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why is this correction needed?" /><div className="button-row"><button className="secondary-button" type="button" onClick={() => void reassign()} disabled={working || !selectedClaimId || !targetStoryId.trim()}>Move Claim</button><button className="quiet-button" type="button" onClick={() => void unassign()} disabled={working || !selectedClaimId}>Unassign Claim</button></div><label htmlFor="extract-headline">Extract selected Claim into new Story</label><input id="extract-headline" value={extractHeadline} onChange={(event) => setExtractHeadline(event.target.value)} placeholder="New Story headline" /><button className="secondary-button" type="button" onClick={() => void extract()} disabled={working || !selectedClaimId || !extractHeadline.trim()}>Extract Claim</button></div>
        <div className="content-grid"><div><h3>Merge</h3><p className="muted">The destination becomes canonical; the source remains historical.</p><div className="button-row"><button className="quiet-button" type="button" onClick={() => void previewMerge()} disabled={working || !targetStoryId.trim()}>Preview merge</button><button className="secondary-button" type="button" onClick={() => void merge()} disabled={working || !mergePreview}>Approve merge</button></div>{mergePreview && <p className="status-note">{mergePreview.source_claim_count} Claims move · {mergePreview.watch_consequences.length} Watch/Monitor effects · source {shortId(mergePreview.source.id)} → destination {shortId(mergePreview.destination.id)}</p>}</div><div><h3>Split</h3><p className="muted">Enter complete Claim groups, one group per line. The source retires and children become current.</p><button className="quiet-button" type="button" onClick={() => void previewSplit()} disabled={working}>Load split preview</button>{splitPreview && <><p className="status-note">{splitPreview.claims.length} current Claims · {splitPreview.current_document_ids.length} current Documents · {splitPreview.current_entity_ids.length} effective Entities</p><textarea rows={3} value={splitGroups} onChange={(event) => setSplitGroups(event.target.value)} placeholder="claim_id_1, claim_id_2\nclaim_id_3" /><button className="secondary-button" type="button" onClick={() => void split()} disabled={working}>Approve split</button></>}</div></div>
      </SectionCard>

      <div className="content-grid"><SectionCard title="Correction history" description="Append-only organizational decisions, not new factual evidence.">{corrections.length ? <ol className="timeline-list">{corrections.map((item) => <li key={item.id}><span className="timeline-dot" aria-hidden="true" /><div><strong>{item.operation_type.replace(/_/g, " ")}</strong><p>{item.reason || "No reason supplied."}</p><small>{item.origin} · {formatDate(item.occurred_at)} · {shortId(item.id)}</small></div></li>)}</ol> : <EmptyState title="No corrections" description="This Story has no recorded correction decisions." />}</SectionCard><SectionCard title="Story lineage" description="Merged sources resolve to a canonical destination; split sources remain historical with explicit children."><p><Badge tone={lineage?.resolution.resolution === "active" ? "mint" : "amber"}>{lineage?.resolution.resolution ?? "unknown"}</Badge>{lineage?.resolution.canonical_story_id ? ` · canonical ${shortId(lineage.resolution.canonical_story_id)}` : ""}</p>{lineage?.incoming.concat(lineage.outgoing).length ? <ul className="compact-list">{lineage.incoming.concat(lineage.outgoing).map((edge) => <li key={edge.id}><Badge tone="neutral">{edge.relationship.replace(/_/g, " ")}</Badge> {shortId(edge.source_story_id)} → {shortId(edge.target_story_id)}</li>)}</ul> : <p className="muted">No lineage edges.</p>}</SectionCard></div>

      {story.lifecycle !== "archived" && <SectionCard title="Duplicate review" description="Suggestions are bounded and dismissals are durable negative decisions. Approval uses the canonical merge service.">{duplicates.length ? <div className="resource-list">{duplicates.map((item) => <div className="resource-row" key={item.evidence_hash}><span><strong>{shortId(item.source_story_id)} ↔ {shortId(item.destination_story_id)}</strong><small>similarity {item.score.toFixed(2)} · {shortId(item.evidence_hash)}</small></span><div className="button-row"><button className="secondary-button" type="button" onClick={() => void runCorrection(() => apiFetch(`/stories/${encodeURIComponent(item.source_story_id)}/duplicates/approve`, { method: "POST", body: jsonBody({ destination_story_id: item.destination_story_id, evidence_hash: item.evidence_hash, reason: "Approved from duplicate review" }) }))} disabled={working}>Approve merge</button><button className="quiet-button" type="button" onClick={() => void runCorrection(() => apiFetch(`/stories/${encodeURIComponent(item.source_story_id)}/duplicates/dismiss`, { method: "POST", body: jsonBody({ destination_story_id: item.destination_story_id, evidence_hash: item.evidence_hash, reason: "Dismissed from duplicate review" }) }))} disabled={working}>Dismiss</button></div></div>)}</div> : <EmptyState title="No duplicate suggestions" description="No bounded duplicate candidate is ready for review." />}</SectionCard>}

      <div className="content-grid"><SectionCard title="Timeline" description="Immutable Story evolution and revision links.">{timeline?.events?.length ? <ol className="timeline-list">{timeline.events.map((event, index) => <li key={index}><span className="timeline-dot" aria-hidden="true" /><div><strong>{String(event.update_class ?? event.event_type ?? "Story event")}</strong><p>{String(event.rationale ?? event.document_id ?? "Recorded evolution event")}</p><small>{formatDate(String(event.created_at ?? ""))}</small></div></li>)}</ol> : <EmptyState title="No timeline events" description="Story evolution will appear here when recorded." />}</SectionCard><SectionCard title="Revision history" description="Saved revisions remain inspectable and immutable.">{ledger.revisions.length ? <div className="resource-list">{ledger.revisions.map((revision) => <div className="resource-row" key={revision.id}><span><strong>Revision {revision.revision_number}</strong><small>{revision.headline} · {revision.claim_ids.length} Claims</small></span><code>{shortId(revision.claim_set_hash)}</code></div>)}</div> : <EmptyState title="No revisions" description="No Story revisions are recorded." />}</SectionCard></div>
    </>}
  </>;
}
