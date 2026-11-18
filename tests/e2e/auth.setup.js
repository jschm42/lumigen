/**
 * Authentication setup – runs once as the Playwright "setup" project before
 * all other test projects. The e2e server always starts with an empty
 * database (scripts/e2e_server.py), so this:
 *
 * 1. Creates the first admin user via the SPA onboarding form.
 * 2. Seeds a stub provider key + stub model config (no real API calls) and a
 *    test profile through the JSON API.
 * 3. Saves the authenticated browser session to playwright/.auth/admin.json
 *    so every spec can reuse it.
 */

// @ts-check
import { test as setup, expect } from "@playwright/test";
import { ADMIN_USERNAME, ADMIN_PASSWORD, AUTH_STATE_PATH, E2E_PROFILE_NAME } from "./e2e-constants.js";
import { api } from "./helpers.js";

setup("onboard admin, seed stub model + profile and save auth state", async ({ page }) => {
  /* 1. Onboarding (fresh database redirects every route to /onboarding). */
  await page.goto("/");
  await expect(page).toHaveURL(/\/onboarding/);

  await page.locator("#admin-username").fill(ADMIN_USERNAME);
  await page.locator("#admin-email").fill("e2e-admin@example.test");
  await page.locator("#admin-password").fill(ADMIN_PASSWORD);
  await page.locator("#admin-confirm-password").fill(ADMIN_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL("/");

  /* 2. Seed fixtures through the JSON API. */
  const key = await api(page, "POST", "/api/admin/providers/stub", { json: { api_key: "e2e-stub-key" } });
  expect(key.status, "stub provider key").toBeLessThan(300);

  const model = await api(page, "POST", "/api/admin/models", {
    json: {
      name: "Stub Model",
      provider: "stub",
      model_identifier: "stub-default",
      is_active: true,
      is_default: true,
    },
  });
  expect(model.status, "stub model config").toBeLessThan(300);

  const profile = await api(page, "POST", "/api/profiles", { json: { name: E2E_PROFILE_NAME } });
  expect(profile.status, "test profile").toBeLessThan(300);

  /* 3. Persist the authenticated session for all specs. */
  await page.context().storageState({ path: AUTH_STATE_PATH });
});
