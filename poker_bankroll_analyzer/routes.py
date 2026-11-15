# poker_bankroll_analyzer/routes.py
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, g
from .decorators import require_auth, require_role
from .errors import error_response
from .extensions import db
from .models import PokerSession

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
        return error_response("VALIDATION_ERROR", "Request body must be a valid JSON object.", 400)

    # 1. Validate required field: game_type
    game_type = data.get("game_type")
    if not game_type or not isinstance(game_type, str) or not game_type.strip():
        return error_response("VALIDATION_ERROR", "game_type is required.", 400)
    game_type = game_type.strip()
    if len(game_type) > 50:
        return error_response("VALIDATION_ERROR", "game_type must be 50 charactes or fewer.", 400)

    # 2. Validate required buy_in field: non-negative number
    if "buy_in" not in data or data["buy_in"] is None:
        return error_response("VALIDATION_ERROR", "buy-in is required.", 400)
    try:
        buy_in = Decimal(str(data["buy_in"]))
    except (InvalidOperation, TypeError, ValueError):
        return error_response("VALIDATION_ERROR", "buy-in must be a valid number.", 400)
    if buy_in < 0:
        return error_response("VALIDATION_ERROR", "buy_in cannot be negative.", 400)

    # 3. Validate required cash_out field: non-negative number
    if "cash_out" not in data or data["cash_out"] is None:
        return error_response("VALIDATION_ERROR", "cash_out is required.", 400)
    try:
        cash_out = Decimal(str(data["cash_out"]))
    except (InvalidOperation, TypeError, ValueError):
        return error_response("VALIDATION_ERROR", "cash_out must be a valid number.", 400)
    if cash_out < 0:
        return error_response("VALIDATION_ERROR", "cash_out cannot be negative.", 400)

    # $. Validate optional played_at (defaults to current UTC if omitted)
    played_at = datetime.now(timezone.utc)
    if data.get("played_at") is not None:
        if not isinstance(data["played_at"], str) or not data["played_at"].strip():
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string", 400)
        try:
            played_at = datetime.fromisoformat(data["played_at"])
        except ValueError:
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string", 400)

    # 5. Validate optional duration_minutes if provided(non-negative)
    duration_minutes = data.get("duration_minutes")
    if duration_minutes is not None:
        if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes < 0:
            return error_response("VALIDATION_ERROR", "duration_minutes must be a non-negative integer.", 400)

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

# 12. List Poker Sessions Route (Owner-Filtered + Pagination Validation)
@poker_blueprint.route("/poker-sessions", methods=["GET"])
@require_auth
def list_poker_sessions():
    """Return all poker sessions owned by the currently authenticated user."""
    raw_page = request.args.get("page", "1")
    raw_per_page = request.args.get("per_page", "10")

    try:
        page = int(raw_page)
        per_page = int(raw_per_page)
    except (TypeError, ValueError):
        return error_response(
            "VALIDATION_ERROR",
            "page and per_page must be valid integers.",
            400,
        )

    if page < 1:
        return error_response(
            "VALIDATION_ERROR",
            "page must be a positive integer (>=1).",
            400,
        )

    if per_page < 1 or per_page > 50:
        return error_response(
            "VALIDATION_ERROR",
            "per_page must be between 1 and 50.",
            400,
        )

    base_query = (
        PokerSession.query
        .filter_by(user_id=g.current_user_id)
        .order_by(PokerSession.id.asc())
    )

    pagination = base_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    items = [
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
        for session in pagination.items
    ]

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }), 200

# DRY Helper ..Don't Repeat Yourself master security ownership checkpoint
def get_owned_session_or_404(session_id):
    """Fetch a PokerSession only if it exists AND belongs to g.current_user_id."""
    session = db.session.get(PokerSession, session_id)

    if not session or session.user_id != g.current_user_id:
        return None, error_response("NOT_FOUND", "Poker session not found", 404)

    return session, None


# 13. Read a single poker session by ID route (OWNER-PROTECTED)
@poker_blueprint.route("/poker-sessions/<int:session_id>", methods=["GET"])
@require_auth
def get_poker_session(session_id):
    """Fetch a single poker session owned by the authenticated user."""
    session, error_response = get_owned_session_or_404(session_id)
    if error_response:
        return error_response

    return jsonify({
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
        "notes": session.notes,
    }), 200


# 14. UPDATE POKER SESSION BY ID ROUTE (OWNER-PROTECTED PARTIAL PATCH)
@poker_blueprint.route("/poker-sessions/<int:session_id>", methods=["PATCH"])
@require_auth
def update_poker_session(session_id):
    """Partially update a poker session owned by the authenticated user."""
    session, error_response.obj = get_owned_session_or_404(session_id)
    if error_response.obj:
        return error_response.obj

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return error_response("VALIDATION_ERROR", "Request body must be a valid JSON object.", 400)

    # Strict allowlist: never permit tampering with id, user_id, or created_at
    allowed_fields = {
        "game_type",
        "buy_in",
        "cash_out",
        "played_at",
        "stakes",
        "location",
        "duration_minutes",
        "notes",
    }
    forbidden_fields = [key for key in data.keys() if key not in allowed_fields]
    if forbidden_fields:
        return error_response(
            "VALIDATION_ERROR",
            f"Cannot update fields(s): {', '.join(forbidden_fields)}.",
            400,
        )

    # Validate & apply only the fields provided in the PATCH payload
    if "game_type" in data:
        game_type = data["game_type"]
        if not game_type or not isinstance(game_type, str) or not game_type.strip():
            return error_response("VALIDATION_ERROR", "game_type must be a non-empty string.", 400)
        game_type = game_type.strip()
        if len(game_type) > 50:
            return error_response("VALIDATION_ERROR", "game_type must be 50 characters or fewer.", 400)
        session.game_type = game_type

    if "buy_in" in data:
        if data["buy_in"] is None:
            return error_response("VALIDATION_ERROR", "buy-in cannot be null.", 400)
        try:
            buy_in = Decimal(str(data["buy_in"]))
        except (InvalidOperation, TypeError, ValueError):
            return error_response("VALIDATION_ERROR", "buy_in must be a valid number.", 400)
        if buy_in < 0:
            return error_response("VALIDATION_ERROR", "buy_in cannot be negative.", 400)
        session.buy_in = buy_in

    if "cash_out" in data:
        if data["cash_out"] is None:
            return error_response("VALIDATION_ERROR", "cash_out cannot be null", 400)
        try:
            cash_out = Decimal(str(data["cash_out"]))
        except (InvalidOperation, TypeError, ValueError):
            return error_response("VALIDATION_ERROR", "cash_out must be a valid number.", 400)
        if cash_out < 0:
            return error_response("VALIDATION_ERROR", "cash_out cannot be negative.", 400)
        session.cash_out = cash_out

    if "played_at" in data:
        if not isinstance(data["played_at"], str) or not data["played_at"].strip():
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string.", 400)
        try:
            session.played_at = datetime.fromisoformat(data["played_at"])
        except ValueError:
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string.", 400)

    if "duration_minutes" in data:
        duration_minutes = data["duration_minutes"]
        if duration_minutes is not None:
            if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes < 0:
                return error_response("VALIDATION_ERROR", "duration_minutes must be a non-negative integer.", 400)
        session.duration_minutes = duration_minutes

    if "stakes" in data:
        stakes = data["stakes"]
        if stakes is not None and not isinstance(stakes, str):
            return error_response("VALIDATION_ERROR", "stakes must be a string or null.", 400)
        session.stakes = stakes.strip() if isinstance(stakes, str) else None

    if "location" in data:
        location = data["location"]
        if location is not None and not isinstance(location, str):
            return error_response("VALIDATION_ERROR", "location must be a string or null.", 400)
        session.location = location.strip() if isinstance(location, str) else None

    if "notes" in data:
        notes = data["notes"]
        if notes is not None and not isinstance(notes, str):
            return error_response("VALIDATION_ERROR", "notes must be a string or null.", 400)
        session.notes = notes.strip() if isinstance(notes, str) else None
    # --- End validation ---

    # Persist all staged changes permanently to SQLite
    db.session.commit()

    return jsonify({
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
        "notes": session.notes,
    }), 200


# 15. DELETE POKER SESSION BY ID ROUTE (OWNER-PROTECTED)
@poker_blueprint.route("/poker-sessions/<int:session_id>", methods=["DELETE"])
@require_auth
def delete_poker_session(session_id):
    """Delete a poker session owned by the authenticated user."""
    session, error_response = get_owned_session_or_404(session_id)
    if error_response:
        return error_response

    db.session.delete(session)
    db.session.commit()

    return "", 204

from . import auth_user_routes




        