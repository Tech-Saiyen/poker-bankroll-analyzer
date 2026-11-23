# tests/test_venues.py
import pytest
from werkzeug.security import generate_password_hash
from poker_bankroll_analyzer import create_app
from poker_bankroll_analyzer.extensions import db
from poker_bankroll_analyzer.models import User
from poker_bankroll_analyzer.venue_routes import seed_dfw_venues_data


@pytest.fixture
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def _login(client, username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    return res.get_json()["access_token"]


def test_seed_and_filter_dfw_venues(client):
    """Public /api/venues returns seeded DFW venues with featured rooms first and filters."""
    with client.application.app_context():
        added = seed_dfw_venues_data()
        assert added == 5
        # Calling a second time must be idempotent (0 duplicates added)
        assert seed_dfw_venues_data() == 0

    all_res = client.get("/api/venues?lat=32.91&lng=-96.89")
    assert all_res.status_code == 200
    body = all_res.get_json()
    assert body["total"] == 5
    assert body["items"][0]["name"] == "Texas Card House Dallas"
    assert body["items"][0]["is_featured"] is True
    assert "distance_miles" in body["items"][0]

    bar_res = client.get("/api/venues?venue_type=bar_league")
    assert bar_res.status_code == 200
    assert bar_res.get_json()["total"] == 1
    assert bar_res.get_json()["items"][0]["venue_type"] == "bar_league"


def test_room_manager_isolated_to_assigned_venue(client):
    """A room_manager can update their own venue's floor/stream, but gets 403 on other venues."""
    with client.application.app_context():
        seed_dfw_venues_data()
        admin = User(
            username="dfw_admin",
            password_hash=generate_password_hash("AdminPass123!"),
            role="admin",
        )
        manager = User(
            username="shuffle_floor",
            password_hash=generate_password_hash("ManagerPass123!"),
            role="player",
        )
        db.session.add_all([admin, manager])
        db.session.commit()
        manager_id = manager.id

    admin_token = _login(client, "dfw_admin", "AdminPass123!")

    # Admin promotes manager to room_manager for Venue 2 (Shuffle 214) and upgrades tier to pro
    gov_res = client.patch(
        f"/api/admin/users/{manager_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "room_manager", "tier": "pro", "managed_venue_id": 2},
    )
    assert gov_res.status_code == 200
    assert gov_res.get_json()["managed_venue_id"] == 2
    assert gov_res.get_json()["tier"] == "pro"

    mgr_token = _login(client, "shuffle_floor", "ManagerPass123!")

    # Allowed: update live game waitlist and stream URL on assigned Venue 2
    game_res = client.post(
        "/api/venues/2/games",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"game_type": "NLH", "stakes": "1/2", "open_tables": 5, "waitlist_count": 9},
    )
    assert game_res.status_code == 200
    assert game_res.get_json()["waitlist_count"] == 9

    stream_res = client.patch(
        "/api/venues/2",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"stream_url": "https://youtube.com"},
    )
    assert stream_res.status_code == 200
    assert "youtube.com" in stream_res.get_json()["stream_url"]

    # Blocked (403): manager tries to update Venue 1 (Texas Card House Dallas)
    forbidden_res = client.post(
        "/api/venues/1/games",
        headers={"Authorization": f"Bearer {mgr_token}"},
        json={"game_type": "NLH", "stakes": "1/2", "open_tables": 1, "waitlist_count": 0},
    )
    assert forbidden_res.status_code == 403
