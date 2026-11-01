import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { AIWorkspace } from "./AIWorkspace";
import type { SourceLocator } from "./sourceLocator";

const doc = { id: "synthetic-doc", name: "synthetic.pdf", page_count: 2, size_bytes: 1024, sha256: "abc123" };
function response(data: unknown, ok = true) { return Promise.resolve({ ok, json: async () => data } as Response); }
function setup(result: unknown, ok = true, locator: SourceLocator = { kind: "page", page_number: 1 }) {
  vi.stubGlobal("fetch", vi.fn((url: string, options?: RequestInit) => {
    if (url === "/api/vessels") return Promise.reject(new Error("profile unavailable"));
    if (url === "/api/ai/status") return response({ configured: false, detail: "Local model unavailable. Configure a GGUF file." });
    if (url === "/api/documents") return response([doc]);
    if (url.startsWith("/api/documents?")) return response(doc);
    if (url.includes("/units/")) return response({ document_name: doc.name, locator, text: "SYNTHETIC lifejacket inspections take place every Friday." });
    if (url === "/api/questions" && options?.method === "POST") return response(result, ok);
    return response({});
  }));
}

it("opens AI Workspace independently of missing Ship Profile and exposes Local Only", async () => {
  setup({});
  render(<App />);
  expect(await screen.findByText("Local model unavailable. Configure a GGUF file.")).toBeVisible();
  expect(screen.getByRole("heading", { name: "AI Workspace" })).toBeVisible();
  expect(screen.getByLabelText("AI mode")).toHaveValue("local_only");
  expect(screen.getByRole("option", { name: /Online/ })).toBeDisabled();
});

it("imports locally, asks a question and inspects an exact cited page", async () => {
  const quote = "Lifejacket inspections take place every Friday.";
  setup({ status: "answered", answer: "Document fact: every Friday.", citations: [{ id: "E1", document_id: doc.id,
    document_name: doc.name, revision_id: "revision-1", unit_id: "unit-1", locator: { kind: "page", page_number: 1 }, quote, excerpt: quote }] });
  const user = userEvent.setup(); render(<AIWorkspace />);
  await screen.findByText(/Local model unavailable/);
  await user.upload(screen.getByLabelText(/Import text-based PDF/), new File(["%PDF-synthetic"], "synthetic.pdf", { type: "application/pdf" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Imported synthetic.pdf");
  await user.type(screen.getByLabelText("Question / Câu hỏi"), "When are lifejacket inspections?");
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  expect(await screen.findByText("Document fact: every Friday.")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Inspect source page 1" }));
  expect(await screen.findByRole("region", { name: "Source content" })).toHaveTextContent("SYNTHETIC lifejacket inspections");
});

it("shows insufficient evidence separately from inference failures", async () => {
  setup({ status: "insufficient_evidence", answer: "Insufficient document evidence.", citations: [] });
  const user = userEvent.setup(); render(<AIWorkspace />);
  await screen.findByText(/Local model unavailable/);
  await user.type(screen.getByLabelText("Question / Câu hỏi"), "Unsupported question?");
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  expect(await screen.findByRole("heading", { name: "Insufficient evidence" })).toBeVisible();
  vi.stubGlobal("fetch", vi.fn(() => response({ detail: "Local inference timed out." }, false)));
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Local inference timed out.");
  await waitFor(() => expect(screen.getByRole("button", { name: "Ask document" })).toBeEnabled());
});

it("resolves a typed non-page citation by its exact revision and unit", async () => {
  const locator: SourceLocator = { kind: "sheet", sheet_name: "Safety", cell_range: "B2:C3" };
  setup({ status: "answered", answer: "SYNTHETIC CONTRACT FIXTURE", citations: [{
    id: "E1", document_id: doc.id, document_name: doc.name, revision_id: "revision-B", unit_id: "unit-9",
    locator, quote: "Synthetic interval Friday", excerpt: "Synthetic interval Friday",
  }] }, true, locator);
  const user = userEvent.setup(); render(<AIWorkspace />);
  await screen.findByText(/Local model unavailable/);
  await user.type(screen.getByLabelText("Question / Câu hỏi"), "Synthetic interval?");
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  await user.click(await screen.findByRole("button", { name: "Inspect source Sheet Safety · B2:C3" }));
  expect(await screen.findByRole("region", { name: "Source content" })).toHaveTextContent("Sheet Safety · B2:C3");
  expect(vi.mocked(fetch)).toHaveBeenCalledWith("/api/documents/synthetic-doc/revisions/revision-B/units/unit-9", undefined);
});
