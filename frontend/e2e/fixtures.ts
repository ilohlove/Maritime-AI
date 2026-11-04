import { test as base, expect } from "@playwright/test";
export const test = base.extend({
  page: async ({ page }, use) => {
    const password = process.env.MARITIME_E2E_PASSWORD ?? (process.env.MARITIME_E2E_SYNTHETIC === "1" ? "synthetic-browser-password" : "");
    if (!password) throw new Error("Set MARITIME_E2E_PASSWORD for the isolated backend.");
    await page.goto("/");
    await page.getByLabel("Username", { exact: true }).fill(process.env.MARITIME_E2E_USERNAME ?? "admin");
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
    await use(page);
  },
});
export { expect };
