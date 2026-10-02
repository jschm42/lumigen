---
name: image-provider-api-docs
description: >-
  Instructs agents on how to access, fetch, and verify the latest live API documentation
  and request/response schemas for AI image generation providers (such as Black Forest Labs / BFL FLUX,
  fal.ai, OpenRouter, OpenAI DALL-E / Images, Google Imagen / Gemini, and MiniMax).
  Use this skill whenever adding new models, updating existing adapters, troubleshooting API errors
  (e.g., 422 extra_forbidden, invalid dimensions, unsupported aspect ratios), or reviewing payload formats.
argument-hint: "Provider name (e.g. 'bfl', 'fal', 'openrouter', 'openai', 'google', 'minimax') or specific documentation URL."
user-invocable: true
---

# Image Provider API Documentation Skill

This skill guides agents on how to reliably fetch, inspect, and apply the latest official API documentation and schemas for all AI image generation providers integrated into Lumigen.

## When to Use This Skill

Activate this skill when:
- Implementing a new image generation provider or model adapter.
- Updating an existing provider adapter in `app/providers/`.
- Diagnosing and fixing API runtime errors (e.g., HTTP `422 Unprocessable Entity` with `extra_forbidden`, HTTP `400 Bad Request`, unexpected response shapes, or invalid aspect ratios/resolutions).
- Verifying the exact request schema, supported parameters, authentication headers, or polling mechanism for a provider.

---

## How to Fetch Live Provider Documentation

When researching or verifying API specifications, do **not** guess parameter names or rely solely on pre-training knowledge. Fetch live provider documentation using the following protocol:

### 1. Primary Method: `read_url_content`
Use the `read_url_content` tool with the official documentation URL.
```
read_url_content(Url="https://docs.bfl.ai/flux_3/flux3_image_generate")
```

### 2. Pro Tip for Mintlify Docs (e.g., Black Forest Labs `docs.bfl.ai`)
Many modern AI documentation platforms (like [Mintlify](https://mintlify.com)) serve raw markdown directly:
- **Append `.md` to the URL:** This bypasses heavy HTML and navigation menus, delivering the clean markdown documentation and OpenAPI schemas directly into your context.
  - Page: `https://docs.bfl.ai/flux_3/flux3_image_generate`
  - Clean Markdown: `https://docs.bfl.ai/flux_3/flux3_image_generate.md`
  - API Reference: `https://docs.bfl.ai/api-reference/utility/generate-an-image-with-flux-3.md`
- **Use `llms.txt`:** Many documentation portals provide an index for LLMs at `/llms.txt`. For instance, BFL maintains `https://docs.bfl.ml/llms.txt` listing all documented endpoints, parameter guides, and models.

### 3. Fallback: Search with `search_web`
If a specific link has moved, returns a 404, or if you need to locate an unlisted endpoint:
- Search targeting the provider's documentation domain:
  - `site:docs.bfl.ai flux 3 image generate`
  - `site:fal.ai/models/fal-ai flux dev api`
  - `site:openrouter.ai/docs image generation`
  - `site:ai.google.dev/gemini-api/docs/image-generation imagen 3`
- Inspect the top returned URLs, then fetch the chosen page with `read_url_content`.

### 4. Fallback for Dynamic / JavaScript-Heavy Portals: `browser_subagent`
If a documentation site blocks static requests, uses Cloudflare challenges, or requires client-side JavaScript rendering to display interactive schema tabs, invoke a `browser_subagent` to open the URL and extract the parameter specifications.

---

## Provider Documentation Catalog

Below is the verified registry of official documentation hubs, key model endpoints, and integration gotchas for providers supported by Lumigen:

### 1. Black Forest Labs (BFL)
- **Official Docs Portal:** [https://docs.bfl.ai](https://docs.bfl.ai)
- **LLM Index:** [https://docs.bfl.ml/llms.txt](https://docs.bfl.ml/llms.txt)
- **Key Endpoints & Guides:**
  - **FLUX.3 Text-to-Image:**
    - Guide: `https://docs.bfl.ai/flux_3/flux3_image_generate` (or `.md`)
    - API Reference: `https://docs.bfl.ai/api-reference/utility/generate-an-image-with-flux-3.md`
    - Base URL & Path: `POST https://api.bfl.ai/v1/flux-3-image`
  - **FLUX 1.1 Pro / Dev / Schnell:**
    - Guide: `https://docs.bfl.ai/quick_start/generating_images#primary-global-endpoint`
- **Authentication:** Header `x-key: <BFL_API_KEY>`
- **Request Mechanics & Gotchas:**
  - **Polling Workflow:** BFL uses asynchronous polling. Submitting a generation POST returns `{ "id": "...", "polling_url": "..." }`. Poll `GET polling_url` with header `x-key` until `status` is `Ready` (or `Error`/`Failed`). Result image URL is in `result.sample`.
  - **Parameter Difference (FLUX.1 vs FLUX.3):**
    - FLUX.1 models accept `width` and `height` (integers, multiples of 32).
    - FLUX.3 uses `aspect_ratio` (e.g., `'16:9'`, `'1:1'`, `'21:9'`, `'3:2'`, `'4:3'`) and `resolution` (tier: `'768sq'`, `'1k'`, `'1.5k'`, `'2k'`, `'4k'`).
    - **CRITICAL:** Do NOT pass `width` or `height` to FLUX.3 endpoints! The API enforces `additionalProperties: false`, which will fail with HTTP 422: `{'type': 'extra_forbidden', 'loc': ['body', 'width'], 'msg': 'Extra inputs are not permitted'}`.

### 2. fal.ai
- **Official Docs Portal:** [https://fal.ai/docs](https://fal.ai/docs)
- **Model Directory & API Specs:** [https://fal.ai/models](https://fal.ai/models)
- **Key Endpoints & Guides:**
  - FLUX Dev / Pro: `https://fal.ai/models/fal-ai/flux/dev/api`
  - Nano Banana 2: `https://fal.ai/models/fal-ai/nano-banana-2/api`
  - Upscaling (AuraSR): `https://fal.ai/models/fal-ai/aura-sr/api`
  - Upscaling (CCSR): `https://fal.ai/models/fal-ai/ccsr/api`
- **Authentication:** Header `Authorization: Key <FAL_KEY>`
- **Request Mechanics & Gotchas:**
  - Queue-based async requests: `POST https://queue.fal.run/...` returns `request_id`, status URL, and response URL.
  - Polling status at `GET https://queue.fal.run/.../requests/{request_id}/status` until status is `COMPLETED`.
  - Fetching output at `GET https://queue.fal.run/.../requests/{request_id}`.

### 3. OpenRouter
- **Image Generation Guide:** [https://openrouter.ai/docs/guides/overview/multimodal/image-generation](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
- **API Reference:** [https://openrouter.ai/docs](https://openrouter.ai/docs)
- **Models API:** `GET https://openrouter.ai/api/v1/models`
- **Authentication:** Header `Authorization: Bearer <OPENROUTER_API_KEY>`
- **Request Mechanics & Gotchas:**
  - Requests typically use the Chat Completions endpoint (`POST https://openrouter.ai/api/v1/chat/completions`) with multimodal modalities parameter `{"modalities": ["image", "text"]}` or direct image generation parameters.
  - Response parsing: image payload may be returned as markdown image URL or base64 data URL in the completion choice message.

### 4. OpenAI
- **Images Guide:** [https://platform.openai.com/docs/guides/images](https://platform.openai.com/docs/guides/images)
- **API Reference (Create Image):** [https://platform.openai.com/docs/api-reference/images/create](https://platform.openai.com/docs/api-reference/images/create)
- **Authentication:** Header `Authorization: Bearer <OPENAI_API_KEY>`
- **Request Mechanics & Gotchas:**
  - DALL-E 3 supports `size` (`1024x1024`, `1024x1792`, `1792x1024`), `quality` (`standard`, `hd`), `style` (`vivid`, `natural`).
  - DALL-E 2 supports `size` (`256x256`, `512x512`, `1024x1024`).
  - Output format can be requested as URL or base64 (`response_format: "b64_json"`).

### 5. Google Gemini / Imagen
- **Imagen Generation Guide:** [https://ai.google.dev/gemini-api/docs/image-generation](https://ai.google.dev/gemini-api/docs/image-generation)
- **REST API Reference:** [https://ai.google.dev/api/rest](https://ai.google.dev/api/rest)
- **Authentication:** Query param `?key=<GEMINI_API_KEY>` or header `x-goog-api-key: <KEY>`
- **Request Mechanics & Gotchas:**
  - Model: `imagen-3.0-generate-002` via `POST https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict`.
  - Accepts parameters: `aspectRatio` (`"1:1"`, `"3:4"`, `"4:3"`, `"9:16"`, `"16:9"`), `sampleCount`, `personGeneration`, `safetySetting`.

### 6. MiniMax / Hailuo AI
- **Developer Portal:** [https://www.minimaxi.com](https://www.minimaxi.com) / [https://api.minimaxi.chat](https://api.minimaxi.chat)
- **API Docs:** [https://www.minimaxi.com/document/](https://www.minimaxi.com/document/)
- **Authentication:** Header `Authorization: Bearer <MINIMAX_API_KEY>`
- **Request Mechanics & Gotchas:**
  - Task submission generates a task ID; follow up with task querying until state reaches success.

---

## Step-by-Step Procedure for Diagnosing Provider Errors

When handling an issue with an image provider (such as a generation error reported by a user or in automated tests):

1. **Inspect the Raw Error Payload**:
   - Check the status code and response body (e.g. `422`, `400`, `extra_forbidden`, `validation_error`).
   - Identify the exact parameter path reported in `loc` (e.g., `['body', 'width']`).

2. **Retrieve the Live API Schema**:
   - Locate the provider in the catalog above.
   - Use `read_url_content` (preferring `.md` for Mintlify sites like BFL).
   - Locate the OpenAPI schema or request body definitions for the exact model version.

3. **Check for Model-Specific Parameter Variations**:
   - Does this model require `aspect_ratio` instead of `width`/`height`?
   - Does the model forbid null values or unexpected keys (`additionalProperties: false`)?
   - Does the model require specific aspect ratio string formats (e.g., `"16:9"` vs `"16/9"` vs pixel dimensions)?

4. **Update the Adapter / Service**:
   - Modify the corresponding adapter in `app/providers/<provider>_adapter.py`.
   - Ensure sanitized payloads exclude disallowed or internal parameters.

5. **Validate**:
   - Run provider unit tests: `python -m pytest -q tests/providers/`
   - Test against the adapter logic to confirm clean execution without schema violations.
