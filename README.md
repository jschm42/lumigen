# Pixelforge

Local-first FastAPI app for image generation with provider adapters (stub, OpenAI, OpenRouter) and SQLite-first storage.

## Features

- FastAPI + Jinja2 + HTMX server-rendered UI
- SQLAlchemy 2.0 + Alembic migrations from day 1
- SQLite DB at `./data/app.db` with WAL + foreign keys enabled
- Provider adapter architecture with per-provider rate limiting/retry
- Safe managed filesystem writes under storage templates
- Reproducible generation snapshots (profile/storage/request)
- Sidecars for successful and failed generations
- Thumbnail generation under `.thumbs/`

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment (optional defaults are already local-first):

```bash
copy .env.example .env
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start app:

```bash
python -m app.main
```

Or:

```bash
uvicorn app.main:app --reload --port 8010
```

Open http://127.0.0.1:8010

If port `8000` is already in use on your machine (common on Windows with other local tools), pick another port (for example `8010`).

## Docker

Build and run with a shared local `data/` folder and port `7003`:

```bash
scripts/docker_run.sh
```

On Windows PowerShell:

```powershell
scripts\docker_run.ps1
```

Configure the host data directory via `.env`:

```dotenv
DOCKER_DATA_DIR=./data
```

Update the container after pulling a new version:

```bash
scripts/docker_update.sh
```

```powershell
scripts\docker_update.ps1
```

## Notes

- Create at least one profile in **Profiles** before generating.
- Use provider `stub` for fully local end-to-end generation.
- OpenAI adapter works with `OPENAI_API_KEY`.
- OpenRouter adapter works with `OPENROUTER_API_KEY` and sends image-generation requests through `/chat/completions` (`modalities: ["image","text"]`).
- Generated files are managed via DB-indexed relative paths only; no arbitrary path browsing is exposed.
