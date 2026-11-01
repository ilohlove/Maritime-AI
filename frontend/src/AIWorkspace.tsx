import { useEffect, useRef, useState, type FormEvent } from "react";
import { request } from "./api";

type Document = { id: string; name: string; page_count: number; size_bytes: number; sha256: string };
type Citation = { id: string; document_id: string; document_name: string; page_number: number; excerpt: string; quote: string };
type Answer = { status: string; answer: string; citations: Citation[]; notice?: string };
type ModelStatus = { configured: boolean; detail: string };

export function AIWorkspace() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState("");
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [page, setPage] = useState<{ document_name: string; page_number: number; text: string } | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const active = useRef<{ id: string; controller: AbortController } | null>(null);

  async function load() {
    setError("");
    try {
      const [docs, state] = await Promise.all([request<Document[]>("/documents"), request<ModelStatus>("/ai/status")]);
      setDocuments(docs);
      setSelected(current => current || docs[0]?.id || "");
      setModel(state);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load workspace."); }
  }
  useEffect(() => { void load(); return () => { active.current?.controller.abort(); }; }, []);

  async function upload(file: File | undefined) {
    if (!file) return;
    setError(""); setStatus("");
    if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 10 * 1024 * 1024) {
      setError("Choose a text-based PDF no larger than 10 MiB."); return;
    }
    setUploading(true); setStatus("Importing and extracting local PDF…");
    try {
      const doc = await request<Document>(`/documents?filename=${encodeURIComponent(file.name)}`, {
        method: "POST", headers: { "Content-Type": "application/pdf" }, body: file,
      });
      setDocuments(current => [doc, ...current]); setSelected(doc.id);
      setAnswer(null); setPage(null); setStatus(`Imported ${doc.name}: ${doc.page_count} pages.`);
    } catch (e) { setStatus(""); setError(e instanceof Error ? e.message : "Import failed."); }
    finally { setUploading(false); }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const operation = { id: crypto.randomUUID(), controller: new AbortController() };
    active.current = operation;
    setAsking(true); setAnswer(null); setPage(null); setError(""); setStatus("Retrieving evidence and generating locally… Model startup can take time.");
    try {
      const result = await request<Answer>("/questions", { method: "POST",
        headers: { "Content-Type": "application/json" }, signal: operation.controller.signal,
        body: JSON.stringify({ request_id: operation.id, document_id: selected, question, mode: "local_only" }),
      });
      setAnswer(result); setStatus(result.status === "answered" ? "Answer generated locally. Review its evidence." : "Insufficient document evidence.");
    } catch (e) {
      if (operation.controller.signal.aborted) setStatus("Inference cancelled.");
      else { setStatus(""); setError(e instanceof Error ? e.message : "Inference failed."); }
    } finally { active.current = null; setAsking(false); }
  }

  async function cancel() {
    const operation = active.current;
    if (!operation) return;
    operation.controller.abort();
    try {
      await request(`/questions/${operation.id}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    } catch { /* Aborting the connection also signals cancellation to the backend. */ }
  }

  const document = documents.find(doc => doc.id === selected);
  return <>
    <section className="card">
      <h2>Work with your local documents</h2>
      <p>Ask in Vietnamese or English. Answers use evidence from your selected PDF; Ship Profile is optional.</p>
      <label htmlFor="ai-mode">AI mode</label>{" "}
      <select id="ai-mode" value="local_only" disabled>
        <option value="local_only">Local Only</option>
        <option disabled>Online — unavailable</option><option disabled>Auto — unavailable</option>
      </select>
      <p className="muted">Documents and questions stay on the computer running this app. No cloud fallback. Online and Auto are unavailable.</p>
      <p>{model?.detail || "Checking local model configuration…"}</p>
      <button onClick={() => void load()} disabled={asking || uploading}>Refresh workspace status</button>
    </section>
    <section className="card">
      <h2>Knowledge &amp; Files</h2>
      <label htmlFor="pdf-upload">Import text-based PDF (10 MiB, 100 pages maximum)</label>
      <input id="pdf-upload" type="file" accept="application/pdf,.pdf" disabled={uploading || asking}
        onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }} />
      <p className="muted">Scanned PDFs and OCR are unavailable. Partial image-only pages may contain no searchable evidence.</p>
      <label htmlFor="source-document">Source document</label>
      <select id="source-document" value={selected} disabled={asking || uploading} onChange={event => {
        setSelected(event.target.value); setAnswer(null); setPage(null); setStatus("");
      }}>
        <option value="">Select an imported PDF</option>
        {documents.map(doc => <option key={doc.id} value={doc.id}>{doc.name}</option>)}
      </select>
      {document && <div><p>{document.name} · {document.page_count} pages · {Math.ceil(document.size_bytes / 1024)} KiB</p>
        <p className="source-hash">SHA-256: {document.sha256}</p>
        <a href={`/api/documents/${document.id}/file`}>Download original PDF</a></div>}
    </section>
    <form className="card" onSubmit={event => void ask(event)}>
      <label htmlFor="question">Question / Câu hỏi</label>
      <textarea id="question" value={question} minLength={3} maxLength={500} required rows={4}
        disabled={asking} onChange={event => setQuestion(event.target.value)} />
      <button className="primary" disabled={!selected || asking || uploading || question.trim().length < 3}>Ask document</button>
      {asking && <button type="button" onClick={() => void cancel()}>Cancel inference</button>}
    </form>
    {status && <p role="status" className="card">{status}</p>}
    {error && <div role="alert" className="card"><h2>Workspace error</h2><p>{error}</p></div>}
    {answer && <section className="card"><h2>{answer.status === "answered" ? "Document answer" : "Insufficient evidence"}</h2>
      <p className="answer-text">{answer.answer}</p>
      {answer.notice && <p className="muted">{answer.notice}</p>}
      {answer.citations.map((source, index) => <details key={`${source.id}-${index}`} open>
        <summary>Source {index + 1}: {source.document_name} · Page {source.page_number}</summary>
        <blockquote>{source.quote}</blockquote>
        <p className="evidence-text">{source.excerpt}</p>
        <button onClick={async () => {
          try { setPage(await request(`/documents/${source.document_id}/pages/${source.page_number}`)); }
          catch (e) { setError(e instanceof Error ? e.message : "Cannot load source page."); }
        }}>Inspect source page {source.page_number}</button>
      </details>)}
    </section>}
    {page && <section className="card" aria-label="Source page"><h2>{page.document_name} · Page {page.page_number}</h2>
      <p>Extracted source text. Download the original PDF to inspect its layout.</p><pre className="evidence-text">{page.text}</pre></section>}
    <p className="muted">AI can misinterpret documents. Inspect cited evidence. You remain responsible for navigation and safety-critical decisions.</p>
  </>;
}
