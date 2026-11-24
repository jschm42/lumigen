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

/**
 * Submits a stub animation and waits until it has succeeded.
 *
 * @param {import("@playwright/test").Page} page
 * @param {Record<string, string>} form
 */
async function runAnimation(page, form) {
  const modelId = await stubModelId(page);
  const submit = await api(page, "POST", "/api/generate", {
    form: { model_config_id: modelId, is_agentic: "true", agentic_kind: "animation", ...form },
  });
  expect(submit.status).toBe(200);
  const jobId = submit.data.job_id;
  await expect
    .poll(async () => (await api(page, "GET", `/api/jobs/${jobId}/status`)).data?.status, { timeout: 60_000 })
    .toBe("succeeded");
  return jobId;
}

/** @param {any} job */
function framesOf(job) {
  return job.assets
    .filter((/** @type {any} */ a) => a.metadata.role === "frame")
    .sort((/** @type {any} */ a, /** @type {any} */ b) => a.stack_order - b.stack_order);
}

/** @param {any} job */
function coverOf(job) {
  return job.assets.find((/** @type {any} */ a) => a.metadata.role === "animation");
}

test.describe("Agentic animation frame editing", () => {
  test("removing a frame rebuilds the animation without it", async ({ page }) => {
    await page.goto("/");
    const jobId = await runAnimation(page, { prompt: "frame removal", min_images: "4", max_images: "4" });
    const before = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
    const removed = framesOf(before)[1];

    const res = await api(page, "DELETE", `/api/jobs/${jobId}/frames/${removed.id}`);
    expect(res.status).toBe(200);
    const frames = framesOf(res.data);
    expect(frames).toHaveLength(3);
    expect(frames.map((/** @type {any} */ f) => f.id)).not.toContain(removed.id);
    expect(frames.map((/** @type {any} */ f) => f.stack_order)).toEqual([1, 2, 3]);
    const cover = coverOf(res.data);
    expect(cover.id).not.toBe(coverOf(before).id); // new asset → no stale cached image
    expect(cover.stack_order).toBe(0);
    expect(cover.metadata.frame_count).toBe(3);
    expect(cover.metadata.frame_asset_ids).toEqual(frames.map((/** @type {any} */ f) => f.id));
    expect((await page.request.get(removed.image_url)).status()).toBe(404);
  });

  test("an animation keeps at least two frames", async ({ page }) => {
    await page.goto("/");
    const jobId = await runAnimation(page, { prompt: "two frames only", min_images: "2", max_images: "2" });
    const job = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
    const res = await api(page, "DELETE", `/api/jobs/${jobId}/frames/${framesOf(job)[0].id}`);
    expect(res.status).toBe(400);
    expect(res.data.detail).toContain("at least two frames");
  });

  test("regenerating a frame replaces it in place and rebuilds the animation", async ({ page }) => {
    await page.goto("/");
    const jobId = await runAnimation(page, {
      prompt: "frame regeneration",
      min_images: "3",
      max_images: "3",
      animation_output: "webp",
    });
    const before = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
    const target = framesOf(before)[1];

    const res = await api(page, "POST", `/api/jobs/${jobId}/frames/${target.id}/regenerate`);
    expect(res.status).toBe(200);
    expect(res.data.status).toBe("running");
    expect(res.data.agentic_step).toBe("regenerating");

    await expect
      .poll(async () => (await api(page, "GET", `/api/jobs/${jobId}/status`)).data?.status, { timeout: 60_000 })
      .toBe("succeeded");
    const after = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
    expect(after.edit_error).toBeNull();
    const frames = framesOf(after);
    expect(frames).toHaveLength(3);
    const replacement = frames[1];
    expect(replacement.id).not.toBe(target.id);
    expect(replacement.metadata.frame_index).toBe(target.metadata.frame_index);
    expect(replacement.metadata.regenerated).toBe(1);
    expect(coverOf(after).mime).toBe("image/webp");
    expect(coverOf(after).metadata.frame_asset_ids).toContain(replacement.id);
  });

  test("frame actions in the generation card remove and regenerate frames", async ({ page }) => {
    await openAgenticBar(page);
    await page.getByRole("tab", { name: "Animation", exact: true }).click();
    await page.getByRole("spinbutton", { name: "Minimum frames" }).fill("3");
    await page.getByRole("spinbutton", { name: "Maximum frames" }).fill("3");
    await page.locator("#prompt_user").fill("ui frame editing");
    await page.locator('button[title="Start generation (Enter)"]').click();

    const card = page.locator('article[data-status="succeeded"]', { hasText: "ui frame editing" }).last();
    await expect(card.getByTestId("frame-actions")).toHaveCount(3, { timeout: 60_000 });

    // Remove frame 2 (with in-app confirmation) → two frames remain, removal is then blocked.
    await card.getByRole("button", { name: "Remove Frame 2" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Remove" }).click();
    await expect(card.getByTestId("frame-actions")).toHaveCount(2);
    await expect(card.getByRole("button", { name: "An animation needs at least two frames" }).first()).toBeDisabled();

    // Regenerate frame 1 → runs in the background, card returns to succeeded with two frames.
    await card.getByRole("button", { name: "Regenerate Frame 1" }).click();
    await expect(page.getByText("Frame regenerated, animation rebuilt.")).toBeVisible({ timeout: 60_000 });
    await expect(card.getByTestId("frame-actions")).toHaveCount(2);
  });

  test("frame edits are rejected for non-animation generations", async ({ page }) => {
    await page.goto("/");
    const modelId = await stubModelId(page);
    const submit = await api(page, "POST", "/api/generate", { form: { prompt: "plain image", model_config_id: modelId } });
    const jobId = submit.data.job_id;
    await expect
      .poll(async () => (await api(page, "GET", `/api/jobs/${jobId}/status`)).data?.status, { timeout: 30_000 })
      .toBe("succeeded");
    const job = (await api(page, "GET", `/api/jobs/${jobId}/status`)).data;
    const res = await api(page, "POST", `/api/jobs/${jobId}/frames/${job.assets[0].id}/regenerate`);
    expect(res.status).toBe(400);
  });
});

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
