/**
 * In-process fake servers for e2e tests: a minimal OpenAI-compatible Images API
 * and a minimal ComfyUI HTTP API. Both record the requests they receive so specs
 * can assert on what Lumigen sent.
 */

// @ts-check
import http from "node:http";

/** 1x1 PNG, valid for Pillow. */
export const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
const PNG = Buffer.from(PNG_BASE64, "base64");

/**
 * @param {http.IncomingMessage} req
 * @returns {Promise<string>}
 */
function readBody(req) {
  return new Promise((resolve) => {
    /** @type {Buffer[]} */
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
  });
}

/**
 * @param {http.ServerResponse} res
 * @param {number} status
 * @param {unknown} body
 */
function sendJson(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

/**
 * Starts one HTTP server that serves both fake APIs:
 * - OpenAI-compatible under `/v1` (`GET /v1/models`, `POST /v1/images/generations`)
 * - ComfyUI at the root (`/object_info/...`, `/prompt`, `/history/:id`, `/view`)
 *
 * @returns {Promise<{ url: string, requests: { method: string, path: string, headers: http.IncomingHttpHeaders, body: any }[], close: () => Promise<void> }>}
 */
export async function startFakeEndpoints() {
  /** @type {{ method: string, path: string, headers: http.IncomingHttpHeaders, body: any }[]} */
  const requests = [];

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url || "/", "http://localhost");
    const raw = await readBody(req);
    let body = raw;
    try {
      body = raw ? JSON.parse(raw) : null;
    } catch {
      /* keep raw */
    }
    requests.push({ method: req.method || "GET", path: url.pathname, headers: req.headers, body });

    // --- OpenAI-compatible ---
    if (url.pathname === "/v1/models") {
      return sendJson(res, 200, { object: "list", data: [{ id: "fake-flux" }, { id: "fake-sdxl" }] });
    }
    if (url.pathname === "/v1/images/generations" && req.method === "POST") {
      const count = Math.max(1, Number(body?.n || 1));
      return sendJson(res, 200, {
        created: 1,
        data: Array.from({ length: count }, () => ({ b64_json: PNG_BASE64 })),
      });
    }

    // --- ComfyUI ---
    if (url.pathname === "/object_info/CheckpointLoaderSimple") {
      return sendJson(res, 200, {
        CheckpointLoaderSimple: { input: { required: { ckpt_name: [["fake_sdxl.safetensors", "fake_flux.safetensors"], {}] } } },
      });
    }
    if (url.pathname === "/prompt" && req.method === "POST") {
      return sendJson(res, 200, { prompt_id: "fake-prompt-1", number: 1, node_errors: {} });
    }
    if (url.pathname.startsWith("/history/")) {
      const promptId = url.pathname.split("/").pop();
      return sendJson(res, 200, {
        [promptId || ""]: {
          status: { status_str: "success", completed: true },
          outputs: { 9: { images: [{ filename: "lumigen_00001_.png", subfolder: "", type: "output" }] } },
        },
      });
    }
    if (url.pathname === "/view") {
      res.writeHead(200, { "Content-Type": "image/png" });
      return res.end(PNG);
    }

    return sendJson(res, 404, { error: `fake endpoint: no route for ${req.method} ${url.pathname}` });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(undefined)));
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;

  return {
    url: `http://127.0.0.1:${port}`,
    requests,
    close: () => new Promise((resolve) => server.close(() => resolve(undefined))),
  };
}
