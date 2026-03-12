/**
 * Home / Generate page e2e tests.
 *
 * Verifies that the main generation UI is accessible after login and that
 * the core structural elements are present.
 */

// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Home page (authenticated)", () => {
  test("renders the generate page with its heading", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL("/");

    /* The page title should contain the app name */
    await expect(page).toHaveTitle(/Lumigen/);
  });

  test("shows the prompt input area", async ({ page }) => {
    await page.goto("/");

    /* The generation page contains a textarea with id="prompt_user" */
    await expect(page.locator("#prompt_user")).toBeVisible();
  });

  test("shows a generate / submit button", async ({ page }) => {
    await page.goto("/");

    /* Submit button has title="Generate" */
    await expect(page.locator('button[title="Generate"]')).toBeVisible();
  });

  test("navigation links to gallery and admin are present", async ({
    page,
  }) => {
    await page.goto("/");

    /* Sidebar workspace nav links to Gallery and Admin */
    await expect(
      page.locator('[data-workspace-nav][data-workspace-view="gallery"]')
    ).toBeVisible();
    await expect(
      page.locator('[data-workspace-nav][data-workspace-view="admin"]')
    ).toBeVisible();
  });
});
