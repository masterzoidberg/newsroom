import { ReactNode, useEffect, useRef, useState } from "react";
import type { ServiceState, ViewKey } from "../lib/types";

type NavItem = { key: ViewKey; label: string; group: string; icon: string };

export const NAV_ITEMS: NavItem[] = [
  { key: "inbox", label: "Inbox", group: "Review", icon: "⌂" },
  { key: "stories", label: "Story & evidence", group: "Review", icon: "◈" },
  { key: "documents", label: "Documents", group: "Review", icon: "▤" },
  { key: "reports", label: "Reports", group: "Review", icon: "▥" },
  { key: "saved", label: "Saved", group: "Review", icon: "☆" },
  { key: "history", label: "History", group: "Review", icon: "↺" },
  { key: "workbench", label: "Research workbench", group: "Review", icon: "⌕" },
  { key: "ask", label: "Ask Newsroom", group: "Review", icon: "✦" },
  { key: "topics", label: "Topics", group: "Configure", icon: "#" },
  { key: "subjects", label: "Subjects", group: "Configure", icon: "◎" },
  { key: "sources", label: "Sources", group: "Configure", icon: "↗" },
  { key: "monitors", label: "Monitors", group: "Configure", icon: "◌" },
  { key: "questions", label: "Research questions", group: "Configure", icon: "?" },
  { key: "runs", label: "Runs & jobs", group: "Operate", icon: "▶" },
  { key: "alerts", label: "Alerts", group: "Operate", icon: "!" },
  { key: "settings", label: "Settings & cost", group: "Operate", icon: "⚙" },
];

export function AppShell({ view, serviceState, username, onLogout, children }: {
  view: ViewKey;
  serviceState: ServiceState;
  username: string;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => { mainRef.current?.focus(); setMenuOpen(false); }, [view]);
  const groups = Array.from(new Set(NAV_ITEMS.map((item) => item.group)));

  return (
    <div className="product-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <button className="mobile-menu-button" type="button" aria-expanded={menuOpen} aria-controls="primary-nav" onClick={() => setMenuOpen((open) => !open)}>Menu</button>
      <aside id="primary-nav" className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup"><span className="brand-dot" aria-hidden="true" /><span>Newsroom</span></div>
        <p className="sidebar-caption">Evidence-first intelligence</p>
        <nav aria-label="Primary navigation">
          {groups.map((group) => <div className="nav-group" key={group}>
            <p className="nav-group-label">{group}</p>
            {NAV_ITEMS.filter((item) => item.group === group).map((item) => <a key={item.key} href={`#${item.key}`} className={`nav-item ${view === item.key ? "active" : ""}`} aria-current={view === item.key ? "page" : undefined}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</a>)}
          </div>)}
        </nav>
        <div className="sidebar-footer"><span className={`service-dot ${serviceState}`} aria-hidden="true" /><span>{serviceState === "online" ? "Service online" : serviceState === "offline" ? "Offline mode" : "Checking service"}</span></div>
      </aside>
      <div className="workspace">
        <header className="workspace-header">
          <div><p className="header-kicker">Private workspace</p><p className="header-user">{username}</p></div>
          <div className="header-actions"><span className={`connection-label ${serviceState}`}>{serviceState === "offline" ? "Offline" : serviceState === "checking" ? "Connecting" : "Synced"}</span><button className="quiet-button" type="button" onClick={onLogout}>Sign out</button></div>
        </header>
        <main ref={mainRef} className="main-content" id="main-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
