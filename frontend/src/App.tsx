import { useEffect, useState } from "react";
import { apiFetch } from "./lib/api";
import type { ServiceState, ViewKey } from "./lib/types";
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

function initialView(): ViewKey {
  const value = window.location.hash.replace(/^#/, "") as ViewKey;
  return ["inbox", "stories", "documents", "reports", "saved", "history", "workbench", "ask", "topics", "subjects", "sources", "monitors", "questions", "runs", "alerts", "settings"].includes(value) ? value : "inbox";
}

export default function App() {
  const [view, setViewState] = useState<ViewKey>(initialView);
  const [serviceState, setServiceState] = useState<ServiceState>("checking");
  const [username, setUsername] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const onHash = () => setViewState(initialView());
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("hashchange", onHash); window.addEventListener("online", onOnline); window.addEventListener("offline", onOffline);
    return () => { window.removeEventListener("hashchange", onHash); window.removeEventListener("online", onOnline); window.removeEventListener("offline", onOffline); };
  }, []);
  useEffect(() => { apiFetch<{ username: string }>("/auth/me").then((user) => setUsername(user.username)).catch(() => setUsername(null)).finally(() => setAuthReady(true)); }, []);
  useEffect(() => { apiFetch<{ status: string }>("/health").then(() => setServiceState("online")).catch(() => setServiceState("offline")); }, [online]);

  function setView(next: ViewKey) { window.location.hash = next; setViewState(next); }
  async function logout() { try { await apiFetch("/auth/logout", { method: "POST" }); } finally { setUsername(null); setAuthReady(true); } }

  if (!authReady) return <main className="auth-page"><LoadingState label="Opening Newsroom" /></main>;
  if (!username) return <AuthView onAuthenticated={setUsername} />;
  return <AppShell view={view} serviceState={serviceState} username={username} onLogout={() => void logout()}><div className="utility-row"><span className={online ? "online-label" : "offline-label"}>{online ? "Live connection" : "Offline · cached shell only"}</span><PwaStatus /></div>{renderView(view, setView)}</AppShell>;
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
