/**
 * Generate studio e2e tests (Vue SPA): layout chrome and submit locking.
 */

// @ts-check
import { test, expect } from "@playwright/test";

const SUBMIT = 'button[title="Start generation (Enter)"]';

test.describe("Generate studio (authenticated)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#prompt_user")).toBeVisible();
  });

  test("renders session header, feed and prompt composer", async ({ page }) => {
    await expect(page).toHaveTitle(/Lumigen/);
    await expect(page.getByTestId("session-title")).toBeVisible();
    await expect(page.getByTestId("generation-feed")).toBeVisible();
  });

  test("main navigation offers all sections for admins", async ({ page }) => {
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    for (const name of ["Generate", "Profiles", "Gallery", "Admin"]) {
      await expect(nav.getByRole("link", { name })).toBeVisible();
    }
  });

  test("submit is disabled until a prompt is entered", async ({ page }) => {
    await expect(page.locator(SUBMIT)).toBeDisabled();
    await page.locator("#prompt_user").fill("a lighthouse in the fog");
    await expect(page.locator(SUBMIT)).toBeEnabled();
  });

  test("submit locks while the request is in flight and sends only once", async ({ page }) => {
    let requestCount = 0;
    /** @type {() => Promise<void>} */
    let release = async () => {};
    await page.route("**/api/generate", (route) => {
      requestCount += 1;
      release = () => route.fulfill({ status: 500, body: "{}" });
    });

    await page.locator("#prompt_user").fill("rapid click test");
    const submit = page.locator(SUBMIT);
    await submit.click();

    await expect(submit).toBeDisabled();
    await expect(submit).toContainText("Queuing...");
    await submit.click({ force: true });
    await submit.click({ force: true });
    expect(requestCount).toBe(1);

    await release();
  });

  test("submit unlocks again after a failed request", async ({ page }) => {
    await page.route("**/api/generate", (route) => route.fulfill({ status: 500, body: "{}" }));

    await page.locator("#prompt_user").fill("prompt for error unlock");
    await page.locator(SUBMIT).click();

    await expect(page.locator(SUBMIT)).toBeEnabled({ timeout: 5000 });
    await expect(page.locator("#prompt_user")).toHaveValue("prompt for error unlock");
  });
});
