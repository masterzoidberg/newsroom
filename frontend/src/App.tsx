import { useEffect, useState } from "react";

type ServiceState = "checking" | "online" | "offline";

export default function App() {
  const [serviceState, setServiceState] = useState<ServiceState>("checking");

  useEffect(() => {
    let active = true;
    fetch("/api/v1/health")
      .then((response) => {
        if (!response.ok) throw new Error("health check failed");
        if (active) setServiceState("online");
      })
      .catch(() => {
        if (active) setServiceState("offline");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="app-shell">
      <nav className="topbar" aria-label="Primary navigation">
        <div className="brand-mark">
          <span className="brand-dot" aria-hidden="true" />
          <span>Newsroom</span>
        </div>
        <span className={`service-pill ${serviceState}`}>
          <span className="status-dot" aria-hidden="true" />
          {serviceState === "checking" ? "Checking service" : serviceState === "online" ? "Service online" : "Service offline"}
        </span>
      </nav>

      <section className="hero" aria-labelledby="welcome-heading">
        <p className="eyebrow">Evidence-first intelligence</p>
        <h1 id="welcome-heading">A clearer view of what is changing.</h1>
        <p className="hero-copy">
          Your monitoring workspace is ready for the first research vertical slice.
          Stories, sources, and evidence will gather here as the system comes online.
        </p>
        <div className="hero-actions">
          <button type="button" disabled>Open workspace</button>
          <span className="quiet-note">Foundation shell · Phase 02</span>
        </div>
      </section>

      <section className="foundation-grid" aria-label="Foundation status">
        <article className="status-card">
          <p className="card-label">Storage</p>
          <h2>SQLite foundation</h2>
          <p>WAL mode, migrations, integrity checks, and online recovery primitives are in place.</p>
        </article>
        <article className="status-card accent-card">
          <p className="card-label">Next layer</p>
          <h2>Evidence workflow</h2>
          <p>The next phase will connect monitored targets to retrieved documents and reviewable claims.</p>
        </article>
      </section>
    </main>
  );
}
