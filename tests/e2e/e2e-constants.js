/**
 * Shared constants used by both the global-setup and spec files.
 *
 * Keeping credentials here avoids having spec files import from the
 * global-setup file (which Playwright rejects as a test importing a test).
 */

export const ADMIN_USERNAME = "e2e-admin";
export const ADMIN_PASSWORD = "E2eTestPass123!";
export const AUTH_STATE_PATH = "playwright/.auth/admin.json";
