from datetime import datetime

from extensions import db


class EmailCode(db.Model):
    """A one-time 6-digit code sent by email (registration verification / password reset)."""
    __tablename__ = "email_codes"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    purpose = db.Column(db.String(20), nullable=False)          # 'register' or 'reset'
    code_hash = db.Column(db.String(64), nullable=False)        # the code itself is never stored
    payload = db.Column(db.Text)                                # pending registration data (JSON)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=False)
