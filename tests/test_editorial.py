# tests/test_editorial.py
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


def test_admin_publishes_player_spotlight_and_blocks_regular_player(client):
    """Admin can publish a North Dallas Player Spotlight linked to a verified player."""
    with client.application.app_context():
        admin = User(
            username="editor_in_chief",
            password_hash=generate_password_hash("AdminPass123!"),
            role="admin",
        )
        grinder = User(
            username="north_dallas_pro",
            password_hash=generate_password_hash("PlayerPass123!"),
            role="player",
            display_name="Marcus 'River King' Vance",
            home_room="Texas Card House Dallas",
            is_verified=True,
        )
        db.session.add_all([admin, grinder])
        db.session.commit()
        grinder_id = grinder.id

    admin_token = _login(client, "editor_in_chief", "AdminPass123!")
    player_token = _login(client, "north_dallas_pro", "PlayerPass123!")

    # Regular player cannot publish articles -> 403 Forbidden
    blocked = client.post(
        "/api/articles",
        headers={"Authorization": f"Bearer {player_token}"},
        json={"title": "My Own Post", "body": "Trying to publish without admin role."},
    )
    assert blocked.status_code == 403

    # Admin publishes North Dallas Player Spotlight with affiliate link
    pub_res = client.post(
        "/api/articles",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "North Dallas Player Spotlight: Marcus Vance",
            "category": "spotlight",
            "summary": "How Marcus crushes 2/5 PLO on Harry Hines.",
            "body": "Full interview with North Dallas grinder Marcus Vance...",
            "affiliate_url": "https://gtowizard.com",
            "featured_user_id": grinder_id,
        },
    )
    assert pub_res.status_code == 201
    created = pub_res.get_json()
    assert created["slug"] == "north-dallas-player-spotlight-marcus-vance"
    assert created["featured_player"]["display_name"] == "Marcus 'River King' Vance"
    assert created["featured_player"]["is_verified"] is True

    # Public feed & slug lookup work without auth
    feed_res = client.get("/api/articles?category=spotlight")
    assert feed_res.status_code == 200
    assert feed_res.get_json()["total"] == 1

    slug_res = client.get("/api/articles/north-dallas-player-spotlight-marcus-vance")
    assert slug_res.status_code == 200
    assert "gtowizard.com" in slug_res.get_json()["affiliate_url"]


def test_sponsor_banners_create_filter_and_toggle(client):
    """Admin can create and toggle local DFW sponsor banners; public endpoint filters active slots."""
    with client.application.app_context():
        admin = User(
            username="ad_manager",
            password_hash=generate_password_hash("AdminPass123!"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()

    admin_token = _login(client, "ad_manager", "AdminPass123!")

    b1 = client.post(
        "/api/sponsors",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "sponsor_name": "Harry Hines Sports Grill",
            "tagline": "20% off late-night food for DFW poker players",
            "image_url": "https://example.com",
            "target_url": "https://example.com",
            "placement": "top_banner",
        },
    )
    assert b1.status_code == 201
    banner_id = b1.get_json()["id"]

    # Active top_banner shows up publicly
    public_banners = client.get("/api/sponsors?placement=top_banner").get_json()
    assert public_banners["total"] == 1
    assert public_banners["items"][0]["sponsor_name"] == "Harry Hines Sports Grill"

    # Admin pauses banner -> public endpoint hides it immediately
    pause_res = client.patch(
        f"/api/sponsors/{banner_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_active": False},
    )
    assert pause_res.status_code == 200
    assert client.get("/api/sponsors?placement=top_banner").get_json()["total"] == 0


def test_lightweight_venue_checkin_live_buzz(client):
    """Players can check in at a DFW venue and appear in active venue check-ins."""
    with client.application.app_context():
        seed_dfw_venues_data()
        grinder = User(
            username="shuffle_reg",
            password_hash=generate_password_hash("PlayerPass123!"),
            role="player",
            display_name="Big D Grinder",
        )
        db.session.add(grinder)
        db.session.commit()

    token = _login(client, "shuffle_reg", "PlayerPass123!")

    checkin_res = client.post(
        "/api/venues/1/check-in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert checkin_res.status_code == 201
    assert checkin_res.get_json()["venue_name"] == "Texas Card House Dallas"

    active_res = client.get("/api/venues/1/check-ins")
    assert active_res.status_code == 200
    body = active_res.get_json()
    assert body["active_count"] == 1
    assert body["players"][0]["display_name"] == "Big D Grinder"
