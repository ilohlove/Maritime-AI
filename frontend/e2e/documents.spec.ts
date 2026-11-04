import { test, expect } from "./fixtures";

// Requires tests/browser_app.py on a disposable database. Official SDK is mocked.
test.skip(process.env.MARITIME_E2E_SYNTHETIC !== "1", "Requires the isolated synthetic SDK backend; see README.");

test("real import, consent and cited answer with synthetic SDK on desktop and mobile", async ({ page }) => {
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await expect(page.getByText(/Configured; connectivity/)).toBeVisible();
  await page.getByLabel("Import document").setInputFiles({
    name: "SYNTHETIC-MANUAL.txt", mimeType: "text/plain",
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
  await expect(page.getByRole("option", { name: "SYNTHETIC-MANUAL.txt" })).toBeAttached();
});
