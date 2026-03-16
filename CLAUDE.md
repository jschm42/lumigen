# Lumigen – Claude Code Instructions

Derived from `.github/copilot-instructions.md`. Trust this file first; search the repo only when information here is missing, stale, or contradicted by runtime output.

## Project summary

Lumigen is a local-first AI image studio (FastAPI monolith) for image generation, gallery management, metadata sidecars, and optional upscaling.

- **Main runtime path:** route (`/generate`) → `GenerationService` → `ProviderRegistry`/adapter → `StorageService` + `ThumbnailService` + `SidecarService` → DB `Asset` rows.
- **Stack:** Python 3.12+, FastAPI, Jinja2 + HTMX, SQLite, SQLAlchemy 2, Alembic.
- **Tooling:** `ruff`, `djlint`, `eslint`, `stylelint`, `pytest`, `@playwright/test`.
- **Server:** `http://127.0.0.1:8010` (dev).

## Setup

Run all commands from the **repository root**.

```bash
# 1. Create/activate a virtualenv
# 2. Install Python deps
pip install -r requirements.txt
# 3. Apply migrations
alembic upgrade head
# 4. Install Node deps (required for JS/CSS lint and Playwright)
npm.cmd ci          # use npm.cmd on Windows (PowerShell script-execution policy)
```

## Running the app

```bash
python -m app.main
```

## Testing

```bash
# Unit tests
python -m pytest -q tests/unit

# Route + UI route tests
python -m pytest -q tests/routes tests/ui_routes

# Playwright e2e (requires npm.cmd ci + browser install once)
npx.cmd playwright install --with-deps chromium
npx.cmd playwright test
npx.cmd playwright test --ui   # interactive runner
```

## Linting (mirrors CI)

```bash
python -m ruff check app/                          # Python lint
djlint app/web/templates/ --lint                   # template lint
npx.cmd eslint app/web/static/js/                  # JS lint
npx.cmd stylelint "app/web/static/css/app.css"     # CSS lint
```

Install linters if missing: `python -m pip install ruff djlint`

## Pre-PR validation order

1. `alembic upgrade head`
2. `python -m pytest -q tests/unit`
3. `python -m pytest -q tests/routes tests/ui_routes`
4. `npx.cmd playwright test`
5. `python -m ruff check app/`
6. `djlint app/web/templates/ --lint`
7. `npx.cmd eslint app/web/static/js/`
8. `npx.cmd stylelint "app/web/static/css/app.css"`

## CI workflows

- `.github/workflows/lint.yml` — lint only (ruff, djlint, eslint, stylelint).
- `.github/workflows/e2e.yml` — Playwright e2e (chromium only); uploads HTML report artifact.

## Architecture map (where to edit)

| Area | Path |
|---|---|
| Route handlers + DI wiring | `app/main.py` |
| SQLAlchemy schema | `app/db/models.py` |
| DB helpers / queries | `app/db/crud.py` |
| Engine / session init | `app/db/engine.py` |
| Schema migrations | `alembic/versions/*` |
| Generation orchestration | `app/services/generation_service.py` |
| Atomic file IO + path safety | `app/services/storage_service.py` |
| Sidecar contract | `app/services/sidecar_service.py` |
| Provider registry + policies | `app/providers/registry.py` |
| Provider HTTP adapters | `app/providers/*_adapter.py` |
| Server-rendered templates | `app/web/templates/` |
| Client JavaScript | `app/web/static/js/` |
| App-wide CSS | `app/web/static/css/app.css` |

## Change rules (prevent regressions)

- Prefer service-layer changes over adding business logic in `app/main.py`.
- Schema changes: update `app/db/models.py` **and** add a matching Alembic migration.
- Provider logic stays in adapters; orchestration/policies stay in `ProviderRegistry`.
- All file writes go through `StorageService` — do not bypass path-safety checks.
- No inline JS or CSS in templates; use `app/web/static/js/*` and `app/web/static/css/app.css`.
- Add/adjust tests for every backend or UI behavior change.
- Tailwind theming: use class-based dark mode only. Do not introduce custom light/dark override systems. Follow [Tailwind theme customization](https://tailwindcss.com/docs/theme#customizing-your-theme).

## Documentation requirements

- Every public Python class must have a docstring describing its purpose.
- Every public method/function (not prefixed with `_`) must have a docstring covering what it does, key parameters, and return value (if non-obvious).
- Private helpers (`_`-prefixed) should be documented when logic is non-trivial.
- Follow PEP 257: triple double-quotes, capital first letter, ends with a period.
- Always include or update docstrings when adding or modifying a class or public method.

## Playwright e2e details

- Config: `playwright.config.js` (root) — `chromium` project, `setup` project (`tests/e2e/auth.setup.js`), `webServer` on port 8765 with isolated SQLite in `/tmp/lumigen-e2e/`.
- Test files: `tests/e2e/*.spec.js` (one per feature area).
- Auth: `auth.setup.js` creates the first admin via onboarding and saves session to `playwright/.auth/admin.json`; all specs reuse it via `storageState`.
- To add a test: create `tests/e2e/<feature>.spec.js`, import `{ test, expect }` from `@playwright/test`.

## Environment / secrets

- `.env.example` has local-dev defaults.
- Production needs a strong `SESSION_SECRET_KEY`.
- API key encryption requires `PROVIDER_CONFIG_KEY` (generate via `scripts/generate_provider_key.ps1` or `.sh`).
- Run Alembic from repo root (`alembic.ini` uses `sqlite:///./data/app.db`).

## Root layout

```
.github/    alembic/    app/    tests/    scripts/    docs/    docker/    data/
README.md   requirements.txt   pyproject.toml   pytest.ini   alembic.ini
package.json   eslint.config.mjs   Dockerfile   .stylelintrc.json   playwright.config.js
```
