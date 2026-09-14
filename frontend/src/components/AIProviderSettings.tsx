import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  configureGlobalBudget,
  createAIProvider,
  deleteAIProvider,
  formatDate,
  getAIStatus,
  listAIUsage,
  removeAIProviderCredential,
  setAIRoute,
  setAIProviderCredential,
  setPaidEnabled,
  testAIProvider,
  updateAIProvider,
} from "../lib/api";
import type { AIBudgetLimit, AIConnection, AIProviderUsage, AIStatus, AIRoute } from "../lib/types";
import { Badge, EmptyState, ErrorState, LoadingState, SectionCard, Stat } from "./ViewPrimitives";

type ProviderAction = "test" | "enable" | "disable" | "remove-credential" | "remove" | "default" | "local";
type ProviderPreset = "custom" | "minimax_token_plan";

const MINIMAX_TOKEN_PLAN_BASE_URL = "https://api.minimax.cn/v1";
const MINIMAX_TOKEN_PLAN_KEY_URL = "https://platform.minimaxi.com/user-center/payment/token-plan";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The request could not be completed.";
}

function statusTone(status: AIConnection["validation_status"]): "neutral" | "mint" | "amber" | "coral" {
  if (status === "passed") return "mint";
  if (status === "failed") return "coral";
  return "amber";
}

function money(value: number): string {
  return `$${value.toFixed(2)}`;
}

function usageStatus(value: string | null): string {
  if (!value) return "recorded";
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed === "object" && parsed !== null && "status" in parsed) {
      const status = (parsed as { status?: unknown }).status;
      if (typeof status === "string" && status.length <= 40) return status;
    }
  } catch {
    return value.length <= 40 ? value : "recorded";
  }
  return "recorded";
}

function routeFor(status: AIStatus, providerId: string): AIRoute | undefined {
  return status.routes.find((route) => route.capability === "article_analysis" && route.connection_id === providerId);
}

type ProviderEditorProps = {
  provider?: AIConnection;
  onSaved: () => void;
  onCancel: () => void;
};

function ProviderEditor({ provider, onSaved, onCancel }: ProviderEditorProps) {
  const [preset, setPreset] = useState<ProviderPreset>("custom");
  const [displayName, setDisplayName] = useState(provider?.display_name ?? "");
  const [baseUrl, setBaseUrl] = useState(provider?.base_url ?? "https://api.openai.com/v1");
  const [model, setModel] = useState(provider?.model ?? "gpt-4o-mini");
  const [credentialRequired, setCredentialRequired] = useState(provider?.credential_required ?? true);
  const [maxInputChars, setMaxInputChars] = useState(String(provider?.max_input_chars ?? 24000));
  const [maxOutputTokens, setMaxOutputTokens] = useState(String(provider?.max_output_tokens ?? 1200));
  const [secret, setSecret] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMiniMax = !provider && preset === "minimax_token_plan";

  function applyPreset(value: ProviderPreset) {
    setPreset(value);
    if (value !== "minimax_token_plan") return;
    setDisplayName("MiniMax Token Plan");
    setBaseUrl(MINIMAX_TOKEN_PLAN_BASE_URL);
    setModel("MiniMax-M3");
    setCredentialRequired(true);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setWorking(true);
    setError(null);
    try {
      const bounds = {
        max_input_chars: Number(maxInputChars),
        max_output_tokens: Number(maxOutputTokens),
      };
      let saved: AIConnection;
      if (provider) {
        saved = await updateAIProvider(provider.id, {
          expected_revision: provider.revision,
          display_name: displayName.trim(),
          base_url: baseUrl.trim(),
          model: model.trim(),
          credential_required: credentialRequired,
          ...bounds,
        });
      } else {
        saved = await createAIProvider({
          display_name: displayName.trim(),
          base_url: baseUrl.trim(),
          model: model.trim(),
          credential_required: credentialRequired,
          ...bounds,
        });
      }
      if (secret) await setAIProviderCredential(saved.id, saved.revision, secret);
      setSecret("");
      onSaved();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      // The raw value is never retained after submission, including failure.
      setSecret("");
      setWorking(false);
    }
  }

  return (
    <form className="ai-editor stack-form" onSubmit={(event) => void submit(event)}>
      <div className="ai-editor-heading">
        <div>
          <h3>{provider ? "Edit provider" : "Add AI provider"}</h3>
          <p className="muted">{isMiniMax ? "MiniMax Token Plan connects through its OpenAI-compatible API using a subscription key." : "OpenAI-compatible structured Article Analysis only."} New connections start disabled.</p>
        </div>
        <button className="quiet-button" type="button" onClick={onCancel} disabled={working}>Cancel</button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="ai-editor-grid">
        {!provider && <div className="ai-editor-wide"><label htmlFor="ai-provider-preset">Provider preset</label><select id="ai-provider-preset" value={preset} onChange={(event) => applyPreset(event.target.value as ProviderPreset)}><option value="custom">OpenAI-compatible (custom)</option><option value="minimax_token_plan">MiniMax Token Plan</option></select><small>Use a preset to fill the documented endpoint and model, then review them before saving.</small></div>}
        <div><label htmlFor="ai-provider-name">Display name</label><input id="ai-provider-name" required maxLength={200} value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></div>
        <div><label htmlFor="ai-provider-model">Model</label><input id="ai-provider-model" required maxLength={200} value={model} onChange={(event) => setModel(event.target.value)} /></div>
        <div className="ai-editor-wide"><label htmlFor="ai-provider-url">Base URL</label><input id="ai-provider-url" required maxLength={2048} type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} aria-describedby="ai-provider-url-help" /><small id="ai-provider-url-help">Hosted endpoints require HTTPS. HTTP is allowed only for an explicit loopback endpoint.</small></div>
        <div><label htmlFor="ai-provider-input-limit">Input character limit</label><input id="ai-provider-input-limit" required min={1} max={1000000} type="number" value={maxInputChars} onChange={(event) => setMaxInputChars(event.target.value)} /></div>
        <div><label htmlFor="ai-provider-output-limit">Output token limit</label><input id="ai-provider-output-limit" required min={1} max={100000} type="number" value={maxOutputTokens} onChange={(event) => setMaxOutputTokens(event.target.value)} /></div>
      </div>
      <label className="checkbox-field" htmlFor="ai-provider-credential-required"><input id="ai-provider-credential-required" type="checkbox" checked={credentialRequired} onChange={(event) => setCredentialRequired(event.target.checked)} /> <span>Endpoint requires a credential <small>Uncheck only for a deliberate loopback service.</small></span></label>
      <div><label htmlFor="ai-provider-secret">{isMiniMax ? "MiniMax Token Plan subscription key" : provider?.credential_configured ? "Replace credential (optional)" : "Credential (optional until enable)"}</label><input id="ai-provider-secret" type="password" autoComplete="new-password" value={secret} onChange={(event) => setSecret(event.target.value)} placeholder={provider?.credential_configured ? "Leave blank to keep configured credential" : "Enter once; it is cleared after save"} aria-describedby="ai-provider-secret-help" /><small id="ai-provider-secret-help">Stored only in the approved OS vault; it is never returned to this page.{isMiniMax && <> MiniMax uses a subscription key here, not its separate pay-as-you-go API key. <a href={MINIMAX_TOKEN_PLAN_KEY_URL} target="_blank" rel="noreferrer">Get a Token Plan key</a>.</>}</small></div>
      <div className="button-row"><button className="primary-button" type="submit" disabled={working}>{working ? "Saving…" : provider ? "Save provider" : "Add provider"}</button><button className="secondary-button" type="button" onClick={onCancel} disabled={working}>Cancel</button></div>
    </form>
  );
}

type ProviderCardProps = {
  provider: AIConnection;
  route?: AIRoute;
  effective?: AIRoute["effective"];
  busy: boolean;
  testAuthorized: boolean;
  onAuthorizeTest: (authorized: boolean) => void;
  onEdit: () => void;
  onAction: (action: ProviderAction) => void;
};

function ProviderCard({ provider, route, effective, busy, testAuthorized, onAuthorizeTest, onEdit, onAction }: ProviderCardProps) {
  const testId = `ai-test-authorize-${provider.id}`;
  return (
    <article className="ai-provider-card">
      <div className="ai-provider-header"><div><p className="eyebrow">OpenAI-compatible</p><h3>{provider.display_name}</h3><p className="ai-provider-url">{provider.base_url}</p></div><Badge tone={provider.enabled ? "mint" : "neutral"}>{provider.enabled ? "enabled" : "disabled"}</Badge></div>
      <div className="ai-provider-details">
        <div><span>Model</span><strong>{provider.model}</strong></div>
        <div><span>Credential</span><strong>{provider.credential_configured ? "Configured" : provider.credential_required ? "Not configured" : "Not required"}</strong></div>
        <div><span>Revision / generation</span><strong>{provider.revision} / {provider.generation}</strong></div>
        <div><span>Article Analysis route</span><strong>{effective?.provider_route === "connection" && effective.connection_id === provider.id ? "Effective connection" : route?.connection_id === provider.id ? "Stored connection · fallback may apply" : "Local / offline"}</strong></div>
      </div>
      <div className="ai-validation-row"><Badge tone={statusTone(provider.validation_status)}>{provider.validation_status}</Badge><span>{provider.validation_code ?? "Not tested yet"}</span>{provider.validated_at && <small>{formatDate(provider.validated_at)} · revision {provider.validation_revision}</small>}</div>
      {provider.credential_cleanup_required && <p className="form-error" role="status">Credential removal needs retry before this provider can be removed.</p>}
      <div className="ai-test-panel"><label className="checkbox-field" htmlFor={testId}><input id={testId} type="checkbox" checked={testAuthorized} onChange={(event) => onAuthorizeTest(event.target.checked)} disabled={busy} /> <span>Authorize one bounded validation call <small>May cost up to $0.01; this does not enable background spending.</small></span></label><button className="secondary-button" type="button" onClick={() => onAction("test")} disabled={busy || !testAuthorized}>Test structured output</button></div>
      <div className="button-row ai-provider-actions"><button className="secondary-button" type="button" onClick={onEdit} disabled={busy}>Edit</button><button className="secondary-button" type="button" onClick={() => onAction(provider.enabled ? "disable" : "enable")} disabled={busy}>{provider.enabled ? "Disable" : "Enable"}</button>{provider.credential_configured && <button className="quiet-button" type="button" onClick={() => onAction("remove-credential")} disabled={busy}>Remove credential</button>}<button className="danger-button" type="button" onClick={() => onAction("remove")} disabled={busy}>Remove provider</button></div>
      <div className="button-row ai-route-actions"><button className="secondary-button" type="button" onClick={() => onAction("default")} disabled={busy || !provider.enabled}>Set as Article Analysis default</button><button className="quiet-button" type="button" onClick={() => onAction("local")} disabled={busy}>Use local / offline</button></div>
    </article>
  );
}

type BudgetControlsProps = {
  status: AIStatus;
  usage: AIProviderUsage[];
  onRefresh: () => Promise<void>;
};

function BudgetControls({ status, usage, onRefresh }: BudgetControlsProps) {
  const [period, setPeriod] = useState<"daily" | "monthly" | "lifetime">("monthly");
  const [capType, setCapType] = useState<"paid_requests" | "usd">("usd");
  const [capValue, setCapValue] = useState("1");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const estimatedTotal = usage.reduce((total, item) => total + (Number.isFinite(Number(item.estimated_cost_usd)) ? Number(item.estimated_cost_usd) : 0), 0);

  async function savePaid(enabled: boolean) {
    setWorking(true); setError(null);
    try { await setPaidEnabled(enabled); await onRefresh(); } catch (caught) { setError(errorMessage(caught)); } finally { setWorking(false); }
  }

  async function saveLimit(event: FormEvent) {
    event.preventDefault();
    setWorking(true); setError(null);
    try { await configureGlobalBudget({ period, cap_type: capType, cap_value: Number(capValue) }); setCapValue("1"); await onRefresh(); } catch (caught) { setError(errorMessage(caught)); } finally { setWorking(false); }
  }

  return <>
    <SectionCard title="Paid routing and limits" description="Local/offline remains the default. Background paid routing is separate from explicit connection tests and stays off until you turn it on.">
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="ai-budget-toggle"><div><strong>Allow background paid Article Analysis</strong><p className="muted">Current state: {status.paid_enabled ? "enabled" : "disabled"}. A provider must also be enabled and routed.</p></div><button className={status.paid_enabled ? "danger-button" : "primary-button"} type="button" onClick={() => void savePaid(!status.paid_enabled)} disabled={working}>{status.paid_enabled ? "Turn paid routing off" : "Turn paid routing on"}</button></div>
      <form className="ai-budget-form" onSubmit={(event) => void saveLimit(event)}><div><label htmlFor="ai-budget-period">Limit period</label><select id="ai-budget-period" value={period} onChange={(event) => setPeriod(event.target.value as typeof period)}><option value="daily">Daily</option><option value="monthly">Monthly</option><option value="lifetime">Lifetime</option></select></div><div><label htmlFor="ai-budget-cap">Limit type</label><select id="ai-budget-cap" value={capType} onChange={(event) => setCapType(event.target.value as typeof capType)}><option value="usd">Estimated USD</option><option value="paid_requests">Paid requests</option></select></div><div><label htmlFor="ai-budget-value">Limit value</label><input id="ai-budget-value" required min={0} step={capType === "usd" ? "0.01" : "1"} type="number" value={capValue} onChange={(event) => setCapValue(event.target.value)} /></div><button className="secondary-button" type="submit" disabled={working}>Save global limit</button></form>
      {status.budget_limits.length ? <div className="table-wrap"><table><thead><tr><th scope="col">Scope</th><th scope="col">Period</th><th scope="col">Limit</th><th scope="col">State</th></tr></thead><tbody>{status.budget_limits.map((limit: AIBudgetLimit) => <tr key={limit.id}><td>{limit.scope_type}{limit.scope_id ? ` · ${limit.scope_id.slice(0, 12)}…` : ""}</td><td>{limit.period}</td><td>{limit.cap_type === "usd" ? money(Number(limit.cap_value)) : `${Number(limit.cap_value)} requests`}</td><td><Badge tone={limit.enabled ? "mint" : "neutral"}>{limit.enabled ? "active" : "off"}</Badge></td></tr>)}</tbody></table></div> : <EmptyState title="No global limits configured" description="Set a small global USD or request cap before enabling background paid routing." />}
    </SectionCard>
    <SectionCard title="Provider usage" description="Estimated reservation cost is shown separately; the current adapter does not expose actual billing cost.">
      <div className="stat-grid ai-usage-stats"><Stat label="Estimated recorded" value={money(estimatedTotal)} tone={estimatedTotal > 0 ? "amber" : "neutral"} /><Stat label="Actual billing" value="Unavailable" /><Stat label="Recent records" value={usage.length} /></div>
      {usage.length ? <div className="table-wrap"><table><thead><tr><th scope="col">When</th><th scope="col">Capability / provider</th><th scope="col">Estimated</th><th scope="col">Outcome</th></tr></thead><tbody>{usage.slice(0, 20).map((item) => <tr key={item.id}><td>{formatDate(item.created_at)}</td><td>{item.capability} · {item.provider ?? "not dispatched"}</td><td>{money(Number(item.estimated_cost_usd) || 0)}</td><td>{usageStatus(item.outcome)}</td></tr>)}</tbody></table></div> : <EmptyState title="No provider usage yet" description="Local analysis costs nothing. Explicit validation and background paid calls will appear here." />}
    </SectionCard>
  </>;
}

export function AIProviderSettings() {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [usage, setUsage] = useState<AIProviderUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [authorizedTests, setAuthorizedTests] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [nextStatus, nextUsage] = await Promise.all([getAIStatus(), listAIUsage()]);
      setStatus(nextStatus); setUsage(nextUsage.items);
    } catch (caught) { setError(caught); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const effective = useMemo(() => status?.effective_operation_routes?.article_analysis ?? status?.effective_routes.article_analysis, [status]);

  async function providerAction(provider: AIConnection, action: ProviderAction) {
    if (!status) return;
    if (action === "test" && !authorizedTests[provider.id]) return;
    if ((action === "remove" || action === "remove-credential") && !window.confirm(action === "remove" ? `Remove ${provider.display_name}? Existing analyses and usage history stay intact.` : `Remove the stored credential for ${provider.display_name}?`)) return;
    setBusy(provider.id); setActionError(null);
    try {
      if (action === "test") await testAIProvider(provider.id, provider.revision);
      if (action === "enable" || action === "disable") await updateAIProvider(provider.id, { expected_revision: provider.revision, enabled: action === "enable" });
      if (action === "remove-credential") await removeAIProviderCredential(provider.id, provider.revision);
      if (action === "remove") {
        const result = await deleteAIProvider(provider.id, provider.revision);
        if (!result.deleted) throw new Error("Credential removal is still required before this provider can be removed.");
      }
      if (action === "default") await setAIRoute({ provider_route: "connection", connection_id: provider.id, fallback_policy: "local", expected_generation: status.generation });
      if (action === "local") await setAIRoute({ provider_route: "local", fallback_policy: "local", expected_generation: status.generation });
      setAuthorizedTests((current) => ({ ...current, [provider.id]: false }));
      await load();
    } catch (caught) { setActionError(errorMessage(caught)); }
    finally { setBusy(null); }
  }

  if (loading) return <SectionCard title="AI Providers" description="Loading managed provider status."><LoadingState label="Loading AI provider settings" /></SectionCard>;
  if (error && !status) return <SectionCard title="AI Providers" description="Managed provider status is separate from general Settings."><ErrorState error={error} retry={() => void load()} /></SectionCard>;
  if (!status) return null;

  const providers = status.items;
  return <div className="ai-settings"><SectionCard title="AI Providers" description="Newsroom works locally and offline by default. Configure one OpenAI-compatible Article Analysis connection only when the improvement and cost are clear." action={<button className="primary-button" type="button" onClick={() => setEditing("new")} disabled={editing !== null}>Add provider</button>}>
    {actionError && <div className="state-panel error-panel" role="alert"><strong>Provider action could not be completed.</strong><p>{actionError}</p><button className="secondary-button" type="button" onClick={() => void load()}>Refresh provider state</button></div>}
    <div className="stat-grid ai-status-stats"><Stat label="Effective route" value={effective?.provider_route === "connection" ? "Managed" : "Local / offline"} tone={effective?.provider_route === "connection" ? "mint" : "neutral"} /><Stat label="Effective model" value={effective?.model ?? "local"} /><Stat label="Generation" value={status.generation} /><Stat label="Background paid" value={status.paid_enabled ? "On" : "Off"} tone={status.paid_enabled ? "amber" : "mint"} /></div>
    <p className="status-note">Article Analysis is currently <strong>{effective?.provider ?? "local"}</strong> on <strong>{effective?.model ?? "local"}</strong> · {effective?.reason ?? "default_local"} · source {status.effective_operation_routes?.article_analysis?.source ?? "managed metadata"}.</p>
    {editing === "new" && <ProviderEditor key="new" onSaved={() => { setEditing(null); void load(); }} onCancel={() => setEditing(null)} />}
    {providers.length ? <div className="ai-provider-list">{providers.map((provider) => editing === provider.id ? <ProviderEditor key={provider.id} provider={provider} onSaved={() => { setEditing(null); void load(); }} onCancel={() => setEditing(null)} /> : <ProviderCard key={provider.id} provider={provider} route={routeFor(status, provider.id)} effective={effective} busy={busy === provider.id} testAuthorized={authorizedTests[provider.id] ?? false} onAuthorizeTest={(authorized) => setAuthorizedTests((current) => ({ ...current, [provider.id]: authorized }))} onEdit={() => setEditing(provider.id)} onAction={(action) => void providerAction(provider, action)} />)}</div> : <EmptyState title="No managed providers" description="The deterministic local route is ready. Add a provider only for an intentional, bounded Article Analysis improvement." action={<button className="secondary-button" type="button" onClick={() => setEditing("new")}>Add first provider</button>} />}
  </SectionCard><BudgetControls status={status} usage={usage} onRefresh={load} /></div>;
}
