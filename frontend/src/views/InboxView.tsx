import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, formatDate, jsonBody, shortId } from "../lib/api";
import type { Alert, AttentionItem, Briefing, Report } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard, Stat } from "../components/ViewPrimitives";

export function InboxView({ openView }: { openView: (view: "alerts" | "reports" | "stories") => void }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [attention, setAttention] = useState<AttentionItem[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [briefingWorking, setBriefingWorking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [reportResponse, alertResponse, attentionResponse] = await Promise.all([apiList<Report>("/reports?page_size=50"), apiList<Alert>("/alerts?page_size=50"), apiFetch<{ items: AttentionItem[] }>("/attention/refresh", { method: "POST" })]);
      setReports(reportResponse.items); setAlerts(alertResponse.items); setAttention(attentionResponse.items);
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

  async function giveFeedback(id: string, feedback: "useful" | "not_important" | "already_knew" | "needs_investigation") {
    try {
      await apiFetch(`/attention/${id}/feedback`, { method: "POST", body: jsonBody({ feedback }) });
      setAttention((items) => items.filter((item) => item.id !== id));
    } catch (caught) { setError(caught); }
  }

  if (loading) return <><PageHeader eyebrow="Review" title="Inbox" description="Material changes, unresolved questions, and evidence-bound reports in one place." /><LoadingState />{error && <ErrorState error={error} />}</>;
  if (error) return <><PageHeader eyebrow="Review" title="Inbox" description="Material changes, unresolved questions, and evidence-bound reports in one place." /><ErrorState error={error} retry={() => void load()} /></>;
  const unread = alerts.filter((alert) => alert.status === "unread").length;
  return <>
    <PageHeader eyebrow="Review / today" title="Inbox" description="Start with what changed, then follow the evidence trail to the exact span." action={<button className="primary-button" type="button" onClick={() => void refreshBriefing()} disabled={briefingWorking}>{briefingWorking ? "Refreshing…" : "Refresh briefing"}</button>} />
    <div className="stat-grid"><Stat label="Unread alerts" value={unread} tone={unread ? "coral" : "mint"} /><Stat label="Living reports" value={reports.length} tone="mint" /><Stat label="Material queue" value={briefing?.items.length ?? "—"} /><Stat label="Last checked" value={formatDate(new Date().toISOString())} /></div>
    <div className="content-grid inbox-grid">
      <SectionCard title="Attention queue" description="A ranked starting point from alerts, coverage gaps, corrections, and approved research blind spots.">
        {attention.length ? <div className="alert-list">{attention.slice(0, 6).map((item) => <article className="alert-detail-row" key={item.id}><div><div className="button-row"><Badge tone={item.importance_score >= .85 ? "coral" : "amber"}>{item.reason_code.replace(/_/g, " ")}</Badge><span>{item.importance_score.toFixed(2)} priority</span></div><strong>{String(item.explanation.title ?? item.explanation.reason ?? item.explanation.target_type ?? "Review item")}</strong><p>{String(item.explanation.body ?? item.explanation.reason ?? "This item needs an explicit review decision.")}</p></div><div className="button-row"><button className="quiet-button" type="button" onClick={() => void giveFeedback(item.id, "needs_investigation")}>Keep open</button><button className="secondary-button" type="button" onClick={() => void giveFeedback(item.id, "not_important")}>Dismiss</button></div></article>)}</div> : <EmptyState title="No open attention items" description="The durable queue is clear. Refresh after the next material change or coverage run." />}
      </SectionCard>
      <SectionCard title="What changed" description="Ranked from material evidence changes, not article volume." action={<button className="text-button" type="button" onClick={() => openView("reports")}>View reports</button>}>
        {briefing?.items.length ? <div className="briefing-list">{briefing.items.slice(0, 6).map((item) => <article className="briefing-item" key={item.id}><span className="rank">{String(item.rank).padStart(2, "0")}</span><div><strong>{item.reason || "Material report update"}</strong><p>{item.claim_ids.length} Claim{item.claim_ids.length === 1 ? "" : "s"} · {item.evidence_span_ids.length} exact span{item.evidence_span_ids.length === 1 ? "" : "s"}</p></div><Badge tone={item.importance_score >= .9 ? "coral" : "amber"}>{item.importance_score.toFixed(2)}</Badge></article>)}</div> : <EmptyState title="No briefing loaded" description="Refresh the daily briefing to see ranked Monitor changes." />}
      </SectionCard>
      <SectionCard title="Needs your attention" description="Durable in-app state stays available when browser delivery is denied or offline." action={<button className="text-button" type="button" onClick={() => openView("alerts")}>All alerts</button>}>
        {alerts.length ? <div className="alert-list">{alerts.slice(0, 5).map((alert) => <article className="alert-row" key={alert.id}><span className={`alert-marker ${alert.status}`} aria-hidden="true" /><div><strong>{alert.title}</strong><p>{alert.body}</p><small>{formatDate(alert.created_at)} · {shortId(alert.id)}</small></div><Badge tone={alert.status === "unread" ? "coral" : "neutral"}>{alert.status}</Badge></article>)}</div> : <EmptyState title="All clear" description="No durable alerts are waiting for review." />}
      </SectionCard>
    </div>
    <SectionCard title="Living reports" description="Each report is a versioned projection over accepted Claims.">
      {reports.length ? <div className="table-wrap"><table><thead><tr><th scope="col">Report</th><th scope="col">Target</th><th scope="col">Status</th><th scope="col">Timezone</th></tr></thead><tbody>{reports.slice(0, 8).map((report) => <tr key={report.id}><td><strong>{report.name}</strong><small>{shortId(report.id)}</small></td><td>{report.target_type} · {shortId(report.target_id)}</td><td><Badge tone={report.status === "active" ? "mint" : "neutral"}>{report.status}</Badge></td><td>{report.timezone_name}</td></tr>)}</tbody></table></div> : <EmptyState title="No Living Reports" description="Create one from the Reports view when a Story or Monitor needs a durable status page." />}
    </SectionCard>
  </>;
}
