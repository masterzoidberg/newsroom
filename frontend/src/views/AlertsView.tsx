import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, apiList, formatDate, jsonBody, shortId } from "../lib/api";
import type { Alert, AlertRule, NotificationPreferences } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, PageHeader, SectionCard } from "../components/ViewPrimitives";
import { queueDocumentNavigation } from "./DocumentView";
import { queueStoryNavigation } from "./StoryEvidenceView";

const EVENT_TYPES = ["new_primary_evidence", "contradiction", "correction", "corroboration", "material_update"];
const RULE_THRESHOLDS = [0, 0.45, 0.5, 0.75, 0.85, 0.95];
const IMPORTANT_THRESHOLD = 0.85;
type AlertViewMode = "important" | "all" | "history";

type Watch = { id: string; name?: string; status?: string };
type WatchSource = { source?: { name?: string }; monitor?: { id?: string } };
type WatchScope = { monitorId: string; watchName: string; sourceName: string };

const label = (value: string) => value.split("_").join(" ");
const thresholdLabel = (value: number) => `${Math.round(value * 100)}%`;

function thresholdOptions(current?: number): number[] {
  if (current !== undefined && !RULE_THRESHOLDS.includes(current)) return [current, ...RULE_THRESHOLDS];
  return RULE_THRESHOLDS;
}

function scopeValue(rule: AlertRule): string {
  if (rule.target_type === "all") return "all";
  return `${rule.target_type}:${rule.target_id ?? ""}`;
}

function scopeDescription(rule: AlertRule, scopes: WatchScope[]): string {
  if (rule.target_type === "all") return "All enabled alert targets";
  const selected = scopes.find((scope) => rule.target_type === "monitor" && scope.monitorId === rule.target_id);
  if (selected) return `${selected.watchName} · ${selected.sourceName}`;
  return `${label(rule.target_type)} · ${shortId(rule.target_id)}`;
}

async function loadWatchScopes(watches: Watch[]): Promise<WatchScope[]> {
  const results = await Promise.all(watches.map(async (watch) => {
    try {
      const response = await apiList<WatchSource>(`/watches/${encodeURIComponent(watch.id)}/sources?page_size=100`);
      return response.items.flatMap((item) => item.monitor?.id ? [{
        monitorId: item.monitor.id,
        watchName: watch.name?.trim() || "Unnamed Watch",
        sourceName: item.source?.name?.trim() || "Source Monitor",
      }] : []);
    } catch {
      // A temporarily unavailable Watch detail must not hide the alert inbox.
      return [];
    }
  }));
  return results.flat();
}

function openStoryEvidence(alert: Alert, claimId?: string | null) {
  if (!alert.story_id) return;
  queueStoryNavigation({ storyId: alert.story_id, ...(claimId ? { claimId } : {}) });
  window.location.hash = "stories";
}

function openExactEvidence(alert: Alert, cause: Alert["cause"][number]) {
  if (!cause.document_id) return;
  queueDocumentNavigation(cause.document_id, {
    ...(cause.evidence_span_id ? { evidenceSpanId: cause.evidence_span_id } : {}),
    ...(alert.story_id ? { returnStoryId: alert.story_id, returnClaimId: cause.claim_id ?? undefined } : {}),
  });
  window.location.hash = "documents";
}

export function AlertsView() {
  const [viewMode, setViewMode] = useState<AlertViewMode>("important");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [watches, setWatches] = useState<WatchScope[]>([]);
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [ruleName, setRuleName] = useState("");
  const [eventType, setEventType] = useState("material_update");
  const [ruleThreshold, setRuleThreshold] = useState("0.5");
  const [ruleScope, setRuleScope] = useState("all");
  const [working, setWorking] = useState(false);
  const [workingRule, setWorkingRule] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const minimumImportance = viewMode === "important" ? IMPORTANT_THRESHOLD : 0;
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ min_importance: String(minimumImportance), page_size: "100" });
      params.set("status", viewMode === "history" ? "acknowledged" : "unread");
      const [alertResult, ruleResult, preferenceResult, watchResult] = await Promise.all([
        apiList<Alert>(`/alerts?${params.toString()}`),
        apiFetch<{ items: AlertRule[] }>("/alert-rules"),
        apiFetch<NotificationPreferences>("/notification-preferences"),
        apiList<Watch>("/watches?page_size=100"),
      ]);
      setAlerts(alertResult.items);
      setRules(ruleResult.items);
      setPreferences(preferenceResult);
      setWatches(await loadWatchScopes(watchResult.items));
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  }, [minimumImportance, viewMode]);

  useEffect(() => { void load(); }, [load]);

  async function acknowledge(id: string) {
    setWorkingRule(id);
    try {
      const updated = await apiFetch<Alert>(`/alerts/${encodeURIComponent(id)}/acknowledge`, { method: "POST" });
      setAlerts((items) => viewMode === "history" ? items.map((item) => item.id === id ? updated : item) : items.filter((item) => item.id !== id));
    } catch (caught) {
      setError(caught);
    } finally {
      setWorkingRule(null);
    }
  }

  async function requestPermission() {
    setWorking(true);
    try {
      const permission = "Notification" in window ? await Notification.requestPermission() : "denied";
      const updated = await apiFetch<NotificationPreferences>("/notification-preferences", {
        method: "PUT",
        body: jsonBody({ browser_enabled: permission === "granted", permission_state: permission, online: navigator.onLine }),
      });
      setPreferences(updated);
    } catch (caught) {
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function createRule(event: FormEvent) {
    event.preventDefault();
    if (!ruleName.trim()) return;
    const [targetType, targetId] = ruleScope.split(":", 2);
    setWorking(true);
    try {
      const rule = await apiFetch<AlertRule>("/alert-rules", {
        method: "POST",
        body: jsonBody({
          name: ruleName.trim(),
          target_type: targetType === "monitor" ? "monitor" : "all",
          ...(targetType === "monitor" && targetId ? { target_id: targetId } : {}),
          event_types: [eventType],
          min_importance: Number(ruleThreshold),
          browser_enabled: preferences?.permission_state === "granted",
        }),
      });
      setRules((items) => [...items, rule]);
      setRuleName("");
    } catch (caught) {
      setError(caught);
    } finally {
      setWorking(false);
    }
  }

  async function updateRule(id: string, patch: Partial<AlertRule>) {
    setWorkingRule(id);
    try {
      const updated = await apiFetch<AlertRule>(`/alert-rules/${encodeURIComponent(id)}`, { method: "PATCH", body: jsonBody(patch) });
      setRules((items) => items.map((item) => item.id === id ? updated : item));
    } catch (caught) {
      setError(caught);
    } finally {
      setWorkingRule(null);
    }
  }

  function renderScopeOptions(rule?: AlertRule) {
    const current = rule ? scopeValue(rule) : ruleScope;
    const hasCurrent = current !== "all" && !watches.some((scope) => `monitor:${scope.monitorId}` === current);
    return <>
      <option value="all">All enabled alert targets</option>
      {watches.length > 0 && <optgroup label="Watch Source monitors">{watches.map((scope) => <option value={`monitor:${scope.monitorId}`} key={scope.monitorId}>{scope.watchName} · {scope.sourceName}</option>)}</optgroup>}
      {hasCurrent && rule && <option value={current}>Existing {label(rule.target_type)} · {shortId(rule.target_id)}</option>}
    </>;
  }

  function patchScope(rule: AlertRule, value: string) {
    const [targetType, targetId] = value.split(":", 2);
    if (targetType === "all") return updateRule(rule.id, { target_type: "all", target_id: null });
    return updateRule(rule.id, { target_type: targetType, target_id: targetId || null });
  }

  const unreadCount = useMemo(() => alerts.filter((alert) => alert.status === "unread").length, [alerts]);
  if (loading) return <><PageHeader eyebrow="Operate" title="Alerts" description="Durable attention state with optional browser delivery." /><LoadingState />{error && <ErrorState error={error} retry={() => void load()} />}</>;

  return <>
    <PageHeader
      eyebrow="Operate / durable state"
      title="Alerts"
      description="Important changes are shown first, while lower-priority alerts and acknowledged history remain available. Browser permission never replaces the authoritative in-app alert."
      action={preferences?.permission_state !== "granted" ? <button className="primary-button" type="button" onClick={() => void requestPermission()} disabled={working}>{working ? "Requesting…" : "Enable browser notifications"}</button> : <Badge tone="mint">Browser notifications enabled</Badge>}
    />
    {error && <ErrorState error={error} retry={() => void load()} />}
    <SectionCard title="Alert inbox" description={viewMode === "history" ? "Acknowledged alerts remain searchable here; acknowledgement never deletes an alert or its cause." : "Use Important for the high-signal queue and All to include every rule-matching alert."}>
      <div className="detail-toolbar" role="group" aria-label="Alert inbox view">
        <button className={viewMode === "important" ? "primary-button" : "secondary-button"} type="button" onClick={() => setViewMode("important")}>Important (≥ {thresholdLabel(IMPORTANT_THRESHOLD)})</button>
        <button className={viewMode === "all" ? "primary-button" : "secondary-button"} type="button" onClick={() => setViewMode("all")}>All alerts</button>
        <button className={viewMode === "history" ? "primary-button" : "secondary-button"} type="button" onClick={() => setViewMode("history")}>Acknowledged history</button>
        <span className="status-note">{viewMode === "history" ? `${alerts.length} historical alert(s)` : `${unreadCount} unread alert(s)`}</span>
      </div>
      {alerts.length ? <div className="alert-list">{alerts.map((alert) => <article className={`alert-detail-row ${alert.status}`} key={alert.id}>
        <div>
          <div className="button-row" style={{ flexWrap: "wrap" }}><Badge tone={alert.event_type === "contradiction" || alert.event_type === "correction" ? "coral" : alert.importance_score >= IMPORTANT_THRESHOLD ? "amber" : "neutral"}>{label(alert.event_type)}</Badge><span>{alert.importance_score.toFixed(2)} importance</span><Badge tone={alert.status === "unread" ? "coral" : "mint"}>{alert.status}</Badge></div>
          <h3>{alert.title}</h3>
          <p>{alert.body}</p>
          {alert.cause.length > 0 && <div className="evidence-cause-list"><h3>Why this alert</h3>{alert.cause.map((cause) => <div className="cause-row" key={cause.id}><span>{cause.rationale}</span><div className="button-row">{alert.story_id && <button className="quiet-button" type="button" onClick={() => openStoryEvidence(alert, cause.claim_id)}>Review Story evidence</button>}{cause.document_id && <button className="quiet-button" type="button" onClick={() => openExactEvidence(alert, cause)}>Open exact source</button>}</div></div>)}</div>}
          <small>{formatDate(alert.created_at)} · {alert.deliveries.map((delivery) => `${delivery.channel}: ${delivery.status}`).join(" · ")}</small>
        </div>
        {alert.status === "unread" && <button className="secondary-button" type="button" onClick={() => void acknowledge(alert.id)} disabled={workingRule === alert.id}>{workingRule === alert.id ? "Saving…" : "Acknowledge"}</button>}
      </article>)}</div> : <EmptyState title={viewMode === "history" ? "No acknowledged alerts" : viewMode === "important" ? "No important alerts" : "No alerts"} description={viewMode === "important" ? "Use All alerts to inspect lower-priority rule matches." : "Material changes will appear here when a rule matches."} />}
    </SectionCard>
    <div className="content-grid alerts-grid">
      <SectionCard title="Create a rule" description="Rules match material report causes, never raw keyword or article volume. Choose a Watch Source monitor when the rule should stay scoped to one Watch path.">
        <form className="stack-form" onSubmit={createRule}>
          <label htmlFor="rule-name">Rule name</label>
          <input id="rule-name" name="rule_name" autoComplete="off" value={ruleName} onChange={(event) => setRuleName(event.target.value)} placeholder="Primary changes" />
          <label htmlFor="rule-scope">Watch scope</label>
          <select id="rule-scope" value={ruleScope} onChange={(event) => setRuleScope(event.target.value)}>{renderScopeOptions()}</select>
          <label htmlFor="rule-event">Material event</label>
          <select id="rule-event" name="event_type" value={eventType} onChange={(event) => setEventType(event.target.value)}>{EVENT_TYPES.map((event) => <option value={event} key={event}>{label(event)}</option>)}</select>
          <label htmlFor="rule-threshold">Minimum importance threshold</label>
          <select id="rule-threshold" value={ruleThreshold} onChange={(event) => setRuleThreshold(event.target.value)}>{thresholdOptions(Number(ruleThreshold)).map((value) => <option value={value} key={value}>{thresholdLabel(value)} and above</option>)}</select>
          <button className="primary-button" type="submit" disabled={working}>Save rule</button>
        </form>
      </SectionCard>
      <SectionCard title="Rules and scope" description="Threshold and scope changes are saved through the canonical rule API and apply to future alert delivery. Existing alerts keep their original cause and importance.">
        {rules.length ? <div className="rule-list">{rules.map((rule) => <div className="rule-row" key={rule.id}><span><strong>{rule.name}</strong><small>{scopeDescription(rule, watches)} · {rule.event_types.length ? rule.event_types.map(label).join(", ") : "all material events"}</small></span><div className="button-row"><label className="status-note" htmlFor={`threshold-${rule.id}`}>Threshold</label><select id={`threshold-${rule.id}`} aria-label={`Alert threshold for ${rule.name}`} value={String(rule.min_importance)} onChange={(event) => void updateRule(rule.id, { min_importance: Number(event.target.value) })} disabled={workingRule === rule.id}>{thresholdOptions(rule.min_importance).map((value) => <option value={value} key={value}>{thresholdLabel(value)}</option>)}</select><select aria-label={`Alert scope for ${rule.name}`} value={scopeValue(rule)} onChange={(event) => void patchScope(rule, event.target.value)} disabled={workingRule === rule.id}>{renderScopeOptions(rule)}</select><button className="quiet-button" type="button" onClick={() => void updateRule(rule.id, { enabled: !rule.enabled })} disabled={workingRule === rule.id}>{rule.enabled ? "Pause" : "Enable"}</button><Badge tone={rule.enabled ? "mint" : "neutral"}>{rule.enabled ? "enabled" : "paused"}</Badge></div></div>)}</div> : <EmptyState title="No alert rules" description="Create a rule to receive durable in-app attention for a material report cause." />}
      </SectionCard>
    </div>
  </>;
}
