# Lumigen Copilot Instructions

## Big picture architecture
- Primary app is a FastAPI monolith in `app/main.py` (routes + dependency wiring + service singletons).
- Runtime flow for generation: route (`/generate`) -> `GenerationService` -> `ProviderRegistry`/adapter -> `StorageService` + `ThumbnailService` + `SidecarService` -> DB `Asset` rows.
- SQLAlchemy models live in `app/db/models.py`; DB access helpers are in `app/db/crud.py`.
- Alembic migrations are the source of schema evolution (`alembic/versions/*`), while `init_db()` in `app/db/engine.py` creates tables for local bootstrap.

## Core boundaries and patterns
- Keep provider-specific HTTP logic inside adapter classes under `app/providers/*_adapter.py`; adapters return normalized `ProviderGenerationResult` objects.
- `ProviderRegistry` (`app/providers/registry.py`) owns adapter registration, per-provider concurrency/spacing, and retry policy.
- Keep file IO inside `StorageService` (`app/services/storage_service.py`): all writes are atomic and must stay under managed base dirs (`ensure_within_base`).
- Persist reproducibility snapshots on generation creation (`profile_snapshot_json`, `storage_template_snapshot_json`, `request_snapshot_json`) as done in `GenerationService.create_generation_from_profile`.
- Sidecar JSONs are part of the product contract: success sidecars next to images, failure sidecars under `.failures/YYYY/MM/`.

## API and UI conventions
- UI is server-rendered Jinja + HTMX; many endpoints return either full-page redirects or fragment templates based on `HX-Request` (`is_htmx` in `app/main.py`).
- Polling job status uses HTMX fragments (`app/web/templates/fragments/job_status.html`, `.../chat_generation_item.html`).
- Validate form/query data in route handlers before CRUD/service calls (see admin create/update handlers and `/generate`).
- Name/length constraints are enforced in app code and DB schema (e.g., category 30 chars, profile/model-config 50 chars).
- No inline scripts in templates: place JavaScript in `app/web/static/js/*` and include via `<script src="...">`.
- No inline styles in templates: prefer existing utility classes/CSS files in `app/web/static/`.

## Clean code expectations
- Keep methods/functions small and single-purpose; extract helpers instead of growing large blocks.
- Add comments where they improve maintainability (non-obvious behavior, constraints, or provider quirks), avoid noise comments.
- Avoid code duplication (DRY): reuse existing helpers/services or introduce shared helpers when logic repeats.
- Prefer clear naming and straightforward control flow over clever/implicit patterns.

## Secrets and provider configuration
- Model-specific API keys are encrypted via Fernet in `ModelConfigService`; requires `PROVIDER_CONFIG_KEY`.
- Use scripts in `scripts/` to generate provider config key (`generate_provider_key.ps1` / `.sh`).
- When custom model key is disabled, code falls back to provider env vars from `Settings` (`app/config.py`).

## Developer workflows (actual repo commands)
- Setup/run (local): `pip install -r requirements.txt`, `alembic upgrade head`, `python -m app.main`.
- Dev server alternative: `uvicorn app.main:app --reload --port 8010`.
- Docker flow: `scripts/docker_run.ps1` / `.sh`, update via `scripts/docker_update.ps1` / `.sh`.
- Backend tests: `pytest -q` (or focused runs like `pytest -q tests/unit` and `pytest -q tests/routes`).

## Testing expectations (backend)
- When changing backend logic, add or update automated tests under `tests/` in the same PR.
- Prioritize deterministic unit tests for `app/utils`, `app/services`, and provider orchestration in `app/providers/registry.py`.
- For FastAPI route tests, prefer assertions on JSON payloads, status codes, redirects, and headers over brittle full-template snapshots.
- Keep backend route tests DB-light by using dependency overrides (`get_session`) and monkeypatching imported `app.main.crud.*` seams where appropriate.
- Avoid real external provider/network calls in tests; mock provider registry/adapter behavior explicitly.

## Testing expectations (frontend)
- Frontend coverage in this repo targets server-rendered Jinja + HTMX behavior through FastAPI route tests under `tests/frontend/`.
- Prefer stable assertions for critical UI markers (form/action attributes, fragment IDs, HTMX attributes, flash/error text) instead of full HTML snapshots.
- Keep frontend tests deterministic by mocking `app.main.crud.*`, service singletons (`gallery_service`, `generation_service`, etc.), and using dependency overrides for `get_session`.
- Do not add browser E2E tooling unless explicitly requested; route/template tests are the default frontend test level in this project.

## Integration points and external dependencies
- External provider APIs: OpenAI, OpenRouter, Google, BFL adapters under `app/providers/`.
- Optional local upscaling uses Real-ESRGAN command execution in `app/services/upscale_service.py`; models can auto-download via `huggingface_hub`.
- README documents an optional Next.js migration frontend under `frontend/` that forwards generation requests to this FastAPI backend.

## Change guidance for AI agents
- Prefer adding logic to existing services/CRUD/helpers instead of growing `app/main.py` further with inline business logic.
- For schema changes: update SQLAlchemy model + add Alembic migration in `alembic/versions/`.
- For new generation metadata: update both DB model fields and sidecar payload builders to keep UI/debug views consistent.
- For new providers: add adapter, register it in `ProviderRegistry._register_defaults`, and expose required settings in `app/config.py`.