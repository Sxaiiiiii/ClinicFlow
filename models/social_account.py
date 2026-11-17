from datetime import datetime

from extensions import db


class SocialAccount(db.Model):
    """Links a ClinicFlow user to an outside login (Google). Kept in its own table so `users` is untouched."""
    __tablename__ = "social_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = db.Column(db.String(20), nullable=False)             # 'google'
    provider_user_id = db.Column(db.String(64), nullable=False)     # Google's stable id ("sub")
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    __table_args__ = (db.UniqueConstraint("provider", "provider_user_id", name="uq_social_provider_id"),)

    user = db.relationship("User", back_populates="social_accounts")
