# poker_bankroll_analyzer/routes.py
from datetime import datetime, timedelta, timezone
import jwt
from flask import Blueprint, current_app, jsonify, request, g
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import User
from .decorators import require_auth

# Creates the department blueprint
# "poker_api" is its name, and __name__ helps my Flask locate its assets.
poker_blueprint = Blueprint("poker_api", __name__)

# Route 1: simple status route to this blueprint department
@poker_blueprint.route("/status", methods=["GET"])
def get_status():
    # Return a simple JSON response to prove the route works
    return jsonify({
        "status": "online",
        "message": "Poker API blueprint is successfully wired"
    })

# Route 2: A welcome dashboard message
@poker_blueprint.route("/welcome", methods=["GET"])
def get_welcome():
    return jsonify({
        "greeting": "Welcome to your Personal Performance Tracker!",
        "greeting_a": "Here is where you redefine your poker journey",
        "tip": "Rememer to separate your freerolls from your cash buy-ins"
    })

# Route 3: A quick mock summary payload
@poker_blueprint.route("/mock-summary", methods=["GET"])
def get_mock_summary():
    return jsonify({
        "total_sessions": 0,
        "net_profit": 0.00,
        "status": "No games logged yet."
    })

# Route 4: My official health check
@poker_blueprint.route("/health", methods=["GET"])
def get_health():
    #Returns a crisp JSON object and an explicit HTTP 200 success code
    return jsonify({
        "status": "healthy",
        "database_fallback": "active",
        "environment": "operational"
    }), 200

# 5. USER REGISTRATION ROUTE (WITH VALIDATION BOUNCER)
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
    new_user = User(username=username, password_hash=hashed_pw)

    db.session.add(new_user)
    db.session.commit()
    
    # If both pass the bouncer, return safe public field (201 Created)
    return jsonify({
        "id": new_user.id,
        "username": new_user.username,
        "created_at": new_user.created_at.isoformat()
    }), 201

# 6. USER LOGIN VERIFICATION ROUTE 
@poker_blueprint.route("/auth/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

    # Simple upfront presense validation
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

    # Signs the token using our secret key from config and the HS256 algorith
    secret_key = current_app.config["JWT_SECRET_KEY"]
    access_token = jwt.encode(payload, secret_key, algorithm="HS256")

    return jsonify({
        "access_token": access_token
    }), 200

# 7. The new token Security Guard
@poker_blueprint.route("/auth/me", methods=["GET"])
@require_auth
def get_current_user():
    """"Return the profile of the currently authenticated user."""
    # Look up the user using the ID save by @require_auth
    user = db.session.get(User, g.current_user_id)

    # Edge case: Valid token, but the user was deleted from the database
    if not user:
        return jsonify({
            "code": "NOT_FOUND",
            "message": "User not found."
        }), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }), 200

# 8. User Profile Read Route w(Token-isolated)
@poker_blueprint.route("/users/me", methods=["GET"])
@require_auth
def get_user_profile():
    """Return the safe public profile of the currenty logged-in user."""
    # Pick the user stricly from the verified JWT token. Never from URL or body.
    user = db.session.get(User, g.current_user_id)

    if not user:
        return jsonify({
            "code": "NOT_FOUND",
            "message": "User not found."
        }), 404

    #Explicitly whitelist safe public fields (never exposing password_hash)
    return jsonify({
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }), 200

# 9. User Profile Update Route(Allowlist-Protected)
@poker_blueprint.route("/users/me", methods=["PATCH"])
@require_auth
def update_user_profile():
    """Safely update allowlisted profile fields for the currently logged-in user."""
    user = db.session.get(User, g.current_user_id)

    if not user:
        return jsonify({
            "code": "NOT_FOUND",
            "message": "User not found."
        }), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a valid JSON object."
        }), 400

    # Strict allowlist: Only 'username' can ever be updated here
    allowed_fields = {"username"}
    forbidden_fields = set(data.keys()) - allowed_fields
    if forbidden_fields:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Only 'username' can be updated on this endpoint."
    }), 400

    # Validate the new username using the same bouncer rules as registration
    new_username = data.get("username")
    if not new_username or not isinstance(new_username, str):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username is required."
        }), 400

    new_username = new_username.strip()
    if len(new_username) < 3 or len(new_username) > 30:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username must be between 3 and 30 characters long."
        }), 400

    # Check if a DIFFERENT user already owns this username (allow keeping your own current name)
    existing_user = User.query.filter_by(username=new_username).first()
    if existing_user and existing_user.id != user.id:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Username is already taken."
        }), 409

    # Apply the safe update and save to SQLite
    user.username = new_username
    db.session.commit()

    return jsonify({
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }), 200
