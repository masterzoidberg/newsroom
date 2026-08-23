import { FormEvent, useEffect, useState } from "react";
import { apiFetch, formatDate, jsonBody, shortId } from "../lib/api";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";
import type { Claim, ListResponse } from "../lib/types";

type SearchItem = {
  entity_type: string;
  entity_id: string;
  title: string;
  body: string;
  snippet: string;
  score: number;
  state?: string | null;
  lifecycle?: string | null;
};
type SearchResponse = { items: SearchItem[]; total: number; page: number; page_size: number; has_more: boolean };
type Health = { status: string; database: string; counts: Record<string, number>; distinctions: Record<string, string> };
type CoverageItem = { monitor: { id: string; target_type: string; target_id: string }; coverage: Record<string, number | string | null> };
type CoverageResponse = { items: CoverageItem[]; total: number };
type SubjectPage = {
  subject: { canonical_name: string; subject_type: string; description: string; aliases: string[] };
  stories: Array<{ id: string; headline: string; lifecycle: string; material_change: number }>;
  timeline: Array<{ id: string; event_type: string; label: string; at: string; story_id: string }>;
  historical_context: { evidence: Array<{ id: string; excerpt: string; document_title: string; source_name: string; retrieved_at: string }> };
};

const ENTITY_OPTIONS = ["monitor", "source", "document", "story", "subject", "claim", "evidence", "tag", "question", "note"];

function asArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

function asText(value: unknown, fallback = "—"): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

export function WorkbenchView() {
  const [query, setQuery] = useState("");
  const [entityType, setEntityType] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [compareIds, setCompareIds] = useState("");
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [comparing, setComparing] = useState(false);
  const [subjectId, setSubjectId] = useState("");
  const [subject, setSubject] = useState<SubjectPage | null>(null);
  const [loadingSubject, setLoadingSubject] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [coverage, setCoverage] = useState<CoverageResponse | null>(null);
  const [pendingClaims, setPendingClaims] = useState<ListResponse<Claim> | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<Health>("/diagnostics/health"),
      apiFetch<CoverageResponse>("/diagnostics/coverage"),
      apiFetch<ListResponse<Claim>>("/claims?state=pending&assignment=unassigned&provenance=automatic&page_size=25"),
    ])
      .then(([healthResult, coverageResult, claimResult]) => { setHealth(healthResult); setCoverage(coverageResult); setPendingClaims(claimResult); })
      .catch(setError);
  }, []);

  async function runSearch(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) return;
    setSearching(true); setError(null);
    const params = new URLSearchParams({ q: query.trim(), page_size: "50" });
    if (entityType) params.set("entity_type", entityType);
    try { setSearchResult(await apiFetch<SearchResponse>(`/search?${params.toString()}`)); }
    catch (caught) { setError(caught); }
    finally { setSearching(false); }
  }

  async function runComparison(event: FormEvent) {
    event.preventDefault();
    const documentIds = compareIds.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
    if (documentIds.length < 2) return;
    setComparing(true); setError(null);
    try { setComparison(await apiFetch<Record<string, unknown>>("/comparisons", { method: "POST", body: jsonBody({ document_ids: documentIds }) })); }
    catch (caught) { setError(caught); }
    finally { setComparing(false); }
  }

  async function loadSubject(event: FormEvent) {
    event.preventDefault();
    if (!subjectId.trim()) return;
    setLoadingSubject(true); setError(null);
    try { setSubject(await apiFetch<SubjectPage>(`/subjects/${encodeURIComponent(subjectId.trim())}/workbench`)); }
    catch (caught) { setError(caught); }
    finally { setLoadingSubject(false); }
  }

  const counts = health?.counts ?? {};
  return <>
    <PageHeader eyebrow="Research workbench" title="Search, compare, diagnose" description="Find authoritative Newsroom objects, compare exact evidence across documents, and see whether a monitor found no change or actually failed." />
    {error && <ErrorState error={error} />}
    <div className="stat-grid">
      <Stat label="Indexed objects" value={searchResult?.total ?? "—"} tone="mint" />
      <Stat label="Monitors" value={counts.monitors ?? "—"} />
      <Stat label="Acquisition failures" value={counts.failed_acquisitions ?? "—"} tone={counts.failed_acquisitions ? "coral" : "mint"} />
      <Stat label="No meaningful change" value={counts.no_meaningful_change ?? "—"} tone="amber" />
    </div>

    <div className="content-grid workbench-grid">
      <SectionCard title="Global search" description="Bounded SQLite FTS5 search with stable BM25 ranking and typed filters.">
        <form className="stack-form" onSubmit={(event) => void runSearch(event)}>
          <label htmlFor="workbench-query">Search terms</label>
          <input id="workbench-query" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try a subject, claim, source, or note" />
          <label htmlFor="workbench-type">Object type</label>
          <select id="workbench-type" value={entityType} onChange={(event) => setEntityType(event.target.value)}>
            <option value="">All indexed objects</option>
            {ENTITY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
          </select>
          <button className="primary-button" type="submit" disabled={searching}>{searching ? "Searching…" : "Search workspace"}</button>
        </form>
        {searching && <LoadingState label="Searching evidence" />}
        {!searching && searchResult && !searchResult.items.length && <EmptyState title="No matches" description="Try fewer terms or remove the object-type filter." />}
        {!searching && searchResult?.items.length ? <div className="workbench-result-list" aria-label="Search results">{searchResult.items.map((item) => <article className="workbench-result" key={`${item.entity_type}:${item.entity_id}`}><div><div className="workbench-result-meta"><Badge tone={item.entity_type === "evidence" ? "mint" : "neutral"}>{item.entity_type}</Badge><code>{shortId(item.entity_id)}</code></div><h3>{item.title}</h3><p>{item.snippet}</p></div><span className="workbench-score">{item.score.toFixed(2)}</span></article>)}</div> : null}
      </SectionCard>

      <SectionCard title="Monitor coverage" description="Recorded state only. A quiet monitor and a failed run are different outcomes.">
        {coverage?.items.length ? <div className="workbench-result-list">{coverage.items.slice(0, 8).map((item) => { const status = asText(item.coverage.latest_status, "not_run"); const tone = status.includes("failed") ? "coral" : status === "no_meaningful_change" ? "amber" : "mint"; return <article className="workbench-result" key={item.monitor.id}><div><div className="workbench-result-meta"><Badge tone={tone}>{status.replace(/_/g, " ")}</Badge><code>{shortId(item.monitor.id)}</code></div><h3>{item.monitor.target_type} monitor</h3><p>{asText(item.coverage.checks, "0")} checks · {asText(item.coverage.meaningful_change, "0")} meaningful changes · {asText(item.coverage.failed_acquisition, "0")} acquisition failures</p></div><span className="workbench-score">{formatDate(asText(item.coverage.last_checked_at, ""))}</span></article>; })}</div> : coverage ? <EmptyState title="No monitors yet" description="Create a Monitor to make coverage and health visible here." /> : <LoadingState label="Reading monitor coverage" />}
        {health && <p className="status-note">Health: <strong>{health.status}</strong> · database {health.database}</p>}
      </SectionCard>
    </div>

    <div className="content-grid workbench-grid">
      <SectionCard title="Pending automatic Claims" description="Verified Claims awaiting deterministic Story assignment, with exact evidence provenance.">
        {pendingClaims ? pendingClaims.items.length ? <div className="workbench-result-list" aria-label="Pending automatic Claims">{pendingClaims.items.map((claim) => <article className="workbench-result" key={claim.id}><div><div className="workbench-result-meta"><Badge tone="amber">{claim.state}</Badge><code>{shortId(claim.id)}</code></div><h3>{claim.proposition}</h3><p>{claim.evidence.length} exact evidence span{claim.evidence.length === 1 ? "" : "s"} · analysis {shortId(claim.provenance.article_analysis_id)} · promotion {shortId(claim.provenance.promotion_id)}</p></div><span className="workbench-score">{formatDate(claim.created_at)}</span></article>)}</div> : <EmptyState title="No pending automatic Claims" description="Every verified automatic Claim is assigned or has moved beyond pending review." /> : <LoadingState label="Reading pending Claims" />}
      </SectionCard>

      <SectionCard title="Compare documents" description="Paste two to twenty Document IDs. Claims, contradictions, dates, numbers, primary-source use, and lineage stay tied to evidence IDs.">
        <form className="stack-form" onSubmit={(event) => void runComparison(event)}>
          <label htmlFor="compare-document-ids">Document IDs</label>
          <textarea id="compare-document-ids" rows={3} value={compareIds} onChange={(event) => setCompareIds(event.target.value)} placeholder="doc_… doc_…" />
          <button className="secondary-button" type="submit" disabled={comparing}>{comparing ? "Comparing…" : "Compare evidence"}</button>
        </form>
        {comparison && <div className="comparison-summary"><div className="stat-grid"><Stat label="Shared claims" value={asArray(comparison.shared_claims).length} tone="mint" /><Stat label="Unique claims" value={asArray(comparison.unique_claims).length} /><Stat label="Contradictions" value={asArray(comparison.contradictions).length} tone={asArray(comparison.contradictions).length ? "coral" : "mint"} /><Stat label="Lineage links" value={asArray(comparison.lineage).length} /></div><h3>Evidence-bound differences</h3>{asArray(comparison.dates_and_numbers && (comparison.dates_and_numbers as Record<string, unknown>).differences).map((item, index) => <p key={index}><Badge tone="amber">{asText(item.kind)}</Badge> {asText(item.assertion)} · {asArray(item.observations).map((observation) => asText(observation.values)).join(" vs ")}</p>)}{asArray(comparison.contradictions).map((item, index) => <p key={`contradiction-${index}`}><Badge tone="coral">Contradiction</Badge> {asText(item.reason)} · evidence {asText(item.evidence_span_ids)}</p>)}<p className="status-note">{asText(comparison.evidence_authority)}</p></div>}
      </SectionCard>

      <SectionCard title="Subject page & context" description="Open a Subject’s timeline and historical context without importing facts from model memory.">
        <form className="inline-form" onSubmit={(event) => void loadSubject(event)}>
          <label htmlFor="subject-id">Subject ID</label>
          <input id="subject-id" value={subjectId} onChange={(event) => setSubjectId(event.target.value)} placeholder="sub_…" />
          <button className="secondary-button" type="submit" disabled={loadingSubject}>{loadingSubject ? "Opening…" : "Open subject"}</button>
        </form>
        {loadingSubject && <LoadingState label="Opening subject context" />}
        {subject && !loadingSubject && <div className="subject-workbench"><div className="story-summary"><div><p className="eyebrow">{subject.subject.subject_type}</p><h2>{subject.subject.canonical_name}</h2><p>{subject.subject.description || "No description recorded."}</p></div><Badge tone="mint">{subject.stories.length} stories</Badge></div><h3>Timeline</h3><ul className="timeline-list">{subject.timeline.slice(0, 6).map((event) => <li key={`${event.event_type}:${event.id}`}><span className="timeline-dot" aria-hidden="true" /><div><strong>{event.label}</strong><p>{event.event_type.replace(/_/g, " ")} · {shortId(event.story_id)}</p><small>{formatDate(event.at)}</small></div></li>)}</ul><h3>Historical context</h3>{subject.historical_context.evidence.slice(0, 5).map((item) => <blockquote key={item.id}>“{item.excerpt}”<footer>{item.source_name} · {item.document_title} · {formatDate(item.retrieved_at)}</footer></blockquote>)}</div>}
      </SectionCard>
    </div>
  </>;
}
