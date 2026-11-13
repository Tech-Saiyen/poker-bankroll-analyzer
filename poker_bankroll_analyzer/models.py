# poker_bankroll_anlyzer/models.py
from datetime import datetime, timezone
from werkzeug.security import check_password_hash
from .extensions import db

class User(db.Model):
    """The master architectural blueprint for user account storage profiles."""
    __tablename__ = "users"

    #1. The numeric, self-incrementing unique tracking key
    id = db.Column(db.Integer, primary_key=True)

    #2. The unique player nickname box (cannot be empty, cannot be duplicated)
    username = db.Column(db.String(50), unique=True, nullable=False)

    #3. The secure cryptographic password vault box (long enough to store complex hashes)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)

    #4. The automatic timestamp clock (records exactly hen the user joined the ecosystem)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # 5. Python-side one-to-many navigation to all sessions owned by this user
    poker_sessions = db.relationship("PokerSession", back_populates="user")

    def check_password(self, candidate_password):
        """Compares a plain-text login password against the stored cryptographic hash."""
        return check_password_hash(self.password_hash, candidate_password)

    def __repr__(self):
        return f"<User {self.username}>"

    
class PokerSession(db.Model):
    """Represents a single poker session logged by a player."""
    __tablename__ = "poker_sessions"

    # 1. Primary key
    id = db.Column(db.Integer, primary_key=True)

    # 2. Foreign key linking every session strictly to its owner in users.
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