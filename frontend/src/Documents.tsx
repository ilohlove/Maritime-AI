import { useEffect, useState, type FormEvent } from "react";
import { request } from "./api";

type Document = { id: string; title: string; format: "pdf" | "text" };
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
  const [synthetic, setSynthetic] = useState<ImportPayload | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [model, setModel] = useState("");
  const [providerId, setProviderId] = useState("openai");
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
        request<{ providers: Provider[]; synthetic_document?: ImportPayload | null }>("/ai/providers"),
      ]);
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
      if (file.size > 10_000_000) throw new Error("Use a file of at most 10 MB.");
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
      setDocumentId(imported.id); setConsent(false); setAnswer(null);
      setNotice("Document imported. No data was sent to an AI service.");
    } catch (e) { setError(e instanceof Error ? e.message : "Import failed."); }
    finally { setBusy(false); }
  }

  async function importSynthetic() {
    if (!synthetic) return;
    setBusy(true); setError("");
    try {
      const imported = await request<Document>("/documents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(synthetic) });
      setDocuments((items) => [imported, ...items]); setDocumentId(imported.id); setConsent(false); setAnswer(null);
      setNotice("Bundled synthetic document imported into temporary storage.");
    } catch (e) { setError(e instanceof Error ? e.message : "Synthetic import failed."); }
    finally { setBusy(false); }
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
    <p>Documents are stored on your configured backend. Importing does not send them to an AI provider. Import a text-based PDF or UTF-8 text file (up to 10 MB). Scanned PDFs require OCR.</p>
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
        <select value={documentId} disabled={busy} onChange={(e) => { setDocumentId(e.target.value); setConsent(false); setAnswer(null); }}>
          <option value="">Select a document</option>
          {documents.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
      </label>
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
      {provider && <p role="status">{provider.online ? "Online provider" : "Offline provider"}: {provider.status === "disabled_disposable" ? "Disabled for disposable testing; no real inference or API charge is allowed" : provider.configured ? "Configured; connectivity has not been verified" : "API key missing — configure OPENAI_API_KEY on the backend"}. No automatic fallback.</p>}
      <label>Question (Vietnamese or English)
        <textarea value={question} maxLength={2000} required disabled={busy} onChange={(e) => { setQuestion(e.target.value); setConsent(false); setAnswer(null); }} />
      </label>
      <label className="consent">
        <input type="checkbox" checked={consent} disabled={busy} onChange={(e) => setConsent(e.target.checked)} />
        I authorize sending this question and up to 6 relevant excerpts (9,600 characters total) to {providerId} for this request. The question is also sent for search translation. A short document may fit entirely within those excerpts.
      </label>
      <button className="primary" disabled={busy || loading || !documentId || !question.trim() || !provider?.configured || (provider.online && !consent)}>Ask document</button>
    </form>
    {busy && <p role="status">Processing request…</p>}
    {answer && <div className="document-answer" aria-live="polite">
      <h3>{answer.status === "no_evidence" ? "No relevant evidence found" : "Answer with validated sources"}</h3>
      <p>{answer.provider} / {answer.model}</p>
      {answer.message && <p>{answer.message}</p>}
      {answer.claims.map((claim, index) => <article key={index}>
        <p>{claim.text}</p>
        <blockquote>{claim.source.quote}</blockquote>
        <p className="muted">{claim.source.title} · {documents.find((d) => d.id === claim.source.document_id)?.format === "text" ? "Text page" : "PDF page"} {claim.source.page} · Excerpt {claim.source.excerpt_id}</p>
      </article>)}
      <p className="muted">Quotes are checked against retrieved text. Review the original before using an answer for operational decisions; citation checks do not prove that an interpretation is correct.</p>
    </div>}
  </section>;
}
