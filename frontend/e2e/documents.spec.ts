import { test, expect } from "./fixtures";

// Requires tests/browser_app.py on a disposable database. Official SDK is mocked.
test.skip(process.env.MARITIME_E2E_SYNTHETIC !== "1", "Requires the isolated synthetic SDK backend; see README.");

test("real import, consent and cited answer with synthetic SDK on desktop and mobile", async ({ page }) => {
  const title = `SYNTHETIC-MANUAL-${Date.now()}.txt`;
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await expect(page.getByText(/Configured; connectivity/)).toBeVisible();
  await page.getByLabel("Import document").setInputFiles({
    name: title, mimeType: "text/plain",
    buffer: Buffer.from("SYNTHETIC TRAINING ONLY. Lifeboat inspections must be performed weekly."),
  });
  await expect(page.getByText(/Document imported./)).toBeVisible();
  await page.getByLabel("Question (Vietnamese or English)").fill("Bao lâu cần kiểm tra xuồng cứu sinh?");
  const ask = page.getByRole("button", { name: "Ask document", exact: true });
  await expect(ask).toBeDisabled();
  await page.getByRole("checkbox").check();
  await ask.click();
  await expect(page.getByText("SYNTHETIC SDK RESPONSE: kiểm tra hằng tuần.")).toBeVisible();
  await expect(page.getByText("Lifeboat inspections must be performed weekly.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Text page 1/)).toBeVisible();
  await expect(page.getByRole("checkbox")).not.toBeChecked();
  await expect(ask).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("document-answer-mobile.png"), fullPage: true });
  await page.reload();
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill(process.env.MARITIME_E2E_PASSWORD ?? "synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  await page.getByRole("button", { name: "AI Assistant", exact: true }).click();
  await expect(page.getByRole("option", { name: title })).toBeAttached();
});

test("imports a real synthetic PDF, inspects its citation and deletes its index", async ({ page }) => {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  const stream = "BT /F1 12 Tf 10 200 Td (Lifeboat inspections must be performed weekly.) Tj ET";
  objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await page.getByLabel("Import document").setInputFiles({ name: "SYNTHETIC-PDF.pdf", mimeType: "application/pdf", buffer: Buffer.from(pdf) });
  await expect(page.getByText(/Document imported./)).toBeVisible();
  await page.getByLabel("Search document without AI").fill("lifeboat");
  await page.getByRole("button", { name: "Search selected document" }).click();
  await expect(page.getByLabel("Local search evidence")).toContainText("Lifeboat inspections must be performed weekly.");
  await page.getByLabel("Question (Vietnamese or English)").fill("lifeboat inspections?");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Ask document", exact: true }).click();
  await expect(page.getByText(/PDF page 1/)).toBeVisible();
  await page.getByRole("button", { name: /Inspect source excerpt/ }).click();
  await expect(page.getByLabel("Source evidence")).toContainText("Lifeboat inspections must be performed weekly.");
  await page.getByRole("button", { name: "Delete selected document" }).click();
  await expect(page.getByText("Document and its search index deleted.")).toBeVisible();
  await page.reload();
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill(process.env.MARITIME_E2E_PASSWORD ?? "synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("option", { name: "SYNTHETIC-PDF.pdf" })).toHaveCount(0);
});
