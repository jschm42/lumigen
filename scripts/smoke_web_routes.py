from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    client = TestClient(app)

    checks: list[tuple[str, str]] = [
        ("/", "root"),
        ("/admin?message=Saved", "admin"),
        ("/profiles", "profiles"),
        ("/gallery?embedded=1", "gallery"),
    ]

    for path, label in checks:
        response = client.get(path)
        assert response.status_code == 200, (
            f"{label} route failed: GET {path} -> {response.status_code}"
        )

    admin_html = client.get("/admin").text
    assert "/static/js/admin-page.js" in admin_html, (
        "admin page does not include external admin-page.js"
    )

    profiles_html = client.get("/profiles").text
    assert "/static/js/profiles-page.js" in profiles_html, (
        "profiles page does not include external profiles-page.js"
    )

    gallery_html = client.get("/gallery").text
    assert "/static/js/gallery-page.js" in gallery_html, (
        "gallery page does not include external gallery-page.js"
    )

    generate_html = client.get("/").text
    assert "/static/js/generate-page.js" in generate_html, (
        "generate page does not include external generate-page.js"
    )
    assert "data-last-thumb-size=" in generate_html, (
        "generate page is missing data-last-thumb-size attribute"
    )

    print("OK: smoke web routes and external script includes")


if __name__ == "__main__":
    main()
