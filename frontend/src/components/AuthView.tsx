import { FormEvent, useState } from "react";
import { apiFetch, ApiError, jsonBody } from "../lib/api";

export function AuthView({ onAuthenticated }: { onAuthenticated: (username: string) => void }) {
  const [mode, setMode] = useState<"login" | "setup">("login");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || password.length < 8) {
      setError("Enter a username and a password of at least 8 characters.");
      return;
    }
    setWorking(true);
    setError(null);
    try {
      if (mode === "setup") await apiFetch<{ username: string }>("/auth/setup", { method: "POST", body: jsonBody({ username, password }) });
      const session = await apiFetch<{ username: string }>("/auth/login", { method: "POST", body: jsonBody({ username, password }) });
      onAuthenticated(session.username);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Authentication failed. Try again.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-heading">
        <div className="brand-lockup"><span className="brand-dot" aria-hidden="true" /><span>Newsroom</span></div>
        <p className="eyebrow">Private evidence workspace</p>
        <h1 id="auth-heading">Keep the signal in view.</h1>
        <p className="auth-copy">Sign in to inspect Stories, source spans, research gaps, and material changes.</p>
        <form onSubmit={submit} className="stack-form">
          <label htmlFor="auth-username">Username</label>
          <input id="auth-username" name="username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" spellCheck={false} />
          <label htmlFor="auth-password">Password</label>
          <input id="auth-password" name="password" value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete={mode === "setup" ? "new-password" : "current-password"} />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={working}>{working ? "Working…" : mode === "setup" ? "Create workspace" : "Sign in"}</button>
        </form>
        <button className="text-button" type="button" onClick={() => { setMode(mode === "login" ? "setup" : "login"); setError(null); }}>
          {mode === "login" ? "First run? Set up the local workspace" : "Already set up? Sign in"}
        </button>
      </section>
    </main>
  );
}
