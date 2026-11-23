# tests/test_sessions.py
import pytest
from poker_bankroll_analyzer import create_app
from poker_bankroll_analyzer.extensions import db


@pytest.fixture
def client():
    """Spin up a fresh, isolated in-memory test app for every single test."""
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def register_and_login(client, username="poker_pro", password="securepassword123"):
    """Helper to register a player and return their Bearer header dict."""
    client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    token = login_res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_sample_session(client, headers, **overrides):
    """Helper to create a valid poker session and return the response."""
    payload = {
        "game_type": "2/5 NLHE",
        "buy_in": 500,
        "cash_out": 920,
        "played_at": "2026-11-15T16:30:00+00:00",
        "stakes": "2/5",
        "location": "Texas Card House Dallas",
        "duration_minutes": 210,
        "notes": "Walkthrough CRUD session",
    }
    payload.update(overrides)
    return client.post("/api/poker-sessions", json=payload, headers=headers)


# ---------------------------------------------------------------------------
# 1. OWNER HAPPY-PATH CRUD TESTS
# ---------------------------------------------------------------------------

def test_owner_full_crud_lifecycle(client):
    """Owner can create, read, partially update, re-read, and delete a session."""
    headers = register_and_login(client, username="hero_player")

    # 1. Create (POST -> 201)
    create_res = create_sample_session(client, headers)
    created = create_res.get_json()
    assert create_res.status_code == 201
    assert created["game_type"] == "2/5 NLHE"
    assert created["net_profit"] == 420.0
    session_id = created["id"]

    # 2. Read by ID (GET -> 200)
    get_res = client.get(f"/api/poker-sessions/{session_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.get_json()["id"] == session_id

    # 3. Partial Update (PATCH -> 200 with recalculated net_profit)
    patch_res = client.patch(
        f"/api/poker-sessions/{session_id}",
        json={"cash_out": 1050, "notes": "Updated session notes"},
        headers=headers,
    )
    patched = patch_res.get_json()
    assert patch_res.status_code == 200
    assert patched["cash_out"] == 1050.0
    assert patched["net_profit"] == 550.0
    assert patched["notes"] == "Updated session notes"

    # 4. Re-read to confirm persistence
    reget_res = client.get(f"/api/poker-sessions/{session_id}", headers=headers)
    assert reget_res.status_code == 200
    assert reget_res.get_json()["cash_out"] == 1050.0

    # 5. Delete (DELETE -> 204) and confirm 404 afterward
    del_res = client.delete(f"/api/poker-sessions/{session_id}", headers=headers)
    assert del_res.status_code == 204
    assert del_res.data == b""

    after_del = client.get(f"/api/poker-sessions/{session_id}", headers=headers)
    assert after_del.status_code == 404
    assert after_del.get_json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 2. OWNERSHIP, AUTH & MISSING-RESOURCE EDGE CASES
# ---------------------------------------------------------------------------

def test_unauthenticated_access_returns_401(client):
    """Requests without an Authorization header return 401 UNAUTHORIZED."""
    owner_headers = register_and_login(client, username="owner_one")
    session_id = create_sample_session(client, owner_headers).get_json()["id"]

    res = client.get(f"/api/poker-sessions/{session_id}")
    assert res.status_code == 401
    assert res.get_json()["code"] == "UNAUTHORIZED"


def test_cross_user_access_returns_non_enumerating_404(client):
    """User B gets consistent 404 NOT_FOUND on GET, PATCH, and DELETE for User A's session."""
    user_a = register_and_login(client, username="user_alpha")
    user_b = register_and_login(client, username="user_beta")

    session_id = create_sample_session(client, user_a).get_json()["id"]

    # Cross-user GET -> 404
    get_res = client.get(f"/api/poker-sessions/{session_id}", headers=user_b)
    assert get_res.status_code == 404
    assert get_res.get_json()["code"] == "NOT_FOUND"

    # Cross-user PATCH -> 404
    patch_res = client.patch(
        f"/api/poker-sessions/{session_id}",
        json={"notes": "Cross-user hijack attempt"},
        headers=user_b,
    )
    assert patch_res.status_code == 404
    assert patch_res.get_json()["code"] == "NOT_FOUND"

    # Cross-user DELETE -> 404
    del_res = client.delete(f"/api/poker-sessions/{session_id}", headers=user_b)
    assert del_res.status_code == 404
    assert del_res.get_json()["code"] == "NOT_FOUND"

    # Confirm User A's session is still intact
    owner_check = client.get(f"/api/poker-sessions/{session_id}", headers=user_a)
    assert owner_check.status_code == 200
    assert owner_check.get_json()["notes"] == "Walkthrough CRUD session"


def test_missing_session_id_returns_404(client):
    """Requesting a non-existent session ID returns 404 NOT_FOUND."""
    headers = register_and_login(client, username="seeker")

    res = client.get("/api/poker-sessions/999999", headers=headers)
    assert res.status_code == 404
    assert res.get_json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 3. VALIDATION & ALLOWLIST ENFORCEMENT TESTS (400 VALIDATION_ERROR)
# ---------------------------------------------------------------------------

def test_create_validation_errors_return_400(client):
    """Invalid or missing fields on POST return 400 VALIDATION_ERROR."""
    headers = register_and_login(client, username="validator_user")

    # Missing game_type
    res_missing = client.post(
        "/api/poker-sessions",
        json={"buy_in": 100, "cash_out": 150},
        headers=headers,
    )
    assert res_missing.status_code == 400
    assert res_missing.get_json()["code"] == "VALIDATION_ERROR"

    # Non-numeric buy_in
    res_bad_num = client.post(
        "/api/poker-sessions",
        json={"game_type": "1/2 NLHE", "buy_in": "not-a-number", "cash_out": 150},
        headers=headers,
    )
    assert res_bad_num.status_code == 400
    assert res_bad_num.get_json()["code"] == "VALIDATION_ERROR"

    # Negative buy_in
    res_neg = client.post(
        "/api/poker-sessions",
        json={"game_type": "1/2 NLHE", "buy_in": -50, "cash_out": 150},
        headers=headers,
    )
    assert res_neg.status_code == 400
    assert res_neg.get_json()["code"] == "VALIDATION_ERROR"


def test_patch_blocks_forbidden_fields_and_invalid_values(client):
    """PATCH rejects user_id tampering and bad numbers with 400 VALIDATION_ERROR."""
    headers = register_and_login(client, username="patch_guard")
    session_id = create_sample_session(client, headers).get_json()["id"]

    # Attempt to overwrite user_id
    res_forbidden = client.patch(
        f"/api/poker-sessions/{session_id}",
        json={"user_id": 999},
        headers=headers,
    )
    assert res_forbidden.status_code == 400
    assert res_forbidden.get_json()["code"] == "VALIDATION_ERROR"

    # Invalid cash_out string
    res_bad_cash = client.patch(
        f"/api/poker-sessions/{session_id}",
        json={"cash_out": "oops"},
        headers=headers,
    )
    assert res_bad_cash.status_code == 400
    assert res_bad_cash.get_json()["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 4. PAGINATION & OWNER LIST ISOLATION TESTS
# ---------------------------------------------------------------------------

def test_pagination_pages_bounds_and_owner_scoping(client):
    """GET /api/poker-sessions paginates owner sessions cleanly and validates query params."""
    user_a = register_and_login(client, username="grinder_a")
    user_b = register_and_login(client, username="grinder_b")

    # Seed 23 sessions for User A and 2 sessions for User B
    for i in range(1, 24):
        create_sample_session(client, user_a, buy_in=100, cash_out=100 + i * 10)
    for _ in range(2):
        create_sample_session(client, user_b, buy_in=200, cash_out=300)

    # Page 1 (per_page=10) -> 10 items, total=23, pages=3
    p1 = client.get("/api/poker-sessions?page=1&per_page=10", headers=user_a).get_json()
    assert len(p1["items"]) == 10
    assert p1["page"] == 1
    assert p1["per_page"] == 10
    assert p1["total"] == 23
    assert p1["pages"] == 3

    # Last page (page=3) -> remaining 3 items
    p3 = client.get("/api/poker-sessions?page=3&per_page=10", headers=user_a).get_json()
    assert len(p3["items"]) == 3
    assert p3["page"] == 3

    # Past-end page (page=4) -> empty items list, valid metadata
    p4_res = client.get("/api/poker-sessions?page=4&per_page=10", headers=user_a)
    p4 = p4_res.get_json()
    assert p4_res.status_code == 200
    assert p4["items"] == []
    assert p4["page"] == 4
    assert p4["total"] == 23

    # Invalid per_page=999 -> 400 VALIDATION_ERROR
    bad_page = client.get("/api/poker-sessions?per_page=999", headers=user_a)
    assert bad_page.status_code == 400
    assert bad_page.get_json()["code"] == "VALIDATION_ERROR"

    # User B only sees their own 2 sessions
    b_list = client.get("/api/poker-sessions", headers=user_b).get_json()
    assert b_list["total"] == 2
    assert len(b_list["items"]) == 2


def _auth_header_for(client, username, password="Password123!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    login_res = client.post("/api/auth/login", json={"username": username, "password": password})
    token = login_res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_session_venue_link_and_expenses_calculation(client):
    """Linking a session to a PokerVenue with expenses computes true_net_profit accurately."""
    from poker_bankroll_analyzer.venue_routes import seed_dfw_venues_data

    with client.application.app_context():
        seed_dfw_venues_data()

    headers_a = _auth_header_for(client, "venue_grinder_a")

    # Valid venue_id=1 (Texas Card House Dallas) + $35 food/tip expenses
    create_res = client.post(
        "/api/poker-sessions",
        headers=headers_a,
        json={
            "venue_id": 1,
            "game_type": "NLH",
            "stakes": "1/2",
            "buy_in": 300,
            "cash_out": 650,
            "expenses": 35,
            "duration_minutes": 300,
        },
    )
    assert create_res.status_code == 201
    data = create_res.get_json()
    assert data["venue_id"] == 1
    assert data["venue_name"] == "Texas Card House Dallas"
    assert data["net_profit"] == 350.0
    assert data["expenses"] == 35.0
    assert data["true_net_profit"] == 315.0

    # Non-existent venue_id -> 404 NOT_FOUND
    bad_venue = client.post(
        "/api/poker-sessions",
        headers=headers_a,
        json={"venue_id": 9999, "game_type": "NLH", "buy_in": 100, "cash_out": 200},
    )
    assert bad_venue.status_code == 404


def test_poker_session_stats_analytics_and_user_isolation(client):
    """GET /api/poker-sessions/stats computes hourly rate, true profit, and venue breakdown."""
    headers_a = _auth_header_for(client, "stats_grinder_a")
    headers_b = _auth_header_for(client, "stats_grinder_b")

    # User A logs two sessions totaling 6 hours (360 mins), +$400 table profit, 40expenses->+360 true net ($60/hr)
    client.post(
        "/api/poker-sessions",
        headers=headers_a,
        json={
            "game_type": "NLH",
            "location": "Shuffle 214",
            "buy_in": 200,
            "cash_out": 500,
            "expenses": 20,
            "duration_minutes": 240,
        },
    )
    client.post(
        "/api/poker-sessions",
        headers=headers_a,
        json={
            "game_type": "PLO",
            "location": "Poker House Dallas",
            "buy_in": 300,
            "cash_out": 400,
            "expenses": 20,
            "duration_minutes": 120,
        },
    )

    # User B logs a huge session that must NOT bleed into User A's stats
    client.post(
        "/api/poker-sessions",
        headers=headers_b,
        json={
            "game_type": "NLH",
            "location": "Shuffle 214",
            "buy_in": 1000,
            "cash_out": 5000,
            "duration_minutes": 60,
        },
    )

    stats_res = client.get("/api/poker-sessions/stats", headers=headers_a)
    assert stats_res.status_code == 200
    stats = stats_res.get_json()

    assert stats["total_sessions"] == 2
    assert stats["gross_table_profit"] == 400.0
    assert stats["total_expenses"] == 40.0
    assert stats["true_net_profit"] == 360.0
    assert stats["total_hours"] == 6.0
    assert stats["hourly_rate"] == 60.0
    assert len(stats["by_venue"]) == 2
    assert stats["by_venue"][0]["venue"] == "Shuffle 214"
    assert stats["by_venue"][0]["true_net_profit"] == 280.0

