import { ReactNode, useEffect, useRef, useState } from "react";
import { apiFetch } from "../lib/api";
import type { ViewKey } from "../lib/types";
import type { RuntimeControlAction, RuntimeStatus, ServiceState } from "../lib/runtime";

type NavItem = { key: ViewKey; label: string; group: string; icon: string };

export const SIMPLE_NAV_ITEMS: NavItem[] = [
  { key: "inbox", label: "Home", group: "Review", icon: "⌂" },
  { key: "stories", label: "Stories", group: "Review", icon: "◈" },
  { key: "ask", label: "Ask", group: "Review", icon: "✦" },
  { key: "reports", label: "Reports", group: "Review", icon: "▥" },
  { key: "monitors", label: "Watches", group: "Configure", icon: "◌" },
];

export const ADVANCED_NAV_ITEMS: NavItem[] = [
  ...SIMPLE_NAV_ITEMS,
  { key: "documents", label: "Documents", group: "Advanced", icon: "▤" },
  { key: "questions", label: "Research", group: "Advanced", icon: "?" },
  { key: "workbench", label: "Research & diagnostics", group: "Advanced", icon: "⌕" },
  { key: "alerts", label: "Alerts", group: "Advanced", icon: "!" },
];

export const NAV_ITEMS = SIMPLE_NAV_ITEMS;

function serviceLabel(state: ServiceState): string {
  return {
    checking: "Checking components",
    starting: "Starting",
    idle: "Ready · idle",
    queued: "Work queued",
    processing: "Processing",
    degraded: "Needs attention",
    stopping: "Stopping",
    stopped: "Stopped",
    unavailable: "Service unavailable",
  }[state];
}

function serviceDotState(state: ServiceState): "online" | "offline" | "checking" {
  if (["idle", "queued", "processing"].includes(state)) return "online";
  if (["degraded", "stopped", "unavailable"].includes(state)) return "offline";
  return "checking";
}

const CONTROL_LABELS: Record<RuntimeControlAction, string> = {
  restart_api: "Restart API",
  restart_worker: "Restart worker",
  restart_scheduler: "Restart scheduler",
  stop_newsroom: "Stop Newsroom",
};

export function AppShell({ view, serviceState, runtimeStatus, controlPending, username, onRuntimeControl, onLogout, children }: {
  view: ViewKey;
  serviceState: ServiceState;
  runtimeStatus: RuntimeStatus | null;
  controlPending: RuntimeControlAction | null;
  username: string;
  onRuntimeControl: (action: RuntimeControlAction) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [mode, setMode] = useState<"simple" | "advanced">("simple");
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const loadMode = () => { void apiFetch<{ mode: "simple" | "advanced" }>("/experience").then((result) => setMode(result.mode)).catch(() => undefined); };
    const onExperienceChange = () => loadMode();
    loadMode();
    window.addEventListener("experience-change", onExperienceChange);
    return () => window.removeEventListener("experience-change", onExperienceChange);
  }, []);
  useEffect(() => { mainRef.current?.focus(); setMenuOpen(false); }, [view]);
  const navItems = mode === "advanced" ? ADVANCED_NAV_ITEMS : SIMPLE_NAV_ITEMS;
  const groups = Array.from(new Set(navItems.map((item) => item.group)));
  const allowedActions = runtimeStatus?.controls.actions ?? [];

  return (
    <div className="product-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <button className="mobile-menu-button" type="button" aria-expanded={menuOpen} aria-controls="primary-nav" onClick={() => setMenuOpen((open) => !open)}>Menu</button>
      <aside id="primary-nav" className={`sidebar ${menuOpen ? "sidebar-open" : ""}`} style={{ overflowY: "auto" }}>
        <div className="brand-lockup"><span className="brand-dot" aria-hidden="true" /><span>Newsroom</span></div>
        <p className="sidebar-caption">Evidence-first intelligence</p>
        <nav aria-label="Primary navigation">
          {groups.map((group) => <div className="nav-group" key={group}>
            <p className="nav-group-label">{group}</p>
            {navItems.filter((item) => item.group === group).map((item) => <a key={item.key} href={`#${item.key}`} className={`nav-item ${view === item.key ? "active" : ""}`} aria-current={view === item.key ? "page" : undefined}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</a>)}
          </div>)}
        </nav>
        <div className="sidebar-footer" style={{ alignItems: "stretch", flexDirection: "column" }}>
          <a className="nav-item" href="#settings"><span className="nav-icon" aria-hidden="true">⚙</span>Settings &amp; cost</a>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}><span className={`service-dot ${serviceDotState(serviceState)}`} aria-hidden="true" /><span>{serviceLabel(serviceState)}</span></div>
          <details open={["degraded", "unavailable", "stopped"].includes(serviceState)} style={{ minWidth: 0, width: "100%" }}>
            <summary>Status &amp; recovery</summary>
            {runtimeStatus ? <>
              <p className="status-note">Work: {runtimeStatus.work.state} · {runtimeStatus.work.queued_jobs} queued · {runtimeStatus.work.running_jobs} running</p>
              {(["api", "worker", "scheduler"] as const).map((role) => <p className="status-note" key={role}><strong>{role.toUpperCase()}:</strong> {runtimeStatus.components[role].status}</p>)}
              {allowedActions.length ? <div className="button-row" style={{ alignItems: "stretch", flexWrap: "wrap" }}>{allowedActions.map((action) => <button className={action === "stop_newsroom" ? "quiet-button" : "secondary-button"} style={{ flex: "1 1 82px", minWidth: 0 }} type="button" key={action} disabled={controlPending !== null} onClick={() => onRuntimeControl(action)}>{controlPending === action ? "Requesting…" : CONTROL_LABELS[action]}</button>)}</div> : <p className="status-note">Managed recovery controls are unavailable. Use your Newsroom launcher if the local service needs to be started.</p>}
            </> : <p className="status-note">Runtime details are unavailable. Browser connectivity alone does not prove Newsroom is healthy.</p>}
          </details>
        </div>
      </aside>
      <div className="workspace">
        <header className="workspace-header">
          <div><p className="header-kicker">Private workspace</p><p className="header-user">{username}</p></div>
          <div className="header-actions"><span className={`connection-label ${serviceDotState(serviceState)}`}>{serviceLabel(serviceState)}</span><button className="quiet-button" type="button" onClick={onLogout}>Sign out</button></div>
        </header>
        <main ref={mainRef} className="main-content" id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
