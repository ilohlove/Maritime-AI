import { test, expect } from "@playwright/test";

// UI-only mock: proves warnings/disabled controls, not provider hosting or TLS.
test.skip(process.env.MARITIME_E2E_DISPOSABLE_UI !== "1", "Enable explicitly for mock disposable UI checks");
test("mock disposable UI warns, imports only the sample and cannot submit inference", async ({ page }) => {
  const sample = { title: "SYNTHETIC UI SAMPLE", format: "text", content: "Fictional test only." };
  let imports = 0;
  let questions = 0;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body: unknown = [];
    if (url.pathname === "/api/auth/login") body = { access_token: "synthetic-ui-token", csrf_token: "unused", expires_at: Date.now()/1000+3600, user: "admin", transport: "bearer", storage_warning: "DISPOSABLE SYNTHETIC TEST: all data may be lost on restart. Real AI is disabled." };
    else if (url.pathname === "/api/ai/providers") body = { disposable_test_mode: true, synthetic_document: sample, providers: [{ id: "openai", configured: false, online: true, status: "disabled_disposable", models: ["gpt-4.1-mini"], default_model: "gpt-4.1-mini" }] };
    else if (url.pathname === "/api/documents" && route.request().method() === "POST") { expect(route.request().postDataJSON()).toEqual(sample); imports++; body = { id: "synthetic-id", title: sample.title, format: "text" }; }
    else if (url.pathname.includes("questions")) { questions++; body = {}; }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-ui-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("data may be lost");
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await expect(page.getByLabel("Import document")).toBeDisabled();
  await page.getByRole("button", { name: "Import bundled synthetic document" }).click();
  await expect(page.getByText("Bundled synthetic document imported into temporary storage.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask document" })).toBeDisabled();
  expect(imports).toBe(1); expect(questions).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("disposable-warning-mobile.png"), fullPage: true });
});
