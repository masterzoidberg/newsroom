import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiList, jsonBody } from "./lib/api";
import type { ViewKey } from "./lib/types";
import type { RuntimeControlAck, RuntimeControlAction, RuntimeStatus, ServiceState } from "./lib/runtime";
import { AppShell } from "./components/AppShell";
import { AuthView } from "./components/AuthView";
import { PwaStatus } from "./components/PwaStatus";
import { LoadingState } from "./components/ViewPrimitives";
import { AlertsView } from "./views/AlertsView";
import { CollectionView, MonitorsView, QuestionsView, RunsView, SettingsView } from "./views/AdminViews";
import { DocumentView } from "./views/DocumentView";
import { InboxView } from "./views/InboxView";
import { ReportsView } from "./views/ReportsView";
import { StoryEvidenceView } from "./views/StoryEvidenceView";
import { HistoryView, SavedView } from "./views/ReviewViews";
import { WorkbenchView } from "./views/WorkbenchView";
import { AskView } from "./views/AskView";

const HEALTHY_POLL_MS = 5_000;
const FAILURE_POLL_MIN_MS = 3_000;
const FAILURE_POLL_MAX_MS = 30_000;

function initialView(): ViewKey {
  const value = window.location.hash.replace(/^#/, "") as ViewKey;
  return ["inbox", "stories", "documents", "reports", "saved", "history", "workbench", "ask", "topics", "subjects", "sources", "monitors", "questions", "runs", "alerts", "settings"].includes(value) ? value : "inbox";
}

export default function App() {
  const [view, setViewState] = useState<ViewKey>(initialView);
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [controlPending, setControlPending] = useState<RuntimeControlAction | null>(null);
  const [lastControl, setLastControl] = useState<{ action: RuntimeControlAction; at: number } | null>(null);

  useEffect(() => {
    const onHash = () => setViewState(initialView());
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("hashchange", onHash);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    apiFetch<{ username: string }>("/auth/me")
      .then((user) => setUsername(user.username))
      .catch(() => setUsername(null))
      .finally(() => setAuthReady(true));
  }, []);

  useEffect(() => {
    if (!username) return;
    let active = true;
    apiList<{ id: string }>("/watches?page_size=1")
      .then((result) => {
        const count = result.total ?? result.items.length;
        if (!active || count !== 0) return;
        window.location.hash = "inbox";
        setViewState("inbox");
      })
      .catch(() => undefined);
    return () => { active = false; };
  }, [username]);

  const applyRuntimeStatus = useCallback((status: RuntimeStatus) => {
    setRuntimeStatus(status);
    if (lastControl?.action === "stop_newsroom") {
      setServiceState("stopping");
      return;
    }
    if (lastControl?.action.startsWith("restart_") && Date.now() - lastControl.at < 1_500) {
      setServiceState("starting");
      return;
    }
    if (lastControl?.action.startsWith("restart_")) setLastControl(null);
    setServiceState(status.overall);
  }, [lastControl]);

  useEffect(() => {
    if (!username) return;
    let active = true;
    let timer: number | undefined;
    let failures = 0;

    const poll = async () => {
      try {
        const status = await apiFetch<RuntimeStatus>("/runtime/status");
        if (!active) return;
        failures = 0;
        applyRuntimeStatus(status);
        timer = window.setTimeout(() => void poll(), HEALTHY_POLL_MS);
      } catch {
        if (!active) return;
        failures += 1;
        setRuntimeStatus(null);
        setServiceState(lastControl?.action === "stop_newsroom" ? "stopped" : lastControl?.action.startsWith("restart_") ? "starting" : "unavailable");
        const delay = Math.min(FAILURE_POLL_MAX_MS, FAILURE_POLL_MIN_MS * (2 ** Math.min(failures - 1, 3)));
        timer = window.setTimeout(() => void poll(), delay);
      }
    };

    const retryNow = () => {
      if (timer !== undefined) window.clearTimeout(timer);
      void poll();
    };

    void poll();
    window.addEventListener("online", retryNow);
    window.addEventListener("offline", retryNow);
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
      window.removeEventListener("online", retryNow);
      window.removeEventListener("offline", retryNow);
    };
  }, [username, applyRuntimeStatus, lastControl]);

  function setView(next: ViewKey) { window.location.hash = next; setViewState(next); }
  async function logout() { try { await apiFetch("/auth/logout", { method: "POST" }); } finally { setUsername(null); setRuntimeStatus(null); setAuthReady(true); } }

  async function runtimeControl(action: RuntimeControlAction) {
    setControlPending(action);
    setLastControl({ action, at: Date.now() });
    setServiceState(action === "stop_newsroom" ? "stopping" : "starting");
    try {
      await apiFetch<RuntimeControlAck>("/runtime/control", { method: "POST", body: jsonBody({ action }) });
    } catch (error) {
      setLastControl(null);
      if (runtimeStatus) setServiceState(runtimeStatus.overall);
      throw error;
    } finally {
      setControlPending(null);
    }
  }

  if (!authReady) return <main className="auth-page"><LoadingState label="Opening Newsroom" /></main>;
  if (!username) return <AuthView onAuthenticated={setUsername} />;
  const recoveryVisible = serviceState === "unavailable" || serviceState === "stopped";
  return <AppShell view={view} serviceState={serviceState} runtimeStatus={runtimeStatus} controlPending={controlPending} username={username} onRuntimeControl={(action) => void runtimeControl(action)} onLogout={() => void logout()}>
    <div className="utility-row"><span className={online ? "online-label" : "offline-label"}>{online ? "Browser network available" : "Browser network offline · cached shell only"}</span><PwaStatus /></div>
    {recoveryVisible && <p className="status-note" role="status"><strong>{serviceState === "stopped" ? "Newsroom is stopped." : "Newsroom service is unavailable."}</strong> {online ? "Your browser has network access, but the local Newsroom API is not responding." : "Browser network status is offline, and the local Newsroom API is not responding."} Use your installed Newsroom launcher to start the local service, then reload this page.</p>}
    {renderView(view, setView)}
  </AppShell>;
}

function renderView(view: ViewKey, setView: (view: ViewKey) => void) {
  switch (view) {
    case "inbox": return <InboxView openView={setView} />;
    case "stories": return <StoryEvidenceView />;
    case "documents": return <DocumentView />;
    case "reports": return <ReportsView />;
    case "alerts": return <AlertsView />;
    case "topics": return <CollectionView kind="topics" />;
    case "subjects": return <CollectionView kind="subjects" />;
    case "sources": return <CollectionView kind="sources" />;
    case "monitors": return <MonitorsView />;
    case "questions": return <QuestionsView />;
    case "runs": return <RunsView />;
    case "settings": return <SettingsView />;
    case "saved": return <SavedView />;
    case "history": return <HistoryView />;
    case "workbench": return <WorkbenchView />;
    case "ask": return <AskView />;
  }
}
