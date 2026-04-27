/**
 * Admin page e2e tests.
 *
 * Verifies that the admin page is accessible to admins, renders the
 * expected sections, and that the static JS bundle is linked correctly.
 */

// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Admin page (authenticated admin)", () => {
  test("renders the admin page with a 200 response", async ({ page }) => {
    const response = await page.goto("/admin");
    expect(response?.status()).toBe(200);
  });

  test("has a page title that contains Admin", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveTitle(/Admin|Lumigen/);
  });

  test("loads the admin-page.js script", async ({ page }) => {
    /** @type {string[]} */
    const scriptsLoaded = [];
    page.on("request", (req) => scriptsLoaded.push(req.url()));

    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    const hasAdminScript = scriptsLoaded.some((url) =>
      url.includes("admin-page.js")
    );
    expect(hasAdminScript).toBe(true);
  });

  test("shows the providers / storage section", async ({ page }) => {
    await page.goto("/admin");

    /* At least one well-known admin section heading should be visible */
    const sectionHeading = page
      .locator("text=Provider")
      .or(page.locator("text=Storage"))
      .or(page.locator("text=Modell"))
      .or(page.locator("text=Model"))
      .or(page.locator("text=Benutzer"))
      .or(page.locator("text=User"));
    await expect(sectionHeading.first()).toBeVisible();
  });

  test("shows the users section when the users tab is active", async ({
    page,
  }) => {
    await page.goto("/admin?section=users");

    /* The users management section should contain a 'create user' element */
    const usersContent = page
      .locator("text=Benutzer")
      .or(page.locator("text=User"))
      .or(page.locator('input[name="username"]'));
    await expect(usersContent.first()).toBeVisible();
  });

  test("can save and reload enhancement prompt", async ({ page }) => {
    await page.goto("/admin?section=enhancement");
    const textarea = page.locator('textarea[name="default_enhancement_prompt"]');
    const testPrompt = `Test prompt ${Date.now()}`;
    await textarea.fill("");
    await textarea.fill(testPrompt);
    await page.click('button[type="submit"]');
    // Wait for reload and success message
    await expect(page.locator('text=Saved')).toBeVisible();
    // Reload page to ensure value is persisted
    await page.goto("/admin?section=enhancement");
    await expect(textarea).toHaveValue(testPrompt);
  });
});
