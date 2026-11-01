import { useEffect, useState } from "react";
import { listVessels, type Vessel } from "./api";
import { ShipProfile } from "./ShipProfile";
import { copy } from "./copy";
import { AIWorkspace } from "./AIWorkspace";

export default function App() {
  const [module, setModule] = useState("AI Workspace");
  const [vessel, setVessel] = useState<Vessel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dark, setDark] = useState(
    () => localStorage.getItem("maritime-theme") === "dark",
  );
  async function load() {
    setLoading(true);
    setError("");
    try {
      setVessel((await listVessels())[0] ?? null);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to load profile.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("maritime-theme", dark ? "dark" : "light");
  }, [dark]);
  const value = (key: string) => String(vessel?.[key] ?? copy.unknown);
  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ⚓
          </span>
          <div>
            MARITIME <strong>AI ASSISTANT</strong>
            <small>PERSONAL AI WORKSPACE</small>
          </div>
        </div>
        <nav aria-label="Main navigation">
          {copy.modules.map((item, index) => (
            <button
              key={item}
              className={module === item ? "nav active" : "nav"}
              aria-current={module === item ? "page" : undefined}
              onClick={() => setModule(item)}
            >
              <span aria-hidden="true" className="nav-index">
                0{index + 1}
              </span>
              {item}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="local-dot" /> Local workspace
          <p>No cloud AI required</p>
        </div>
      </aside>
      <div className="main-shell">
        <header>
          <div>
            <span className="eyebrow">ONBOARD / WORKSPACE</span>
            <h1>{module}</h1>
          </div>
          <button
            className="theme-toggle"
            onClick={() => setDark(!dark)}
            aria-label="Toggle color theme"
          >
            {dark ? "Light theme" : "Dark theme"}
          </button>
        </header>
        <main>
          <div hidden={module !== "AI Workspace" && module !== "Knowledge & Files"}><AIWorkspace /></div>
          {module === "AI Workspace" || module === "Knowledge & Files" ? null : loading ? (
            <div role="status" className="card">
              Loading local vessel data…
            </div>
          ) : error ? (
            <div role="alert" className="card">
              <h2>Local backend unavailable</h2>
              <p>{error}</p>
              <button onClick={() => void load()}>Retry connection</button>
            </div>
          ) : module === "Dashboard" ? (
            <>
              <section className="welcome card">
                <span className="eyebrow">VESSEL OVERVIEW</span>
                <h2>
                  {vessel
                    ? value("vessel_name")
                    : "Your vessel workspace starts here"}
                </h2>
                <p>
                  {vessel
                    ? "Vessel particulars from your local database."
                    : "Create a ship profile to establish your vessel’s operational record."}
                </p>
                <button
                  className="primary"
                  onClick={() => setModule("Ship Profile")}
                >
                  {vessel ? "View / edit ship profile" : "Create ship profile"}
                </button>
              </section>
              <div className="stats-grid">
                {[
                  ["IMO number", "imo_number"],
                  ["Flag", "flag"],
                  ["Vessel type", "vessel_type"],
                  ["Call sign", "call_sign"],
                ].map(([label, key]) => (
                  <section className="card stat" key={key}>
                    <span>{label}</span>
                    <strong>{value(key)}</strong>
                  </section>
                ))}
              </div>
              <section className="card">
                <h2>Record status</h2>
                <dl className="record-status">
                  <div>
                    <dt>Profile</dt>
                    <dd>
                      {vessel
                        ? "Saved in local SQLite database"
                        : "Not created"}
                    </dd>
                  </div>
                  <div>
                    <dt>Last updated</dt>
                    <dd>
                      {vessel
                        ? new Date(vessel.updated_at).toLocaleString()
                        : copy.unknown}
                    </dd>
                  </div>
                  <div>
                    <dt>Verification</dt>
                    <dd>
                      {vessel
                        ? `${Object.values(vessel.field_provenance).filter((p) => p.verification_status === "verified").length} of ${Object.keys(vessel.field_provenance).length} recorded fields verified`
                        : "No data recorded"}
                    </dd>
                  </div>
                  <div>
                    <dt>AI engine</dt>
                    <dd>Local Only · See AI Workspace for model status</dd>
                  </div>
                </dl>
                <p className="muted">
                  User entries are unverified by default. This workspace does
                  not provide navigational advice.
                </p>
              </section>
            </>
          ) : module === "Ship Profile" ? (
            <ShipProfile vessel={vessel} onSaved={setVessel} />
          ) : (
            <section className="card coming-soon">
              <span className="pill">{copy.comingSoon}</span>
              <h2>{module}</h2>
              <p>This module is planned for a future release.</p>
              {module === "AI Assistant" && (
                <p>
                  Development mock only. No AI model is installed and no
                  maritime advice is generated.
                </p>
              )}
            </section>
          )}
        </main>
        <footer>
          {copy.product} <span>Local data · Local Only AI</span>
        </footer>
      </div>
    </div>
  );
}
