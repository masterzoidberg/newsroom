import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, formatDate, isApiUnavailable, jsonBody, shortId } from "../lib/api";
import type { CollectionRecord } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";

type Watch = CollectionRecord & {
  target_type?: string;
  target_id?: string;
  vocabulary?: CollectionRecord[];
  primary_terms?: CollectionRecord[];
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

type SetupDraft = {
  request_id: string;
  interest: string;
  name: string;
  primary_terms: string[];
  term_draft: string;
  name_touched: boolean;
  term_touched: boolean;
};

type PausedWatchDraft = {
  resumed: boolean;
  watch_id: string;
  topic_id: string;
  policy_id: string;
  status: "paused";
  next_action: "add_sources";
  primary_terms: string[];
};

const SETUP_DRAFT_KEY = "newsroom.watch-setup.v1";
const SELECTED_WATCH_KEY = "newsroom.selected-watch.v1";
const MAX_PRIMARY_TERMS = 100;
const MAX_PRIMARY_TERM_LENGTH = 300;
const text = (value: unknown, fallback = "—") => String(value ?? fallback);

function freshSetupDraft(): SetupDraft {
  return {
    request_id: window.crypto.randomUUID(),
    interest: "",
    name: "",
    primary_terms: [],
    term_draft: "",
    name_touched: false,
    term_touched: false,
  };
}

function loadStoredSetupDraft(): SetupDraft {
  try {
    const raw = window.localStorage.getItem(SETUP_DRAFT_KEY);
    if (!raw) return freshSetupDraft();
    const saved = JSON.parse(raw) as Partial<SetupDraft>;
    if (typeof saved.request_id !== "string" || typeof saved.interest !== "string" || typeof saved.name !== "string") return freshSetupDraft();
    const primaryTerms = Array.isArray(saved.primary_terms) ? saved.primary_terms.filter((item): item is string => typeof item === "string").slice(0, MAX_PRIMARY_TERMS) : [];
    return {
      request_id: saved.request_id,
      interest: saved.interest,
      name: saved.name,
      primary_terms: primaryTerms,
      term_draft: typeof saved.term_draft === "string" ? saved.term_draft : "",
      name_touched: saved.name_touched === true,
      term_touched: saved.term_touched === true,
    };
  } catch {
    return freshSetupDraft();
  }
}

function normalizedTerm(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

export function WatchManagementView() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [policies, setPolicies] = useState<CollectionRecord[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<Watch | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [setupDraft, setSetupDraft] = useState<SetupDraft>(loadStoredSetupDraft);
  const [setupError, setSetupError] = useState<unknown>(null);
  const [setupValidation, setSetupValidation] = useState("");
  const [setupSaved, setSetupSaved] = useState("");
  const [policyId, setPolicyId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [targetType, setTargetType] = useState("topic");
  const [legacyWatchName, setLegacyWatchName] = useState("");
  const [legacyPolicyName, setLegacyPolicyName] = useState("");
  const [editName, setEditName] = useState("");
  const [term, setTerm] = useState("");
  const [kind, setKind] = useState("alias");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try { window.localStorage.setItem(SETUP_DRAFT_KEY, JSON.stringify(setupDraft)); } catch { /* Browser storage may be unavailable. */ }
  }, [setupDraft]);

  const loadDetail = useCallback(async (id: string) => {
    const watch = await apiFetch<Watch>(`/watches/${id}`);
    const primaryTermsRequest = watch.target_type === "topic" && watch.target_id
      ? apiList<CollectionRecord>(`/topics/${watch.target_id}/vocabulary?page_size=100`)
      : Promise.resolve({ items: [] as CollectionRecord[] });
    const [watchHealth, vocabulary, candidates, sources, primaryTerms] = await Promise.all([
      apiFetch<Health>(`/watches/${id}/health`),
      apiList<CollectionRecord>(`/watches/${id}/vocabulary?page_size=100`),
      apiList<CollectionRecord>(`/watches/${id}/source-candidates?page_size=100`),
      apiList<{ source?: CollectionRecord; monitor?: CollectionRecord }>(`/watches/${id}/sources?page_size=100`),
      primaryTermsRequest,
    ]);
    setSelected({ ...watch, vocabulary: vocabulary.items, primary_terms: primaryTerms.items, source_candidates: candidates.items, sources: sources.items });
    setHealth(watchHealth);
    setEditName(text(watch.name, ""));
  }, []);

  const load = useCallback(async (preferredId = "") => {
    setLoading(true);
    setError(null);
    try {
      const [watchResult, policyResult] = await Promise.all([
        apiList<Watch>("/watches?page_size=100"),
        apiList<CollectionRecord>("/monitoring-policies?page_size=100"),
      ]);
      setWatches(watchResult.items);
      setPolicies(policyResult.items);
      setPolicyId((current) => current && policyResult.items.some((item) => item.id === current) ? current : policyResult.items[0]?.id ?? "");
      let storedId = preferredId;
      if (!storedId) {
        try { storedId = window.localStorage.getItem(SELECTED_WATCH_KEY) ?? ""; } catch { storedId = ""; }
      }
      const nextId = storedId && watchResult.items.some((item) => item.id === storedId) ? storedId : watchResult.items[0]?.id ?? "";
      setSelectedId(nextId);
      if (nextId) {
        try { window.localStorage.setItem(SELECTED_WATCH_KEY, nextId); } catch { /* Keep in-memory selection. */ }
        await loadDetail(nextId);
      } else {
        setSelected(null);
        setHealth(null);
        try { window.localStorage.removeItem(SELECTED_WATCH_KEY); } catch { /* No durable selection available. */ }
      }
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, [loadDetail]);

  useEffect(() => { void load(); }, [load]);

  async function selectWatch(id: string) {
    setSelectedId(id);
    setWorking(true);
    setError(null);
    try {
      try { window.localStorage.setItem(SELECTED_WATCH_KEY, id); } catch { /* Keep in-memory selection. */ }
      await loadDetail(id);
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function refresh(id = selectedId) {
    if (!id) return;
    setWorking(true);
    try {
      await loadDetail(id);
      const result = await apiList<Watch>("/watches?page_size=100");
      setWatches(result.items);
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  function updateInterest(value: string) {
    setSetupError(null); setSetupValidation(""); setSetupSaved("");
    setSetupDraft((current) => ({
      ...current,
      interest: value,
      name: current.name_touched ? current.name : value.slice(0, 200),
      term_draft: current.term_touched || current.primary_terms.length ? current.term_draft : value.slice(0, MAX_PRIMARY_TERM_LENGTH),
    }));
  }

  function addPrimaryTerm() {
    const candidate = setupDraft.term_draft.trim();
    setSetupValidation("");
    if (!candidate) { setSetupValidation("Enter a primary term before confirming it."); return; }
    if (candidate.length > MAX_PRIMARY_TERM_LENGTH) { setSetupValidation(`Primary terms are limited to ${MAX_PRIMARY_TERM_LENGTH} characters.`); return; }
    if (setupDraft.primary_terms.length >= MAX_PRIMARY_TERMS) { setSetupValidation(`A Watch can have at most ${MAX_PRIMARY_TERMS} primary terms during setup.`); return; }
    const identity = normalizedTerm(candidate);
    if (setupDraft.primary_terms.some((item) => normalizedTerm(item) === identity)) {
      setSetupDraft((current) => ({ ...current, term_draft: "", term_touched: true }));
      return;
    }
    setSetupDraft((current) => ({ ...current, primary_terms: [...current.primary_terms, candidate], term_draft: "", term_touched: true }));
  }

  function removePrimaryTerm(index: number) {
    setSetupDraft((current) => ({ ...current, primary_terms: current.primary_terms.filter((_item, itemIndex) => itemIndex !== index), term_touched: true }));
  }

  async function saveSetup() {
    if (!setupDraft.interest.trim() || !setupDraft.name.trim() || setupDraft.primary_terms.length === 0) {
      setSetupValidation("Enter an interest and name, then explicitly confirm at least one primary term.");
      return;
    }
    setWorking(true); setSetupError(null); setSetupValidation(""); setSetupSaved("");
    try {
      const result = await apiFetch<PausedWatchDraft>("/watches/setup", {
        method: "POST",
        body: jsonBody({
          request_id: setupDraft.request_id,
          interest: setupDraft.interest.trim(),
          name: setupDraft.name.trim(),
          primary_terms: setupDraft.primary_terms,
        }),
      });
      try {
        window.localStorage.setItem(SELECTED_WATCH_KEY, result.watch_id);
        window.localStorage.removeItem(SETUP_DRAFT_KEY);
      } catch { /* The server draft remains canonical even without browser storage. */ }
      setSelectedId(result.watch_id);
      setSetupSaved(result.resumed ? "Recovered the same saved paused Watch. Next: Add Sources." : "Setup saved as a paused Watch. Nothing is collecting yet. Next: Add Sources.");
      setSetupDraft(freshSetupDraft());
      await load(result.watch_id);
    } catch (caught) {
      setSetupError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function submitSetup(event: FormEvent) {
    event.preventDefault();
    await saveSetup();
  }

  async function createPolicy(event: FormEvent) {
    event.preventDefault(); if (!legacyPolicyName.trim()) return;
    setWorking(true); setError(null);
    try {
      const policy = await apiFetch<CollectionRecord>("/monitoring-policies", { method: "POST", body: jsonBody({ name: legacyPolicyName.trim(), allowed_channels: ["direct_http"], base_cadence_seconds: 3600, min_cadence_seconds: 900, max_cadence_seconds: 86400, priority: "normal", query_budget: 10, local_model_budget: 10, paid_budget_usd: 0 }) });
      setPolicies((items) => [...items, policy]);
      setPolicyId(policy.id);
      setLegacyPolicyName("");
    } catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function createWatch(event: FormEvent) {
    event.preventDefault(); if (!targetId.trim() || !policyId || !legacyWatchName.trim()) return;
    setWorking(true); setError(null);
    try {
      const watch = await apiFetch<Watch>("/watches", { method: "POST", body: jsonBody({ name: legacyWatchName.trim(), target_type: targetType, target_id: targetId.trim(), policy_id: policyId }) });
      setTargetId(""); setLegacyWatchName("");
      try { window.localStorage.setItem(SELECTED_WATCH_KEY, watch.id); } catch { /* Keep in-memory selection. */ }
      await load(watch.id);
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

  if (loading) return <><PageHeader eyebrow="Configure" title="Watches" description="Persistent monitoring intent, approved vocabulary, Sources, and schedules." /><LoadingState label="Loading Watches" />{error && <ErrorState error={error} />}</>;

  const setupTitle = watches.length ? "Create another Watch" : "What do you want Newsroom to watch?";
  const canDiscover = Boolean(selectedId && selected?.status === "active");
  return <>
    <PageHeader eyebrow="Configure / intelligent monitoring" title="Watches" description="Start with an interest in ordinary language. Newsroom saves the setup paused so you can review scope and Sources before collection begins." action={canDiscover ? <button className="secondary-button" type="button" onClick={() => void action("discover-sources", { limit: 25 })} disabled={working}>Discover Sources</button> : undefined} />
    {error && <ErrorState error={error} retry={() => void load(selectedId)} />}

    <SectionCard title={setupTitle} description="No internal IDs are required. This step creates a Topic, confirmed primary scope, private zero-paid hourly policy, and paused Watch together.">
      <form className="stack-form" onSubmit={(event) => void submitSetup(event)} aria-busy={working}>
        <label htmlFor="watch-interest">Interest</label>
        <textarea id="watch-interest" rows={4} maxLength={2000} value={setupDraft.interest} onChange={(event) => updateInterest(event.target.value)} placeholder="What do you want to stay on top of?" />
        <label htmlFor="watch-setup-name">Watch name</label>
        <input id="watch-setup-name" maxLength={200} value={setupDraft.name} onChange={(event) => { setSetupSaved(""); setSetupDraft((current) => ({ ...current, name: event.target.value, name_touched: true })); }} placeholder="A short name you will recognize" />
        <label htmlFor="watch-primary-term">Primary term to confirm</label>
        <input id="watch-primary-term" maxLength={MAX_PRIMARY_TERM_LENGTH} value={setupDraft.term_draft} onChange={(event) => { setSetupValidation(""); setSetupDraft((current) => ({ ...current, term_draft: event.target.value, term_touched: true })); }} placeholder="Seeded from your interest; edit before confirming" aria-describedby="primary-term-help" />
        <p id="primary-term-help" className="status-note">Confirm at least one exact term. Newsroom will not invent or preapprove synonyms in this step.</p>
        <div className="button-row"><button className="secondary-button" type="button" onClick={addPrimaryTerm} disabled={working || !setupDraft.term_draft.trim() || setupDraft.primary_terms.length >= MAX_PRIMARY_TERMS}>Confirm primary term</button></div>
        {setupDraft.primary_terms.length > 0 && <div className="resource-list" aria-label="Confirmed primary terms">{setupDraft.primary_terms.map((primaryTerm, index) => <div className="resource-row" key={`${normalizedTerm(primaryTerm)}-${index}`}><span><strong>{primaryTerm}</strong><small>Confirmed primary monitoring term</small></span><button className="quiet-button" type="button" onClick={() => removePrimaryTerm(index)} disabled={working} aria-label={`Remove primary term ${primaryTerm}`}>Remove</button></div>)}</div>}
        {setupValidation && <p className="status-note" role="alert">{setupValidation}</p>}
        {setupError !== null && <div className="state-panel error-panel" role="alert"><strong>Could not save this Watch.</strong><p>{setupError instanceof Error ? setupError.message : "The request failed."}</p>{isApiUnavailable(setupError) && <p>Use your installed Start Newsroom launcher to start the local service, reload this page, and retry. Your draft and request identity are retained in this browser.</p>}<button className="secondary-button" type="button" onClick={() => void saveSetup()} disabled={working}>Retry the same save</button></div>}
        {setupSaved && <p className="status-note" role="status"><strong>{setupSaved}</strong></p>}
        <button className="primary-button" type="submit" disabled={working || !setupDraft.interest.trim() || !setupDraft.name.trim() || setupDraft.primary_terms.length === 0}>{working ? "Saving paused Watch…" : setupError ? "Retry save" : "Save paused Watch"}</button>
      </form>
    </SectionCard>

    <details className="section-card">
      <summary><strong>Advanced: create from an existing canonical object</strong></summary>
      <p className="muted">These controls preserve the existing ID-based workflow for advanced use. Ordinary Watch setup above does not require IDs or a separately created policy.</p>
      <div className="content-grid">
        <SectionCard title="Existing target" description="Create a Watch against an existing Topic, Subject, Story, Source, or Research Question.">
          <form className="stack-form" onSubmit={createWatch}><label htmlFor="watch-target-type">Target type</label><select id="watch-target-type" value={targetType} onChange={(event) => setTargetType(event.target.value)}><option value="topic">Topic</option><option value="subject">Subject</option><option value="story">Story</option><option value="source">Source</option><option value="research_question">Research Question</option></select><label htmlFor="watch-target-id">Target ID</label><input id="watch-target-id" value={targetId} onChange={(event) => setTargetId(event.target.value)} placeholder="canonical target ID" /><label htmlFor="legacy-watch-name">Watch name</label><input id="legacy-watch-name" value={legacyWatchName} onChange={(event) => setLegacyWatchName(event.target.value)} /><button className="primary-button" type="submit" disabled={working || !policyId || !targetId.trim() || !legacyWatchName.trim()}>Create Watch</button></form>
        </SectionCard>
        <SectionCard title="Monitoring policy" description="Advanced cadence and budget policy controls."><form className="stack-form" onSubmit={createPolicy}><label htmlFor="policy-name">Policy name</label><input id="policy-name" value={legacyPolicyName} onChange={(event) => setLegacyPolicyName(event.target.value)} /><button className="secondary-button" type="submit" disabled={working || !legacyPolicyName.trim()}>Create policy</button></form>{policies.length ? <div className="resource-list">{policies.map((policy) => <button type="button" className={`resource-row ${policy.id === policyId ? "selected" : ""}`} key={policy.id} onClick={() => setPolicyId(policy.id)}><span><strong>{text(policy.name, "Policy")}</strong><small>{shortId(policy.id)} · {text(policy.priority, "normal")}</small></span><Badge tone={policy.id === policyId ? "mint" : "neutral"}>{policy.id === policyId ? "selected" : "select"}</Badge></button>)}</div> : <EmptyState title="No policy" description="Create an advanced policy before using the canonical-ID workflow." />}</SectionCard>
      </div>
    </details>

    <SectionCard title="Configured Watches" description={`${watches.length} Watch${watches.length === 1 ? "" : "es"}; select one to inspect its durable state.`}>{watches.length ? <div className="resource-list">{watches.map((watch) => <button type="button" className={`resource-row ${selectedId === watch.id ? "selected" : ""}`} key={watch.id} onClick={() => void selectWatch(watch.id)}><span><strong>{text(watch.name, text(watch.target_type))}</strong><small>{text(watch.target_type, "Watch")} · {text(watch.status, "active")}</small></span><Badge tone={watch.status === "active" ? "mint" : "neutral"}>{text(watch.status, "active")}</Badge></button>)}</div> : <EmptyState title="No Watches yet" description="Use the interest form above to save your first paused Watch." />}</SectionCard>
    {selected && health && <WatchDetail watch={selected} health={health} name={editName} setName={setEditName} term={term} setTerm={setTerm} kind={kind} setKind={setKind} working={working} onSave={saveName} onAddTerm={addTerm} onAction={action} onReview={review} />}
  </>;
}

function WatchDetail({ watch, health, name, setName, term, setTerm, kind, setKind, working, onSave, onAddTerm, onAction, onReview }: { watch: Watch; health: Health; name: string; setName: (value: string) => void; term: string; setTerm: (value: string) => void; kind: string; setKind: (value: string) => void; working: boolean; onSave: (event: FormEvent) => void; onAddTerm: (event: FormEvent) => void; onAction: (path: string, body?: unknown) => Promise<void>; onReview: (path: string, status: "approved" | "rejected") => Promise<void> }) {
  const vocabulary = watch.vocabulary ?? [];
  const primaryTerms = watch.primary_terms ?? [];
  const candidates = watch.source_candidates ?? [];
  const sources = watch.sources ?? [];
  const canResume = health.status !== "active" && sources.length > 0;
  const isUnstartedDraft = health.status === "paused" && sources.length === 0;
  return <>
    {isUnstartedDraft && <SectionCard title="Setup saved" description="This Watch is paused and is not collecting yet."><div className="button-row"><Badge tone="neutral">Paused</Badge><Badge tone="amber">Next: Add Sources</Badge></div><p className="muted">Your approved primary terms are stored. Source selection is the next setup step; starting collection comes later after Sources and cadence are reviewed.</p></SectionCard>}
    <SectionCard title={text(watch.name)} description={`${text(watch.target_type, "Watch")} monitoring intent`} action={<div className="button-row"><Badge tone={health.status === "active" ? "mint" : "neutral"}>{health.status}</Badge>{health.status === "active" && <button className="quiet-button" type="button" onClick={() => void onAction("pause")} disabled={working}>Pause</button>}{canResume && <button className="quiet-button" type="button" onClick={() => void onAction("resume")} disabled={working}>Resume</button>}{sources.length > 0 && <button className="secondary-button" type="button" onClick={() => void onAction("vocabulary/suggest", { limit: 20 })} disabled={working}>Suggest vocabulary</button>}</div>}>
      <div className="stats-grid"><Stat label="Active Sources" value={health.active_source_count} tone="mint" /><Stat label="Pending terms" value={health.pending_vocabulary_suggestion_count} tone="amber" /><Stat label="Pending Sources" value={health.pending_source_candidate_count} tone="amber" /><Stat label="Next run" value={formatDate(text(health.next_scheduled_run, "Not scheduled"))} /></div>
      <form className="inline-form" onSubmit={onSave}><label htmlFor="selected-watch-name">Edit name</label><input id="selected-watch-name" value={name} onChange={(event) => setName(event.target.value)} /><button className="secondary-button" type="submit" disabled={working}>Save</button></form>
      {health.last_error && <p className="status-note">Recent error: {health.last_error}</p>}
    </SectionCard>
    {watch.target_type === "topic" && <SectionCard title="Confirmed primary scope" description="These exact Topic terms are active monitoring scope. AST-24 does not generate or preapprove additional semantics.">{primaryTerms.length ? <div className="resource-list">{primaryTerms.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.term)}</strong><small>{text(item.term_type, "include")} · {text(item.concept_kind, "term")}</small></span><Badge tone="mint">confirmed</Badge></div>)}</div> : <EmptyState title="No primary terms" description="This Topic has no confirmed primary scope. Edit the Topic vocabulary before relying on it for monitoring." />}</SectionCard>}
    <div className="content-grid">
      <SectionCard title="Additional vocabulary" description="Approved Watch vocabulary affects future monitoring; suggestions remain inert until reviewed."><form className="inline-form" onSubmit={onAddTerm}><label htmlFor="watch-term">Add term</label><input id="watch-term" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Additional alias or exclusion" /><select aria-label="Vocabulary kind" value={kind} onChange={(event) => setKind(event.target.value)}><option value="alias">Alias</option><option value="synonym">Synonym</option><option value="acronym">Acronym</option><option value="acronym_expansion">Acronym expansion</option><option value="include">Include</option><option value="exclude">Exclude</option></select><button className="secondary-button" type="submit" disabled={working}>Add</button></form>{vocabulary.length ? <div className="resource-list">{vocabulary.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.term)}</strong><small>{text(item.kind)} · {text(item.origin)} · {text(item.status)}</small></span>{item.status === "suggested" && <div className="button-row"><button className="secondary-button" type="button" onClick={() => void onReview(`vocabulary/${item.id}`, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void onReview(`vocabulary/${item.id}`, "rejected")} disabled={working}>Reject</button></div>}</div>)}</div> : <EmptyState title="No additional vocabulary" description="The confirmed Topic terms above are enough for the paused draft. Additional vocabulary can be reviewed later." />}</SectionCard>
      <SectionCard title="Source candidates" description="Candidates retain URL, method, rationale, and provenance until reviewed.">{candidates.length ? <div className="resource-list">{candidates.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.name)}</strong><small>{text(item.homepage_url)} · {text(item.discovery_method)} · {text(item.rationale)}</small></span>{item.status === "suggested" && <div className="button-row"><button className="secondary-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "rejected")} disabled={working}>Reject</button></div>}</div>)}</div> : <EmptyState title="No candidates" description={isUnstartedDraft ? "Add Sources is the next setup step. No Source has been approved yet." : "Run Source discovery when a Watch has relevant corpus state."} />}</SectionCard>
    </div>
    <SectionCard title="Attached Sources" description="Approved Sources use the normal Monitor acquisition path.">{sources.length ? <div className="resource-list">{sources.map((item) => <div className="resource-row" key={text(item.source?.id)}><span><strong>{text(item.source?.name)}</strong><small>{text(item.source?.domain)} · next {formatDate(text(item.monitor?.next_check_at, "Not scheduled"))}</small></span><Badge tone={item.monitor?.enabled ? "mint" : "neutral"}>{item.monitor?.enabled ? "enabled" : "paused"}</Badge></div>)}</div> : <EmptyState title="No attached Sources" description={isUnstartedDraft ? "Your Watch is safely paused. Add Sources is next; nothing is collecting yet." : "Approve a Source candidate to start normal acquisition."} />}</SectionCard>
  </>;
}
