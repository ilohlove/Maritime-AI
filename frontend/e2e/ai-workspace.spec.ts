import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";

// Real PDF extraction/storage/retrieval routes. Successful generation below is an
// explicit browser stub; real-model acceptance is scripts/validate_local_model.py.
test("AI Workspace imports PDF, reports model errors and inspects cited pages", async ({ page }) => {
  const python = process.env.PLAYWRIGHT_PYTHON_EXECUTABLE || resolve("..", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const pdf = join(mkdtempSync(join(tmpdir(), "maritime-pdf-")), "synthetic-training.pdf");
  execFileSync(python, [resolve("..", "scripts/create_synthetic_pdf.py"), pdf]);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AI Workspace", exact: true })).toBeVisible();
  await page.getByLabel("Import text-based PDF", { exact: false }).setInputFiles(pdf);
  await expect(page.getByRole("status")).toContainText("Imported synthetic-training.pdf: 2 pages.");
  await page.getByLabel("Question / Câu hỏi").fill("When do lifejacket inspections take place?");
  await page.getByRole("button", { name: "Ask document", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await page.getByLabel("Question / Câu hỏi").fill("quantum astrophysics");
  await page.getByRole("button", { name: "Ask document", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Insufficient evidence", exact: true })).toBeVisible();
  const id = await page.getByLabel("Source document", { exact: true }).inputValue();
  const source = await (await page.request.get(`/api/documents/${id}/pages/1`)).json();
  const docs = await (await page.request.get('/api/documents')).json();
  const doc = docs.find((item: {id: string}) => item.id === id);
  // The PDF extractor uses the unit resolved by the legacy-compatible source endpoint.
  const unitId = source.unit_id;
  await page.route("**/api/questions", route => route.fulfill({ json: {
    status: "answered", answer: "BROWSER TEST STUB: Document fact: every Friday.", citations: [{
      id: "E1", document_id: id, document_name: "synthetic-training.pdf", revision_id: doc.revision_id, unit_id: unitId, locator: { kind: "page", page_number: 1 },
      excerpt: source.text, quote: "Lifejacket inspections take place every Friday.",
    }],
  } }));
  await page.getByLabel("Question / Câu hỏi").fill("When do lifejacket inspections take place?");
  await page.getByRole("button", { name: "Ask document", exact: true }).click();
  await page.getByRole("button", { name: "Inspect source page 1", exact: true }).click();
  await expect(page.getByRole("region", { name: "Source content" })).toContainText("Lifejacket inspections take place every Friday.");
  await page.reload();
  await expect(page.getByLabel("Source document")).toHaveValue(id);
  await page.setViewportSize({ width: 393, height: 851 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("ai-workspace-mobile.png"), fullPage: true });
});
