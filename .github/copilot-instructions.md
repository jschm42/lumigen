# Lumigen Copilot Instructions

Use this file as the primary onboarding source. Trust these instructions first and only search the repo when information here is missing, stale, or contradicted by runtime output.

## Repository summary
- Lumigen is a local-first AI image studio (FastAPI monolith) for image generation, gallery management, metadata sidecars, and optional upscaling.
- Main runtime path: route (`/generate`) -> `GenerationService` -> `ProviderRegistry`/adapter -> `StorageService` + `ThumbnailService` + `SidecarService` -> DB `Asset` rows.
- Primary stack: Python 3.12+, FastAPI, Jinja2 + HTMX, SQLite, SQLAlchemy 2, Alembic.
- Additional tooling: `ruff`, `djlint`, `eslint`, `stylelint`, `pytest`, `@playwright/test`.

## Repository profile
- Project type: server-rendered web app + API in one Python service.
- Size/layout: single backend app under `app/`, migrations under `alembic/`, tests under `tests/`, helper scripts under `scripts/`.
- Runtimes observed in repo:
	- Python `3.12.10`.
	- Node available (observed `v24.13.0`; CI uses Node 20).

## Most reliable command order
Always run commands from repository root.

1. Create/activate virtualenv.
2. Install Python deps: `pip install -r requirements.txt`.
3. Apply migrations: `alembic upgrade head`.
4. Install Node deps before JS/CSS lint: `npm ci`.
5. Run app or tests/lints as needed.

## Command matrix (validated)
Status values: `verified`, `verified with caveat`, `failed here with workaround`, `documented only`.

- `python --version` -> `verified` (3.12.10).
- `alembic upgrade head` -> `verified`.
- `python -m app.main` -> `verified` (server starts on `http://127.0.0.1:8010`).
- `python -m pytest -q tests/unit/test_gallery_service.py` -> `verified` (`5 passed`, ~0.4s).
- `python -m pytest -q tests/ui_routes/test_ui_routes.py` -> `verified` (`15 passed`, ~12s).
- `python -m pytest -q tests/routes tests/ui_routes` -> `verified` (`54 passed`, ~28s).
- `npx playwright test` -> run all Playwright e2e tests (requires `npm ci` and `npx playwright install --with-deps chromium` first).
- `npx playwright test --ui` -> open the Playwright interactive UI runner.
- `python scripts/smoke_web_routes.py` -> `verified with caveat`: currently fails with `AssertionError: admin page does not include external admin-page.js`.
- `ruff check app/` -> `failed here with workaround`: command not found in shell until tool installed.
- `python -m ruff check app/` -> `failed here with workaround`: module not installed in current venv.
- `djlint app/web/templates/ --lint` -> `failed here with workaround`: command not found until installed.
- `npm ci` -> `failed here with workaround` in PowerShell due `npm.ps1` execution policy.
- `npm.cmd ci` -> `verified with caveat` (succeeds; observed AutoRun warning lines but install completes).
- `npx eslint app/web/static/js/` -> use `npx.cmd eslint app/web/static/js/` on Windows PowerShell.
- `npx stylelint "app/web/static/css/app.css"` -> use `npx.cmd stylelint "app/web/static/css/app.css"` on Windows PowerShell.

### Required workarounds observed
- If `ruff`/`djlint` are missing locally, install first:
	- `python -m pip install ruff djlint`
- For Playwright, install browsers after `npm ci`:
	- `npx playwright install --with-deps chromium`
- On Windows PowerShell with script execution restrictions, use `.cmd` shims:
	- `npm.cmd ci`
	- `npx.cmd eslint ...`
	- `npx.cmd stylelint ...`
	- `npx.cmd playwright test`

## CI checks and how to replicate locally
GitHub workflow: `.github/workflows/lint.yml`.

CI currently runs lint only (no pytest job):
- Python lint: `ruff check app/`
- Template lint: `djlint app/web/templates/ --lint`
- JS lint: `npx eslint app/web/static/js/`
- CSS lint: `npx stylelint "app/web/static/css/app.css"`

A separate workflow (`.github/workflows/e2e.yml`) runs Playwright e2e tests:
- Installs Python + Node dependencies, then runs `npx playwright test`
- Uploads the HTML report as a workflow artifact (`playwright-report`)
- Only the `chromium` browser is tested in CI

Recommended pre-PR validation order:
1. `alembic upgrade head`
2. `python -m pytest -q tests/unit`
3. `python -m pytest -q tests/routes tests/ui_routes`
4. `npx playwright test` (requires `npm ci` and `npx playwright install --with-deps chromium`)
5. `ruff check app/`
6. `djlint app/web/templates/ --lint`
7. `npx eslint app/web/static/js/`
8. `npx stylelint "app/web/static/css/app.css"`

## Architecture map (where to edit)
- `app/main.py`: route handlers, request validation, dependency wiring, service singletons.
- `app/db/models.py`: SQLAlchemy schema.
- `app/db/crud.py`: DB helpers and query routines.
- `app/db/engine.py`: engine/session init (`init_db` exists for local bootstrap).
- `alembic/versions/*`: authoritative schema evolution.
- `app/services/generation_service.py`: generation orchestration and reproducibility snapshots (`profile_snapshot_json`, `storage_template_snapshot_json`, `request_snapshot_json`).
- `app/services/storage_service.py`: atomic file IO and path-safety (`ensure_within_base`).
- `app/services/sidecar_service.py`: success/failure sidecar contract (`.failures/YYYY/MM/` for failures).
- `app/providers/registry.py`: provider registration, concurrency/rate limits, retry policy.
- `app/providers/*_adapter.py`: provider-specific HTTP integrations.
- `app/web/templates/`: server-rendered Jinja templates + HTMX fragments.
- `app/web/static/js/`: all client JavaScript. Do not use inline scripts in templates.
- `app/web/static/css/app.css`: app-wide styles.

## Change rules that prevent regressions
- Prefer service-layer changes over adding business logic in `app/main.py`.
- For schema changes: update `app/db/models.py` and add a matching Alembic migration.
- Keep provider logic inside adapters; keep orchestration/policies in `ProviderRegistry`.
- Keep writes inside `StorageService`; do not bypass path safety checks.
- Keep templates free of inline JS/CSS; add scripts in `app/web/static/js/*`.
- Add/adjust tests in `tests/` for any backend or UI behavior change.
- Tailwind theming policy: use only the original Tailwind light/dark theme approach (class-based dark mode). Do not introduce custom light/dark override systems that bypass Tailwind utilities.
- If theme customization is required, implement it strictly according to Tailwind's official theme customization guidance: https://tailwindcss.com/docs/theme#customizing-your-theme

## Documentation requirements
- Every public Python class **must** have a one-line (or multi-line) docstring that describes its purpose.
- Every public method or function (i.e. not prefixed with `_`) **must** have a docstring that describes what it does, its key parameters, and its return value (if non-obvious).
- Private helpers (prefixed with `_`) should be documented when the logic is non-trivial.
- Docstrings must follow standard Python conventions (PEP 257): use triple double-quotes, start with a capital letter, and end with a period.
- When adding or modifying a class or public method, always include or update its docstring.

## Environment notes that are easy to miss
- `.env.example` defaults are local-dev oriented.
- Production auth requires strong `SESSION_SECRET_KEY`.
- Custom model API key encryption requires `PROVIDER_CONFIG_KEY` (generate via `scripts/generate_provider_key.ps1` or `.sh`).
- `alembic.ini` uses `sqlite:///./data/app.db` (relative path): run Alembic from repo root.

## Root layout quick reference
- Root files: `README.md`, `requirements.txt`, `pyproject.toml`, `pytest.ini`, `alembic.ini`, `package.json`, `eslint.config.mjs`, `Dockerfile`, `.stylelintrc.json`, `playwright.config.js`.
- Top directories: `.github/`, `alembic/`, `app/`, `tests/`, `scripts/`, `docs/`, `docker/`, `data/`.

## Playwright e2e tests
- Config: `playwright.config.js` (root) – defines the `chromium` project, a `setup` project that runs `tests/e2e/auth.setup.js`, and a `webServer` block that starts the app on port 8765 against an isolated SQLite database in `/tmp/lumigen-e2e/`.
- Test files: `tests/e2e/*.spec.js` – one file per feature area (`auth`, `home`, `gallery`, `admin`, `profiles`).
- Auth strategy: `tests/e2e/auth.setup.js` creates the first admin user via the onboarding form and saves the browser session to `playwright/.auth/admin.json`.  All spec files reuse this session via `storageState`.
- Playwright artifacts (report, test results, auth state) are git-ignored; `playwright/.auth/.gitkeep` preserves the directory.
- To add a new e2e test: create `tests/e2e/<feature>.spec.js`, import `{ test, expect }` from `@playwright/test`, and use the `storageState` from the `chromium` project (configured automatically).
- Browser installation: run `npx playwright install --with-deps chromium` once after `npm ci`.

## When to search
Only search if one of these is true:
- A command/path in this file no longer exists.
- Runtime output contradicts this document.
- The requested change touches an area not mapped above.