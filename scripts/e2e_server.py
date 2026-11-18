"""Start Lumigen for Playwright e2e tests against a fresh, isolated data directory.

The data directory is wiped on every start so the onboarding flow and all seeded
fixtures are deterministic. The Vue SPA must be built beforehand
(``npm run build:frontend``), otherwise the server only serves a fallback page.

Usage:
    python scripts/e2e_server.py [--port 8765] [--data-dir <path>]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_INDEX = REPO_ROOT / "app" / "web" / "dist" / "index.html"


def main() -> int:
    """Wipe the e2e data directory, configure the environment and run uvicorn."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=str(Path(tempfile.gettempdir()) / "lumigen-e2e"))
    args = parser.parse_args()

    if not DIST_INDEX.exists():
        print(
            f"[e2e] {DIST_INDEX} is missing. Build the frontend first: npm run build:frontend",
            file=sys.stderr,
        )
        return 1

    data_dir = Path(args.data_dir).resolve()
    if data_dir.exists():
        shutil.rmtree(data_dir)
    (data_dir / "images").mkdir(parents=True)

    os.environ.update(
        {
            "DATA_DIR": str(data_dir),
            "DEFAULT_BASE_DIR": str(data_dir / "images"),
            "SQLITE_PATH": str(data_dir / "test.db"),
            "SESSION_HTTPS_ONLY": "false",
            "SESSION_SECRET_KEY": "e2e-test-secret-key-not-for-production",
        }
    )
    os.chdir(REPO_ROOT)
    # Running as a script puts scripts/ (not the repo root) on sys.path.
    sys.path.insert(0, str(REPO_ROOT))

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
