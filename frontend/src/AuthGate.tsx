import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { request } from "./api";
import { getSession, setSession, type Session } from "./session";

export function AuthGate({ children }: { children: ReactNode }) {
  const [session, updateSession] = useState<Session | null>(getSession);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    function expired() { updateSession(null); setError("Your session expired. Sign in again."); }
    window.addEventListener("maritime-session-expired", expired);
    return () => window.removeEventListener("maritime-session-expired", expired);
  }, []);
  useEffect(() => {
    if (!session) return;
    const timer = window.setTimeout(() => { setSession(null); updateSession(null); setError("Your session expired. Sign in again."); }, Math.max(0, session.expires_at * 1000 - Date.now()));
    return () => window.clearTimeout(timer);
  }, [session]);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const value = await request<Session>("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
      if (value.transport !== (import.meta.env.VITE_AUTH_TRANSPORT ?? "bearer")) throw new Error("Frontend and backend authentication configuration do not match.");
      setSession(value); updateSession(value); setPassword("");
    } catch (e) { setPassword(""); setError(e instanceof Error ? e.message : "Sign-in failed."); }
    finally { setBusy(false); }
  }
  async function logout() {
    setBusy(true); setError("");
    try {
      await request("/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      setSession(null); updateSession(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to confirm logout. Retry."); }
    finally { setBusy(false); }
  }
  if (session) return <>{session.storage_warning && <aside role="alert" className="storage-warning">{session.storage_warning}</aside>}<div className="session-bar"><span>Private workspace · {session.user}</span><button disabled={busy} onClick={() => void logout()}>Log out</button>{error && <p role="alert">{error}</p>}</div>{children}</>;
  return <main className="auth-shell"><section className="card">
    <h1>Sign in to Maritime AI</h1>
    <p>Private vessel and document workspace. Sign in again after refreshing or closing this page.</p>
    <form onSubmit={(e) => void login(e)}>
      <label>Username<input autoComplete="username" value={username} maxLength={100} required disabled={busy} onChange={(e) => setUsername(e.target.value)} /></label>
      <label>Password<input type="password" autoComplete="current-password" value={password} maxLength={256} required disabled={busy} onChange={(e) => setPassword(e.target.value)} /></label>
      <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
    {error && <p role="alert">{error}</p>}
  </section></main>;
}
