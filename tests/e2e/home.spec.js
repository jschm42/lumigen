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

  test.describe("generation form locking", () => {
    test("submit button becomes disabled immediately on form submission", async ({
      page,
    }) => {
      /* Intercept the /generate endpoint and hold the response so we can
         observe the locked state while the request is in flight. */
      let resolveRequest;
      await page.route("**/generate", (route) => {
        resolveRequest = () => route.continue();
      });

      await page.goto("/");
      await page.locator("#prompt_user").fill("test prompt for locking");

      const submitBtn = page.locator('[data-generate-submit]');
      await expect(submitBtn).not.toBeDisabled();

      await submitBtn.click();

      /* The button must be disabled immediately after the click */
      await expect(submitBtn).toBeDisabled();

      /* Unblock the request so the page can clean up */
      if (resolveRequest) resolveRequest();
    });

    test("prompt textarea becomes readonly while generation is in flight", async ({
      page,
    }) => {
      let resolveRequest;
      await page.route("**/generate", (route) => {
        resolveRequest = () => route.continue();
      });

      await page.goto("/");
      const textarea = page.locator("#prompt_user");
      await textarea.fill("test prompt for readonly check");

      await page.locator('[data-generate-submit]').click();

      /* The textarea must be readonly while the request is in flight */
      await expect(textarea).toHaveAttribute("readonly", "");

      if (resolveRequest) resolveRequest();
    });

    test("rapid repeated clicks result in only one generation request", async ({
      page,
    }) => {
      let requestCount = 0;
      await page.route("**/generate", (route) => {
        requestCount += 1;
        route.continue();
      });

      await page.goto("/");
      await page.locator("#prompt_user").fill("rapid click test");

      const submitBtn = page.locator('[data-generate-submit]');
      /* Click the button three times in quick succession */
      await submitBtn.click();
      await submitBtn.click({ force: true });
      await submitBtn.click({ force: true });

      /* Wait briefly for any requests to be sent */
      await page.waitForTimeout(300);

      expect(requestCount).toBe(1);
    });

    test("submit button and textarea are unlocked after a failed request", async ({
      page,
    }) => {
      await page.route("**/generate", (route) =>
        route.fulfill({ status: 500, body: "error" })
      );

      await page.goto("/");
      const textarea = page.locator("#prompt_user");
      await textarea.fill("test prompt for error unlock");

      const submitBtn = page.locator('[data-generate-submit]');
      await submitBtn.click();

      /* After the (failed) request completes the form must unlock */
      await expect(submitBtn).not.toBeDisabled({ timeout: 5000 });
      await expect(textarea).not.toHaveAttribute("readonly", "");
    });
  });
});
