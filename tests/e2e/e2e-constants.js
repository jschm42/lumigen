/**
 * Shared constants used by both the setup project and spec files.
 *
 * Keeping credentials here avoids having spec files import from the
 * setup file (which Playwright rejects as a test importing a test).
 */

export const ADMIN_USERNAME = "e2e-admin";
export const ADMIN_PASSWORD = "E2eTestPass123!";
export const AUTH_STATE_PATH = "playwright/.auth/admin.json";
/** Profile seeded by auth.setup.js; specs must not delete it. */
export const E2E_PROFILE_NAME = "E2E Test Profile";
