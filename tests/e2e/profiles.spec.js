/**
 * Profiles page e2e tests (Vue SPA): list, create dialog and delete confirmation.
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { E2E_PROFILE_NAME } from "./e2e-constants.js";
import { api, navigateTo } from "./helpers.js";

test.describe("Profiles page (authenticated)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await navigateTo(page, "Profiles");
    await expect(page).toHaveURL(/\/profiles/);
  });

  test("lists the seeded profile", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Profiles" })).toBeVisible();
    await expect(page.getByRole("heading", { name: E2E_PROFILE_NAME })).toBeVisible();
  });

  test("New Profile opens the editor dialog", async ({ page }) => {
    await page.getByRole("button", { name: /New Profile/ }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("delete asks for in-app confirmation and respects cancel", async ({ page }) => {
    const name = `Disposable ${Date.now()}`;
    const created = await api(page, "POST", "/api/profiles", { json: { name } });
    expect(created.status).toBeLessThan(300);
    await page.reload();

    /** @type {string[]} */
    const nativeDialogs = [];
    page.on("dialog", (dialog) => {
      nativeDialogs.push(dialog.message());
      dialog.dismiss();
    });

    const card = page.getByTestId("profile-card").filter({ has: page.getByRole("heading", { name, exact: true }) });
    const heading = page.getByRole("heading", { name, exact: true });

    await card.getByRole("button", { name: "Delete profile" }).click();
    const confirmDialog = page.getByRole("dialog", { name: "Delete profile" });
    await expect(confirmDialog).toBeVisible();
    await confirmDialog.getByRole("button", { name: "Cancel" }).click();
    await expect(confirmDialog).toBeHidden();
    await expect(heading).toBeVisible();

    await card.getByRole("button", { name: "Delete profile" }).click();
    await confirmDialog.getByRole("button", { name: "Delete" }).click();
    await expect(heading).toBeHidden();

    expect(nativeDialogs).toEqual([]);
  });
});
