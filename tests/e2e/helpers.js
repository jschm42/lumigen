/**
 * Shared helpers for the Lumigen e2e suite (Vue SPA).
 */

// @ts-check
import { expect } from "@playwright/test";

/**
 * Calls a JSON/form API endpoint from inside the page so the session cookie
 * and the CSRF double-submit token are sent exactly like the SPA does.
 *
 * @param {import("@playwright/test").Page} page
 * @param {string} method
 * @param {string} url
 * @param {{ json?: unknown, form?: Record<string, string> }} [body]
 * @returns {Promise<{ status: number, data: any }>}
 */
export async function api(page, method, url, body = {}) {
  return page.evaluate(
    async ({ method, url, body }) => {
      const match = document.cookie.match(/(^| )csrf_token=([^;]+)/);
      /** @type {Record<string, string>} */
      const headers = { "X-Requested-With": "XMLHttpRequest" };
      if (match) headers["X-CSRF-Token"] = decodeURIComponent(match[2]);

      /** @type {BodyInit | undefined} */
      let payload;
      if (body.form) {
        const formData = new FormData();
        for (const [key, value] of Object.entries(body.form)) formData.append(key, value);
        payload = formData;
      } else if (body.json !== undefined) {
        headers["Content-Type"] = "application/json";
        payload = JSON.stringify(body.json);
      }

      const response = await fetch(url, { method, headers, body: payload, credentials: "include" });
      let data = null;
      try {
        data = await response.json();
      } catch {
        /* non-JSON response */
      }
      return { status: response.status, data };
    },
    { method, url, body },
  );
}

/**
 * Navigates inside the SPA via the main navigation (works at every breakpoint).
 *
 * @param {import("@playwright/test").Page} page
 * @param {"Generate" | "Profiles" | "Gallery" | "Admin"} name
 */
export async function navigateTo(page, name) {
  const toggle = page.getByTestId("mobile-nav-toggle");
  if (await toggle.isVisible()) {
    await toggle.click();
    await page.locator("#mobile-nav").getByRole("link", { name }).click();
  } else {
    await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name }).click();
  }
}

/**
 * Returns the inline `overflow` style of <body> (the overlay scroll lock).
 *
 * @param {import("@playwright/test").Page} page
 */
export function bodyOverflow(page) {
  return page.evaluate(() => document.body.style.overflow);
}

/**
 * Asserts that keyboard focus currently sits inside an open dialog.
 *
 * @param {import("@playwright/test").Page} page
 */
export async function expectFocusInDialog(page) {
  await expect
    .poll(() => page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]')))
    .toBe(true);
}

/**
 * Ensures a finished stub generation with one asset exists and returns the asset count.
 *
 * @param {import("@playwright/test").Page} page
 */
export async function ensureStubAsset(page) {
  const models = await api(page, "GET", "/api/admin/models");
  const stub = (models.data || []).find((/** @type {any} */ m) => m.provider === "stub");
  expect(stub, "stub model seeded by auth.setup.js").toBeTruthy();

  const before = await api(page, "GET", "/api/assets?page_size=1");
  if ((before.data?.total ?? 0) > 0) return before.data.total;

  const generation = await api(page, "POST", "/api/generate", {
    form: { prompt: "e2e stub image", model_config_id: String(stub.id) },
  });
  expect(generation.status).toBeLessThan(300);

  await expect
    .poll(async () => (await api(page, "GET", "/api/assets?page_size=1")).data?.total ?? 0, {
      timeout: 20_000,
    })
    .toBeGreaterThan(0);
  return (await api(page, "GET", "/api/assets?page_size=1")).data.total;
}
