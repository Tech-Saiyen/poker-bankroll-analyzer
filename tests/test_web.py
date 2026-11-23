# tests/test_web.py
import pytest
from poker_bankroll_analyzer import create_app


@pytest.fixture
def client():
    app = create_app("testing")
    return app.test_client()


def test_homepage_renders_mobile_web_app(client):
    """GET / serves the mobile-first DFW Poker Life web interface."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "DFW" in html
    assert "POKER LIFE" in html
    assert "/api/venues" in html


def test_pwa_manifest_endpoint(client):
    """GET /manifest.json returns valid Progressive Web App metadata."""
    res = client.get("/manifest.json")
    assert res.status_code == 200
    data = res.get_json()
    assert data["short_name"] == "DFW Poker"
    assert data["display"] == "standalone"
