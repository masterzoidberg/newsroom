import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiError, apiFetch, apiList, formatDate, jsonBody, shortId } from "../lib/api";
import type { Briefing, Report, ReportRevision } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";

const label = (value: string) => value.split("_").join(" ");

type WatchContext = {
  id: string;
  name: string;
  target_type: string;
  target_id: string;
  status?: string;
};

type ReportGeneration = {
  status: "material" | "no_change" | "deferred" | "failed";
  reason_code?: string;
  detail?: string;
  revision_id?: string | null;
};

type ReportRecord = Report & { generation?: ReportGeneration };

type BriefingSchedule = {
  id: number;
  cadence: "daily" | "weekly";
  timezone_name: string;
  scope: { monitor_ids: string[] };
  enabled: boolean;
  paused: boolean;
  next_due_at: string | null;
};

const localTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const briefingTimezones = () => Array.from(new Set([localTimezone(), "UTC", "America/New_York", "America/Los_Angeles", "Europe/London", "Asia/Tokyo"]));

function formatInTimezone(value: string | null | undefined, timezone: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: timezone, timeZoneName: "short" }).format(date);
  } catch {
    return formatDate(value);
  }
}

function briefingCadenceLabel(cadence: BriefingSchedule["cadence"]): string {
  return cadence === "daily" ? "Every day" : "Every week";
}

function readSelectedWatchId(): string {
  try { return window.localStorage.getItem("newsroom.selected-watch.v1") ?? ""; } catch { return ""; }
}

function rememberWatch(id: string): void {
  try { window.localStorage.setItem("newsroom.selected-watch.v1", id); } catch { /* Keep the selection in memory. */ }
}

function reportForWatch(reports: ReportRecord[], watch?: WatchContext): ReportRecord | undefined {
  if (!watch) return undefined;
  return reports.find((report) => report.target_type === watch.target_type && report.target_id === watch.target_id);
}

function contextLabel(report: ReportRecord, watches: WatchContext[]): string {
  const watch = watches.find((item) => item.target_type === report.target_type && item.target_id === report.target_id);
  return watch ? `${watch.name} · ${label(report.target_type)} Watch` : `Existing ${label(report.target_type)} target`;
}

export function ReportsView() {
  const [reports, setReports] = useState<ReportRecord[]>([]);
  const [watches, setWatches] = useState<WatchContext[]>([]);
  const [selected, setSelected] = useState<ReportRecord | null>(null);
  const [selectedWatchId, setSelectedWatchId] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [working, setWorking] = useState(false);
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState<BriefingSchedule | null>(null);
  const [latestBriefing, setLatestBriefing] = useState<Briefing | null>(null);
  const [scheduleCadence, setScheduleCadence] = useState<BriefingSchedule["cadence"]>("daily");
  const [scheduleTimezone, setScheduleTimezone] = useState(localTimezone);
  const [scheduleLoading, setScheduleLoading] = useState(true);
  const [scheduleWorking, setScheduleWorking] = useState(false);
  const [scheduleError, setScheduleError] = useState<unknown>(null);

  const loadLatestBriefing = useCallback(async (savedSchedule: BriefingSchedule | null) => {
    const query = savedSchedule ? `?period=${savedSchedule.cadence}&timezone_name=${encodeURIComponent(savedSchedule.timezone_name)}` : "";
    setLatestBriefing(await apiFetch<Briefing | null>(`/briefings/latest${query}`));
  }, []);

  const loadSchedule = useCallback(async () => {
    setScheduleLoading(true);
    setScheduleError(null);
    try {
      const savedSchedule = await apiFetch<BriefingSchedule | null>("/briefing-schedule");
      setSchedule(savedSchedule);
      if (savedSchedule) {
        setScheduleCadence(savedSchedule.cadence);
        setScheduleTimezone(savedSchedule.timezone_name);
      }
      await loadLatestBriefing(savedSchedule);
    } catch (caught) {
      setScheduleError(caught);
    } finally {
      setScheduleLoading(false);
    }
  }, [loadLatestBriefing]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [reportResult, watchResult] = await Promise.all([
        apiList<ReportRecord>("/reports?page_size=100"),
        apiList<WatchContext>("/watches?page_size=100"),
      ]);
      setReports(reportResult.items);
      setWatches(watchResult.items);
      const storedId = readSelectedWatchId();
      const watch = watchResult.items.find((item) => item.id === storedId) ?? watchResult.items[0];
      const report = reportForWatch(reportResult.items, watch) ?? (!watch ? reportResult.items[0] : undefined);
      setSelectedWatchId(watch?.id ?? "");
      if (watch) rememberWatch(watch.id);
      if (report) {
        try { setSelected(await apiFetch<ReportRecord>(`/reports/${report.id}`)); }
        catch { setSelected(report); }
      } else {
        setSelected(null);
      }
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { void loadSchedule(); }, [loadSchedule]);

  useEffect(() => {
    if (!schedule?.enabled) return;
    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const latest = await apiFetch<Briefing | null>(`/briefings/latest?period=${schedule.cadence}&timezone_name=${encodeURIComponent(schedule.timezone_name)}`);
        if (!cancelled) setLatestBriefing(latest);
      } catch (caught) {
        if (!cancelled) setScheduleError(caught);
      }
      if (!cancelled) timer = window.setTimeout(() => void poll(), 10_000);
    };
    timer = window.setTimeout(() => void poll(), 10_000);
    return () => { cancelled = true; if (timer !== undefined) window.clearTimeout(timer); };
  }, [schedule?.cadence, schedule?.enabled, schedule?.timezone_name]);

  async function openReport(report: ReportRecord): Promise<void> {
    setSelected(report);
    try {
      setSelected(await apiFetch<ReportRecord>(`/reports/${report.id}`));
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "The report generation request failed.";
      setSelected((current) => current?.id === report.id ? { ...current, generation: { status: "failed", detail } } : current);
      setError(caught);
    }
  }

  function chooseWatch(id: string): void {
    setSelectedWatchId(id);
    rememberWatch(id);
    const watch = watches.find((item) => item.id === id);
    const existing = reportForWatch(reports, watch);
    if (existing) void openReport(existing);
    else setSelected(null);
  }

  async function create(event: FormEvent): Promise<void> {
    event.preventDefault();
    const watch = watches.find((item) => item.id === selectedWatchId);
    if (!watch) {
      setError(new Error("Select a named Watch before creating a Living Report."));
      return;
    }
    const existing = reportForWatch(reports, watch);
    if (existing) {
      setName("");
      await openReport(existing);
      return;
    }
    setWorking(true);
    setError(null);
    try {
      const report = await apiFetch<ReportRecord>("/reports", {
        method: "POST",
        body: jsonBody({
          name: name.trim() || `${watch.name} report`,
          target_type: watch.target_type,
          target_id: watch.target_id,
          timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        }),
      });
      setReports((items) => [report, ...items]);
      setSelected(report);
      setName("");
    } catch (caught) {
      // A stale list can race with another tab. Re-read the named target and
      // converge on the unique canonical report instead of surfacing a false
      // duplicate-create failure.
      if (caught instanceof ApiError && caught.status === 409) {
        try {
          const refreshed = await apiList<ReportRecord>("/reports?page_size=100");
          const concurrent = reportForWatch(refreshed.items, watch);
          setReports(refreshed.items);
          if (concurrent) {
            setName("");
            await openReport(concurrent);
            return;
          }
        } catch { /* Preserve the original actionable error below. */ }
      }
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function generate(report: ReportRecord): Promise<void> {
    setWorking(true);
    setError(null);
    try {
      const result = await apiFetch<ReportRecord>(`/reports/${report.id}/generate`, { method: "POST" });
      setSelected(result);
      setReports((items) => items.map((item) => item.id === result.id ? result : item));
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "The report generation request failed.";
      setSelected((current) => current?.id === report.id ? { ...current, generation: { status: "failed", detail } } : current);
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function archive(report: ReportRecord): Promise<void> {
    if (!window.confirm(`Archive “${report.name}”? It will stop generating new revisions.`)) return;
    setWorking(true);
    setError(null);
    try {
      const result = await apiFetch<ReportRecord>(`/reports/${report.id}/archive`, { method: "POST" });
      setSelected(result);
      setReports((items) => items.map((item) => item.id === result.id ? result : item));
    } catch (caught) {
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function saveBriefingSchedule(event: FormEvent): Promise<void> {
    event.preventDefault();
    setScheduleWorking(true);
    setScheduleError(null);
    try {
      const saved = await apiFetch<BriefingSchedule>("/briefing-schedule", {
        method: "PUT",
        body: jsonBody({ cadence: scheduleCadence, timezone_name: scheduleTimezone, enabled: true }),
      });
      setSchedule(saved);
      setScheduleCadence(saved.cadence);
      setScheduleTimezone(saved.timezone_name);
      await loadLatestBriefing(saved);
    } catch (caught) {
      setScheduleError(caught);
    } finally {
      setScheduleWorking(false);
    }
  }

  async function pauseBriefingSchedule(): Promise<void> {
    setScheduleWorking(true);
    setScheduleError(null);
    try {
      const saved = await apiFetch<BriefingSchedule>("/briefing-schedule", { method: "PUT", body: jsonBody({ enabled: false }) });
      setSchedule(saved);
    } catch (caught) {
      setScheduleError(caught);
    } finally {
      setScheduleWorking(false);
    }
  }

  if (loading) return <><PageHeader eyebrow="Review" title="Reports" description="Versioned status pages grounded in exact accepted Claims." /><LoadingState label="Loading Living Reports" />{error && <ErrorState error={error} />}</>;

  const selectedWatch = watches.find((watch) => watch.id === selectedWatchId);
  const existingForSelection = reportForWatch(reports, selectedWatch);
  return <>
    <PageHeader eyebrow="Review / evidence-bound" title="Living Reports" description="Inspect the latest successful revision for a named Watch, including what changed and the exact evidence behind it." />
    {error && <ErrorState error={error} retry={() => void load()} />}
    <SectionCard title="Briefing preferences" description="Choose a durable workspace briefing cadence and timezone. This is separate from each Watch's acquisition cadence." action={schedule?.enabled ? <Badge tone="mint">Enabled</Badge> : <Badge tone="neutral">{schedule ? "Paused" : "Not configured"}</Badge>}>
      {scheduleLoading ? <LoadingState label="Loading briefing preferences" /> : scheduleError ? <ErrorState error={scheduleError} retry={() => void loadSchedule()} /> : <>
        <form className="stack-form" onSubmit={(event) => void saveBriefingSchedule(event)}>
          <label htmlFor="briefing-cadence">Briefing cadence</label>
          <select id="briefing-cadence" name="briefing_cadence" value={scheduleCadence} onChange={(event) => setScheduleCadence(event.target.value as BriefingSchedule["cadence"])} disabled={scheduleWorking}>
            <option value="daily">Every day</option>
            <option value="weekly">Every week</option>
          </select>
          <label htmlFor="briefing-timezone">Delivery timezone</label>
          <select id="briefing-timezone" name="briefing_timezone" value={scheduleTimezone} onChange={(event) => setScheduleTimezone(event.target.value)} disabled={scheduleWorking}>
            {briefingTimezones().map((timezone) => <option value={timezone} key={timezone}>{timezone}{timezone === localTimezone() ? " (local)" : ""}</option>)}
          </select>
          <p className="status-note">{schedule?.enabled ? `Next delivery: ${formatInTimezone(schedule.next_due_at, schedule.timezone_name)}.` : schedule ? "Briefings are paused. Saving these choices resumes the schedule." : "No delivery is scheduled until you save a cadence."} {schedule?.scope.monitor_ids.length ? `${schedule.scope.monitor_ids.length} selected Monitor${schedule.scope.monitor_ids.length === 1 ? "" : "s"} are in scope.` : "The briefing includes all eligible Monitor reports."}</p>
          <div className="button-row"><button className="primary-button" type="submit" disabled={scheduleWorking}>{scheduleWorking ? "Saving…" : schedule?.enabled ? "Save preferences" : "Enable briefing"}</button>{schedule?.enabled && <button className="secondary-button" type="button" onClick={() => void pauseBriefingSchedule()} disabled={scheduleWorking}>Pause briefings</button>}</div>
        </form>
        <SectionCard title="Latest saved briefing" description={latestBriefing ? `${briefingCadenceLabel(latestBriefing.period)} · ${latestBriefing.timezone_name} · saved for ${formatInTimezone(latestBriefing.period_end, latestBriefing.timezone_name)}` : "Scheduled output is read from persisted briefing state."}>
          {latestBriefing?.items.length ? <div className="briefing-list">{latestBriefing.items.slice(0, 6).map((item) => <article className="briefing-item" key={item.id}><span className="rank">{String(item.rank).padStart(2, "0")}</span><div><strong>{item.reason || "Material report update"}</strong><p>{item.claim_ids.length} Claim{item.claim_ids.length === 1 ? "" : "s"} · {item.evidence_span_ids.length} exact span{item.evidence_span_ids.length === 1 ? "" : "s"}</p></div><Badge tone={item.importance_score >= .9 ? "coral" : "amber"}>{item.importance_score.toFixed(2)}</Badge></article>)}</div> : <EmptyState title={schedule?.enabled ? "No briefing published yet" : "No briefing output"} description={schedule?.enabled ? `The next saved delivery is ${formatInTimezone(schedule.next_due_at, schedule.timezone_name)}. A briefing appears after an eligible scheduled job completes.` : schedule ? "Resume the schedule to receive future briefings. Existing output will remain available when it matches the selected cadence and timezone." : "Save a briefing cadence to begin receiving scheduled output."} />}
        </SectionCard>
      </>}
    </SectionCard>
    <div className="content-grid reports-layout">
      <SectionCard title="Create or open a report" description="Choose a named Watch. Newsroom maps it to the existing canonical target; no target ID is required here.">
        {watches.length ? <form className="stack-form" onSubmit={(event) => void create(event)}>
          <label htmlFor="report-watch">Watch</label>
          <select id="report-watch" name="report_watch" value={selectedWatchId} onChange={(event) => chooseWatch(event.target.value)} disabled={working}>
            {watches.map((watch) => <option value={watch.id} key={watch.id}>{watch.name} · {label(watch.target_type)}</option>)}
          </select>
          <label htmlFor="report-name">Report name <span className="muted">(optional)</span></label>
          <input id="report-name" name="report_name" autoComplete="off" value={name} onChange={(event) => setName(event.target.value)} placeholder={selectedWatch ? `${selectedWatch.name} report` : "Living report"} />
          <button className="primary-button" type="submit" disabled={working || !selectedWatchId}>{existingForSelection ? "Open Living Report" : working ? "Creating…" : "Create Living Report"}</button>
        </form> : <EmptyState title="No named Watches yet" description="Save a named Watch first. Reports stay anchored to existing canonical targets and are not created from free-form IDs." />}
      </SectionCard>
      <SectionCard title="Saved reports" description="Select a report to inspect its latest immutable revision.">
        {reports.length ? <div className="resource-list">{reports.map((report) => <button type="button" className={`resource-row ${selected?.id === report.id ? "selected" : ""}`} key={report.id} onClick={() => void openReport(report)}><span><strong>{report.name}</strong><small>{contextLabel(report, watches)}</small></span><Badge tone={report.status === "active" ? "mint" : "neutral"}>{report.status}</Badge></button>)}</div> : <EmptyState title="No reports yet" description="Select a named Watch above to create its first Living Report." />}
      </SectionCard>
    </div>
    {selected && <ReportDetail report={selected} watch={watches.find((watch) => watch.target_type === selected.target_type && watch.target_id === selected.target_id)} onGenerate={() => void generate(selected)} onArchive={() => void archive(selected)} working={working} />}
  </>;
}

function ReportDetail({ report, watch, onGenerate, onArchive, working }: { report: ReportRecord; watch?: WatchContext; onGenerate: () => void; onArchive: () => void; working: boolean }) {
  const revision = report.current_revision;
  const generation = report.generation;
  const statusMessage = generation?.status === "deferred"
    ? `No new revision was saved: ${generation.reason_code === "no_accepted_evidence" ? "this Watch has no accepted evidence yet." : generation.detail || "accepted evidence is incomplete."}`
    : generation?.status === "failed"
      ? `Generation failed. The previous successful revision remains current.${generation.detail ? ` ${generation.detail}` : ""}`
      : generation?.status === "no_change" ? "No material input changed; the existing revision remains current." : "";
  return <SectionCard title={report.name} description={watch ? `${watch.name} · ${label(report.target_type)} Watch` : `Existing ${label(report.target_type)} target`} action={<div className="button-row"><button className="secondary-button" type="button" onClick={onGenerate} disabled={working || report.status !== "active"}>{working ? "Generating…" : "Generate revision"}</button>{report.status === "active" && <button className="danger-button" type="button" onClick={onArchive} disabled={working}>Archive</button>}</div>}>
    {statusMessage && <p className="status-note" role="status">{statusMessage}</p>}
    {!revision ? <EmptyState title="No successful revision yet" description="Generate the first revision after this Watch has accepted, evidence-backed Claims." /> : <div className="report-detail"><div className="detail-toolbar"><Badge tone={revision.audit.passed ? "mint" : "coral"}>{revision.audit.passed ? "Closed-world audit passed" : "Audit failed"}</Badge><span>Latest successful revision {revision.revision_number} · {formatDate(revision.generated_at)}</span><code>{shortId(revision.claim_set_hash)}</code></div><div className="report-section-grid">{["current_status", "what_changed", "active_stories", "evidence_strength", "contradictions", "unresolved_questions", "recommended_investigations"].map((key) => <section className="report-section" key={key}><h3>{label(key)}</h3>{key === "current_status" ? <p>{revision.sections.current_status || "No status text."}</p> : <ReportSectionValue value={revision.sections[key as keyof ReportRevision["sections"]]} />}</section>)}</div><div className="evidence-cause-list"><h3>Evidence provenance</h3>{revision.change_causes.length ? revision.change_causes.map((cause) => <div className="cause-row" key={cause.id}><Badge tone={cause.cause_type === "contradiction" || cause.cause_type === "correction" ? "coral" : "mint"}>{label(cause.cause_type)}</Badge><span>{cause.rationale}</span><code>{cause.evidence_span_id ? `Evidence span ${shortId(cause.evidence_span_id)}${cause.claim_id ? ` · Claim ${shortId(cause.claim_id)}` : ""}${cause.document_id ? ` · Document ${shortId(cause.document_id)}` : ""}` : "Unresolved provenance"}</code></div>) : <p className="muted">No material cause recorded.</p>}</div></div>}
  </SectionCard>;
}

function ReportSectionValue({ value }: { value: unknown }) {
  if (!Array.isArray(value) || value.length === 0) return <p className="muted">None recorded.</p>;
  return <ul className="compact-list">{value.slice(0, 8).map((item, index) => <li key={index}>{typeof item === "string" ? item : <>{String((item as Record<string, unknown>).text ?? (item as Record<string, unknown>).proposition ?? (item as Record<string, unknown>).question ?? (item as Record<string, unknown>).suggestion ?? (item as Record<string, unknown>).headline ?? "Evidence-backed detail recorded.")}</>}</li>)}</ul>;
}
