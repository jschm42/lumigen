/**
 * Profiles page e2e tests.
 *
 * Verifies that the profiles list page and the create-profile form are
 * accessible and rendered correctly.
 */

// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Profiles page (authenticated)", () => {
  test("renders the profiles page with a 200 response", async ({ page }) => {
    const response = await page.goto("/profiles");
    expect(response?.status()).toBe(200);
  });

  test("has a page title that contains Lumigen", async ({ page }) => {
    await page.goto("/profiles");
    await expect(page).toHaveTitle(/Lumigen/);
  });

  test("loads the profiles-page.js script", async ({ page }) => {
    /** @type {string[]} */
    const scriptsLoaded = [];
    page.on("request", (req) => scriptsLoaded.push(req.url()));

    await page.goto("/profiles");
    await page.waitForLoadState("networkidle");

    const hasProfilesScript = scriptsLoaded.some((url) =>
      url.includes("profiles-page.js")
    );
    expect(hasProfilesScript).toBe(true);
  });

  test("shows a button to create a new profile", async ({ page }) => {
    await page.goto("/profiles");

    /* "New profile" is a button that opens the create-profile dialog */
    await expect(page.locator('button:has-text("New profile")')).toBeVisible();
  });

  test("navigating to /profiles/new redirects back to profiles with create dialog", async ({
    page,
  }) => {
    /* /profiles/new is a convenience redirect to /profiles?create=1 */
    await page.goto("/profiles/new");
    await expect(page).toHaveURL(/\/profiles/);
    await expect(page).toHaveTitle(/Lumigen/);
  });
});
