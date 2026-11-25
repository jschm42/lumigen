/**
 * Custom endpoint e2e tests: OpenAI-compatible APIs and ComfyUI servers.
 *
 * A fake server (fake-endpoints.js) stands in for LocalAI/ComfyUI, so the whole
 * path is exercised: admin UI -> connection test -> model discovery -> generation
 * through the real backend adapters -> asset in the gallery.
 */

// @ts-check
import { test, expect } from "@playwright/test";
import { api, navigateTo } from "./helpers.js";
import { startFakeEndpoints } from "./fake-endpoints.js";

/** @type {Awaited<ReturnType<typeof startFakeEndpoints>>} */
let fake;

test.beforeAll(async () => {
  fake = await startFakeEndpoints();
});

test.afterAll(async () => {
  await fake?.close();
});

/**
 * @param {import("@playwright/test").Page} page
 */
async function openEndpointsTab(page) {
  await page.goto("/");
  await navigateTo(page, "Admin");
  await page.getByRole("tab", { name: "Endpoints" }).click();
}

/**
 * Submit a generation for a model config and wait until it produced an asset.
 *
 * @param {import("@playwright/test").Page} page
 * @param {number} modelConfigId
 * @param {string} prompt
 */
async function generateAndWait(page, modelConfigId, prompt) {
  const before = (await api(page, "GET", "/api/assets?page_size=1")).data?.total ?? 0;
  const submitted = await api(page, "POST", "/api/generate", {
    form: { prompt, model_config_id: String(modelConfigId), width: "512", height: "512" },
  });
  expect(submitted.status).toBeLessThan(300);
  await expect
    .poll(async () => (await api(page, "GET", "/api/assets?page_size=1")).data?.total ?? 0, { timeout: 20_000 })
    .toBeGreaterThan(before);
}

test.describe.serial("OpenAI-compatible endpoint", () => {
  test("create endpoint via UI, test connection and add a discovered model", async ({ page }) => {
    await openEndpointsTab(page);
    await page.getByTestId("add-endpoint").click();

    const dialog = page.getByRole("dialog", { name: "Add Endpoint" });
    await dialog.getByLabel("Name").fill("Fake LocalAI");
    await dialog.getByLabel("Base URL").fill(`${fake.url}/v1`);
    await dialog.getByLabel("API Key (optional)").fill("sk-e2e");
    await dialog.getByTestId("test-endpoint").click();
    await expect(dialog.getByRole("status")).toContainText("Connected. 2 models available.");
    await dialog.getByRole("button", { name: "Save" }).click();

    const row = page.getByRole("row").filter({ hasText: "Fake LocalAI" });
    await expect(row).toContainText("OpenAI-compatible API");
    await expect(row).toContainText("Stored");

    await page.getByRole("tab", { name: "Image Models" }).click();
    await page.getByRole("button", { name: "Add Model" }).click();
    const editor = page.getByRole("dialog", { name: "Add New Model" });
    await editor.getByLabel("Provider").selectOption("openai_compatible");
    await expect(editor.getByLabel("Endpoint")).toHaveValue(/\d+/); // single endpoint is preselected
    await editor.getByTestId("load-endpoint-models").click();
    await editor.getByRole("option", { name: "fake-flux" }).click();
    await expect(editor.getByLabel("Model Identifier")).toHaveValue("fake-flux");
    await editor.getByLabel("Display Name").fill("Fake Flux (LocalAI)");
    await editor.getByRole("button", { name: "Save" }).click();

    await expect(page.getByRole("row").filter({ hasText: "Fake Flux (LocalAI)" })).toContainText("Fake LocalAI");
  });

  test("generates through the endpoint with the stored key", async ({ page }) => {
    await page.goto("/");
    const models = (await api(page, "GET", "/api/admin/models")).data;
    const model = models.find((/** @type {any} */ m) => m.name === "Fake Flux (LocalAI)");
    expect(model?.endpoint_name).toBe("Fake LocalAI");

    fake.requests.length = 0;
    await generateAndWait(page, model.id, "a fake lighthouse");

    const call = fake.requests.find((r) => r.path === "/v1/images/generations");
    expect(call?.headers.authorization).toBe("Bearer sk-e2e");
    expect(call?.body).toMatchObject({
      model: "fake-flux",
      prompt: expect.stringContaining("a fake lighthouse"),
      size: "512x512",
      response_format: "b64_json",
    });
  });
});

test.describe.serial("ComfyUI endpoint", () => {
  test("rejects UI-format workflows and runs a custom API workflow", async ({ page }) => {
    await page.goto("/");
    const endpoint = await api(page, "POST", "/api/admin/endpoints", {
      json: { name: "Fake ComfyUI", kind: "comfyui", base_url: fake.url },
    });
    expect(endpoint.status).toBeLessThan(300);

    await navigateTo(page, "Admin");
    await page.getByRole("tab", { name: "Image Models" }).click();
    await page.getByRole("button", { name: "Add Model" }).click();
    const editor = page.getByRole("dialog", { name: "Add New Model" });
    await editor.getByLabel("Provider").selectOption("comfyui");
    await editor.getByTestId("load-endpoint-models").click();
    await editor.getByRole("option", { name: "fake_sdxl.safetensors" }).click();
    await editor.getByLabel("Display Name").fill("Fake SDXL (ComfyUI)");

    await editor.getByText("Use a custom workflow").click();
    const workflowField = editor.getByLabel("Workflow (API format JSON)");
    await workflowField.fill(JSON.stringify({ nodes: [], links: [] }));
    await editor.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText(/UI format/)).toBeVisible();
    await expect(editor).toBeVisible(); // editor stays open on validation errors

    const workflow = {
      4: { class_type: "CheckpointLoaderSimple", inputs: { ckpt_name: "{{model}}" } },
      5: { class_type: "EmptyLatentImage", inputs: { width: "{{width}}", height: "{{height}}", batch_size: "{{batch_size}}" } },
      6: { class_type: "CLIPTextEncode", inputs: { text: "masterpiece, {{prompt}}", clip: ["4", 1] } },
      3: { class_type: "KSampler", inputs: { seed: "{{seed}}", steps: 4, model: ["4", 0], positive: ["6", 0], latent_image: ["5", 0] } },
      9: { class_type: "SaveImage", inputs: { images: ["3", 0] } },
    };
    await workflowField.fill(JSON.stringify(workflow));
    await editor.getByRole("button", { name: "Save" }).click();
    await expect(editor).toBeHidden();
    await expect(page.getByRole("row").filter({ hasText: "Fake SDXL (ComfyUI)" })).toContainText("Fake ComfyUI");

    const models = (await api(page, "GET", "/api/admin/models")).data;
    const model = models.find((/** @type {any} */ m) => m.name === "Fake SDXL (ComfyUI)");
    fake.requests.length = 0;
    await generateAndWait(page, model.id, "a fake castle");

    const queued = fake.requests.find((r) => r.path === "/prompt");
    const graph = queued?.body?.prompt;
    expect(graph["4"].inputs.ckpt_name).toBe("fake_sdxl.safetensors");
    expect(graph["5"].inputs).toEqual({ width: 512, height: 512, batch_size: 1 });
    expect(graph["6"].inputs.text).toContain("masterpiece, ");
    expect(graph["6"].inputs.text).toContain("a fake castle");
    expect(typeof graph["3"].inputs.seed).toBe("number");
    expect(fake.requests.some((r) => r.path === "/view")).toBe(true);
  });

  test("an endpoint in use cannot be deleted", async ({ page }) => {
    await openEndpointsTab(page);
    const row = page.getByRole("row").filter({ hasText: "Fake ComfyUI" });
    await expect(row).toContainText("1");
    await row.getByRole("button", { name: "Delete" }).click();
    await page.getByRole("dialog", { name: "Delete endpoint" }).getByRole("button", { name: "Delete" }).click();

    await expect(page.getByText(/Endpoint is used by model\(s\): Fake SDXL \(ComfyUI\)/)).toBeVisible();
    await expect(row).toBeVisible();
  });
});
