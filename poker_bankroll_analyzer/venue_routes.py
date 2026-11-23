# poker_bankroll_analyzer/venue_routes.py
from datetime import datetime, timedelta, timezone
import math
from flask import Blueprint, g, jsonify, request
from .extensions import db
from .models import LiveGame, PokerVenue, User, VenueCheckIn, VALID_VENUE_TYPES
from .decorators import require_auth, require_role

venue_blueprint = Blueprint("venues", __name__)


def _calculate_distance_miles(lat1, lon1, lat2, lon2):
    """Computes great-circle distance in miles between two GPS points."""
    radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_miles * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _can_manage_venue(venue_id):
    """Checks whether the authenticated caller is an admin or the assigned room_manager."""
    user = db.session.get(User, getattr(g, "current_user_id", None))
    if not user:
        return False, None
    if user.role == "admin":
        return True, user
    if user.role == "room_manager" and user.managed_venue_id == venue_id:
        return True, user
    return False, user


@venue_blueprint.route("/venues", methods=["GET"])
def list_venues():
    """Public DFW venue directory with game, stakes, type, city, and distance filters."""
    venue_type = request.args.get("venue_type", "").strip().lower()
    city = request.args.get("city", "").strip().lower()
    game_type = request.args.get("game_type", "").strip().upper()
    stakes = request.args.get("stakes", "").strip()

    user_lat = request.args.get("lat", type=float)
    user_lng = request.args.get("lng", type=float)
    max_miles = request.args.get("max_miles", type=float)

    query = PokerVenue.query.filter_by(is_active=True)
    if venue_type:
        query = query.filter(PokerVenue.venue_type == venue_type)
    if city:
        query = query.filter(db.func.lower(PokerVenue.city) == city)

    venues = query.all()
    results = []

    for venue in venues:
        # Filter by active game_type or stakes if requested
        if game_type or stakes:
            matching_games = [
                g_item for g_item in venue.live_games
                if (not game_type or g_item.game_type.upper() == game_type)
                and (not stakes or g_item.stakes == stakes)
            ]
            if not matching_games:
                continue

        distance = None
        if (
            user_lat is not None
            and user_lng is not None
            and venue.latitude is not None
            and venue.longitude is not None
        ):
            distance = _calculate_distance_miles(
                user_lat, user_lng, venue.latitude, venue.longitude
            )
            if max_miles is not None and distance > max_miles:
                continue

        results.append((venue, distance))

    # Featured venues pinned first, then closest distance (if provided), then alphabetical
    results.sort(
        key=lambda item: (
            not item[0].is_featured,
            item[1] if item[1] is not None else 999999.0,
            item[0].name.lower(),
        )
    )

    items = [venue.to_dict(distance_miles=dist) for venue, dist in results]
    return jsonify({"items": items, "total": len(items)}), 200


@venue_blueprint.route("/venues/<int:venue_id>", methods=["GET"])
def get_venue(venue_id):
    """Fetch a single venue and its live floor table/waitlist counts."""
    venue = db.session.get(PokerVenue, venue_id)
    if not venue or not venue.is_active:
        return jsonify({"code": "NOT_FOUND", "message": "Poker venue not found."}), 404

    return jsonify(venue.to_dict()), 200


@venue_blueprint.route("/venues", methods=["POST"])
@require_auth
@require_role("admin")
def create_venue():
    """Admin-only endpoint to add a new poker venue to the DFW directory."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    city = (data.get("city") or "").strip()
    venue_type = (data.get("venue_type") or "card_club").strip().lower()

    if not name or not city:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Both 'name' and 'city' are required."
        }), 400

    if venue_type not in VALID_VENUE_TYPES:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": f"venue_type must be one of: {', '.join(sorted(VALID_VENUE_TYPES))}."
        }), 400

    if PokerVenue.query.filter_by(name=name).first():
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "A venue with that name already exists."
        }), 409

    venue = PokerVenue(
        name=name,
        venue_type=venue_type,
        city=city,
        address=(data.get("address") or "").strip() or None,
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        website_url=(data.get("website_url") or "").strip() or None,
        stream_url=(data.get("stream_url") or "").strip() or None,
        is_featured=bool(data.get("is_featured", False)),
    )
    db.session.add(venue)
    db.session.commit()
    return jsonify(venue.to_dict()), 201


@venue_blueprint.route("/venues/<int:venue_id>", methods=["PATCH"])
@require_auth
@require_role("room_manager", "admin")
def update_venue(venue_id):
    """Allows an assigned room_manager or admin to update venue details & stream URL."""
    venue = db.session.get(PokerVenue, venue_id)
    if not venue:
        return jsonify({"code": "NOT_FOUND", "message": "Poker venue not found."}), 404

    allowed, user = _can_manage_venue(venue_id)
    if not allowed:
        return jsonify({
            "code": "FORBIDDEN",
            "message": "You are not assigned to manage this venue."
        }), 403

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Request body must be a valid JSON object."
        }), 400

    manager_fields = {"stream_url", "website_url", "address"}
    admin_extra_fields = {"name", "venue_type", "city", "latitude", "longitude", "is_featured", "is_active"}
    permitted = manager_fields | (admin_extra_fields if user.role == "admin" else set())

    forbidden = set(data.keys()) - permitted
    if forbidden:
        return jsonify({
            "code": "FORBIDDEN",
            "message": f"You cannot update these fields: {', '.join(sorted(forbidden))}."
        }), 403

    if "venue_type" in data:
        if data["venue_type"] not in VALID_VENUE_TYPES:
            return jsonify({
                "code": "VALIDATION_ERROR",
                "message": f"venue_type must be one of: {', '.join(sorted(VALID_VENUE_TYPES))}."
            }), 400
        venue.venue_type = data["venue_type"]

    for str_field in ("name", "city", "address", "website_url", "stream_url"):
        if str_field in data:
            val = data[str_field]
            setattr(venue, str_field, val.strip() if isinstance(val, str) and val.strip() else None)

    for num_field in ("latitude", "longitude"):
        if num_field in data:
            setattr(venue, num_field, data[num_field])

    for bool_field in ("is_featured", "is_active"):
        if bool_field in data:
            if not isinstance(data[bool_field], bool):
                return jsonify({
                    "code": "VALIDATION_ERROR",
                    "message": f"{bool_field} must be a boolean."
                }), 400
            setattr(venue, bool_field, data[bool_field])

    db.session.commit()
    return jsonify(venue.to_dict()), 200


@venue_blueprint.route("/venues/<int:venue_id>/games", methods=["POST"])
@require_auth
@require_role("room_manager", "admin")
def upsert_live_game(venue_id):
    """10-second floor manager portal: add or update table & waitlist counts for a game."""
    venue = db.session.get(PokerVenue, venue_id)
    if not venue:
        return jsonify({"code": "NOT_FOUND", "message": "Poker venue not found."}), 404

    allowed, _ = _can_manage_venue(venue_id)
    if not allowed:
        return jsonify({
            "code": "FORBIDDEN",
            "message": "You are not assigned to manage this venue."
        }), 403

    data = request.get_json(silent=True) or {}
    game_type = (data.get("game_type") or "").strip().upper()
    stakes = (data.get("stakes") or "").strip()
    open_tables = data.get("open_tables", 0)
    waitlist_count = data.get("waitlist_count", 0)

    if not game_type or not stakes:
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "Both 'game_type' and 'stakes' are required."
        }), 400

    if (
        not isinstance(open_tables, int)
        or isinstance(open_tables, bool)
        or open_tables < 0
        or not isinstance(waitlist_count, int)
        or isinstance(waitlist_count, bool)
        or waitlist_count < 0
    ):
        return jsonify({
            "code": "VALIDATION_ERROR",
            "message": "open_tables and waitlist_count must be non-negative integers."
        }), 400

    existing = LiveGame.query.filter_by(
        venue_id=venue_id, game_type=game_type, stakes=stakes
    ).first()

    if existing:
        existing.open_tables = open_tables
        existing.waitlist_count = waitlist_count
        existing.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify(existing.to_dict()), 200

    new_game = LiveGame(
        venue_id=venue_id,
        game_type=game_type,
        stakes=stakes,
        open_tables=open_tables,
        waitlist_count=waitlist_count,
    )
    db.session.add(new_game)
    db.session.commit()
    return jsonify(new_game.to_dict()), 201


@venue_blueprint.route("/venues/<int:venue_id>/check-in", methods=["POST"])
@require_auth
def check_in_at_venue(venue_id):
    """Lightweight 6-hour player check-in showing live social buzz at a DFW venue."""
    venue = db.session.get(PokerVenue, venue_id)
    if not venue or not venue.is_active:
        return jsonify({"code": "NOT_FOUND", "message": "Poker venue not found."}), 404

    now = datetime.now(timezone.utc)
    # Remove any expired check-ins for this user and refresh if already checked in here
    VenueCheckIn.query.filter(VenueCheckIn.user_id == g.current_user_id).delete()

    checkin = VenueCheckIn(
        user_id=g.current_user_id,
        venue_id=venue.id,
        checked_in_at=now,
        expires_at=now + timedelta(hours=6),
    )
    db.session.add(checkin)
    db.session.commit()
    return jsonify(checkin.to_dict()), 201


@venue_blueprint.route("/venues/<int:venue_id>/check-ins", methods=["GET"])
def list_active_venue_checkins(venue_id):
    """Lists players currently checked in at a venue within the last 6 hours."""
    venue = db.session.get(PokerVenue, venue_id)
    if not venue or not venue.is_active:
        return jsonify({"code": "NOT_FOUND", "message": "Poker venue not found."}), 404

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    active = (
        VenueCheckIn.query
        .filter(
            VenueCheckIn.venue_id == venue.id,
            VenueCheckIn.expires_at > now_naive,
        )
        .order_by(VenueCheckIn.checked_in_at.desc())
        .all()
    )
    items = [c.to_dict() for c in active]
    return jsonify({"venue_id": venue.id, "active_count": len(items), "players": items}), 200


def seed_dfw_venues_data():
    """Idempotently seeds starter Dallas-Fort Worth venues and sample live games."""
    starter_venues = [
        {
            "name": "Texas Card House Dallas",
            "venue_type": "card_club",
            "city": "Dallas",
            "address": "11834 Harry Hines Blvd, Dallas, TX 75234",
            "latitude": 32.9096,
            "longitude": -96.8925,
            "is_featured": True,
            "games": [("NLH", "1/2", 6, 8), ("NLH", "2/5", 3, 5), ("PLO", "1/2/5", 2, 4)],
        },
        {
            "name": "Shuffle 214",
            "venue_type": "card_club",
            "city": "Dallas",
            "address": "11411 E Northwest Hwy, Dallas, TX 75218",
            "latitude": 32.8639,
            "longitude": -96.6836,
            "is_featured": False,
            "games": [("NLH", "1/2", 4, 3), ("PLO", "1/3", 1, 2)],
        },
        {
            "name": "Poker House Dallas",
            "venue_type": "card_club",
            "city": "Dallas",
            "address": "13530 Inwood Rd, Dallas, TX 75244",
            "latitude": 32.9332,
            "longitude": -96.8211,
            "is_featured": False,
            "games": [("NLH", "1/2", 5, 6), ("NLH", "2/5", 2, 3)],
        },
        {
            "name": "Champions Club Dallas",
            "venue_type": "card_club",
            "city": "Dallas",
            "address": "11661 Preston Rd, Dallas, TX 75230",
            "latitude": 32.9082,
            "longitude": -96.8034,
            "is_featured": False,
            "games": [("NLH", "1/3", 4, 2)],
        },
        {
            "name": "DFW Bar Poker League - North Dallas",
            "venue_type": "bar_league",
            "city": "Dallas",
            "address": "Addison / North Dallas Partner Grill",
            "latitude": 32.9618,
            "longitude": -96.8292,
            "is_featured": False,
            "games": [("NLH", "Freeroll", 3, 0)],
        },
    ]

    created_count = 0
    for item in starter_venues:
        if PokerVenue.query.filter_by(name=item["name"]).first():
            continue
        venue = PokerVenue(
            name=item["name"],
            venue_type=item["venue_type"],
            city=item["city"],
            address=item["address"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            is_featured=item["is_featured"],
        )
        db.session.add(venue)
        db.session.flush()
        for g_type, stakes, tables, waitlist in item["games"]:
            db.session.add(
                LiveGame(
                    venue_id=venue.id,
                    game_type=g_type,
                    stakes=stakes,
                    open_tables=tables,
                    waitlist_count=waitlist,
                )
            )
        created_count += 1

    db.session.commit()
    return created_count



