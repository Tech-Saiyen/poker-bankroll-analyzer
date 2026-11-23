# poker_bankroll_analyzer/models.py
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from .extensions import db

VALID_USER_ROLES = {"player", "room_manager", "admin"}
VALID_USER_TIERS = {"amateur", "pro"}
VALID_VENUE_TYPES = {"card_club", "bar_league", "restaurant", "casino", "private_game"}
VALID_ARTICLE_CATEGORIES = {"spotlight", "news", "strategy"}
VALID_BANNER_PLACEMENTS = {"top_banner", "feed_card", "venue_sidebar"}


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
    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("poker_venues.id", ondelete="SET NULL"),
        nullable=True
    )

    game_type = db.Column(db.String(50), nullable=False)
    buy_in = db.Column(db.Numeric(10, 2), nullable=False)
    cash_out = db.Column(db.Numeric(10, 2), nullable=False)
    expenses = db.Column(db.Numeric(10, 2), default=0, nullable=False)
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
    venue = db.relationship("PokerVenue")

    def to_dict(self):
        table_profit = float(self.cash_out - self.buy_in)
        expense_val = float(self.expenses or 0)
        return {
            "id": self.id,
            "user_id": self.user_id,
            "venue_id": self.venue_id,
            "venue_name": self.venue.name if self.venue else self.location,
            "game_type": self.game_type,
            "buy_in": float(self.buy_in),
            "cash_out": float(self.cash_out),
            "expenses": expense_val,
            "net_profit": table_profit,
            "true_net_profit": round(table_profit - expense_val, 2),
            "played_at": self.played_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "stakes": self.stakes,
            "location": self.location,
            "duration_minutes": self.duration_minutes,
            "notes": self.notes,
        }

    def __repr__(self):
        return f"<PokerSession {self.id} User={self.user_id} {self.game_type}>"


class Article(db.Model):
    """Editorial blog posts, North Dallas Player Spotlights, and training affiliate articles."""
    __tablename__ = "articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    category = db.Column(db.String(30), default="spotlight", nullable=False)
    summary = db.Column(db.String(300), nullable=True)
    body = db.Column(db.Text, nullable=False)
    cover_image_url = db.Column(db.String(255), nullable=True)
    affiliate_url = db.Column(db.String(255), nullable=True)
    featured_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    featured_user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "category": self.category,
            "summary": self.summary,
            "body": self.body,
            "cover_image_url": self.cover_image_url,
            "affiliate_url": self.affiliate_url,
            "featured_user_id": self.featured_user_id,
            "featured_player": self.featured_user.to_public_dict() if self.featured_user else None,
            "is_published": self.is_published,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Article {self.slug} ({self.category})>"


class SponsorBanner(db.Model):
    """Local DFW sponsor banner slots for bars, restaurants, recovery, and poker brands."""
    __tablename__ = "sponsor_banners"

    id = db.Column(db.Integer, primary_key=True)
    sponsor_name = db.Column(db.String(120), nullable=False)
    tagline = db.Column(db.String(200), nullable=True)
    image_url = db.Column(db.String(255), nullable=False)
    target_url = db.Column(db.String(255), nullable=False)
    placement = db.Column(db.String(40), default="top_banner", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "sponsor_name": self.sponsor_name,
            "tagline": self.tagline,
            "image_url": self.image_url,
            "target_url": self.target_url,
            "placement": self.placement,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<SponsorBanner {self.sponsor_name} ({self.placement})>"


class VenueCheckIn(db.Model):
    """Lightweight 6-hour social check-in showing live player buzz at DFW venues."""
    __tablename__ = "venue_checkins"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("poker_venues.id", ondelete="CASCADE"),
        nullable=False
    )
    checked_in_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User")
    venue = db.relationship("PokerVenue")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "display_name": self.user.display_name if self.user else None,
            "is_verified": self.user.is_verified if self.user else False,
            "venue_id": self.venue_id,
            "venue_name": self.venue.name if self.venue else None,
            "checked_in_at": self.checked_in_at.isoformat() if self.checked_in_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def __repr__(self):
        return f"<VenueCheckIn User={self.user_id} Venue={self.venue_id}>"
