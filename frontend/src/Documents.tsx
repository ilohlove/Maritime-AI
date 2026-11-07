import { useEffect, useState, type FormEvent } from "react";
import { request } from "./api";

type Document = { id: string; title: string; format: "pdf" | "text"; state?: "pending" | "ready" | "deleting" };
type ImportPayload = { title: string; format: "text"; content: string };
type Provider = { id: string; online: boolean; configured: boolean; models: string[]; default_model: string; status: string };
type Answer = {
  status: "answered" | "no_evidence";
  message?: string;
  provider: string;
  model: string;
  claims: { text: string; source: { document_id: string; title: string; page: number; excerpt_id: number; quote: string } }[];
};

export function Documents({ assistant = false }: { assistant?: boolean }) {
  const [mode, setMode] = useState("offline-local");
  const [uploadLimit, setUploadLimit] = useState(10_000_000);
  const [evidence, setEvidence] = useState<{ title: string; page: number; text: string } | null>(null);
  const [usage, setUsage] = useState<{ reserved_tokens: number; daily_token_budget: number; estimated_recorded_cost_usd: string; reserved_cost_upper_bound_usd: string } | null>(null);
  const [synthetic, setSynthetic] = useState<ImportPayload | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [model, setModel] = useState("");
  const [providerId, setProviderId] = useState("openai");
  const [searchQuery, setSearchQuery] = useState("");
  const [passages, setPassages] = useState<{ excerpt_id: number; page: number; text: string }[] | null>(null);
  const [question, setQuestion] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const provider = providers.find((p) => p.id === providerId);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [library, configuration] = await Promise.all([
        request<Document[]>("/documents"),
        request<{ providers: Provider[]; mode?: string; upload_max_bytes?: number; synthetic_document?: ImportPayload | null }>("/ai/providers"),
      ]);
      setMode(configuration.mode ?? "offline-local");
      setUploadLimit(configuration.upload_max_bytes ?? 10_000_000);
      setSynthetic(configuration.synthetic_document ?? null);
      setDocuments(library);
      setProviders(configuration.providers);
      setDocumentId((current) => library.some((d) => d.id === current) ? current : library[0]?.id ?? "");
      setProviderId(configuration.providers[0]?.id ?? "openai");
      setModel(configuration.providers[0]?.default_model ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cannot load documents.");
    } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function importFile(file: File) {
    setError(""); setNotice(""); setBusy(true);
    try {
      if (file.size > uploadLimit) throw new Error(`Use a file of at most ${uploadLimit / 1_000_000} MB.`);
      const pdf = file.name.toLowerCase().endsWith(".pdf");
      if (!pdf && !/\.txt$/i.test(file.name)) throw new Error("Select a PDF or UTF-8 .txt file.");
      let content: string;
      if (pdf) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const parts: string[] = [];
        for (let i = 0; i < bytes.length; i += 8192) parts.push(String.fromCharCode(...bytes.subarray(i, i + 8192)));
        content = btoa(parts.join(""));
      } else content = await file.text();
      const imported = await request<Document>("/documents", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: file.name, format: pdf ? "pdf" : "text", content }),
      });
      setDocuments((items) => [imported, ...items]);
      setDocumentId(imported.id); setConsent(false); setAnswer(null); setEvidence(null); setPassages(null);
      setNotice("Document imported. No data was sent to an AI service.");
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
    finally { setBusy(false); }
  }

  async function importSynthetic() {
    if (!synthetic) return;
    setBusy(true); setError("");
    try {
      const imported = await request<Document>("/documents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(synthetic) });
      setDocuments((items) => [imported, ...items]); setDocumentId(imported.id); setConsent(false); setAnswer(null); setEvidence(null); setPassages(null);
      setNotice("Bundled synthetic document imported into temporary storage.");
    } catch (e) { setError(e instanceof Error ? e.message : "Synthetic import failed."); }
    finally { setBusy(false); }
  }

  async function deleteSelected() {
    if (!documentId) return;
    setBusy(true); setError(""); setConsent(false); setAnswer(null); setEvidence(null); setPassages(null);
    try {
      await request(`/documents/${documentId}`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: "{}" });
      setDocuments((items) => items.filter((d) => d.id !== documentId)); setDocumentId("");
      setNotice("Document and its search index deleted.");
    } catch (e) { setError(e instanceof Error ? e.message : "Deletion failed. Retry after storage recovery."); }
    finally { setBusy(false); }
  }

  async function inspect(document: string, excerpt: number) {
    setError("");
    try { setEvidence(await request(`/documents/${document}/excerpts/${excerpt}`)); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot inspect evidence."); }
  }

  async function searchLocally() {
    setBusy(true); setError(""); setPassages(null); setEvidence(null);
    try { setPassages(await request(`/documents/${documentId}/search?q=${encodeURIComponent(searchQuery)}`)); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot search document."); }
    finally { setBusy(false); }
  }

  async function showUsage() {
    setError("");
    try { setUsage(await request("/ai/usage")); }
    catch (e) { setError(e instanceof Error ? e.message : "Cannot load usage."); }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setAnswer(null); setNotice("");
    // Consume consent on every attempt; retry requires a fresh explicit action.
    const authorized = consent;
    setConsent(false);
    try {
      setAnswer(await request<Answer>(`/documents/${documentId}/questions`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, provider: providerId, model, external_consent: authorized }),
      }));
    } catch (e) { setError(e instanceof Error ? e.message : "Question failed."); }
    finally { setBusy(false); }
  }

  return <section className="card document-workspace">
    <h2>{assistant ? "Ask a document" : "Private document library"}</h2>
    <p role="status">Workspace mode: {mode === "online-mvp" ? "Online MVP · persistent storage" : synthetic ? "Disposable synthetic test · temporary storage" : "Local workspace"}</p>
    <p>Documents are stored on your configured backend. Importing does not send them to an AI provider. Import a text-based PDF or UTF-8 text file (up to {uploadLimit / 1_000_000} MB{mode === "online-mvp" ? ", 50 pages" : ""}). Scanned PDFs require OCR.</p>
    {mode === "online-mvp" && <><button disabled={busy} onClick={() => void showUsage()}>View today's AI usage</button>{usage && <p>Reserved tokens: {usage.reserved_tokens} / {usage.daily_token_budget}. Recorded cost estimate: ${usage.estimated_recorded_cost_usd}; reserved cost bound: ${usage.reserved_cost_upper_bound_usd}. Estimates use configured prices; failed calls may have unreported usage.</p>}</>}
    <label>Import document
      <input type="file" accept=".pdf,.txt" disabled={busy || loading || !!synthetic} onChange={(e) => {
        const file = e.target.files?.[0]; e.target.value = "";
        if (file) void importFile(file);
      }} />
    </label>
    {synthetic && <button disabled={busy || loading} onClick={() => void importSynthetic()}>Import bundled synthetic document</button>}
    {loading && <p role="status">Loading library and provider configuration…</p>}
    {error && <div role="alert"><p>{error}</p><button disabled={busy} onClick={() => void load()}>Reload library / configuration</button></div>}
    {notice && <p role="status">{notice}</p>}
    {!loading && documents.length === 0 && <p>No documents imported. Import a document to begin.</p>}
    <form onSubmit={(e) => void ask(e)}>
      <label>Selected document
        <select value={documentId} disabled={busy} onChange={(e) => { setDocumentId(e.target.value); setConsent(false); setAnswer(null); setEvidence(null); setPassages(null); }}>
          <option value="">Select a document</option>
          {documents.map((d) => <option key={d.id} value={d.id}>{d.title}{d.state && d.state !== "ready" ? ` · ${d.state} — delete and retry` : ""}</option>)}
        </select>
      </label>
      <button type="button" disabled={busy || !documentId} onClick={() => void deleteSelected()}>Delete selected document</button>
      <label>Search document without AI
        <input value={searchQuery} maxLength={2000} disabled={busy} onChange={(e) => setSearchQuery(e.target.value)} />
      </label>
      <button type="button" disabled={busy || loading || !documentId || !searchQuery.trim() || (documents.find((d) => d.id === documentId)?.state ?? "ready") !== "ready"} onClick={() => void searchLocally()}>Search selected document</button>
      {passages && <aside aria-label="Local search evidence">
        <h3>Source passages · no AI inference</h3>
        {passages.length === 0 && <p>No matching passages found.</p>}
        {passages.map((passage) => <article key={passage.excerpt_id}><p>Source passage · Page {passage.page}</p><p>{passage.text}</p><button type="button" onClick={() => void inspect(documentId, passage.excerpt_id)}>Inspect passage {passage.excerpt_id}</button></article>)}
      </aside>}
      <label>AI provider
        <select value={providerId} disabled={busy} onChange={(e) => {
          setProviderId(e.target.value); setModel(providers.find((p) => p.id === e.target.value)?.default_model ?? "");
          setConsent(false); setAnswer(null);
        }}>
          {providers.map((p) => <option key={p.id} value={p.id}>{p.id} · {p.online ? "Online" : "Offline"}</option>)}
        </select>
      </label>
      <label>Model
        <select value={model} disabled={busy} onChange={(e) => { setModel(e.target.value); setConsent(false); setAnswer(null); }}>
          {provider?.models.map((m) => <option key={m}>{m}</option>)}
        </select>
      </label>
      {provider && <p role="status">{provider.online ? "Online provider" : "Offline provider"}: {provider.status === "disabled_disposable" ? "Disabled for disposable testing; no real inference or API charge is allowed" : provider.status === "disabled_online" ? "Disabled by administrator; paid inference is off" : provider.configured ? "Configured; connectivity has not been verified" : "API key missing — configure OPENAI_API_KEY on the backend"}. No automatic fallback.</p>}
      <label>Question (Vietnamese or English)
        <textarea value={question} maxLength={2000} required disabled={busy} onChange={(e) => { setQuestion(e.target.value); setConsent(false); setAnswer(null); }} />
      </label>
      <label className="consent">
        <input type="checkbox" checked={consent} disabled={busy} onChange={(e) => setConsent(e.target.checked)} />
        I authorize sending this question and up to 6 relevant excerpts (9,600 characters total) to {providerId} for this request. The question is also sent for search translation. A short document may fit entirely within those excerpts.
      </label>
      <button className="primary" disabled={busy || loading || !documentId || (documents.find((d) => d.id === documentId)?.state ?? "ready") !== "ready" || !question.trim() || !provider?.configured || (provider.online && !consent)}>Ask document</button>
    </form>
    {busy && <p role="status">Processing request…</p>}
    {evidence && <aside aria-label="Source evidence"><h3>{evidence.title} · Page {evidence.page}</h3><p>{evidence.text}</p></aside>}
    {answer && <div className="document-answer" aria-live="polite">
      <h3>{answer.status === "no_evidence" ? "No relevant evidence found" : "Answer with validated sources"}</h3>
      <p>{answer.provider} / {answer.model}</p>
      {answer.message && <p>{answer.message}</p>}
      {answer.claims.map((claim, index) => <article key={index}>
        <p><span className="muted">AI interpretation: </span>{claim.text}</p>
        <p className="muted">Source evidence</p><blockquote>{claim.source.quote}</blockquote>
        <button type="button" onClick={() => void inspect(claim.source.document_id, claim.source.excerpt_id)}>Inspect source excerpt {claim.source.excerpt_id}</button>
        <p className="muted">{claim.source.title} · {documents.find((d) => d.id === claim.source.document_id)?.format === "text" ? "Text page" : "PDF page"} {claim.source.page} · Excerpt {claim.source.excerpt_id}</p>
      </article>)}
      <p className="muted">Quotes are checked against retrieved text. Review the original before using an answer for operational decisions; citation checks do not prove that an interpretation is correct.</p>
    </div>}
  </section>;
}
