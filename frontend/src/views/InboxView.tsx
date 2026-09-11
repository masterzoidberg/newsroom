import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, formatDate, jsonBody, shortId } from "../lib/api";
import type { AttentionItem, Briefing, Report } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";
import { queueStoryNavigation } from "./StoryEvidenceView";

type InboxViewKey = "alerts" | "reports" | "stories" | "monitors" | "documents";
type WatchPriority = "urgent" | "high" | "normal" | "low";

type HomeWatch = {
  id: string;
  name?: string;
  status?: string;
  priority?: WatchPriority;
  target_type?: string;
};

type WatchHealth = {
  watch_id: string;
  status: string;
  last_attempt?: string | null;
  last_success?: string | null;
  next_scheduled_run?: string | null;
  last_error?: string | null;
  progress?: { state: string; label: string; detail: string };
};

type ReviewChange = {
  id: string;
  revision_id: string;
  knowledge_at: string;
  publication_at?: string | null;
  claim_count: number;
  supporting_evidence_count: number;
  story: { id: string; headline: string; lifecycle: string };
  summary?: string | null;
  why_it_matters?: string | null;
  watch_context: Array<{ id: string; name: string; target_type: string }>;
};

type ReviewChangesPage = {
  cursor: string | null;
  since: string;
  items: ReviewChange[];
  next_cursor: string | null;
  has_more: boolean;
  bounded: boolean;
};

const text = (value: unknown, fallback = "—") => String(value ?? fallback);

function priorityForChange(change: ReviewChange, watches: HomeWatch[]): WatchPriority {
  const priorities = change.watch_context
    .map((context) => watches.find((watch) => watch.id === context.id)?.priority ?? "normal");
  if (priorities.includes("urgent")) return "urgent";
  if (priorities.includes("high")) return "high";
  if (priorities.length > 0 && priorities.every((priority) => priority === "low")) return "low";
  return "normal";
}

function priorityTone(priority: WatchPriority): "neutral" | "mint" | "amber" | "coral" {
  return priority === "urgent" || priority === "high" ? "coral" : priority === "low" ? "neutral" : "amber";
}

function priorityLabel(priority: WatchPriority): string {
  return priority === "urgent" ? "Urgent priority" : `${priority[0].toUpperCase()}${priority.slice(1)} priority`;
}

function freshnessLabel(watch: HomeWatch, health?: WatchHealth): string {
  if (!health) return "Health unavailable · collection time unavailable";
  if (health?.last_success) return `Last successful collection ${formatDate(health.last_success)}`;
  if (health?.status === "paused" || watch.status === "paused") return "Paused · no collection yet";
  if (health?.last_attempt) return `No successful collection yet · attempted ${formatDate(health.last_attempt)}`;
  return "No successful collection recorded";
}

function ReviewChangeRow({ change, watches, openView }: { change: ReviewChange; watches: HomeWatch[]; openView: (view: InboxViewKey) => void }) {
  const priority = priorityForChange(change, watches);
  const watchNames = change.watch_context.map((watch) => watch.name).join(", ") || "No named Watch context recorded";
  return <article className="briefing-item">
    <div>
      <div className="button-row"><Badge tone={priorityTone(priority)}>{priorityLabel(priority)}</Badge><span>{formatDate(change.knowledge_at)} known</span></div>
      <strong>{change.story.headline}</strong>
      <p>{change.why_it_matters || change.summary || "An evidence-backed material Story revision was recorded."}</p>
      <small>{watchNames} · {change.claim_count} Claim{change.claim_count === 1 ? "" : "s"} · {change.supporting_evidence_count} supporting evidence span{change.supporting_evidence_count === 1 ? "" : "s"}{change.publication_at ? ` · published ${formatDate(change.publication_at)}` : ""} · {change.story.lifecycle}</small>
    </div>
    <div className="button-row">
      <a className="secondary-button" href="#stories" onClick={() => { queueStoryNavigation({ storyId: change.story.id }); openView("stories"); }} aria-label={`Open Story review for ${change.story.headline}`}>Open Story review</a>
    </div>
  </article>;
}

export function InboxView({ openView }: { openView: (view: InboxViewKey) => void }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [watches, setWatches] = useState<HomeWatch[]>([]);
  const [watchHealth, setWatchHealth] = useState<Record<string, WatchHealth>>({});
  const [changesPage, setChangesPage] = useState<ReviewChangesPage | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [boundaryWorking, setBoundaryWorking] = useState(false);
  const [briefingWorking, setBriefingWorking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [reportResponse, attentionResponse, watchResponse, changesResponse] = await Promise.all([
        apiList<Report>("/reports?page_size=50"),
        apiFetch<{ items: AttentionItem[] }>("/attention"),
        apiList<HomeWatch>("/watches?page_size=100"),
        apiFetch<ReviewChangesPage>("/review-boundary/changes?limit=25"),
      ]);
      const healthPairs = await Promise.all(watchResponse.items.map(async (watch) => {
        try { return [watch.id, await apiFetch<WatchHealth>(`/watches/${encodeURIComponent(watch.id)}/health`)] as const; }
        catch { return [watch.id, null] as const; }
      }));
      setReports(reportResponse.items);
      setAttention(attentionResponse.items);
      setWatches(watchResponse.items);
      setWatchHealth(Object.fromEntries(healthPairs.filter((item): item is readonly [string, WatchHealth] => item[1] !== null)));
      setChangesPage(changesResponse);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function loadMoreChanges() {
    if (!changesPage?.next_cursor || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      const nextPage = await apiFetch<ReviewChangesPage>(`/review-boundary/changes?limit=25&page_token=${encodeURIComponent(changesPage.next_cursor)}`);
      setChangesPage((current) => current ? { ...nextPage, cursor: current.cursor, since: current.since, items: [...current.items, ...nextPage.items] } : nextPage);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoadingMore(false);
    }
  }

  async function advanceBoundary() {
    setBoundaryWorking(true);
    setError(null);
    try {
      await apiFetch("/review-boundary", { method: "PUT", body: jsonBody({}) });
      await load();
    } catch (caught) {
      setError(caught);
    } finally {
      setBoundaryWorking(false);
    }
  }

  async function refreshBriefing() {
    setBriefingWorking(true);
    setError(null);
    try {
      const timezone_name = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      const result = await apiFetch<Briefing>("/briefings/generate", { method: "POST", body: jsonBody({ period: "daily", timezone_name, monitor_ids: [] }) });
      setBriefing(result);
    } catch (caught) { setError(caught); } finally { setBriefingWorking(false); }
  }

  async function decideAttention(id: string, action: "seen" | "snoozed" | "not_useful") {
    try {
      await apiFetch(`/attention/${id}/decision`, { method: "POST", body: jsonBody({ action, snooze_days: action === "snoozed" ? 7 : undefined }) });
      setAttention((items) => items.filter((item) => item.id !== id));
    } catch (caught) { setError(caught); }
  }

  if (loading) return <><PageHeader eyebrow="Review" title="Home" description="Material changes, Watch freshness, and evidence-bound reports in one place." /><LoadingState />{error && <ErrorState error={error} />}</>;
  if (error && watches.length === 0) return <><PageHeader eyebrow="Review" title="Home" description="Material changes, Watch freshness, and evidence-bound reports in one place." /><ErrorState error={error} retry={() => void load()} /></>;

  if (watches.length === 0) {
    const hasExistingIntelligence = reports.length > 0 || attention.length > 0;
    return <>
      <PageHeader
        eyebrow="Welcome"
        title="Keep the signal in view."
        description="Newsroom follows what you care about and shows what changed, with the sources behind each claim. Start by saving one Watch as a paused draft so you can review its scope before anything begins collecting."
        action={<div className="button-row"><button className="primary-button" type="button" onClick={() => openView("monitors")}>Create your first Watch</button>{hasExistingIntelligence && <button className="secondary-button" type="button" onClick={() => openView("stories")}>Explore existing intelligence</button>}</div>}
      />
      {error && <ErrorState error={error} retry={() => void load()} />}
      <div className="content-grid">
        <SectionCard title="1. Tell Newsroom what matters" description="Use ordinary language. You do not need Topic IDs, policy IDs, or any other internal identifier.">
          <p className="muted">Enter an interest and a short editable Watch name. Newsroom creates the Topic and zero-paid hourly draft behind the scenes.</p>
        </SectionCard>
        <SectionCard title="2. Confirm the primary term" description="A Topic name alone is not enough monitoring scope.">
          <p className="muted">Newsroom will visibly seed a primary-term field from your interest. Review it, edit it if needed, and explicitly confirm at least one term before saving.</p>
        </SectionCard>
      </div>
      <SectionCard title="3. Save paused, then add Sources" description="Saving the setup does not start monitoring.">
        <p className="muted">The first draft stays paused and makes no paid calls. Your next setup step is Add Sources, where you can choose what Newsroom is allowed to collect from.</p>
        <div className="button-row"><button className="primary-button" type="button" onClick={() => openView("monitors")}>Create your first Watch</button></div>
      </SectionCard>
      {hasExistingIntelligence && <SectionCard title="Existing intelligence" description="Imported or previously created intelligence can still be reviewed without completing onboarding.">
        <div className="button-row"><button className="secondary-button" type="button" onClick={() => openView("stories")}>Stories</button><button className="secondary-button" type="button" onClick={() => openView("reports")}>Reports</button>{attention.length > 0 && <button className="secondary-button" type="button" onClick={() => openView("alerts")}>Alerts</button>}</div>
      </SectionCard>}
    </>;
  }

  const changes = changesPage?.items ?? [];
  const highPriorityCount = changes.filter((change) => ["urgent", "high"].includes(priorityForChange(change, watches))).length;
  const lowPriorityCount = changes.filter((change) => priorityForChange(change, watches) === "low").length;
  const reviewRange = changesPage?.cursor ? `Since ${formatDate(changesPage.cursor)}` : "First review · all recorded changes";
  return <>
    <PageHeader eyebrow="Review / since your last visit" title="Home" description="Start with evidence-backed changes in your named Watch context, then follow the existing Story or Document path." action={<button className="primary-button" type="button" onClick={() => void advanceBoundary()} disabled={boundaryWorking}>{boundaryWorking ? "Saving review boundary…" : "Mark current review boundary"}</button>} />
    {error && <ErrorState error={error} retry={() => void load()} />}
    <div className="stat-grid"><Stat label="Watches" value={watches.length} tone="mint" /><Stat label="Changes loaded" value={changes.length} tone={changes.length ? "amber" : "mint"} /><Stat label="High priority" value={highPriorityCount} tone={highPriorityCount ? "coral" : "mint"} /><Stat label="Lower priority" value={lowPriorityCount} /></div>

    <SectionCard title="Watch overview" description="Named scope and actual last successful collection. Attempts and schedules are shown separately from freshness." action={<button className="text-button" type="button" onClick={() => openView("monitors")}>Manage Watches</button>}>
      {watches.some((watch) => !watchHealth[watch.id]) && <p className="status-note" role="status">Some Watch health details are temporarily unavailable. Collection freshness and scheduling remain unverified until the health read recovers.</p>}
      <div className="resource-list">{watches.map((watch) => { const health = watchHealth[watch.id]; return <div className="resource-row" key={watch.id}><span><strong>{text(watch.name, "Unnamed Watch")}</strong><small>{text(watch.target_type, "Watch")} · {text(watch.priority, "normal")} priority · {freshnessLabel(watch, health)}{health?.next_scheduled_run ? ` · next ${formatDate(health.next_scheduled_run)}` : ""}</small></span><Badge tone={!health ? "coral" : health.progress?.state === "ready" ? "mint" : health.progress?.state === "error" ? "coral" : watch.status === "active" ? "amber" : "neutral"}>{!health ? "Health unavailable" : health.progress?.label ?? text(health.status, text(watch.status, "unknown"))}</Badge></div>; })}</div>
    </SectionCard>

    <SectionCard title="Since your last review" description={`${reviewRange}. Reading does not mark these changes seen; use the explicit boundary action when you are finished reviewing.`}>
      {changes.length ? <div className="briefing-list">{changes.map((change) => <ReviewChangeRow key={change.id} change={change} watches={watches} openView={openView} />)}</div> : <EmptyState title="No new evidence-backed changes" description={changesPage?.cursor ? "Your Watch boundary has no material Story revisions after it. New knowledge will appear here after a later collection." : "No evidence-backed material Story revisions are recorded yet. Start a Watch and return after its first persisted result."} />}
      {changesPage?.has_more && <div className="button-row"><button className="secondary-button" type="button" onClick={() => void loadMoreChanges()} disabled={loadingMore}>{loadingMore ? "Loading more changes…" : "Load more changes"}</button><span className="status-note">More changes are available; nothing is hidden by the first page.</span></div>}
    </SectionCard>

    <div className="content-grid inbox-grid">
      <SectionCard title="Attention queue" description="A ranked starting point from unread alerts and material Story corrections.">
        {attention.length ? <div className="alert-list">{attention.slice(0, 6).map((item) => <article className="alert-detail-row" key={item.id}><div><div className="button-row"><Badge tone={item.importance_score >= .85 ? "coral" : "amber"}>{item.reason_code.replace(/_/g, " ")}</Badge><span>{item.importance_score.toFixed(2)} priority</span></div><strong>{String(item.explanation.title ?? item.explanation.reason ?? item.explanation.target_type ?? "Review item")}</strong><p>{String(item.explanation.body ?? item.explanation.reason ?? "This item needs an explicit review decision.")}</p></div><div className="button-row"><button className="quiet-button" type="button" onClick={() => void decideAttention(item.id, "seen")}>Seen</button><button className="quiet-button" type="button" onClick={() => void decideAttention(item.id, "snoozed")}>Snooze</button><button className="secondary-button" type="button" onClick={() => void decideAttention(item.id, "not_useful")}>Not useful</button></div></article>)}</div> : <EmptyState title="No open attention items" description="The current queue is clear. New unread alerts and Story corrections will appear here." />}
      </SectionCard>
      <SectionCard title="Daily briefing" description="A manually generated briefing remains available separately from the since-visit change boundary." action={<button className="text-button" type="button" onClick={() => void refreshBriefing()} disabled={briefingWorking}>{briefingWorking ? "Refreshing…" : "Refresh briefing"}</button>}>
        {briefing?.items.length ? <div className="briefing-list">{briefing.items.slice(0, 6).map((item) => <article className="briefing-item" key={item.id}><span className="rank">{String(item.rank).padStart(2, "0")}</span><div><strong>{item.reason || "Material report update"}</strong><p>{item.claim_ids.length} Claim{item.claim_ids.length === 1 ? "" : "s"} · {item.evidence_span_ids.length} exact span{item.evidence_span_ids.length === 1 ? "" : "s"}</p></div><Badge tone={item.importance_score >= .9 ? "coral" : "amber"}>{item.importance_score.toFixed(2)}</Badge></article>)}</div> : <EmptyState title="No briefing loaded" description="Refresh the daily briefing to see the optional ranked projection over existing Reports." />}
        <button className="secondary-button" type="button" onClick={() => openView("reports")}>View reports</button>
      </SectionCard>
    </div>
    <SectionCard title="Living reports" description="Each report is a versioned projection over accepted Claims.">
      {reports.length ? <div className="table-wrap"><table><thead><tr><th scope="col">Report</th><th scope="col">Target</th><th scope="col">Status</th><th scope="col">Timezone</th></tr></thead><tbody>{reports.slice(0, 8).map((report) => <tr key={report.id}><td><strong>{report.name}</strong><small>{shortId(report.id)}</small></td><td>{report.target_type} · {shortId(report.target_id)}</td><td><Badge tone={report.status === "active" ? "mint" : "neutral"}>{report.status}</Badge></td><td>{report.timezone_name}</td></tr>)}</tbody></table></div> : <EmptyState title="No Living Reports" description="Create one from the Reports view when a Story or Monitor needs a durable status page." />}
    </SectionCard>
  </>;
}
