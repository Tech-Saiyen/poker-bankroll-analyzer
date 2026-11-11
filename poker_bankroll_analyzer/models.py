# poker_bankroll_anlyzer/models.py
from datetime import datetime, timezone
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

    #4. The automatic timestamp clock (records exactly hen the user joined the ecosystem)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self):
        return f"<User {self.username}>"