import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Documents } from "./Documents";

const library = [{ id: "synthetic-doc", title: "Synthetic manual", format: "pdf" }];
const config = { providers: [{ id: "openai", online: true, configured: true, models: ["test-model"], default_model: "test-model", status: "configured_unverified" }] };
const answer = { status: "answered", provider: "openai", model: "test-model", claims: [{ text: "Kiểm tra hằng tuần.", source: { document_id: "synthetic-doc", title: "Synthetic manual", page: 3, excerpt_id: 4, quote: "Inspect weekly." } }] };
function response(data: unknown, ok = true) { return Promise.resolve({ ok, json: async () => data } as Response); }
function setup(result: unknown = answer, ok = true, configured = true) {
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (url === "/api/ai/providers") return response({ providers: config.providers.map((p) => ({ ...p, configured })) });
    if (url === "/api/documents" && !options?.method) return response(library);
    if (url === "/api/documents" && options?.method) return response({ id: "imported", title: "test.txt", format: "text" });
    return response(result, ok);
  });
  vi.stubGlobal("fetch", fetcher);
  render(<Documents />);
  return fetcher;
}

it("requires consent, renders validated sources, consumes consent after each request", async () => {
  const fetcher = setup(); const user = userEvent.setup();
  await screen.findByText(/Configured; connectivity/);
  expect(screen.getByRole("button", { name: "Ask document" })).toBeDisabled();
  await user.type(screen.getByLabelText("Question (Vietnamese or English)"), "Bao lâu kiểm tra?");
  expect(screen.getByRole("button", { name: "Ask document" })).toBeDisabled();
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  expect(await screen.findByText("Kiểm tra hằng tuần.")).toBeInTheDocument();
  expect(screen.getByText("Inspect weekly.")).toBeInTheDocument();
  expect(screen.getByText(/PDF page 3/)).toBeInTheDocument();
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Ask document" })).toBeDisabled();
  const sent = fetcher.mock.calls.find(([url]) => url.includes("/questions"));
  expect(JSON.parse(sent?.[1]?.body as string)).toEqual({ question: "Bao lâu kiểm tra?", provider: "openai", model: "test-model", external_consent: true });
});

it("distinguishes missing evidence from technical errors", async () => {
  setup({ status: "no_evidence", claims: [], provider: "openai", model: "test-model", message: "Try other terms." });
  const user = userEvent.setup(); await screen.findByText(/Configured; connectivity/);
  await user.type(screen.getByLabelText("Question (Vietnamese or English)"), "unknown");
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  expect(await screen.findByText("No relevant evidence found")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it.each(["retrieval_unavailable", "provider_timeout", "model_declined", "citation_validation_failed"])("shows actionable %s errors without treating them as missing evidence", async (code) => {
  setup({ detail: { code, message: "Review source or retry." } }, false);
  const user = userEvent.setup(); await screen.findByText(/Configured; connectivity/);
  await user.type(screen.getByLabelText("Question (Vietnamese or English)"), "test question");
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Ask document" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(code);
  expect(screen.queryByText("No relevant evidence found")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Question (Vietnamese or English)")).toHaveValue("test question");
  expect(screen.getByRole("checkbox")).not.toBeChecked();
});

it("disables online processing when the backend has no API key", async () => {
  setup(answer, true, false);
  await screen.findByText(/API key missing/);
  expect(screen.getByRole("button", { name: "Ask document" })).toBeDisabled();
});

it("revokes consent when the question changes", async () => {
  setup(); const user = userEvent.setup(); await screen.findByText(/Configured; connectivity/);
  await user.click(screen.getByRole("checkbox"));
  await user.type(screen.getByLabelText("Question (Vietnamese or English)"), "changed");
  expect(screen.getByRole("checkbox")).not.toBeChecked();
});

it("imports locally without an inference request", async () => {
  const fetcher = setup(); const user = userEvent.setup(); await screen.findByText(/Configured; connectivity/);
  const file = new File(["SYNTHETIC ONLY"], "test.txt", { type: "text/plain" });
  Object.defineProperty(file, "text", { value: async () => "SYNTHETIC ONLY" }); // jsdom lacks Blob.text
  await user.upload(screen.getByLabelText("Import document"), file);
  expect(await screen.findByText(/Document imported./)).toBeInTheDocument();
  expect(screen.getByLabelText("Selected document")).toHaveValue("imported");
  expect(fetcher.mock.calls.some(([url]) => url.includes("/questions"))).toBe(false);
  const payload = fetcher.mock.calls.find(([url, options]) => url === "/api/documents" && options?.method);
  expect(JSON.parse(payload?.[1]?.body as string).content).toBe("SYNTHETIC ONLY");
});

it("reports and retries library loading failures", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline")).mockImplementation((url: string) => response(url.includes("providers") ? config : library));
  vi.stubGlobal("fetch", fetcher); render(<Documents />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the backend");
  await userEvent.click(screen.getByRole("button", { name: "Reload library / configuration" }));
  await waitFor(() => expect(screen.getByLabelText("Selected document")).toHaveValue("synthetic-doc"));
});

it("restricts disposable UI to the bundled synthetic sample and disables inference", async () => {
  const synthetic = { title: "SYNTHETIC SAMPLE", format: "text", content: "Fictional test only." };
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (url.includes("providers")) return response({ providers: [{ ...config.providers[0], configured: false, status: "disabled_disposable" }], disposable_test_mode: true, synthetic_document: synthetic });
    if (!options?.method) return response([]);
    return response({ id: "sample", title: synthetic.title, format: "text" });
  });
  vi.stubGlobal("fetch", fetcher); render(<Documents />);
  const button = await screen.findByRole("button", { name: "Import bundled synthetic document" });
  expect(screen.getByLabelText("Import document")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Ask document" })).toBeDisabled();
  await userEvent.click(button);
  expect(await screen.findByText(/Bundled synthetic document imported/)).toBeInTheDocument();
  const call = fetcher.mock.calls.find(([url, options]) => url === "/api/documents" && options?.method === "POST");
  expect(JSON.parse(call?.[1]?.body as string)).toEqual(synthetic);
});

it("shows online persistence and enforces the backend's conservative upload size", async () => {
  const fetcher = vi.fn((url: string) => response(url.includes("providers") ? { ...config, mode: "online-mvp", upload_max_bytes: 3_000_000 } : library));
  vi.stubGlobal("fetch", fetcher); render(<Documents />);
  expect(await screen.findByText(/Online MVP · persistent storage/)).toBeInTheDocument();
  expect(screen.getByText(/3 MB, 50 pages/)).toBeInTheDocument();
  const file = new File([new Uint8Array(3_000_001)], "large.pdf", { type: "application/pdf" });
  await userEvent.upload(screen.getByLabelText("Import document"), file);
  expect(await screen.findByRole("alert")).toHaveTextContent("Use a file of at most 3 MB.");
  expect(fetcher.mock.calls.some(([url]) => url.includes("questions"))).toBe(false);
});

it("deletes a selected document and clears its answer", async () => {
  const fetcher = setup();
  await screen.findByText(/Configured; connectivity/);
  await userEvent.click(screen.getByRole("button", { name: "Delete selected document" }));
  expect(await screen.findByText("Document and its search index deleted.")).toBeInTheDocument();
  expect(screen.getByLabelText("Selected document")).toHaveValue("");
  const deleted = fetcher.mock.calls.find(([url, options]) => url === "/api/documents/synthetic-doc" && options?.method === "DELETE");
  expect(deleted).toBeDefined();
});

it("inspects the full source excerpt separately from AI interpretation", async () => {
  const fetcher = setup();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation((url, options) => url.endsWith("/excerpts/4") ? response({ title: "Synthetic manual", page: 3, text: "Full synthetic source passage. Inspect weekly." }) : original(url, options));
  const user = userEvent.setup(); await screen.findByText(/Configured; connectivity/);
  await user.type(screen.getByLabelText("Question (Vietnamese or English)"), "frequency?");
  await user.click(screen.getByRole("checkbox")); await user.click(screen.getByRole("button", { name: "Ask document" }));
  await user.click(await screen.findByRole("button", { name: "Inspect source excerpt 4" }));
  expect(await screen.findByLabelText("Source evidence")).toHaveTextContent("Full synthetic source passage");
  expect(screen.getByText("AI interpretation:")).toBeInTheDocument();
});

it("keeps online paid inference disabled even when a key might be configured", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => response(url.includes("providers") ? { ...config, mode: "online-mvp", providers: [{ ...config.providers[0], status: "disabled_online", configured: false }] } : library)));
  render(<Documents />);
  expect(await screen.findByText(/Disabled by administrator; paid inference is off/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ask document" })).toBeDisabled();
});

it("displays durable token reservations and configured cost estimates", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => response(url.includes("providers") ? { ...config, mode: "online-mvp" } : url.endsWith("/usage") ? { reserved_tokens: 42512, daily_token_budget: 100000, estimated_recorded_cost_usd: "0.0012", reserved_cost_upper_bound_usd: "0.0680192" } : library)));
  render(<Documents />);
  await userEvent.click(await screen.findByRole("button", { name: "View today's AI usage" }));
  expect(await screen.findByText(/Reserved tokens: 42512 \/ 100000/)).toHaveTextContent("$0.0012");
});

it("searches and inspects document passages without consent or paid inference", async () => {
  const fetcher = vi.fn((url: string) => response(url.includes("providers") ? { ...config, providers: [{ ...config.providers[0], configured: false }] } : url.includes("/search?") ? [{ excerpt_id: 7, page: 2, text: "Synthetic local evidence." }] : library));
  vi.stubGlobal("fetch", fetcher); render(<Documents />);
  await screen.findByText(/API key missing/);
  await userEvent.type(screen.getByLabelText("Search document without AI"), "lifeboat");
  await userEvent.click(screen.getByRole("button", { name: "Search selected document" }));
  expect(await screen.findByLabelText("Local search evidence")).toHaveTextContent("Synthetic local evidence.");
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  expect(fetcher.mock.calls.some(([url]) => url.includes("/questions"))).toBe(false);
});
