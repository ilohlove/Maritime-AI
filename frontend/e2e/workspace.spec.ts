import { test, expect } from "@playwright/test";
// Run against an isolated, migrated SQLite backend; see README.
test("create, edit and reload real persisted profile on desktop and mobile", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Ship Profile", exact: true }).click();
  await page
    .getByLabel("Vessel Name", { exact: true })
    .fill("SYNTHETIC E2E VESSEL");
  await page.getByLabel("Length Overall (m)", { exact: true }).fill("123.456");
  await page
    .getByLabel("Length Between Perpendiculars (m)", { exact: true })
    .fill("120.000");
  await page
    .getByRole("button", { name: /Create ship profile|Save changes/ })
    .click();
  await expect(page.getByRole("status")).toHaveText(
    "Ship profile saved locally.",
  );
  await page.getByLabel("Flag", { exact: true }).fill("SYNTHETIC FLAG");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "Ship profile saved locally.",
  );
  await page.reload();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "SYNTHETIC E2E VESSEL" }),
  ).toBeVisible();
  await expect(page.getByText("SYNTHETIC FLAG", { exact: true })).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("dashboard-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Ship Profile", exact: true }).click();
  await expect(page.getByLabel("Vessel Name", { exact: true })).toHaveValue(
    "SYNTHETIC E2E VESSEL",
  );
  await page.screenshot({
    path: test.info().outputPath("ship-profile-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
