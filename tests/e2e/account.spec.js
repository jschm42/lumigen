/**
 * Account e2e tests – sidebar account footer, profile page and the
 * "forgot password" flow.
 *
 * Uses the saved admin session from auth.setup.js; guest tests clear cookies.
 */

// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Sidebar account footer", () => {
  test("offers profile, credits and logout in the generate sidebar", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("lumigen_generate_sidebar_collapsed", "0");
    });
    await page.goto("/");

    const footer = page.getByTestId("session-sidebar").getByTestId("user-nav-footer");
    await expect(footer).toBeVisible();
    await expect(footer.getByTestId("nav-profile")).toBeVisible();
    await expect(footer.getByTestId("nav-credits")).toBeVisible();
    await expect(footer.getByTestId("nav-logout")).toBeVisible();

    await footer.getByTestId("nav-profile").click();
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.locator("#account-email")).toBeVisible();
    await expect(page.locator("#account-current-password")).toBeVisible();
  });

  test("keeps account actions reachable when the sidebar is collapsed", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("lumigen_generate_sidebar_collapsed", "0");
    });
    await page.goto("/");
    await page.getByTestId("sidebar-collapse").click();

    const rail = page.getByTestId("session-sidebar-collapsed");
    await expect(rail).toBeVisible();
    await expect(rail.getByTestId("nav-logout")).toBeVisible();
  });
});

test.describe("Forgot password", () => {
  test("login page links to the reset request form", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/login");

    await page.getByTestId("forgot-password-link").click();
    await expect(page).toHaveURL(/\/forgot-password$/);

    await page.locator("#identifier").fill("someone-who-does-not-exist");
    await page.locator('button[type="submit"]').click();
    await expect(page.getByTestId("forgot-password-success")).toBeVisible();
  });

  test("an invalid reset token shows an error state", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/reset-password?token=invalid-token");
    await expect(page.locator("text=already used or has expired")).toBeVisible();
  });
});
