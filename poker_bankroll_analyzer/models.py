# poker_bankroll_analyzer/models.py
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from .extensions import db

VALID_USER_ROLES = {"player", "room_manager", "admin"}


class User(db.Model):
    """The master architectural blueprint for user account storage profiles."""
    __tablename__ = "users"

    # 1. Core identity & security fields
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="player", nullable=False)
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

    # 4. Python-side one-to-many navigation to all sessions owned by this user
    poker_sessions = db.relationship("PokerSession", back_populates="user")

    def check_password(self, candidate_password):
        """Compares a plain-text login password against the stored cryptographic hash."""
        return check_password_hash(self.password_hash, candidate_password)

    def to_public_dict(self):
        """Returns safe, whitelisted public profile fields (never exposes password_hash)."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
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


class PokerSession(db.Model):
    """Represents a single poker session logged by a player."""
    __tablename__ = "poker_sessions"

    # 1. Primary key
    id = db.Column(db.Integer, primary_key=True)

    # 2. Foreign key linking every session strictly to its owner in users
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # 3. Required core session & bankroll fields
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

    # 4. Optional context fields
    stakes = db.Column(db.String(30), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # 5. Python-side many-to-one navigation back to the owning User
    user = db.relationship("User", back_populates="poker_sessions")

    def __repr__(self):
        return f"<PokerSession {self.id} User={self.user_id} {self.game_type}>"
