/**
 * Auth e2e tests – login page rendering, form validation, login and logout.
 *
 * These tests use the "chromium" project which starts with a saved admin
 * session.  The logout test clears that session and verifies the redirect
 * back to /login.
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { ADMIN_USERNAME, ADMIN_PASSWORD } from "./e2e-constants.js";

test.describe("Login page", () => {
  test("redirects unauthenticated requests to /login", async ({ page }) => {
    /* Use a fresh context (no stored auth) to test the redirect */
    await page.context().clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows the login form with username and password fields", async ({
    page,
  }) => {
    await page.context().clearCookies();
    await page.goto("/login");

    await expect(page.locator("#username")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("shows an error for invalid credentials", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/login");

    await page.locator("#username").fill("wrong-user");
    await page.locator("#password").fill("wrong-password");
    await page.locator('button[type="submit"]').click();

    /* The server re-renders the login page with an error message */
    await expect(page).toHaveURL(/\/login/);
    /* Error text is rendered inside a <div> on the login page */
    await expect(page.locator("text=Invalid credentials").or(page.locator("text=Ungültige"))).toBeVisible();
  });

  test("logs in with valid credentials and lands on the home page", async ({
    page,
  }) => {
    await page.context().clearCookies();
    await page.goto("/login");

    await page.locator("#username").fill(ADMIN_USERNAME);
    await page.locator("#password").fill(ADMIN_PASSWORD);
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL("/");
  });
});

test.describe("Logout", () => {
  test("logs out and redirects to /login", async ({ page }) => {
    /* Start from the home page (auth state is loaded automatically) */
    await page.goto("/");
    await expect(page).toHaveURL("/");

    await page.goto("/logout");
    await expect(page).toHaveURL(/\/login/);

    /* After logout /admin should redirect back to /login */
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login/);
  });
});
