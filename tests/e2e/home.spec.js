/**
 * Home / Generate page e2e tests.
 *
 * Verifies that the main generation UI is accessible after login and that
 * the core structural elements are present.
 */

// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Home page (authenticated)", () => {
  test("renders the generate page with its heading", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL("/");

    /* The page title should contain the app name */
    await expect(page).toHaveTitle(/Lumigen/);
  });

  test("shows the prompt input area", async ({ page }) => {
    await page.goto("/");

    /* The generation page contains a textarea with id="prompt_user" */
    await expect(page.locator("#prompt_user")).toBeVisible();
  });

  test("shows a generate / submit button", async ({ page }) => {
    await page.goto("/");

    /* Submit button has title="Generate" */
    await expect(page.locator('button[title="Generate"]')).toBeVisible();
  });

  test("navigation links to gallery and admin are present", async ({
    page,
  }) => {
    await page.goto("/");

    /* Sidebar workspace nav links to Gallery and Admin */
    await expect(
      page.locator('[data-workspace-nav][data-workspace-view="gallery"]')
    ).toBeVisible();
    await expect(
      page.locator('[data-workspace-nav][data-workspace-view="admin"]')
    ).toBeVisible();
  });

  test.describe("generation form locking", () => {
    test("submit button becomes disabled immediately on form submission", async ({
      page,
    }) => {
      /* Intercept the /generate endpoint and hold the response so we can
         observe the locked state while the request is in flight. */
      let resolveRequest;
      await page.route("**/generate", (route) => {
        resolveRequest = () => route.continue();
      });

      await page.goto("/");
      await page.locator("#prompt_user").fill("test prompt for locking");

      const submitBtn = page.locator('[data-generate-submit]');
      await expect(submitBtn).not.toBeDisabled();

      await submitBtn.click();

      /* The button must be disabled immediately after the click */
      await expect(submitBtn).toBeDisabled();

      /* Unblock the request so the page can clean up */
      if (resolveRequest) resolveRequest();
    });

    test("prompt textarea becomes readonly while generation is in flight", async ({
      page,
    }) => {
      let resolveRequest;
      await page.route("**/generate", (route) => {
        resolveRequest = () => route.continue();
      });

      await page.goto("/");
      const textarea = page.locator("#prompt_user");
      await textarea.fill("test prompt for readonly check");

      await page.locator('[data-generate-submit]').click();

      /* The textarea must be readonly while the request is in flight */
      await expect(textarea).toHaveAttribute("readonly", "");

      if (resolveRequest) resolveRequest();
    });

    test("rapid repeated clicks result in only one generation request", async ({
      page,
    }) => {
      let requestCount = 0;
      await page.route("**/generate", (route) => {
        requestCount += 1;
        route.continue();
      });

      await page.goto("/");
      await page.locator("#prompt_user").fill("rapid click test");

      const submitBtn = page.locator('[data-generate-submit]');
      /* Click the button three times in quick succession */
      await submitBtn.click();
      await submitBtn.click({ force: true });
      await submitBtn.click({ force: true });

      /* Wait briefly for any requests to be sent */
      await page.waitForTimeout(300);

      expect(requestCount).toBe(1);
    });

    test("submit button and textarea are unlocked after a failed request", async ({
      page,
    }) => {
      await page.route("**/generate", (route) =>
        route.fulfill({ status: 500, body: "error" })
      );

      await page.goto("/");
      const textarea = page.locator("#prompt_user");
      await textarea.fill("test prompt for error unlock");

      const submitBtn = page.locator('[data-generate-submit]');
      await submitBtn.click();

      /* After the (failed) request completes the form must unlock */
      await expect(submitBtn).not.toBeDisabled({ timeout: 5000 });
      await expect(textarea).not.toHaveAttribute("readonly", "");
    });
  });

  test.describe("Re-Generate hover button", () => {
    test("Re-Generate button fills prompt textarea and submits form on click", async ({
      page,
    }) => {
      const testPrompt = "a breathtaking mountain landscape at dawn";

      /* Intercept generate requests so we can observe submissions */
      let generateCallCount = 0;
      await page.route("**/generate", (route) => {
        generateCallCount += 1;
        route.fulfill({ status: 200, body: "" });
      });

      await page.goto("/");

      /* Inject a fake chat generation item that includes the Re-Generate button */
      await page.evaluate((prompt) => {
        const chatHistory = document.getElementById("chat-history");
        if (!chatHistory) return;
        const div = document.createElement("div");
        div.className = "chat-generation space-y-3";
        div.setAttribute("id", "chat-generation-test");
        div.innerHTML =
          '<div class="flex justify-end">' +
          '<article class="group max-w-[90%] rounded-2xl border border-sky-300/40 bg-sky-100/80 px-4 py-3 text-sm">' +
          '<p class="whitespace-pre-wrap">' + prompt + "</p>" +
          '<div class="mt-2 flex justify-end">' +
          '<button type="button" data-regenerate-prompt="' + prompt + '" ' +
          'aria-label="Re-Generate with this prompt" title="Re-Generate" ' +
          'class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold">' +
          "Re-Generate</button>" +
          "</div>" +
          "</article>" +
          "</div>";
        chatHistory.appendChild(div);
      }, testPrompt);

      /* Click the Re-Generate button */
      const regenBtn = page.locator('[data-regenerate-prompt]');
      await expect(regenBtn).toBeVisible();
      await regenBtn.click();

      /* The prompt textarea must be populated with the original prompt */
      await expect(page.locator("#prompt_user")).toHaveValue(testPrompt);

      /* The form must have been submitted (generate endpoint called) */
      await expect(page.locator('[data-generate-submit]')).toBeDisabled({ timeout: 3000 });
      expect(generateCallCount).toBeGreaterThan(0);
    });

    test("Re-Generate button is hidden by default and visible on hover", async ({
      page,
    }) => {
      const testPrompt = "futuristic cityscape at night";

      await page.goto("/");

      /* Inject a fake chat item with the same hover-button markup used in the template */
      await page.evaluate((prompt) => {
        const chatHistory = document.getElementById("chat-history");
        if (!chatHistory) return;
        const div = document.createElement("div");
        div.className = "chat-generation space-y-3";
        div.innerHTML =
          '<div class="flex justify-end">' +
          '<article class="group max-w-[90%] rounded-2xl px-4 py-3 text-sm">' +
          '<p class="whitespace-pre-wrap">' + prompt + "</p>" +
          '<div class="mt-2 flex justify-end opacity-0 transition-opacity group-hover:opacity-100">' +
          '<button type="button" data-regenerate-prompt="' + prompt + '" ' +
          'aria-label="Re-Generate with this prompt" title="Re-Generate" ' +
          'class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold">' +
          "Re-Generate</button>" +
          "</div>" +
          "</article>" +
          "</div>";
        chatHistory.appendChild(div);
      }, testPrompt);

      const article = page.locator(".chat-generation article").last();
      const buttonWrapper = article.locator(".opacity-0");

      /* Before hover the wrapper has opacity-0 */
      await expect(buttonWrapper).toHaveClass(/opacity-0/);

      /* After hovering the article, Tailwind group-hover removes opacity-0 */
      await article.hover();
      await expect(buttonWrapper).not.toHaveClass(/opacity-0/);
    });
  });
});

