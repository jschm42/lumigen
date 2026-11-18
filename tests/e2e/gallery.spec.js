/**
 * Gallery page e2e tests (Vue SPA).
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { ensureStubAsset, navigateTo } from "./helpers.js";

test.describe("Gallery page (authenticated)", () => {
  test("deep link renders the SPA with the filter bar", async ({ page }) => {
    const response = await page.goto("/gallery");
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle(/Lumigen/);
    await expect(page.getByTestId("gallery-search")).toBeVisible();
  });

  test("shows a stub-generated asset in the grid", async ({ page }) => {
    await page.goto("/");
    await ensureStubAsset(page);

    await navigateTo(page, "Gallery");
    await expect(page.getByTestId("gallery-grid")).toBeVisible();
    await expect(page.getByTestId("gallery-grid").locator("img").first()).toBeVisible();
  });

  test("search without matches shows the filtered empty state", async ({ page }) => {
    await page.goto("/gallery");
    await page.getByTestId("gallery-search").fill("zz-no-such-prompt-zz");

    await expect(page.getByText("No images match your filters")).toBeVisible();
    await page.getByRole("button", { name: "Reset filters" }).click();
    await expect(page.getByTestId("gallery-search")).toHaveValue("");
  });
});
