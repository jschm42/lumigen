// @ts-check
import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright end-to-end test configuration.
 *
 * The webServer block starts Lumigen (scripts/e2e_server.py) against a
 * freshly wiped SQLite database in the OS temp dir so that tests never touch
 * your real data directory. Build the Vue SPA first: npm run build:frontend
 *
 * Run all e2e tests:
 *   npx playwright test
 *
 * Run with the interactive UI:
 *   npx playwright test --ui
 *
 * Run a single spec file:
 *   npx playwright test tests/e2e/auth.spec.js
 */

const E2E_PORT = 8765;
const BASE_URL = `http://127.0.0.1:${E2E_PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",

  /* Run test files sequentially so that shared auth state is not corrupted
     by concurrent sessions. Tests within a single file always run serially. */
  fullyParallel: false,

  /* Re-run failing tests once before reporting them as failures */
  retries: process.env.CI ? 1 : 0,

  /* All specs share one seeded database, so run them in a single worker. */
  workers: 1,

  /* Reporter: list for local dev, HTML report in CI */
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",

  use: {
    baseURL: BASE_URL,
    /* Capture trace on first retry to help debug flaky failures */
    trace: "on-first-retry",
    /* Keep screenshots on failure */
    screenshot: "only-on-failure",
  },

  projects: [
    /* Setup project – creates the admin user and saves the auth state once */
    {
      name: "setup",
      testMatch: /auth\.setup\.js/,
    },

    /* Chromium is the primary browser for e2e */
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        /* Reuse the admin session created by the setup project */
        storageState: "playwright/.auth/admin.json",
      },
      dependencies: ["setup"],
    },
  ],

  /* Start Lumigen against a freshly wiped, isolated data directory.
     Requires the SPA build in app/web/dist (npm run build:frontend). */
  webServer: {
    command: `python scripts/e2e_server.py --port ${E2E_PORT}`,
    url: `${BASE_URL}/login`,
    /* Never reuse a running server: every run must start from an empty database. */
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
