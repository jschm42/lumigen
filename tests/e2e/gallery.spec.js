/**
 * Gallery page e2e tests.
 *
 * Verifies that the gallery page is accessible and renders the expected
 * chrome (navigation, page title, empty-state message when there are no
 * assets in the test database).
 */

// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Gallery page (authenticated)", () => {
  test("renders the gallery page with a 200 response", async ({ page }) => {
    const response = await page.goto("/gallery");
    expect(response?.status()).toBe(200);
  });

  test("has a page title that contains Lumigen", async ({ page }) => {
    await page.goto("/gallery");
    await expect(page).toHaveTitle(/Lumigen/);
  });

  test("shows an empty-state message when no assets exist", async ({
    page,
  }) => {
    await page.goto("/gallery");

    /* The gallery renders this placeholder when the asset list is empty */
    await expect(
      page.locator("text=No assets found for current filters.")
    ).toBeVisible();
  });

  test("loads the gallery-page.js script", async ({ page }) => {
    /** @type {string[]} */
    const scriptsLoaded = [];
    page.on("request", (req) => scriptsLoaded.push(req.url()));

    await page.goto("/gallery");
    await page.waitForLoadState("networkidle");

    const hasGalleryScript = scriptsLoaded.some((url) =>
      url.includes("gallery-page.js")
    );
    expect(hasGalleryScript).toBe(true);
  });
});
