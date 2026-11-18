/**
 * Auth e2e tests – login page, invalid/valid credentials and logout (Vue SPA).
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { ADMIN_USERNAME, ADMIN_PASSWORD } from "./e2e-constants.js";

test.describe("Login page", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("redirects unauthenticated visitors to /login", async ({ page }) => {
    await page.goto("/gallery");
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows the login form", async ({ page }) => {
    await page.goto("/login");

    await expect(page.locator("#username")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Log in" })).toBeVisible();
  });

  test("shows an error for invalid credentials", async ({ page }) => {
    await page.goto("/login");

    await page.locator("#username").fill("wrong-user");
    await page.locator("#password").fill("wrong-password");
    await page.getByRole("button", { name: "Log in" }).click();

    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText("Invalid credentials")).toBeVisible();
  });

  test("logs in with valid credentials and lands on the studio", async ({ page }) => {
    await page.goto("/login");

    await page.locator("#username").fill(ADMIN_USERNAME);
    await page.locator("#password").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Log in" }).click();

    await expect(page).toHaveURL("/");
    await expect(page.getByTestId("session-title")).toBeVisible();
  });
});

test.describe("Logout", () => {
  test("signs out via the user menu and protects private routes", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Account menu/ }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();

    await expect(page).toHaveURL(/\/login/);

    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login/);
  });
});
