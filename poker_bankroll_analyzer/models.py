# poker_bankroll_analyzer/models.py
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from .extensions import db

VALID_USER_ROLES = {"player", "room_manager", "admin"}
VALID_USER_TIERS = {"amateur", "pro"}
VALID_VENUE_TYPES = {"card_club", "bar_league", "restaurant", "casino", "private_game"}


class User(db.Model):
    """The master architectural blueprint for user account storage profiles."""
    __tablename__ = "users"

    # 1. Core identity & security fields
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="player", nullable=False)
    tier = db.Column(db.String(20), default="amateur", nullable=False)
    managed_venue_id = db.Column(
        db.Integer,
        db.ForeignKey("poker_venues.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # 2. Public player profile & style fields
    display_name = db.Column(db.String(80), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    home_room = db.Column(db.String(100), nullable=True)
    style_tags = db.Column(db.String(120), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    # 3. Verification & external league links (admin-controlled badge)
    hendonmob_url = db.Column(db.String(255), nullable=True)
    external_player_id = db.Column(db.String(80), nullable=True)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)

    # 4. Relationships
    poker_sessions = db.relationship("PokerSession", back_populates="user")
    managed_venue = db.relationship("PokerVenue", back_populates="managers")

    def check_password(self, candidate_password):
        """Compares a plain-text login password against the stored cryptographic hash."""
        return check_password_hash(self.password_hash, candidate_password)

    def to_public_dict(self):
        """Returns safe, whitelisted public profile fields (never exposes password_hash)."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "tier": self.tier,
            "managed_venue_id": self.managed_venue_id,
            "display_name": self.display_name,
            "bio": self.bio,
            "home_room": self.home_room,
            "style_tags": self.style_tags,
            "avatar_url": self.avatar_url,
            "hendonmob_url": self.hendonmob_url,
            "external_player_id": self.external_player_id,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class PokerVenue(db.Model):
    """Represents a DFW poker room, bar league, restaurant game, or casino."""
    __tablename__ = "poker_venues"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    venue_type = db.Column(db.String(30), default="card_club", nullable=False)
    city = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    website_url = db.Column(db.String(255), nullable=True)
    stream_url = db.Column(db.String(255), nullable=True)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    live_games = db.relationship(
        "LiveGame",
        back_populates="venue",
        cascade="all, delete-orphan"
    )
    managers = db.relationship("User", back_populates="managed_venue")

    def to_dict(self, distance_miles=None):
        payload = {
            "id": self.id,
            "name": self.name,
            "venue_type": self.venue_type,
            "city": self.city,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "website_url": self.website_url,
            "stream_url": self.stream_url,
            "is_featured": self.is_featured,
            "is_active": self.is_active,
            "live_games": [game.to_dict() for game in self.live_games],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if distance_miles is not None:
            payload["distance_miles"] = round(distance_miles, 1)
        return payload

    def __repr__(self):
        return f"<PokerVenue {self.name} ({self.venue_type})>"


class LiveGame(db.Model):
    """Tracks active tables and waitlist counts for a specific game & stakes at a venue."""
    __tablename__ = "live_games"

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("poker_venues.id", ondelete="CASCADE"),
        nullable=False
    )
    game_type = db.Column(db.String(40), nullable=False)
    stakes = db.Column(db.String(40), nullable=False)
    open_tables = db.Column(db.Integer, default=0, nullable=False)
    waitlist_count = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    venue = db.relationship("PokerVenue", back_populates="live_games")

    def to_dict(self):
        return {
            "id": self.id,
            "venue_id": self.venue_id,
            "game_type": self.game_type,
            "stakes": self.stakes,
            "open_tables": self.open_tables,
            "waitlist_count": self.waitlist_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<LiveGame Venue={self.venue_id} {self.stakes} {self.game_type}>"


class PokerSession(db.Model):
    """Represents a single poker session logged by a player."""
    __tablename__ = "poker_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    game_type = db.Column(db.String(50), nullable=False)
    buy_in = db.Column(db.Numeric(10, 2), nullable=False)
    cash_out = db.Column(db.Numeric(10, 2), nullable=False)
    played_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    stakes = db.Column(db.String(30), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    user = db.relationship("User", back_populates="poker_sessions")

    def __repr__(self):
        return f"<PokerSession {self.id} User={self.user_id} {self.game_type}>"



