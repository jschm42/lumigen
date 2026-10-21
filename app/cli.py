"""Console entry points exposed as Poetry scripts (see ``[project.scripts]`` in pyproject.toml)."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def start() -> None:
    """Start the Lumigen web server with uvicorn.

    Reads ``BACKEND_HOST``/``HOST``, ``BACKEND_PORT``/``PORT``, ``UVICORN_RELOAD``,
    ``LUMIGEN_SSL_CERT_FILE`` and ``LUMIGEN_SSL_KEY_FILE`` from the environment and .env file.
    """
    import uvicorn
    from dotenv import load_dotenv

    from app.config import get_settings

    # Ensure .env is loaded into environment
    load_dotenv(PROJECT_ROOT / ".env")

    settings = get_settings()
    host = os.getenv("BACKEND_HOST") or os.getenv("HOST") or settings.server_host
    raw_port = os.getenv("BACKEND_PORT") or os.getenv("PORT")
    port = int(raw_port) if raw_port else settings.server_port
    reload_enabled = os.getenv("UVICORN_RELOAD", "1") in {"1", "true", "True"}
    ssl_certfile = os.getenv("LUMIGEN_SSL_CERT_FILE") or None
    ssl_keyfile = os.getenv("LUMIGEN_SSL_KEY_FILE") or None
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )


def migrate() -> None:
    """Apply all pending Alembic migrations (equivalent to ``alembic upgrade head``).

    Runs from the project root because ``alembic.ini`` uses a relative SQLite path.
    """
    from alembic.config import Config

    from alembic import command

    os.chdir(PROJECT_ROOT)
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
