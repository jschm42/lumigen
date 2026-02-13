# Lumigen

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

## React migration frontend (Next.js)

A React/Next.js frontend is available under `./frontend` as a migration path from server-rendered templates.

- Uses `next`, `react`, `next-intl`, `react-hook-form`, `zod`, `clsx`, `tailwind-merge`, `lucide-react`, `@prisma/client`.
- Reads existing SQLite data through Prisma (`DATABASE_URL=file:../../data/app.db` from `frontend/prisma/schema.prisma`).
- For generation execution, it forwards requests to the existing FastAPI backend (`FASTAPI_BASE_URL`).

Quick start:

```bash
cd frontend
npm install
copy .env.example .env
npm run prisma:generate
npm run dev
```

Open `http://127.0.0.1:3100/de`.

## Upscaling (Linux, local Real-ESRGAN)

Lumigen can upscale generated images locally using Real-ESRGAN (NCNN Vulkan). The app calls the binary directly, so you only need to install the executable and the model files.

### 1) Download the binary

- Real-ESRGAN releases: https://github.com/xinntao/Real-ESRGAN/releases
- Download the Linux build (for example `realesrgan-ncnn-vulkan`), extract it, and make it executable:

```bash
chmod +x realesrgan-ncnn-vulkan
sudo cp realesrgan-ncnn-vulkan /usr/local/bin/
```

### 2) Download the models

- Model weights are available in the repo under `weights/` or in the release assets:
	- https://github.com/xinntao/Real-ESRGAN/tree/master/weights
- Hugging Face hosts mirrors too (search for Real-ESRGAN weights):
	- https://huggingface.co/models?search=Real-ESRGAN

The app expects model names (not full paths), so place the model files next to the binary or in the `models` directory that Real-ESRGAN uses by default (for example `/usr/local/bin/models`).

Recommended model files:
- `realesrgan-x2plus` (x2)
- `realesrgan-x4plus` (x4)

For x8, Lumigen runs x4 then x2 sequentially.

### 3) Configure .env

```dotenv
UPSCALER_COMMAND=/usr/local/bin/realesrgan-ncnn-vulkan
UPSCALER_MODEL_X2=realesrgan-x2plus
UPSCALER_MODEL_X4=realesrgan-x4plus
```

Restart the app and enable the upscale option in the Generate form.

### Optional: auto-download models from Hugging Face

Lumigen can auto-download Real-ESRGAN NCNN model files (`.param` and `.bin`) from a Hugging Face repo. You need a repo that actually contains those NCNN files.

Example `.env`:

```dotenv
UPSCALER_AUTO_DOWNLOAD=true
UPSCALER_HF_REPO=ai-forever/Real-ESRGAN
UPSCALER_HF_REVISION=main
UPSCALER_MODEL_DIR=./data/models/realesrgan
```

Expected files in the repo:
- `realesrgan-x2plus.param`
- `realesrgan-x2plus.bin`
- `realesrgan-x4plus.param`
- `realesrgan-x4plus.bin`
