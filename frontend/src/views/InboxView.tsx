import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, formatDate, jsonBody, shortId } from "../lib/api";
import type { AttentionItem, Briefing, Report } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";

type InboxViewKey = "alerts" | "reports" | "stories" | "monitors";

export function InboxView({ openView }: { openView: (view: InboxViewKey) => void }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [watchCount, setWatchCount] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [briefingWorking, setBriefingWorking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [reportResponse, attentionResponse, watchResponse] = await Promise.all([
        apiList<Report>("/reports?page_size=50"),
        apiFetch<{ items: AttentionItem[] }>("/attention"),
        apiList<{ id: string }>("/watches?page_size=1"),
      ]);
      setReports(reportResponse.items);
      setAttention(attentionResponse.items);
      setWatchCount(watchResponse.total ?? watchResponse.items.length);
    } catch (caught) { setError(caught); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function refreshBriefing() {
    setBriefingWorking(true); setError(null);
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

  if (loading) return <><PageHeader eyebrow="Review" title="Inbox" description="Material changes, unresolved questions, and evidence-bound reports in one place." /><LoadingState />{error && <ErrorState error={error} />}</>;
  if (error) return <><PageHeader eyebrow="Review" title="Inbox" description="Material changes, unresolved questions, and evidence-bound reports in one place." /><ErrorState error={error} retry={() => void load()} /></>;

  if (watchCount === 0) {
    const hasExistingIntelligence = reports.length > 0 || attention.length > 0;
    return <>
      <PageHeader
        eyebrow="Welcome"
        title="Keep the signal in view."
        description="Newsroom follows what you care about and shows what changed, with the sources behind each claim. Start by saving one Watch as a paused draft so you can review its scope before anything begins collecting."
        action={<div className="button-row"><button className="primary-button" type="button" onClick={() => openView("monitors")}>Create your first Watch</button>{hasExistingIntelligence && <button className="secondary-button" type="button" onClick={() => openView("stories")}>Explore existing intelligence</button>}</div>}
      />
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

  return <>
    <PageHeader eyebrow="Review / today" title="Inbox" description="Start with what changed, then follow the evidence trail to the exact span." action={<button className="primary-button" type="button" onClick={() => void refreshBriefing()} disabled={briefingWorking}>{briefingWorking ? "Refreshing…" : "Refresh briefing"}</button>} />
    <div className="stat-grid"><Stat label="Attention items" value={attention.length} tone={attention.length ? "coral" : "mint"} /><Stat label="Living reports" value={reports.length} tone="mint" /><Stat label="Material queue" value={briefing?.items.length ?? "—"} /><Stat label="Last checked" value={formatDate(new Date().toISOString())} /></div>
    <div className="content-grid inbox-grid">
      <SectionCard title="Attention queue" description="A ranked starting point from unread alerts and material Story corrections.">
        {attention.length ? <div className="alert-list">{attention.slice(0, 6).map((item) => <article className="alert-detail-row" key={item.id}><div><div className="button-row"><Badge tone={item.importance_score >= .85 ? "coral" : "amber"}>{item.reason_code.replace(/_/g, " ")}</Badge><span>{item.importance_score.toFixed(2)} priority</span></div><strong>{String(item.explanation.title ?? item.explanation.reason ?? item.explanation.target_type ?? "Review item")}</strong><p>{String(item.explanation.body ?? item.explanation.reason ?? "This item needs an explicit review decision.")}</p></div><div className="button-row"><button className="quiet-button" type="button" onClick={() => void decideAttention(item.id, "seen")}>Seen</button><button className="quiet-button" type="button" onClick={() => void decideAttention(item.id, "snoozed")}>Snooze</button><button className="secondary-button" type="button" onClick={() => void decideAttention(item.id, "not_useful")}>Not useful</button></div></article>)}</div> : <EmptyState title="No open attention items" description="The current queue is clear. New unread alerts and Story corrections will appear here." />}
      </SectionCard>
      <SectionCard title="What changed" description="Ranked from material evidence changes, not article volume." action={<button className="text-button" type="button" onClick={() => openView("reports")}>View reports</button>}>
        {briefing?.items.length ? <div className="briefing-list">{briefing.items.slice(0, 6).map((item) => <article className="briefing-item" key={item.id}><span className="rank">{String(item.rank).padStart(2, "0")}</span><div><strong>{item.reason || "Material report update"}</strong><p>{item.claim_ids.length} Claim{item.claim_ids.length === 1 ? "" : "s"} · {item.evidence_span_ids.length} exact span{item.evidence_span_ids.length === 1 ? "" : "s"}</p></div><Badge tone={item.importance_score >= .9 ? "coral" : "amber"}>{item.importance_score.toFixed(2)}</Badge></article>)}</div> : <EmptyState title="No briefing loaded" description="Refresh the daily briefing to see ranked Monitor changes." />}
      </SectionCard>
    </div>
    <SectionCard title="Living reports" description="Each report is a versioned projection over accepted Claims.">
      {reports.length ? <div className="table-wrap"><table><thead><tr><th scope="col">Report</th><th scope="col">Target</th><th scope="col">Status</th><th scope="col">Timezone</th></tr></thead><tbody>{reports.slice(0, 8).map((report) => <tr key={report.id}><td><strong>{report.name}</strong><small>{shortId(report.id)}</small></td><td>{report.target_type} · {shortId(report.target_id)}</td><td><Badge tone={report.status === "active" ? "mint" : "neutral"}>{report.status}</Badge></td><td>{report.timezone_name}</td></tr>)}</tbody></table></div> : <EmptyState title="No Living Reports" description="Create one from the Reports view when a Story or Monitor needs a durable status page." />}
    </SectionCard>
  </>;
}
