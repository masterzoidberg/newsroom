import { ReactNode, useEffect, useRef, useState } from "react";
import { apiFetch } from "../lib/api";
import type { ServiceState, ViewKey } from "../lib/types";

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

export function AppShell({ view, serviceState, username, onLogout, children }: {
  view: ViewKey;
  serviceState: ServiceState;
  username: string;
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
            {navItems.filter((item) => item.group === group).map((item) => <a key={item.key} href={`#${item.key}`} className={`nav-item ${view === item.key ? "active" : ""}`} aria-current={view === item.key ? "page" : undefined}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</a>)}
          </div>)}
        </nav>
        <div className="sidebar-footer"><a className="nav-item" href="#settings"><span className="nav-icon" aria-hidden="true">⚙</span>Settings &amp; cost</a><span className={`service-dot ${serviceState}`} aria-hidden="true" /><span>{serviceState === "online" ? "Service online" : serviceState === "offline" ? "Offline mode" : "Checking service"}</span></div>
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
