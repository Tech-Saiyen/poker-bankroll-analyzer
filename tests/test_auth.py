# tests/test_auth.py
import pytest
from werkzeug.security import generate_password_hash
from poker_bankroll_analyzer import create_app
from poker_bankroll_analyzer.extensions import db
from poker_bankroll_analyzer.models import User


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
    """Helper to register a regular player and return their JWT access token."""
    client.post(
        "/api/auth/register",
        json={"username": username, "password": password}
    )
    login_res = client.post(
        "/api/auth/login",
        json={"username": username, "password": password}
    )
    return login_res.get_json()["access_token"]


# ---------------------------------------------------------------------------
# 1. REGISTRATION & PASSWORD HASHING TESTS
# ---------------------------------------------------------------------------

def test_register_success_hides_password_hash(client):
    """Registering a new player returns 201 and never exposes password_hash."""
    res = client.post(
        "/api/auth/register",
        json={"username": "rounders_mike", "password": "securepassword123"}
    )
    data = res.get_json()

    assert res.status_code == 201
    assert data["username"] == "rounders_mike"
    assert "id" in data
    assert "password_hash" not in data


def test_register_duplicate_username_rejected(client):
    """Two players cannot claim the exact same username (returns 409)."""
    client.post(
        "/api/auth/register",
        json={"username": "rounders_mike", "password": "securepassword123"}
    )
    res = client.post(
        "/api/auth/register",
        json={"username": "rounders_mike", "password": "anotherpassword123"}
    )
    data = res.get_json()

    assert res.status_code == 409
    assert data["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 2. LOGIN & WRONG-PASSWORD ATTACK TESTS
# ---------------------------------------------------------------------------

def test_login_success_mints_jwt(client):
    """Valid credentials return 200 and an access_token wristband."""
    client.post(
        "/api/auth/register",
        json={"username": "rounders_mike", "password": "securepassword123"}
    )
    res = client.post(
        "/api/auth/login",
        json={"username": "rounders_mike", "password": "securepassword123"}
    )
    data = res.get_json()

    assert res.status_code == 200
    assert "access_token" in data


def test_login_wrong_password_rejected(client):
    """Wrong password fails check_password_hash and returns 401 without a token."""
    client.post(
        "/api/auth/register",
        json={"username": "rounders_mike", "password": "securepassword123"}
    )
    res = client.post(
        "/api/auth/login",
        json={"username": "rounders_mike", "password": "wrong_password_guess"}
    )
    data = res.get_json()

    assert res.status_code == 401
    assert data["code"] == "UNAUTHORIZED"
    assert "access_token" not in data


# ---------------------------------------------------------------------------
# 3. @require_auth DOOR 1 GUARD TESTS
# ---------------------------------------------------------------------------

def test_protected_route_missing_token_returns_401(client):
    """Knocking on /api/users/me with no Authorization header returns 401."""
    res = client.get("/api/users/me")
    data = res.get_json()

    assert res.status_code == 401
    assert data["code"] == "UNAUTHORIZED"


def test_protected_route_fake_token_returns_401(client):
    """Knocking on /api/users/me with a forged token returns 401."""
    res = client.get(
        "/api/users/me",
        headers={"Authorization": "Bearer fake.tampered.token"}
    )
    data = res.get_json()

    assert res.status_code == 401
    assert data["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# 4. TOKEN-ISOLATED PROFILE & ALLOWLIST PROTECTION TESTS
# ---------------------------------------------------------------------------

def test_profile_update_blocks_role_escalation(client):
    """Sending role='admin' in PATCH /api/users/me is blocked with 400."""
    token = register_and_login(client, username="sneaky_player")

    res = client.patch(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "sneaky_player", "role": "admin"}
    )
    data = res.get_json()

    assert res.status_code == 400
    assert data["code"] == "VALIDATION_ERROR"


def test_two_users_remain_strictly_isolated(client):
    """Updating Player A never modifies Player B's account."""
    token_a = register_and_login(client, username="player_alpha")
    token_b = register_and_login(client, username="player_beta")

    # Player A updates their own username
    patch_res = client.patch(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"username": "player_alpha_updated"}
    )
    assert patch_res.status_code == 200

    # Player B's profile must remain completely untouched
    get_b = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert get_b.status_code == 200
    assert get_b.get_json()["username"] == "player_beta"


# ---------------------------------------------------------------------------
# 5. @require_role("admin") DOOR 2 GUARD TESTS (401 vs 403 vs 200)
# ---------------------------------------------------------------------------

def test_admin_route_rejects_regular_user_with_403(client):
    """A valid regular user token passes Door 1 but is blocked at Door 2 with 403."""
    user_token = register_and_login(client, username="regular_grinder")

    res = client.get(
        "/api/admin/ping",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    data = res.get_json()

    assert res.status_code == 403
    assert data["code"] == "FORBIDDEN"


def test_admin_route_allows_admin_user_with_200(client):
    """A database-verified admin user passes both doors and receives 200 OK."""
    # Seed an admin user directly inside the temporary test database
    with client.application.app_context():
        admin = User(
            username="vault_admin",
            password_hash=generate_password_hash("AdminSecret123!"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()

    login_res = client.post(
        "/api/auth/login",
        json={"username": "vault_admin", "password": "AdminSecret123!"}
    )
    admin_token = login_res.get_json()["access_token"]

    res = client.get(
        "/api/admin/ping",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    data = res.get_json()

    assert res.status_code == 200
    assert data["status"] == "ok"
    assert data["role"] == "admin"



