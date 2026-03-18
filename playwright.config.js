// @ts-check
import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright end-to-end test configuration.
 *
 * The webServer block starts the Lumigen development server against an
 * isolated SQLite database in /tmp so that tests never touch your real
 * data directory.
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

  /* Limit parallelism in CI to save resources */
  workers: process.env.CI ? 1 : undefined,

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

  /* Start the Lumigen server against an isolated test database */
  webServer: {
    command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${E2E_PORT}`,
    url: `${BASE_URL}/login`,
    reuseExistingServer: !process.env.CI,
    /* Isolated data directory – separate from your real data/ folder */
    env: {
      DATA_DIR: "/tmp/lumigen-e2e",
      DEFAULT_BASE_DIR: "/tmp/lumigen-e2e/images",
      SQLITE_PATH: "/tmp/lumigen-e2e/test.db",
      SESSION_HTTPS_ONLY: "false",
      SESSION_SECRET_KEY: "e2e-test-secret-key-not-for-production",
    },
  },
});
