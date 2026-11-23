# poker_bankroll_analyzer/routes.py
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, g
from .decorators import require_auth, require_role
from .errors import error_response
from .extensions import db
from .models import PokerSession, PokerVenue

poker_blueprint = Blueprint("poker_api", __name__)


def get_owned_session_or_404(session_id):
    """Fetches a PokerSession only if it exists AND belongs to g.current_user_id."""
    session = db.session.get(PokerSession, session_id)
    if session is None or session.user_id != g.current_user_id:
        return None, error_response("NOT_FOUND", "Poker session not found.", 404)
    return session, None


@poker_blueprint.route("/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": "online",
        "message": "Poker API blueprint is successfully wired"
    })


@poker_blueprint.route("/welcome", methods=["GET"])
def get_welcome():
    return jsonify({
        "greeting": "Welcome to your Personal Performance Tracker!",
        "greeting_a": "Here is where you redefine your poker journey",
        "tip": "Remember to separate your freerolls from your cash buy-ins"
    })


@poker_blueprint.route("/mock-summary", methods=["GET"])
def get_mock_summary():
    return jsonify({
        "total_sessions": 0,
        "net_profit": 0.00,
        "status": "No games logged yet."
    })


@poker_blueprint.route("/health", methods=["GET"])
def get_health():
    return jsonify({
        "status": "healthy",
        "database_fallback": "active",
        "environment": "operational"
    }), 200


@poker_blueprint.route("/admin/ping", methods=["GET"])
@require_auth
@require_role("admin")
def admin_ping():
    """Simple admin-only endpoint proving role-based access control."""
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

    game_type = data.get("game_type")
    if not game_type or not isinstance(game_type, str) or not game_type.strip():
        return error_response("VALIDATION_ERROR", "game_type is required.", 400)
    game_type = game_type.strip()
    if len(game_type) > 50:
        return error_response("VALIDATION_ERROR", "game_type must be 50 characters or fewer.", 400)

    if "buy_in" not in data or data["buy_in"] is None:
        return error_response("VALIDATION_ERROR", "buy_in is required.", 400)
    try:
        buy_in = Decimal(str(data["buy_in"]))
    except (InvalidOperation, TypeError, ValueError):
        return error_response("VALIDATION_ERROR", "buy_in must be a valid number.", 400)
    if buy_in < 0:
        return error_response("VALIDATION_ERROR", "buy_in cannot be negative.", 400)

    if "cash_out" not in data or data["cash_out"] is None:
        return error_response("VALIDATION_ERROR", "cash_out is required.", 400)
    try:
        cash_out = Decimal(str(data["cash_out"]))
    except (InvalidOperation, TypeError, ValueError):
        return error_response("VALIDATION_ERROR", "cash_out must be a valid number.", 400)
    if cash_out < 0:
        return error_response("VALIDATION_ERROR", "cash_out cannot be negative.", 400)

    expenses = Decimal("0.00")
    if data.get("expenses") is not None:
        if isinstance(data["expenses"], bool):
            return error_response("VALIDATION_ERROR", "expenses must be a valid number.", 400)
        try:
            expenses = Decimal(str(data["expenses"]))
        except (InvalidOperation, TypeError, ValueError):
            return error_response("VALIDATION_ERROR", "expenses must be a valid number.", 400)
        if expenses < 0:
            return error_response("VALIDATION_ERROR", "expenses cannot be negative.", 400)

    played_at = datetime.now(timezone.utc)
    if data.get("played_at") is not None:
        if not isinstance(data["played_at"], str) or not data["played_at"].strip():
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string.", 400)
        try:
            played_at = datetime.fromisoformat(data["played_at"])
        except ValueError:
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string.", 400)

    duration_minutes = data.get("duration_minutes")
    if duration_minutes is not None:
        if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes < 0:
            return error_response("VALIDATION_ERROR", "duration_minutes must be a non-negative integer.", 400)

    venue_id = data.get("venue_id")
    linked_venue = None
    if venue_id is not None:
        if isinstance(venue_id, bool) or not isinstance(venue_id, int):
            return error_response("VALIDATION_ERROR", "venue_id must be an integer.", 400)
        linked_venue = db.session.get(PokerVenue, venue_id)
        if not linked_venue:
            return error_response("NOT_FOUND", "Selected poker venue not found.", 404)

    raw_location = data.get("location").strip() if isinstance(data.get("location"), str) else None
    resolved_location = raw_location or (linked_venue.name if linked_venue else None)

    new_session = PokerSession(
        user_id=g.current_user_id,
        venue_id=linked_venue.id if linked_venue else None,
        game_type=game_type,
        buy_in=buy_in,
        cash_out=cash_out,
        expenses=expenses,
        played_at=played_at,
        stakes=data.get("stakes").strip() if isinstance(data.get("stakes"), str) else None,
        location=resolved_location,
        duration_minutes=duration_minutes,
        notes=data.get("notes").strip() if isinstance(data.get("notes"), str) else None,
    )

    db.session.add(new_session)
    db.session.commit()

    return jsonify(new_session.to_dict()), 201


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
        return error_response("VALIDATION_ERROR", "page and per_page must be valid integers.", 400)

    if page < 1:
        return error_response("VALIDATION_ERROR", "page must be a positive integer (>=1).", 400)

    if per_page < 1 or per_page > 50:
        return error_response("VALIDATION_ERROR", "per_page must be between 1 and 50.", 400)

    base_query = (
        PokerSession.query
        .filter_by(user_id=g.current_user_id)
        .order_by(PokerSession.id.asc())
    )

    pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [session.to_dict() for session in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }), 200


# 12B. Player Bankroll & Performance Analytics Summary ("See My Poker Life")
@poker_blueprint.route("/poker-sessions/stats", methods=["GET"])
@require_auth
def get_poker_session_stats():
    """Calculates total profit, expenses, true net profit, hourly rate, and venue breakdown."""
    sessions = (
        PokerSession.query
        .filter_by(user_id=g.current_user_id)
        .order_by(PokerSession.played_at.asc())
        .all()
    )

    total_buy_in = Decimal("0.00")
    total_cash_out = Decimal("0.00")
    total_expenses = Decimal("0.00")
    total_minutes = 0
    venue_map = {}

    for s in sessions:
        buy = Decimal(str(s.buy_in or 0))
        cash = Decimal(str(s.cash_out or 0))
        exp = Decimal(str(s.expenses or 0))
        mins = s.duration_minutes or 0

        total_buy_in += buy
        total_cash_out += cash
        total_expenses += exp
        total_minutes += mins

        venue_label = (s.venue.name if s.venue else s.location) or "Unspecified Venue"
        bucket = venue_map.setdefault(
            venue_label,
            {"venue": venue_label, "sessions": 0, "minutes": 0, "true_net_profit": Decimal("0.00")},
        )
        bucket["sessions"] += 1
        bucket["minutes"] += mins
        bucket["true_net_profit"] += (cash - buy - exp)

    gross_profit = total_cash_out - total_buy_in
    true_net_profit = gross_profit - total_expenses
    total_hours = round(total_minutes / 60.0, 2)
    hourly_rate = round(float(true_net_profit) / total_hours, 2) if total_hours > 0 else 0.0

    by_venue = [
        {
            "venue": info["venue"],
            "sessions": info["sessions"],
            "hours": round(info["minutes"] / 60.0, 2),
            "true_net_profit": round(float(info["true_net_profit"]), 2),
        }
        for info in sorted(venue_map.values(), key=lambda x: x["true_net_profit"], reverse=True)
    ]

    return jsonify({
        "total_sessions": len(sessions),
        "total_buy_in": round(float(total_buy_in), 2),
        "total_cash_out": round(float(total_cash_out), 2),
        "gross_table_profit": round(float(gross_profit), 2),
        "total_expenses": round(float(total_expenses), 2),
        "true_net_profit": round(float(true_net_profit), 2),
        "total_minutes": total_minutes,
        "total_hours": total_hours,
        "hourly_rate": hourly_rate,
        "by_venue": by_venue,
    }), 200


# 13. Get Single Poker Session by ID (Owner-Protected)
@poker_blueprint.route("/poker-sessions/<int:session_id>", methods=["GET"])
@require_auth
def get_poker_session(session_id):
    """Fetch a single poker session owned by the authenticated user."""
    session, err_resp = get_owned_session_or_404(session_id)
    if err_resp:
        return err_resp

    return jsonify(session.to_dict()), 200


# 14. Update Poker Session by ID Route (Owner-Protected Partial PATCH)
@poker_blueprint.route("/poker-sessions/<int:session_id>", methods=["PATCH"])
@require_auth
def update_poker_session(session_id):
    """Partially update a poker session owned by the authenticated user."""
    session, err_resp = get_owned_session_or_404(session_id)
    if err_resp:
        return err_resp

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return error_response("VALIDATION_ERROR", "Request body must be a valid JSON object.", 400)

    allowed_fields = {
        "venue_id",
        "game_type",
        "buy_in",
        "cash_out",
        "expenses",
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
            f"Fields cannot be updated: {', '.join(sorted(forbidden_fields))}.",
            400,
        )

    if "venue_id" in data:
        if data["venue_id"] is None:
            session.venue_id = None
        else:
            if isinstance(data["venue_id"], bool) or not isinstance(data["venue_id"], int):
                return error_response("VALIDATION_ERROR", "venue_id must be an integer.", 400)
            venue = db.session.get(PokerVenue, data["venue_id"])
            if not venue:
                return error_response("NOT_FOUND", "Selected poker venue not found.", 404)
            session.venue_id = venue.id
            if "location" not in data and not session.location:
                session.location = venue.name

    if "game_type" in data:
        if not isinstance(data["game_type"], str) or not data["game_type"].strip():
            return error_response("VALIDATION_ERROR", "game_type cannot be empty.", 400)
        session.game_type = data["game_type"].strip()

    for money_field in ("buy_in", "cash_out", "expenses"):
        if money_field in data:
            if data[money_field] is None or isinstance(data[money_field], bool):
                return error_response("VALIDATION_ERROR", f"{money_field} must be a valid number.", 400)
            try:
                val = Decimal(str(data[money_field]))
            except (InvalidOperation, TypeError, ValueError):
                return error_response("VALIDATION_ERROR", f"{money_field} must be a valid number.", 400)
            if val < 0:
                return error_response("VALIDATION_ERROR", f"{money_field} cannot be negative.", 400)
            setattr(session, money_field, val)

    if "played_at" in data:
        if not isinstance(data["played_at"], str) or not data["played_at"].strip():
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string.", 400)
        try:
            session.played_at = datetime.fromisoformat(data["played_at"])
        except ValueError:
            return error_response("VALIDATION_ERROR", "played_at must be a valid ISO-8601 date/time string.", 400)

    if "duration_minutes" in data:
        dur = data["duration_minutes"]
        if dur is not None and (isinstance(dur, bool) or not isinstance(dur, int) or dur < 0):
            return error_response("VALIDATION_ERROR", "duration_minutes must be a non-negative integer.", 400)
        session.duration_minutes = dur

    for text_field in ("stakes", "location", "notes"):
        if text_field in data:
            val = data[text_field]
            setattr(session, text_field, val.strip() if isinstance(val, str) and val.strip() else None)

    db.session.commit()
    return jsonify(session.to_dict()), 200


# 15. Delete Poker Session by ID Route (Owner-Protected)
@poker_blueprint.route("/poker-sessions/<int:session_id>", methods=["DELETE"])
@require_auth
def delete_poker_session(session_id):
    """Delete a poker session owned by the authenticated user."""
    session, err_resp = get_owned_session_or_404(session_id)
    if err_resp:
        return err_resp

    db.session.delete(session)
    db.session.commit()

    return "", 204


from . import auth_user_routes