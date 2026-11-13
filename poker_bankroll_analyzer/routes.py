# poker_bankroll_analyzer/routes.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import jwt
from flask import Blueprint, current_app, jsonify, request, g
from werkzeug.security import generate_password_hash
from .extensions import db
from .models import User, PokerSession
from .decorators import require_auth, require_role

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

# 10. Admin-Only Diagnostic Route (Two-Door Security Airlock)
@poker_blueprint.route("/admin/ping", methods=["GET"])
@require_auth
@require_role("admin")
def admin_ping():
    """Simple admin-only endpoint proving role-based accesss control."""
    return jsonify({
        "status": "ok",
        "message": "Welcome to the admin control room.",
        "admin_id": g.current_user_id,
        "role": g.current_user_role
    }), 200

# 11. Create Poker Session Route (Token-Owned)
@poker_blueprint.route("/poker-sessions", methods=["POST"])
@require_auth
def create_poker_session():
    """Log a new poker session owned strictly by the authenticated user."""
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a valid JSON object."
        }), 400

    # 1. Validate required field: game_type
    game_type = data.get("game_type")
    if not game_type or not isinstance(game_type, str) or not game_type.strip():
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "game_type is required."
        }), 400
    game_type = game_type.strip()
    if len(game_type) > 50:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "game_type must be 50 characters or fewer."
        }), 400

    # 2. Validate required money fields: buy_in and cash_out
    if "buy_in" not in data or "cash_out" not in data:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "buy_in and cash_out are required."
        }), 400

    try:
        buy_in = Decimal(str(data["buy_in"]))
        cash_out = Decimal(str(data["cash_out"]))
    except (InvalidOperation, TypeError, ValueError):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "buy_in and cash_out must be valid numbers."
        }), 400

    if buy_in < 0 or cash_out < 0:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "buy_in and cash_out cannot be negative."
        }), 400

    # 3. Validate optional played_at (defaults to current UTC if omitted)
    played_at = datetime.now(timezone.utc)
    if data.get("played_at") is not None:
        if not isinstance(data["played_at"], str):
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": "played_at must be an ISO-8601 date/time string."
            }), 400
        try:
            played_at = datetime.fromisoformat(data["played_at"])
        except ValueError:
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": "played_at must be a valid ISO-8601 date/time string."
            }), 400

    # 4. Validate optional duration_minutes if provided
    duration_minutes = data.get("duration_minutes")
    if duration_minutes is not None:
        if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes < 0:
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": "duration_minutes must be a non-negative integer."
            }), 400

    # 5. Build session with user_id set STRICTLY from g.current_user_id (never from JSON)
    new_session = PokerSession(
        user_id=g.current_user_id,
        game_type=game_type,
        buy_in=buy_in,
        cash_out=cash_out,
        played_at=played_at,
        stakes=data.get("stakes").strip() if isinstance(data.get("stakes"), str) else None,
        location=data.get("location").strip() if isinstance(data.get("location"), str) else None,
        duration_minutes=duration_minutes,
        notes=data.get("notes").strip() if isinstance(data.get("notes"), str) else None,
    )

    db.session.add(new_session)
    db.session.commit()

    net_profit = float(new_session.cash_out - new_session.buy_in)

    return jsonify({
        "id": new_session.id,
        "user_id": new_session.user_id,
        "game_type": new_session.game_type,
        "buy_in": float(new_session.buy_in),
        "cash_out": float(new_session.cash_out),
        "net_profit": net_profit,
        "played_at": new_session.played_at.isoformat(),
        "created_at": new_session.created_at.isoformat(),
        "stakes": new_session.stakes,
        "location": new_session.location,
        "duration_minutes": new_session.duration_minutes,
        "notes": new_session.notes,
    }), 201

# 12. List Poker Sessions Rout (Owner-Filtered)
@poker_blueprint.route("/poker-sessions", methods=["GET"])
@require_auth
def list_poker_sessions():
    """Return all poker sessions owned by the currently authenticated user."""
    sessions = PokerSession.query.filter_by(user_id=g.current_user_id).all()

    results = [
        {
            "id": session.id,
            "user_id": session.user_id,
            "game_type": session.game_type,
            "buy_in": float(session.buy_in),
            "cash_out": float(session.cash_out),
            "net_profit": float(session.cash_out - session.buy_in),
            "played_at": session.played_at.isoformat(),
            "created_at": session.created_at.isoformat(),
            "stakes": session.stakes,
            "location": session.location,
            "duration_minutes": session.duration_minutes,
            "notes": session.notes
        }
        for session in sessions
    ]

    return jsonify(results), 200