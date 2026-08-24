import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, formatDate, jsonBody, shortId } from "../lib/api";
import type { CollectionRecord } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";

type Watch = CollectionRecord & {
  target_type?: string;
  vocabulary?: CollectionRecord[];
  source_candidates?: CollectionRecord[];
  sources?: Array<{ source?: CollectionRecord; monitor?: CollectionRecord }>;
};

type Health = {
  status: string;
  discovery_enabled: boolean;
  active_source_count: number;
  pending_source_candidate_count: number;
  pending_vocabulary_suggestion_count: number;
  last_attempt?: string | null;
  next_scheduled_run?: string | null;
  last_discovery_run?: string | null;
  last_error?: string | null;
};

const text = (value: unknown, fallback = "—") => String(value ?? fallback);

export function WatchManagementView() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [policies, setPolicies] = useState<CollectionRecord[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<Watch | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [policyId, setPolicyId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [targetType, setTargetType] = useState("topic");
  const [name, setName] = useState("UAP disclosure");
  const [editName, setEditName] = useState("");
  const [term, setTerm] = useState("");
  const [kind, setKind] = useState("alias");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const loadDetail = useCallback(async (id: string) => {
    const [watch, watchHealth, vocabulary, candidates, sources] = await Promise.all([
      apiFetch<Watch>(`/watches/${id}`),
      apiFetch<Health>(`/watches/${id}/health`),
      apiList<CollectionRecord>(`/watches/${id}/vocabulary?page_size=100`),
      apiList<CollectionRecord>(`/watches/${id}/source-candidates?page_size=100`),
      apiList<{ source?: CollectionRecord; monitor?: CollectionRecord }>(`/watches/${id}/sources?page_size=100`),
    ]);
    setSelected({ ...watch, vocabulary: vocabulary.items, source_candidates: candidates.items, sources: sources.items });
    setHealth(watchHealth);
    setEditName(text(watch.name, ""));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [watchResult, policyResult] = await Promise.all([
        apiList<Watch>("/watches?page_size=100"),
        apiList<CollectionRecord>("/monitoring-policies?page_size=100"),
      ]);
      setWatches(watchResult.items);
      setPolicies(policyResult.items);
      const nextPolicyId = policyId && policyResult.items.some((item) => item.id === policyId) ? policyId : policyResult.items[0]?.id ?? "";
      setPolicyId(nextPolicyId);
      const nextId = selectedId && watchResult.items.some((item) => item.id === selectedId) ? selectedId : watchResult.items[0]?.id ?? "";
      setSelectedId(nextId);
      if (nextId) await loadDetail(nextId);
      else { setSelected(null); setHealth(null); }
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, [loadDetail, policyId, selectedId]);

  useEffect(() => { void load(); }, [load]);

  async function refresh(id = selectedId) {
    if (!id) return;
    setWorking(true);
    try { await loadDetail(id); const result = await apiList<Watch>("/watches?page_size=100"); setWatches(result.items); }
    catch (caught) { setError(caught); }
    finally { setWorking(false); }
  }

  async function createPolicy(event: FormEvent) {
    event.preventDefault(); setWorking(true); setError(null);
    try {
      const policy = await apiFetch<CollectionRecord>("/monitoring-policies", { method: "POST", body: jsonBody({ name, allowed_channels: ["direct_http"], base_cadence_seconds: 3600, min_cadence_seconds: 900, max_cadence_seconds: 86400, priority: "normal", query_budget: 10, local_model_budget: 10, paid_budget_usd: 0 }) });
      setPolicies((items) => [...items, policy]);
      setPolicyId(policy.id);
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function createWatch(event: FormEvent) {
    event.preventDefault(); if (!targetId.trim() || !policyId) return;
    setWorking(true); setError(null);
    try {
      const watch = await apiFetch<Watch>("/watches", { method: "POST", body: jsonBody({ name, target_type: targetType, target_id: targetId.trim(), policy_id: policyId }) });
      setTargetId(""); setSelectedId(watch.id); await load();
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function action(path: string, body?: unknown) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selectedId}/${path}`, { method: "POST", body: body ? jsonBody(body) : undefined }); await refresh(); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function saveName(event: FormEvent) {
    event.preventDefault(); if (!selected || !editName.trim()) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selected.id}`, { method: "PATCH", body: jsonBody({ name: editName.trim() }) }); await refresh(selected.id); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function addTerm(event: FormEvent) {
    event.preventDefault(); if (!selectedId || !term.trim()) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selectedId}/vocabulary`, { method: "POST", body: jsonBody({ term: term.trim(), kind, rationale: "Added in Watch management" }) }); setTerm(""); await refresh(); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function review(path: string, status: "approved" | "rejected") { await action(`${path}/review`, { status }); }

  if (loading) return <><PageHeader eyebrow="Configure" title="Watches" description="Persistent monitoring intent, approved vocabulary, Sources, and schedules." /><LoadingState />{error && <ErrorState error={error} />}</>;
  return <>
    <PageHeader eyebrow="Configure / intelligent monitoring" title="Watches" description="Create a Watch, review vocabulary and Source candidates, and inspect bounded monitoring health." action={<button className="secondary-button" type="button" onClick={() => void action("discover-sources", { limit: 25 })} disabled={working || !selectedId}>Discover Sources</button>} />
    {error && <ErrorState error={error} retry={() => void load()} />}
    <div className="content-grid">
      <SectionCard title="Create Watch" description="Use an existing Topic, Subject, Story, Source, or Research Question.">
        <form className="stack-form" onSubmit={createWatch}><label htmlFor="watch-target-type">Target type</label><select id="watch-target-type" value={targetType} onChange={(event) => setTargetType(event.target.value)}><option value="topic">Topic</option><option value="subject">Subject</option><option value="story">Story</option><option value="source">Source</option><option value="research_question">Research Question</option></select><label htmlFor="watch-target-id">Target ID</label><input id="watch-target-id" value={targetId} onChange={(event) => setTargetId(event.target.value)} placeholder="canonical target ID" /><label htmlFor="watch-name">Watch name</label><input id="watch-name" value={name} onChange={(event) => setName(event.target.value)} /><button className="primary-button" type="submit" disabled={working || !policyId}>Create Watch</button></form>
      </SectionCard>
      <SectionCard title="Monitoring policy" description="Cadence and budgets remain server-side policy controls."><form className="stack-form" onSubmit={createPolicy}><label htmlFor="policy-name">Policy name</label><input id="policy-name" value={name} onChange={(event) => setName(event.target.value)} /><button className="secondary-button" type="submit" disabled={working}>Create policy</button></form>{policies.length ? <div className="resource-list">{policies.map((policy) => <button type="button" className={`resource-row ${policy.id === policyId ? "selected" : ""}`} key={policy.id} onClick={() => setPolicyId(policy.id)}><span><strong>{text(policy.name, "Policy")}</strong><small>{shortId(policy.id)} · {text(policy.priority, "normal")}</small></span><Badge tone={policy.id === policyId ? "mint" : "neutral"}>{policy.id === policyId ? "selected" : "select"}</Badge></button>)}</div> : <EmptyState title="No policy" description="Create a policy before creating a Watch." />}</SectionCard>
    </div>
    <SectionCard title="Configured Watches" description={`${watches.length} Watch(es); select one to inspect its durable state.`}>{watches.length ? <div className="resource-list">{watches.map((watch) => <button type="button" className={`resource-row ${selectedId === watch.id ? "selected" : ""}`} key={watch.id} onClick={() => { setSelectedId(watch.id); void refresh(watch.id); }}><span><strong>{text(watch.name, text(watch.target_type))}</strong><small>{text(watch.target_type)} · {shortId(watch.id)}</small></span><Badge tone={watch.status === "active" ? "mint" : "neutral"}>{text(watch.status, "active")}</Badge></button>)}</div> : <EmptyState title="No Watches" description="Create a Watch from a canonical information need." />}</SectionCard>
    {selected && health && <WatchDetail watch={selected} health={health} name={editName} setName={setEditName} term={term} setTerm={setTerm} kind={kind} setKind={setKind} working={working} onSave={saveName} onAddTerm={addTerm} onAction={action} onReview={review} />}
  </>;
}

function WatchDetail({ watch, health, name, setName, term, setTerm, kind, setKind, working, onSave, onAddTerm, onAction, onReview }: { watch: Watch; health: Health; name: string; setName: (value: string) => void; term: string; setTerm: (value: string) => void; kind: string; setKind: (value: string) => void; working: boolean; onSave: (event: FormEvent) => void; onAddTerm: (event: FormEvent) => void; onAction: (path: string, body?: unknown) => Promise<void>; onReview: (path: string, status: "approved" | "rejected") => Promise<void> }) {
  const vocabulary = watch.vocabulary ?? [];
  const candidates = watch.source_candidates ?? [];
  return <>
    <SectionCard title={text(watch.name)} description={`${text(watch.target_type)} · ${shortId(watch.id)}`} action={<div className="button-row"><Badge tone={health.status === "active" ? "mint" : "neutral"}>{health.status}</Badge><button className="quiet-button" type="button" onClick={() => void onAction(health.status === "active" ? "pause" : "resume")} disabled={working}>{health.status === "active" ? "Pause" : "Resume"}</button><button className="secondary-button" type="button" onClick={() => void onAction("vocabulary/suggest", { limit: 20 })} disabled={working}>Suggest vocabulary</button></div>}>
      <div className="stats-grid"><Stat label="Active Sources" value={health.active_source_count} tone="mint" /><Stat label="Pending terms" value={health.pending_vocabulary_suggestion_count} tone="amber" /><Stat label="Pending Sources" value={health.pending_source_candidate_count} tone="amber" /><Stat label="Next run" value={formatDate(text(health.next_scheduled_run, "Not scheduled"))} /></div>
      <form className="inline-form" onSubmit={onSave}><label htmlFor="selected-watch-name">Edit name</label><input id="selected-watch-name" value={name} onChange={(event) => setName(event.target.value)} /><button className="secondary-button" type="submit" disabled={working}>Save</button></form>
      {health.last_error && <p className="status-note">Recent error: {health.last_error}</p>}
    </SectionCard>
    <div className="content-grid">
      <SectionCard title="Vocabulary" description="Approved terms affect future monitoring; suggestions remain inert until reviewed."><form className="inline-form" onSubmit={onAddTerm}><label htmlFor="watch-term">Add term</label><input id="watch-term" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="AARO" /><select aria-label="Vocabulary kind" value={kind} onChange={(event) => setKind(event.target.value)}><option value="alias">Alias</option><option value="synonym">Synonym</option><option value="acronym">Acronym</option><option value="acronym_expansion">Acronym expansion</option><option value="include">Include</option><option value="exclude">Exclude</option></select><button className="secondary-button" type="submit" disabled={working}>Add</button></form>{vocabulary.length ? <div className="resource-list">{vocabulary.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.term)}</strong><small>{text(item.kind)} · {text(item.origin)} · {text(item.status)}</small></span>{item.status === "suggested" && <div className="button-row"><button className="secondary-button" type="button" onClick={() => void onReview(`vocabulary/${item.id}`, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void onReview(`vocabulary/${item.id}`, "rejected")} disabled={working}>Reject</button></div>}</div>)}</div> : <EmptyState title="No vocabulary" description="Add a term or request deterministic suggestions." />}</SectionCard>
      <SectionCard title="Source candidates" description="Candidates retain URL, method, rationale, and provenance until reviewed.">{candidates.length ? <div className="resource-list">{candidates.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.name)}</strong><small>{text(item.homepage_url)} · {text(item.discovery_method)} · {text(item.rationale)}</small></span>{item.status === "suggested" && <div className="button-row"><button className="secondary-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "rejected")} disabled={working}>Reject</button></div>}</div>)}</div> : <EmptyState title="No candidates" description="Run Source discovery when a Watch has relevant corpus state." />}</SectionCard>
    </div>
    <SectionCard title="Attached Sources" description="Approved Sources use the normal Monitor acquisition path.">{watch.sources?.length ? <div className="resource-list">{watch.sources.map((item) => <div className="resource-row" key={text(item.source?.id)}><span><strong>{text(item.source?.name)}</strong><small>{text(item.source?.domain)} · next {formatDate(text(item.monitor?.next_check_at, "Not scheduled"))}</small></span><Badge tone={item.monitor?.enabled ? "mint" : "neutral"}>{item.monitor?.enabled ? "enabled" : "paused"}</Badge></div>)}</div> : <EmptyState title="No attached Sources" description="Approve a Source candidate to start normal acquisition." />}</SectionCard>
  </>;
}
