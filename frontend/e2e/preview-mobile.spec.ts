import { test, expect, devices } from "@playwright/test";

test.use({ ...devices["Pixel 7"] });

// Use only a disposable, migrated database, as for workspace.spec.ts.
test("Android touch navigation, edit, validation, save and reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AI Workspace", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Dashboard", exact: true }).tap();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ship Profile", exact: true }).tap();
  const name = page.getByLabel("Vessel Name", { exact: true });
  await name.fill("SYNTHETIC ANDROID REVIEW — TEST DATA");
  const flag = page.getByLabel("Flag", { exact: true });
  await flag.fill("SYNTHETIC ANDROID FLAG");
  const mmsi = page.getByLabel("MMSI", { exact: true });
  await mmsi.fill("invalid");
  await page.getByRole("button", { name: /Create ship profile|Save changes/ }).tap();
  await expect(page.getByText("Enter exactly 9 digits.", { exact: true })).toBeVisible();
  await mmsi.fill("");
  await page.getByRole("button", { name: /Create ship profile|Save changes/ }).tap();
  await expect(page.getByRole("status")).toHaveText("Ship profile saved locally.");
  await page.getByRole("button", { name: "Dashboard", exact: true }).tap();
  await expect(page.getByRole("heading", { name: "SYNTHETIC ANDROID REVIEW — TEST DATA" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Dashboard", exact: true }).tap();
  await expect(page.getByText("SYNTHETIC ANDROID FLAG", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ship Profile", exact: true }).tap();
  await expect(name).toHaveValue("SYNTHETIC ANDROID REVIEW — TEST DATA");
  await expect(flag).toHaveValue("SYNTHETIC ANDROID FLAG");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
