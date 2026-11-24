/**
 * Agentic GIF animation e2e tests: composer controls and a full stub run.
 *
 * No reasoning model is configured in the e2e studio, so the planner falls back
 * to its generic plan; the stub provider accepts reference images.
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { api } from "./helpers.js";

/** @param {import("@playwright/test").Page} page */
async function stubModelId(page) {
  const models = await api(page, "GET", "/api/admin/models");
  const stub = (models.data || []).find((/** @type {any} */ m) => m.provider === "stub");
  expect(stub, "stub model seeded by auth.setup.js").toBeTruthy();
  expect(stub.capabilities).toContain("image_input");
  return String(stub.id);
}

/** @param {import("@playwright/test").Page} page */
async function openAgenticBar(page) {
  await page.goto("/");
  await expect(page.locator("#prompt_user")).toBeVisible();
  await page.getByRole("button", { name: "Agentic Mode" }).click();
  await expect(page.getByTestId("agentic-settings")).toBeVisible();
}

test.describe("Agentic GIF animation", () => {
  test("stub run produces frames and a GIF stack cover", async ({ page }) => {
    await page.goto("/");
    const modelId = await stubModelId(page);

    const submit = await api(page, "POST", "/api/generate", {
      form: {
        prompt: "a bouncing ball",
        model_config_id: modelId,
        is_agentic: "true",
        agentic_kind: "animation",
        min_images: "3",
        max_images: "3",
        animation_loop: "pingpong",
        animation_transparent: "false",
      },
    });
    expect(submit.status).toBe(200);
    const jobId = submit.data.job_id;

    await expect
      .poll(async () => (await api(page, "GET", `/api/jobs/${jobId}/status`)).data?.status, { timeout: 60_000 })
      .toBe("succeeded");

    const job = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
    expect(job.agentic_kind).toBe("animation");
    expect(job.agentic_step).toBe("completed");
    expect(job.agentic_plan.frames).toHaveLength(3);
    expect(job.assets).toHaveLength(4);

    const cover = job.assets.find((/** @type {any} */ a) => a.stack_order === 0);
    expect(cover.mime).toBe("image/gif");
    expect(cover.metadata.role).toBe("animation");
    expect(cover.metadata.loop).toBe("pingpong");
    const frames = job.assets.filter((/** @type {any} */ a) => a.stack_order > 0);
    expect(frames.map((/** @type {any} */ a) => a.mime)).toEqual(["image/png", "image/png", "image/png"]);
    expect(new Set(job.assets.map((/** @type {any} */ a) => a.stack_id)).size).toBe(1);

    const gif = await page.request.get(cover.image_url);
    expect(gif.ok()).toBeTruthy();
    expect((await gif.body()).subarray(0, 6).toString("ascii")).toBe("GIF89a");
  });

  test("animation request with an unsupported model is rejected", async ({ page }) => {
    await page.goto("/");
    const created = await api(page, "POST", "/api/admin/models", {
      json: { name: `Text-only ${Date.now()}`, provider: "stub", model_identifier: "stub-text-only" },
    });
    expect(created.status).toBeLessThan(300);
    const modelId = created.data.id;
    try {
      const update = await api(page, "PUT", `/api/admin/models/${modelId}`, { json: { supports_image_input: false } });
      expect(update.data.capabilities).not.toContain("image_input");

      const submit = await api(page, "POST", "/api/generate", {
        form: { prompt: "a spinning coin", model_config_id: String(modelId), is_agentic: "true", agentic_kind: "animation" },
      });
      expect(submit.status).toBe(422);
      expect(submit.data.detail).toContain("image input");
    } finally {
      await api(page, "DELETE", `/api/admin/models/${modelId}`);
    }
  });

  test("composer shows animation settings for image-input models", async ({ page }) => {
    await openAgenticBar(page);
    await expect(page.getByTestId("animation-settings")).toHaveCount(0);

    await page.getByRole("tab", { name: "Animation", exact: true }).click();
    const settings = page.getByTestId("animation-settings");
    await expect(settings).toBeVisible();
    await expect(settings.getByRole("combobox", { name: "Loop mode" })).toBeVisible();
    await expect(settings.getByRole("switch", { name: "Transparent background" })).toBeVisible();
    await expect(page.getByRole("spinbutton", { name: "Maximum frames" })).toBeVisible();
    await expect(page.locator("#prompt_user")).toHaveAttribute("placeholder", /Describe the animation/);

    // "Frames only" hides the settings that only apply to an assembled animation file.
    const output = settings.getByRole("combobox", { name: "Output" });
    await expect(output).toHaveValue("gif");
    await output.selectOption("none");
    await expect(settings.getByRole("combobox", { name: "Loop mode" })).toHaveCount(0);
    await expect(settings.getByRole("spinbutton", { name: "Frame duration in milliseconds" })).toHaveCount(0);
    await output.selectOption("webp");
    await expect(settings.getByRole("combobox", { name: "Loop mode" })).toBeVisible();

    await page.getByRole("tab", { name: "Image set" }).click();
    await expect(page.getByTestId("animation-settings")).toHaveCount(0);
  });

  for (const [output, expectedCoverMime, expectedCount] of /** @type {const} */ ([
    ["webp", "image/webp", 3],
    ["none", "image/png", 2],
  ])) {
    test(`output "${output}" produces the expected stack`, async ({ page }) => {
      await page.goto("/");
      const modelId = await stubModelId(page);
      const submit = await api(page, "POST", "/api/generate", {
        form: {
          prompt: `a waving flag (${output})`,
          model_config_id: modelId,
          is_agentic: "true",
          agentic_kind: "animation",
          min_images: "2",
          max_images: "2",
          animation_output: output,
        },
      });
      expect(submit.status).toBe(200);
      const jobId = submit.data.job_id;
      await expect
        .poll(async () => (await api(page, "GET", `/api/jobs/${jobId}/status`)).data?.status, { timeout: 60_000 })
        .toBe("succeeded");

      const job = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
      expect(job.animation.output).toBe(output);
      expect(job.assets).toHaveLength(expectedCount);
      const cover = job.assets.find((/** @type {any} */ a) => a.stack_order === 0);
      expect(cover.mime).toBe(expectedCoverMime);
    });
  }

  test("animation tab is disabled when the model has no image input", async ({ page }) => {
    await page.route("**/api/models/active", async (route) => {
      const response = await route.fetch();
      const models = await response.json();
      for (const model of models) {
        model.capabilities = (model.capabilities || []).filter((/** @type {string} */ c) => c !== "image_input");
      }
      await route.fulfill({ response, json: models });
    });

    await openAgenticBar(page);
    const tab = page.getByRole("tab", { name: "Animation", exact: true });
    await expect(tab).toBeDisabled();
    await expect(tab).toHaveAttribute("title", /does not support image input/);
  });
});
