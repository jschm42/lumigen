/**
 * Overlay stack e2e tests: dialog a11y, focus management, scroll lock,
 * stacked Escape handling and the mobile navigation.
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { bodyOverflow, ensureStubAsset, expectFocusInDialog, navigateTo } from "./helpers.js";

test.describe("Queue drawer", () => {
  test("is an accessible dialog that locks scroll and closes on Escape", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: /Queue/ }).click();

    const drawer = page.getByRole("dialog", { name: "Generation queue" });
    await expect(drawer).toBeVisible();
    await expect(drawer).toHaveAttribute("aria-modal", "true");
    expect(await bodyOverflow(page)).toBe("hidden");
    await expectFocusInDialog(page);

    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    expect(await bodyOverflow(page)).toBe("");
  });
});

test.describe("Modal", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await navigateTo(page, "Profiles");
  });

  test("is labelled, traps focus and returns it to the trigger", async ({ page }) => {
    const trigger = page.getByRole("button", { name: /New Profile/ });
    await trigger.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog).toHaveAttribute("aria-labelledby", /.+/);
    await expect(dialog.getByRole("button", { name: "Close dialog" })).toBeVisible();
    await expectFocusInDialog(page);

    for (let i = 0; i < 30; i += 1) await page.keyboard.press("Tab");
    await expectFocusInDialog(page);
    for (let i = 0; i < 5; i += 1) await page.keyboard.press("Shift+Tab");
    await expectFocusInDialog(page);

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
    expect(await bodyOverflow(page)).toBe("");
  });
});

test.describe("Stacked overlays", () => {
  test("Escape closes only the top-most dialog and keeps the scroll lock", async ({ page }) => {
    await page.goto("/");
    await ensureStubAsset(page);
    await navigateTo(page, "Gallery");

    await page.getByTestId("gallery-grid").locator("img").first().click();
    const dialogs = page.getByRole("dialog");
    await expect(dialogs).toHaveCount(1);

    await dialogs.first().getByRole("button", { name: /Delete/ }).last().click();
    await expect(dialogs).toHaveCount(2);

    await page.keyboard.press("Escape");
    await expect(dialogs).toHaveCount(1);
    expect(await bodyOverflow(page)).toBe("hidden");

    await page.keyboard.press("Escape");
    await expect(dialogs).toHaveCount(0);
    expect(await bodyOverflow(page)).toBe("");
  });
});

test.describe("Mobile navigation", () => {
  test.use({ viewport: { width: 375, height: 780 } });

  test("reaches every section below the md breakpoint", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByTestId("mobile-nav-toggle");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");

    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await page.locator("#mobile-nav").getByRole("link", { name: "Gallery" }).click();
    await expect(page).toHaveURL(/\/gallery/);
    await expect(page.locator("#mobile-nav")).toHaveCount(0);

    await toggle.click();
    await page.keyboard.press("Escape");
    await expect(page.locator("#mobile-nav")).toHaveCount(0);

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(375);
  });

  test("is hidden on desktop widths", async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 });
    await page.goto("/");
    await expect(page.getByTestId("mobile-nav-toggle")).toBeHidden();
  });
});

test.describe("Account menu", () => {
  test("supports keyboard navigation and returns focus on Escape", async ({ page }) => {
    await page.goto("/");
    const trigger = page.getByRole("button", { name: /Account menu/ });
    await expect(trigger).toHaveAttribute("aria-expanded", "false");

    await trigger.click();
    await expect(trigger).toHaveAttribute("aria-expanded", "true");
    const items = page.getByRole("menu").getByRole("menuitem");
    await expect(items.first()).toBeFocused();

    await page.keyboard.press("ArrowDown");
    await expect(items.nth(1)).toBeFocused();
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("ArrowUp");
    await expect(items.last()).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("closes on outside click and navigates via menu items", async ({ page }) => {
    await page.goto("/");
    const trigger = page.getByRole("button", { name: /Account menu/ });

    await trigger.click();
    await page.getByTestId("session-title").click();
    await expect(page.getByRole("menu")).toHaveCount(0);

    await trigger.click();
    await page.getByRole("menuitem", { name: "My Profile" }).click();
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByRole("menu")).toHaveCount(0);
  });
});
