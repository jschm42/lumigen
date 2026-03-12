/**
 * Authentication setup – runs once as a Playwright "setup" project before
 * all other test projects.
 *
 * 1. Creates the first admin user via the onboarding form (shown when the
 *    database has no users).
 * 2. Creates a stub model config so that profiles can be created.
 * 3. Creates a test profile so the generate page shows the prompt input.
 * 4. Saves the authenticated browser session to playwright/.auth/admin.json
 *    so every test project can reuse it without going through login again.
 */

// @ts-check
import { test as setup, expect } from "@playwright/test";
import { ADMIN_USERNAME, ADMIN_PASSWORD, AUTH_STATE_PATH } from "./e2e-constants.js";

setup("create admin account, model config, profile and save auth state", async ({ page }) => {
  /* ------------------------------------------------------------------
   * 1. Log in (or complete onboarding on a fresh database).
   * ------------------------------------------------------------------ */
  await page.goto("/login");
  await expect(page.locator("form")).toBeVisible();

  await page.locator("#username").fill(ADMIN_USERNAME);
  await page.locator("#password").fill(ADMIN_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL("/");

  /* ------------------------------------------------------------------
   * 2. Create a stub model config via the admin page.
   *    The stub provider never calls a real API, so no API key is needed.
   * ------------------------------------------------------------------ */
  await page.goto("/admin?section=models");

  const csrfMeta = await page.locator('meta[name="csrf-token"]').getAttribute("content");
  expect(csrfMeta).toBeTruthy();

  const modelConfigResponse = await page.request.post("/admin/model-configs", {
    form: {
      name: "Stub Model",
      provider: "stub",
      model: "stub-default",
      csrf_token: csrfMeta ?? "",
    },
  });
  /* Server redirects on success */
  expect([200, 303]).toContain(modelConfigResponse.status());

  /* ------------------------------------------------------------------
   * 3. Fetch the created model config ID from the profile create form.
   * ------------------------------------------------------------------ */
  await page.goto("/profiles/new");
  /* /profiles/new redirects to /profiles?create=1; select is in the DOM
     even when the create-profile dialog is hidden */
  const firstOption = await page
    .locator('select[name="model_config_id"] option:not([value=""])')
    .first()
    .getAttribute("value");
  const modelConfigId = firstOption ?? null;
  expect(modelConfigId).toBeTruthy();

  /* ------------------------------------------------------------------
   * 4. Create a test profile using the stub model config.
   * ------------------------------------------------------------------ */
  await page.goto("/profiles");
  const profileCsrf = await page.locator('meta[name="csrf-token"]').getAttribute("content");
  expect(profileCsrf).toBeTruthy();

  const profileResponse = await page.request.post("/profiles", {
    form: {
      name: "E2E Test Profile",
      model_config_id: modelConfigId ?? "",
      csrf_token: profileCsrf ?? "",
    },
  });
  expect([200, 303]).toContain(profileResponse.status());

  /* ------------------------------------------------------------------
   * 5. Persist the authenticated session for all test projects.
   * ------------------------------------------------------------------ */
  await page.context().storageState({ path: AUTH_STATE_PATH });
});
