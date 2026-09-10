import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, formatDate, isApiUnavailable, jsonBody, shortId } from "../lib/api";
import type { CollectionRecord } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";

type Watch = CollectionRecord & {
  target_type?: string;
  target_id?: string;
  policy?: CollectionRecord;
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

type SetupSubmission = {
  request_id: string;
  interest: string;
  name: string;
  primary_terms: string[];
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

type SourceCandidateInput = {
  source_id?: string;
  name: string;
  homepage_url?: string;
  feed_url?: string;
  discovery_method: "manual" | "existing_source";
  rationale: string;
};

const SETUP_DRAFT_KEY = "newsroom.watch-setup.v2";
const SETUP_PENDING_KEY = "newsroom.watch-setup.pending.v1";
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

function validPrimaryTerms(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const terms = value.filter((item): item is string => typeof item === "string").slice(0, MAX_PRIMARY_TERMS);
  if (terms.some((item) => item.length > MAX_PRIMARY_TERM_LENGTH)) return null;
  return terms;
}

function loadStoredSetupDraft(): SetupDraft {
  try {
    const raw = window.sessionStorage.getItem(SETUP_DRAFT_KEY);
    if (!raw) return freshSetupDraft();
    const saved = JSON.parse(raw) as Partial<SetupDraft>;
    if (typeof saved.request_id !== "string" || typeof saved.interest !== "string" || typeof saved.name !== "string") return freshSetupDraft();
    const primaryTerms = validPrimaryTerms(saved.primary_terms);
    if (primaryTerms === null) return freshSetupDraft();
    return {
      request_id: saved.request_id,
      interest: saved.interest,
      name: saved.name,
      primary_terms: primaryTerms,
      term_draft: typeof saved.term_draft === "string" && saved.term_draft.length <= MAX_PRIMARY_TERM_LENGTH ? saved.term_draft : "",
      name_touched: saved.name_touched === true,
      term_touched: saved.term_touched === true,
    };
  } catch {
    return freshSetupDraft();
  }
}

function loadStoredPendingSubmission(): SetupSubmission | null {
  try {
    const raw = window.sessionStorage.getItem(SETUP_PENDING_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as Partial<SetupSubmission>;
    const primaryTerms = validPrimaryTerms(saved.primary_terms);
    if (
      typeof saved.request_id !== "string" || !saved.request_id ||
      typeof saved.interest !== "string" || !saved.interest.trim() ||
      typeof saved.name !== "string" || !saved.name.trim() ||
      primaryTerms === null || primaryTerms.length === 0
    ) return null;
    return {
      request_id: saved.request_id,
      interest: saved.interest,
      name: saved.name,
      primary_terms: primaryTerms,
    };
  } catch {
    return null;
  }
}

function persistPendingSubmission(submission: SetupSubmission | null) {
  try {
    if (submission) window.sessionStorage.setItem(SETUP_PENDING_KEY, JSON.stringify(submission));
    else window.sessionStorage.removeItem(SETUP_PENDING_KEY);
  } catch { /* Keep in-memory recovery when browser storage is unavailable. */ }
}

function normalizedTerm(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function submissionFromDraft(draft: SetupDraft): SetupSubmission {
  return {
    request_id: draft.request_id,
    interest: draft.interest.trim(),
    name: draft.name.trim(),
    primary_terms: draft.primary_terms.map((item) => item.trim()),
  };
}

export function WatchManagementView() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [policies, setPolicies] = useState<CollectionRecord[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<Watch | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [setupDraft, setSetupDraft] = useState<SetupDraft>(loadStoredSetupDraft);
  const [pendingSubmission, setPendingSubmission] = useState<SetupSubmission | null>(loadStoredPendingSubmission);
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
    try { window.sessionStorage.setItem(SETUP_DRAFT_KEY, JSON.stringify(setupDraft)); } catch { /* Browser storage may be unavailable. */ }
  }, [setupDraft]);

  useEffect(() => { persistPendingSubmission(pendingSubmission); }, [pendingSubmission]);

  const loadDetail = useCallback(async (id: string) => {
    const watch = await apiFetch<Watch>(`/watches/${id}`);
    const policyRequest = watch.policy_id
      ? apiFetch<CollectionRecord>(`/monitoring-policies/${watch.policy_id}`)
      : Promise.resolve(null);
    const primaryTermsRequest = watch.target_type === "topic" && watch.target_id
      ? apiList<CollectionRecord>(`/topics/${watch.target_id}/vocabulary?page_size=100`)
      : Promise.resolve({ items: [] as CollectionRecord[] });
    const [watchHealth, vocabulary, candidates, sources, primaryTerms, policy] = await Promise.all([
      apiFetch<Health>(`/watches/${id}/health`),
      apiList<CollectionRecord>(`/watches/${id}/vocabulary?page_size=100`),
      apiList<CollectionRecord>(`/watches/${id}/source-candidates?page_size=100`),
      apiList<{ source?: CollectionRecord; monitor?: CollectionRecord }>(`/watches/${id}/sources?page_size=100`),
      primaryTermsRequest,
      policyRequest,
    ]);
    setSelected({ ...watch, policy: policy ?? undefined, vocabulary: vocabulary.items, primary_terms: primaryTerms.items, source_candidates: candidates.items, sources: sources.items });
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
    const materialChange = normalizedTerm(setupDraft.interest) !== normalizedTerm(value);
    const invalidatedApproval = materialChange && setupDraft.primary_terms.length > 0;
    setSetupError(null);
    setSetupSaved("");
    setSetupValidation(invalidatedApproval ? "Interest changed. Reconfirm at least one primary term before saving." : "");
    setSetupDraft((current) => ({
      ...current,
      interest: value,
      name: current.name_touched ? current.name : value.slice(0, 200),
      primary_terms: materialChange ? [] : current.primary_terms,
      term_draft: materialChange ? value.slice(0, MAX_PRIMARY_TERM_LENGTH) : current.term_draft,
      term_touched: materialChange ? false : current.term_touched,
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

  async function attemptSetup(submission: SetupSubmission) {
    setWorking(true); setSetupError(null); setSetupValidation(""); setSetupSaved("");
    try {
      const result = await apiFetch<PausedWatchDraft>("/watches/setup", {
        method: "POST",
        body: jsonBody(submission),
      });
      try {
        window.localStorage.setItem(SELECTED_WATCH_KEY, result.watch_id);
        window.sessionStorage.removeItem(SETUP_DRAFT_KEY);
        window.sessionStorage.removeItem(SETUP_PENDING_KEY);
      } catch { /* The server draft remains canonical even without browser storage. */ }
      setPendingSubmission(null);
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

  async function saveSetup() {
    if (pendingSubmission) {
      setSetupValidation("A previous save may already have reached Newsroom. Retry that exact submitted save before starting another.");
      return;
    }
    if (!setupDraft.interest.trim() || !setupDraft.name.trim() || setupDraft.primary_terms.length === 0) {
      setSetupValidation("Enter an interest and name, then explicitly confirm at least one primary term.");
      return;
    }
    const submission = submissionFromDraft(setupDraft);
    persistPendingSubmission(submission);
    setPendingSubmission(submission);
    await attemptSetup(submission);
  }

  async function retryPendingSetup() {
    if (!pendingSubmission) return;
    await attemptSetup(pendingSubmission);
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

  async function addSourceCandidate(input: SourceCandidateInput) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/watches/${selectedId}/source-candidates`, { method: "POST", body: jsonBody(input) });
      await refresh();
    } catch (caught) { setError(caught); throw caught; } finally { setWorking(false); }
  }

  async function detachSource(sourceId: string) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try { await apiFetch(`/watches/${selectedId}/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" }); await refresh(); }
    catch (caught) { setError(caught); } finally { setWorking(false); }
  }

  async function updateCadence(baseCadenceSeconds: number) {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      await apiFetch(`/watches/${selectedId}/cadence`, { method: "PATCH", body: jsonBody({ base_cadence_seconds: baseCadenceSeconds }) });
      await refresh();
    } catch (caught) { setError(caught); throw caught; } finally { setWorking(false); }
  }

  async function review(path: string, status: "approved" | "rejected") { await action(`${path}/review`, { status }); }

  if (loading) return <><PageHeader eyebrow="Configure" title="Watches" description="Persistent monitoring intent, approved vocabulary, Sources, and schedules." /><LoadingState label="Loading Watches" />{error && <ErrorState error={error} />}</>;

  const setupTitle = watches.length ? "Create another Watch" : "What do you want Newsroom to watch?";
  const canDiscover = Boolean(selectedId && selected?.status === "active");
  const canSubmitSetup = !working && !pendingSubmission && Boolean(setupDraft.interest.trim() && setupDraft.name.trim() && setupDraft.primary_terms.length > 0);
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
        {pendingSubmission && <div className="state-panel error-panel" role={setupError !== null ? "alert" : "status"}><strong>{setupError !== null ? "Could not confirm this save." : "A previous save still needs confirmation."}</strong>{setupError !== null && <p>{setupError instanceof Error ? setupError.message : "The request failed."}</p>}{isApiUnavailable(setupError) && <p>Use your installed Start Newsroom launcher to start the local service, reload this page, and retry. The exact submitted request is retained in this tab.</p>}<p>Retry will resend the original submitted Watch named <strong>{pendingSubmission.name}</strong> with the same approved scope. Later edits in this form are kept separate until that save is resolved.</p><button className="secondary-button" type="button" onClick={() => void retryPendingSetup()} disabled={working}>Retry the same save</button></div>}
        {setupError !== null && !pendingSubmission && <div className="state-panel error-panel" role="alert"><strong>Could not save this Watch.</strong><p>{setupError instanceof Error ? setupError.message : "The request failed."}</p>{isApiUnavailable(setupError) && <p>Use your installed Start Newsroom launcher to start the local service, reload this page, and retry.</p>}</div>}
        {setupSaved && <p className="status-note" role="status"><strong>{setupSaved}</strong></p>}
        <button className="primary-button" type="submit" disabled={!canSubmitSetup}>{working ? "Saving paused Watch…" : pendingSubmission ? "Resolve previous save first" : "Save paused Watch"}</button>
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
    {selected && health && <WatchDetail watch={selected} health={health} name={editName} setName={setEditName} term={term} setTerm={setTerm} kind={kind} setKind={setKind} working={working} onSave={saveName} onAddTerm={addTerm} onAddSource={addSourceCandidate} onDetachSource={detachSource} onUpdateCadence={updateCadence} onAction={action} onReview={review} />}
  </>;
}

type CadenceChoice = "hourly" | "several_times_daily" | "daily" | "custom";

const PRESET_SECONDS: Record<Exclude<CadenceChoice, "custom">, number> = {
  hourly: 3_600,
  several_times_daily: 21_600,
  daily: 86_400,
};

function numericValue(value: unknown, fallback: number): number {
  const result = typeof value === "number" ? value : Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function cadenceChoice(seconds: number): CadenceChoice {
  if (seconds === PRESET_SECONDS.hourly) return "hourly";
  if (seconds === PRESET_SECONDS.several_times_daily) return "several_times_daily";
  if (seconds === PRESET_SECONDS.daily) return "daily";
  return "custom";
}

function cadenceLabel(seconds: number): string {
  if (seconds % 86_400 === 0) return `every ${seconds / 86_400} day${seconds === 86_400 ? "" : "s"}`;
  if (seconds % 3_600 === 0) return `every ${seconds / 3_600} hour${seconds === 3_600 ? "" : "s"}`;
  if (seconds % 60 === 0) return `every ${seconds / 60} minute${seconds === 60 ? "" : "s"}`;
  return `every ${seconds} seconds`;
}

function formatNextCheck(value: string | null | undefined): string {
  if (!value) return "Not scheduled while this Watch is paused";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZoneName: "short" }).format(date);
}

function CadenceSetup({ watch, health, policy, working, onSave }: { watch: Watch; health: Health; policy?: CollectionRecord; working: boolean; onSave: (seconds: number) => Promise<void> }) {
  const base = numericValue(policy?.base_cadence_seconds, 3_600);
  const minimum = numericValue(policy?.min_cadence_seconds, 1);
  const maximum = numericValue(policy?.max_cadence_seconds, 31_536_000);
  const [choice, setChoice] = useState<CadenceChoice>(cadenceChoice(base));
  const [seconds, setSeconds] = useState(String(base));
  const [validation, setValidation] = useState("");

  useEffect(() => {
    setChoice(cadenceChoice(base));
    setSeconds(String(base));
    setValidation("");
  }, [policy?.id, base]);

  function choose(value: CadenceChoice) {
    setChoice(value);
    if (value !== "custom") setSeconds(String(PRESET_SECONDS[value]));
    setValidation("");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const value = Number(seconds);
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
      setValidation(`Choose a cadence between ${cadenceLabel(minimum)} and ${cadenceLabel(maximum)}.`);
      return;
    }
    try { await onSave(value); setValidation(""); } catch { /* The parent keeps the last good policy and renders recovery. */ }
  }

  const channels = Array.isArray(policy?.allowed_channels) ? policy.allowed_channels.map(String) : [];
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "local time";
  return <SectionCard title="Cadence" description="Choose how often this Watch should be checked. These choices update only this Watch's policy and do not start collection.">
    <form className="stack-form" onSubmit={(event) => void save(event)}>
      <label htmlFor="watch-cadence-choice">Check frequency</label>
      <select id="watch-cadence-choice" value={choice} onChange={(event) => choose(event.target.value as CadenceChoice)} disabled={working}>
        <option value="hourly">Hourly</option>
        <option value="several_times_daily">Several times daily (every 6 hours)</option>
        <option value="daily">Daily</option>
        <option value="custom">Custom interval</option>
      </select>
      {choice === "custom" && <><label htmlFor="watch-cadence-seconds">Custom interval in seconds</label><input id="watch-cadence-seconds" type="number" min={minimum} max={maximum} step={1} value={seconds} onChange={(event) => { setSeconds(event.target.value); setValidation(""); }} onInvalid={(event) => { event.preventDefault(); setValidation(`Choose a cadence between ${cadenceLabel(minimum)} and ${cadenceLabel(maximum)}.`); }} aria-describedby="watch-cadence-help" /><p id="watch-cadence-help" className="status-note">Supported range: {cadenceLabel(minimum)} to {cadenceLabel(maximum)}.</p></>}
      {validation && <p className="status-note" role="alert">{validation}</p>}
      <div className="stats-grid"><Stat label="Saved cadence" value={cadenceLabel(base)} /><Stat label="Next check" value={formatNextCheck(health.next_scheduled_run)} /><Stat label="Timezone" value={timezone} /></div>
      <p className="muted">Supported channels: {channels.length ? channels.join(", ") : "none configured"}. Paid mode: {numericValue(policy?.paid_budget_usd, 0) === 0 ? "zero paid calls" : "configured server policy"}. {watch.status === "paused" ? "This Watch remains paused until you explicitly start it." : "This change preserves the Watch's current state."}</p>
      <button className="secondary-button" type="submit" disabled={working}>{working ? "Saving cadence…" : "Save cadence"}</button>
    </form>
  </SectionCard>;
}

function SourceSetup({ working, onCreate }: { working: boolean; onCreate: (input: SourceCandidateInput) => Promise<void> }) {
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<CollectionRecord[]>([]);
  const [searched, setSearched] = useState(false);
  const [searchError, setSearchError] = useState<unknown>(null);
  const [manualName, setManualName] = useState("");
  const [homepageUrl, setHomepageUrl] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [rationale, setRationale] = useState("Added manually by the owner.");
  const [formError, setFormError] = useState("");

  async function search(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (!value) { setSearchError(new Error("Enter a Source name or URL to search.")); return; }
    setSearchError(null); setSearched(true);
    try { setMatches((await apiList<CollectionRecord>(`/sources?q=${encodeURIComponent(value)}&page_size=25`)).items); }
    catch (caught) { setSearchError(caught); setMatches([]); }
  }

  async function previewExisting(source: CollectionRecord) {
    setFormError("");
    try {
      await onCreate({
        source_id: source.id,
        name: text(source.name, "Existing Source"),
        discovery_method: "existing_source",
        rationale: "Existing Source selected by name or URL; review before attaching.",
      });
      setQuery(""); setMatches([]); setSearched(false);
    } catch (caught) { setFormError(caught instanceof Error ? caught.message : "Could not create the Source preview."); }
  }

  async function previewManual(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    if (!manualName.trim() || !homepageUrl.trim() || !rationale.trim()) {
      setFormError("Enter a Source name, homepage or feed URL, and a reason before previewing.");
      return;
    }
    try {
      await onCreate({
        name: manualName.trim(),
        homepage_url: homepageUrl.trim(),
        feed_url: feedUrl.trim() || undefined,
        discovery_method: "manual",
        rationale: rationale.trim(),
      });
      setManualName(""); setHomepageUrl(""); setFeedUrl(""); setRationale("Added manually by the owner.");
    } catch (caught) { setFormError(caught instanceof Error ? caught.message : "Could not create the Source preview."); }
  }

  return <SectionCard title="Add Sources" description="Search by name or URL to reuse an existing Source, or preview a manual page/feed. A preview is never attached until you explicitly approve it.">
    <form className="inline-form" onSubmit={(event) => void search(event)}>
      <label htmlFor="existing-source-search">Find an existing Source</label>
      <input id="existing-source-search" value={query} onChange={(event) => { setQuery(event.target.value); setSearchError(null); }} placeholder="Source name or URL" />
      <button className="secondary-button" type="submit" disabled={working}>Search Sources</button>
    </form>
    {searchError !== null && <p className="status-note" role="alert">{searchError instanceof Error ? searchError.message : "Source search failed."}</p>}
    {searched && (matches.length ? <div className="resource-list" aria-label="Existing Source search results">{matches.map((source) => <div className="resource-row" key={source.id}><span><strong>{text(source.name, "Unnamed Source")}</strong><small>{text(source.domain, text(source.homepage_url, "No domain recorded"))}</small></span><button className="secondary-button" type="button" onClick={() => void previewExisting(source)} disabled={working || !text(source.homepage_url, text(source.feed_url, ""))}>Preview Source</button></div>)}</div> : <EmptyState title="No matching Sources" description="Try another name or URL, or use the manual preview below." />)}
    <form className="stack-form" onSubmit={(event) => void previewManual(event)}>
      <h3>Preview a manual Source</h3>
      <p className="muted">Unsafe, local, and private URLs are rejected by the server before anything is saved.</p>
      <label htmlFor="manual-source-name">Source name</label>
      <input id="manual-source-name" value={manualName} onChange={(event) => setManualName(event.target.value)} placeholder="Example: NASA News" />
      <label htmlFor="manual-source-homepage">Homepage or page URL</label>
      <input id="manual-source-homepage" type="url" value={homepageUrl} onChange={(event) => setHomepageUrl(event.target.value)} placeholder="https://example.org/news" />
      <label htmlFor="manual-source-feed">Feed URL (optional)</label>
      <input id="manual-source-feed" type="url" value={feedUrl} onChange={(event) => setFeedUrl(event.target.value)} placeholder="https://example.org/feed.xml" />
      <label htmlFor="manual-source-rationale">Why this Source?</label>
      <textarea id="manual-source-rationale" rows={2} value={rationale} onChange={(event) => setRationale(event.target.value)} />
      {formError && <p className="status-note" role="alert">{formError}</p>}
      <button className="secondary-button" type="submit" disabled={working}>Preview Source for approval</button>
    </form>
  </SectionCard>;
}

function WatchDetail({ watch, health, name, setName, term, setTerm, kind, setKind, working, onSave, onAddTerm, onAddSource, onDetachSource, onUpdateCadence, onAction, onReview }: { watch: Watch; health: Health; name: string; setName: (value: string) => void; term: string; setTerm: (value: string) => void; kind: string; setKind: (value: string) => void; working: boolean; onSave: (event: FormEvent) => void; onAddTerm: (event: FormEvent) => Promise<void>; onAddSource: (input: SourceCandidateInput) => Promise<void>; onDetachSource: (sourceId: string) => Promise<void>; onUpdateCadence: (seconds: number) => Promise<void>; onAction: (path: string, body?: unknown) => Promise<void>; onReview: (path: string, status: "approved" | "rejected") => Promise<void> }) {
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
    <SourceSetup working={working} onCreate={onAddSource} />
    <div className="content-grid">
      <SectionCard title="Additional vocabulary" description="Approved Watch vocabulary affects future monitoring; suggestions remain inert until reviewed."><form className="inline-form" onSubmit={onAddTerm}><label htmlFor="watch-term">Add term</label><input id="watch-term" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Additional alias or exclusion" /><select aria-label="Vocabulary kind" value={kind} onChange={(event) => setKind(event.target.value)}><option value="alias">Alias</option><option value="synonym">Synonym</option><option value="acronym">Acronym</option><option value="acronym_expansion">Acronym expansion</option><option value="include">Include</option><option value="exclude">Exclude</option></select><button className="secondary-button" type="submit" disabled={working}>Add</button></form>{vocabulary.length ? <div className="resource-list">{vocabulary.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.term)}</strong><small>{text(item.kind)} · {text(item.origin)} · {text(item.status)}</small></span>{item.status === "suggested" && <div className="button-row"><button className="secondary-button" type="button" onClick={() => void onReview(`vocabulary/${item.id}`, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void onReview(`vocabulary/${item.id}`, "rejected")} disabled={working}>Reject</button></div>}</div>)}</div> : <EmptyState title="No additional vocabulary" description="The confirmed Topic terms above are enough for the paused draft. Additional vocabulary can be reviewed later." />}</SectionCard>
      <SectionCard title="Source previews" description="Review each candidate before attaching it. Approval reuses an existing shared Source when possible; rejection keeps the decision without attaching anything.">{candidates.length ? <div className="resource-list">{candidates.map((item) => <div className="resource-row" key={item.id}><span><strong>{text(item.name)}</strong><small>{text(item.homepage_url)} · {text(item.discovery_method)} · {text(item.rationale)}</small></span><div className="button-row"><Badge tone={item.status === "approved" ? "mint" : item.status === "rejected" ? "neutral" : "amber"}>{item.status === "suggested" ? "preview" : text(item.status)}</Badge>{item.status === "suggested" && <><button className="secondary-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "approved")} disabled={working}>Approve</button><button className="quiet-button" type="button" onClick={() => void onReview(`source-candidates/${item.id}`, "rejected")} disabled={working}>Reject</button></>}</div></div>)}</div> : <EmptyState title="No Source previews" description={isUnstartedDraft ? "Search or preview a Source above. Nothing is attached or collecting yet." : "Run Source discovery when a Watch has relevant corpus state."} />}</SectionCard>
    </div>
    <CadenceSetup watch={watch} health={health} policy={watch.policy} working={working} onSave={onUpdateCadence} />
    <SectionCard title="Attached Sources" description="Approved Sources use the normal Monitor acquisition path. Detach removes only this Watch relationship; the shared Source and its history stay intact.">{sources.length ? <div className="resource-list">{sources.map((item) => <div className="resource-row" key={text(item.source?.id)}><span><strong>{text(item.source?.name)}</strong><small>{text(item.source?.domain)} · next {formatDate(text(item.monitor?.next_check_at, "Not scheduled"))}</small></span><div className="button-row"><Badge tone={item.monitor?.enabled ? "mint" : "neutral"}>{item.monitor?.enabled ? "enabled" : "paused"}</Badge><button className="quiet-button" type="button" onClick={() => void onDetachSource(text(item.source?.id, ""))} disabled={working}>Detach</button></div></div>)}</div> : <EmptyState title="No attached Sources" description={isUnstartedDraft ? "Your Watch is safely paused. Add Sources is next; nothing is collecting yet." : "Approve a Source candidate to start normal acquisition."} />}</SectionCard>
  </>;
}
