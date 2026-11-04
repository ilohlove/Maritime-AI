import { test, expect } from "./fixtures";

test("private session rejects anonymous calls, handles expiry and permits explicit logout", async ({ page }) => {
  const unauthorized = await page.evaluate(async () => (await fetch("/api/documents", { credentials: "omit" })).status);
  expect(unauthorized).toBe(401);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  await page.route("**/api/documents", (route) => route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: { code: "session_expired", message: "Synthetic expiry" } }) }));
  await page.getByRole("button", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Maritime AI" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("session expired");
  await page.unroute("**/api/documents");
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill(process.env.MARITIME_E2E_PASSWORD ?? "synthetic-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in to Maritime AI" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("login-mobile.png"), fullPage: true });
});
