# MCP endpoint

Lumigen has a [Model Context Protocol](https://modelcontextprotocol.io) endpoint at `/mcp`. External
apps, such as the text adventure engine TaleWeaver, use it to generate images with the models,
profiles and categories configured in Lumigen. The images land in the Lumigen gallery like any
other generation, each request in its own session.

## Setup

1. Generate a token and store it in `.env` (run from the repository root):

   ```bash
   ./scripts/generate_mcp_token.sh --write      # Linux / macOS
   .\scripts\generate_mcp_token.ps1 --write    # Windows PowerShell
   ```

   The script sets (or replaces) `MCP_API_TOKEN` in `.env` and prints the token for your client.
   Without `--write` it only prints a new token. Optionally set the longest wait for a finished
   image in `.env` as well, `MCP_MAX_WAIT_SECONDS=300`.

2. Restart Lumigen.

3. Point the client at `http://<lumigen-host>:8010/mcp` and send the header
   `Authorization: Bearer <token>`.

The endpoint returns `404` while `MCP_API_TOKEN` is empty and `401` for a missing or wrong token.
It does not use the web UI login. Anyone with the token can generate images at your provider's
cost, so treat it like an API key and serve Lumigen over HTTPS when it is reachable from other
machines.

## Docker

The container reads `MCP_API_TOKEN` from the `.env` on the host, both with `docker compose`
(`env_file`) and with `scripts/docker_run.*` / `scripts/docker_update.*` (`--env-file`). No token
is generated automatically, so the endpoint stays off until you create one on the host:

```bash
./scripts/generate_mcp_token.sh --write          # or .\scripts\generate_mcp_token.ps1 --write
./scripts/docker_update.sh                       # recreates the container with the new .env
# with docker compose instead:
docker compose up -d --force-recreate app
```

A plain `docker compose restart` does not re-read `.env`. The run and update scripts print the
MCP URL, or a hint when no token is set.

Without Python on the host, create the token with
`openssl rand -base64 32 | tr '+/' '-_' | tr -d '='` and add `MCP_API_TOKEN=<token>` to `.env` by hand.

Endpoint URL:

| Setup | URL |
|---|---|
| `docker compose` (nginx with TLS) | `https://<host>/mcp` |
| `scripts/docker_run.*` | `http://<host>:<PORT>/mcp` (default port 7003) |
| Client in the same compose network | `http://app:7003/mcp` |

The bundled nginx config gives `/mcp` a 900 s read timeout. Keep `MCP_MAX_WAIT_SECONDS` below that,
otherwise long generations end in a `504` from nginx before Lumigen answers.

## Transport

Streamable HTTP in stateless JSON mode: every call is a single `POST /mcp` with a JSON-RPC body and
the headers `Content-Type: application/json` and `Accept: application/json, text/event-stream`.
No session handshake is needed between calls.

## Tools

| Tool | Purpose |
|---|---|
| `list_models` | Configured image models (`id`, `name`, `provider`, `model`) |
| `list_profiles` | Profiles with their model, aspect ratio, image count and categories |
| `list_categories` | Gallery categories |
| `generate_image` | Generate images and (by default) wait for them |
| `get_generation` | Status, error and image IDs of a job |
| `get_image` | One image by `asset_id`, full size or thumbnail |

### `generate_image`

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `prompt` | string | required | What to draw |
| `model` | string or int | profile's model | Model config ID, name or provider model identifier (case-insensitive). Overrides the profile's model |
| `profile` | string or int | neutral `Default` profile | Profile ID or name. Supplies base prompt, size, upscaling and default categories |
| `categories` | list of string or int | profile's categories | Category IDs or names. Unknown names are created (max. 30 characters) |
| `negative_prompt` | string | profile's | Things to avoid |
| `aspect_ratio` | string | profile's, else `1:1` | For example `16:9` |
| `resolution` | string | `1K` | Provider size tier such as `1K`, `2K`, `4K` (where supported) |
| `n_images` | int | profile's | 1 to 8 |
| `seed` | int | profile's | Fixed seed |
| `session_title` | string | start of the prompt | Title of the Lumigen session that holds the result |
| `wait` | bool | `true` | Wait for the result. With `false` the call returns the `job_id` right away |
| `timeout_seconds` | int | `MCP_MAX_WAIT_SECONDS` | Wait limit, capped at `MCP_MAX_WAIT_SECONDS` |
| `include_images` | `full`, `thumbnail`, `none` | `full` | Return the images inline as base64 image content |

The result contains a JSON summary (also as `structuredContent`) and, for finished jobs, one image
block per image:

```json
{
  "job_id": 42,
  "status": "succeeded",
  "finished": true,
  "error": null,
  "prompt": "A lighthouse on a cliff in a storm, oil painting",
  "model": "<provider model identifier>",
  "model_config_id": 3,
  "provider": "openrouter",
  "profile": "Story Scenes",
  "aspect_ratio": "16:9",
  "seed": null,
  "images": [{ "asset_id": 118, "width": 1344, "height": 768, "mime": "image/png" }]
}
```

`status` is one of `queued`, `running`, `succeeded`, `failed` or `cancelled`. If the wait limit
passes first, the job keeps running; poll it with `get_generation` and fetch the images with
`get_image`. Failed jobs and invalid input (unknown model or profile, invalid aspect ratio) come
back as tool results with `isError: true` and a readable message.

Jobs run one after another in Lumigen's generation queue, also alongside jobs from the web UI.

## Examples

Raw JSON-RPC with `curl`:

```bash
curl -s http://127.0.0.1:8010/mcp \
  -H "Authorization: Bearer $MCP_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"A lighthouse on a cliff in a storm, oil painting","profile":"Story Scenes","categories":["TaleWeaver"],"include_images":"thumbnail"}}}'
```

MCP client configuration (for clients that support remote HTTP servers with headers):

```json
{
  "mcpServers": {
    "lumigen": {
      "type": "http",
      "url": "http://127.0.0.1:8010/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

## Code map

| Part | Path |
|---|---|
| MCP server, tools, bearer token check | `app/mcp_server.py` |
| Name resolution, job creation, image reading | `app/services/external_generation_service.py` |
| Settings | `MCP_API_TOKEN`, `MCP_MAX_WAIT_SECONDS` in `app/config.py` |
| Tests | `tests/unit/test_mcp_endpoint.py`, `tests/unit/test_external_generation_service.py` |
