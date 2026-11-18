/**
 * Admin page e2e tests (Vue SPA).
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { ADMIN_USERNAME } from "./e2e-constants.js";
import { api, navigateTo } from "./helpers.js";

test.describe("Admin page (authenticated admin)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await navigateTo(page, "Admin");
    await expect(page).toHaveURL(/\/admin/);
  });

  test("renders the administration heading and tabs", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Studio Administration" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Users" })).toBeVisible();
  });

  test("lists the seeded stub model", async ({ page }) => {
    await page.getByRole("tab", { name: "Image Models" }).click();
    await expect(page.getByRole("cell", { name: "Stub Model" })).toBeVisible();
  });

  test("shows the admin account in the users tab", async ({ page }) => {
    await page.getByRole("tab", { name: "Users" }).click();
    await expect(page.getByTestId("add-user")).toBeVisible();
    await expect(page.getByText(ADMIN_USERNAME).first()).toBeVisible();
  });

  test("deleting a model requires confirmation", async ({ page }) => {
    const name = `Disposable Model ${Date.now()}`;
    const created = await api(page, "POST", "/api/admin/models", {
      json: { name, provider: "stub", model_identifier: `stub-${Date.now()}`, is_active: false },
    });
    expect(created.status).toBeLessThan(300);

    await page.reload();
    await page.getByRole("tab", { name: "Image Models" }).click();
    const row = page.getByRole("row").filter({ hasText: name });
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: "Delete" }).click();
    const dialog = page.getByRole("dialog", { name: "Delete model" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: "Delete" }).click();
    await dialog.getByRole("button", { name: "Delete" }).click();
    await expect(row).toHaveCount(0);
  });
});
