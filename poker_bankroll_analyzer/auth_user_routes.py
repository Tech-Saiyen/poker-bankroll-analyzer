# poker_bankroll_analyzer/auth_user_routes.py
from datetime import datetime, timedelta, timezone
import jwt
from flask import current_app, jsonify, request, g
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import User, VALID_USER_ROLES
from .decorators import require_auth, require_role
from .routes import poker_blueprint

# 1. USER REGISTRATION ROUTE (WITH VALIDATION BOUNCER)
@poker_blueprint.route("/auth/register", methods=["POST"])
def register_user():
   # Open the incoming JSON envelope safely (silent=True prevents ugly HTML crashes with bad JSON)
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

   # --- BOUNCER CHECK 1: Validate Username ---
    if not username or not isinstance(username, str):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username is required."
        }), 400

   # Strips all accidental leading/trailing spaces before checking the length
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username must be between 3 and 30 characters long."
        }), 400

   # --- BOUNCER CHECK 2: Validate Password ---
    if not password or not isinstance(password, str):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Password is required."
        }), 400

    if len(password) < 8 or len(password) > 128:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Password must be between 8 and 128 characters long."
        }), 400

   # --- BOUNCER CHECK 3: Check For Duplicate Username ---
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username is already taken."
        }), 409

   # Hash Password and Create User
    hashed_pw = generate_password_hash(password)
    new_user = User(username=username, password_hash=hashed_pw, role="player")

    db.session.add(new_user)
    db.session.commit()

   # If both pass the bouncer, return safe public field (201 Created)
    return jsonify({
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
        "created_at": new_user.created_at.isoformat()
    }), 201

# 2. USER LOGIN VERIFICATION ROUTE
@poker_blueprint.route("/auth/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

   # Simple upfront presence validation
    if not username or not password:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username and password are required."
        }), 400

   # Search for the user records by their unique nickname
    user = User.query.filter_by(username=username.strip()).first()
   # If the user doesn't exist, or the password check fails -> Denied
    if not user or not user.check_password(password):
        return jsonify({
            "code": "UNAUTHORIZED",
            "message": "Invalid username or password."
        }), 401

   # Calculate the future expiration timestamp using UTC and the config value
    expires_minutes = current_app.config["JWT_ACCESS_TOKEN_EXPIRES_MINUTES"]
    expiration_time = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

   # Builds the wristband payload
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": expiration_time
    }

   # Signs the token using our secret key from config and the HS256 algorithm
    secret_key = current_app.config["JWT_SECRET_KEY"]
    access_token = jwt.encode(payload, secret_key, algorithm="HS256")

    return jsonify({
        "access_token": access_token
    }), 200

# 3. The new token Security Guard
@poker_blueprint.route("/auth/me", methods=["GET"])
@require_auth
def get_current_user():
    """Return the profile of the currently authenticated user."""
   # Look up the user using the ID saved by @require_auth
    user = db.session.get(User, g.current_user_id)
   # Edge case: Valid token, but the user was deleted from the database
    if not user:
        return jsonify({"code": "NOT_FOUND", "message": "User not found."}), 404

    return jsonify(user.to_public_dict()), 200

# 4. User Profile Read Route (Token-isolated)
@poker_blueprint.route("/users/me", methods=["GET"])
@require_auth
def get_user_profile():
    """Return the safe public profile of the currently logged-in user."""
   # Pick the user strictly from the verified JWT token. Never from URL or body.
    user = db.session.get(User, g.current_user_id)
    if not user:
        return jsonify({"code": "NOT_FOUND", "message": "User not found."}), 404

    return jsonify(user.to_public_dict()), 200


@poker_blueprint.route("/users/me", methods=["PATCH"])
@require_auth
def update_user_profile():
    """Safely update allowlisted profile fields for the currently logged-in user."""
    user = db.session.get(User, g.current_user_id)
    if not user:
        return jsonify({"code": "NOT_FOUND", "message": "User not found."}), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a valid JSON object."
        }), 400

    # Strict allowlist: players can edit their own profile details, NEVER role or is_verified
    allowed_fields = {
        "username",
        "display_name",
        "bio",
        "home_room",
        "style_tags",
        "avatar_url",
        "hendonmob_url",
        "external_player_id",
    }
    forbidden_fields = set(data.keys()) - allowed_fields
    if forbidden_fields:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": f"Fields cannot be updated here: {', '.join(sorted(forbidden_fields))}."
        }), 400

    if "username" in data:
        new_username = data.get("username")
        if not new_username or not isinstance(new_username, str):
            return jsonify({"code": "VALIDATION_ERROR", "message": "Username is required."}), 400
        new_username = new_username.strip()
        if len(new_username) < 3 or len(new_username) > 30:
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": "Username must be between 3 and 30 characters long."
            }), 400
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != user.id:
            return jsonify({"code": "VALIDATION_ERROR", "message": "Username is already taken."}), 409
        user.username = new_username

    optional_string_fields = {
        "display_name": 80,
        "bio": 2000,
        "home_room": 100,
        "style_tags": 120,
        "avatar_url": 255,
        "hendonmob_url": 255,
        "external_player_id": 80,
    }
    for field, max_len in optional_string_fields.items():
        if field in data:
            val = data[field]
            if val is None:
                setattr(user, field, None)
            elif not isinstance(val, str):
                return jsonify({
                    "code": "VALIDATION_ERROR",
                    "message": f"{field} must be a string or null."
                }), 400
            else:
                cleaned = val.strip()
                if len(cleaned) > max_len:
                    return jsonify({
                        "code": "VALIDATION_ERROR",
                        "message": f"{field} must be {max_len} characters or fewer."
                    }), 400
                setattr(user, field, cleaned or None)

    db.session.commit()
    return jsonify(user.to_public_dict()), 200


@poker_blueprint.route("/players/<int:user_id>", methods=["GET"])
def get_public_player_profile(user_id):
    """Public player card for DFW leaderboards, spotlights, and profiles."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"code": "NOT_FOUND", "message": "Player not found."}), 404

    return jsonify(user.to_public_dict()), 200


@poker_blueprint.route("/admin/users/<int:user_id>", methods=["PATCH"])
@require_auth
@require_role("admin")
def admin_update_user_governance(user_id):
    """Admin-only endpoint to assign platform roles or verify player badges."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"code": "NOT_FOUND", "message": "User not found."}), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a valid JSON object."
        }), 400

    allowed_admin_fields = {"role", "is_verified"}
    forbidden_fields = set(data.keys()) - allowed_admin_fields
    if forbidden_fields:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": f"Admin governance only allows: {', '.join(sorted(allowed_admin_fields))}."
        }), 400

    if "role" in data:
        new_role = data["role"]
        if new_role not in VALID_USER_ROLES:
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": f"Role must be one of: {', '.join(sorted(VALID_USER_ROLES))}."
            }), 400
        user.role = new_role

    if "is_verified" in data:
        if not isinstance(data["is_verified"], bool):
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": "is_verified must be a boolean (true or false)."
            }), 400
        user.is_verified = data["is_verified"]

    db.session.commit()
    return jsonify(user.to_public_dict()), 200