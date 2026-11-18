"""Deep links to SPA-only public routes must serve the Vue index.html."""

from __future__ import annotations

import pytest

SPA_MARKER = "<!-- lumigen-spa-index -->"


@pytest.fixture
def spa_dist(app_module, tmp_path, monkeypatch):
    """Point the app at a fake built SPA so index.html can be served."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(f"<!doctype html><html>{SPA_MARKER}</html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "dist_dir", dist)
    return dist


@pytest.mark.parametrize("path", ["/onboarding", "/forgot-password", "/reset-password"])
def test_spa_public_deep_link_serves_index(anon_client, spa_dist, path):
    response = anon_client.get(path, follow_redirects=False)

    assert response.status_code == 200
    assert SPA_MARKER in response.text
