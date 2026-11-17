"""6-digit email codes: issue, verify, resend. Codes are stored hashed, expire, and are attempt-limited."""
import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from flask import current_app

from extensions import db
from models import EmailCode
from utils import now


class VerificationService:
    EXPIRY_MINUTES = 10
    MAX_ATTEMPTS = 5
    RESEND_SECONDS = 60

    @staticmethod
    def _hash(email, purpose, code):
        key = current_app.config["SECRET_KEY"].encode()
        return hmac.new(key, f"{email}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def latest(email, purpose):
        return (EmailCode.query.filter_by(email=email, purpose=purpose)
                .order_by(EmailCode.id.desc()).first())

    @classmethod
    def issue(cls, email, purpose, payload=None):
        """Create a new code (older unused codes stop working). Returns the plain code; caller commits."""
        last = cls.latest(email, purpose)
        if last is not None:
            wait = cls.RESEND_SECONDS - (now() - last.created_at).total_seconds()
            if wait > 0:
                raise ValueError(f"Please wait {int(wait) + 1} seconds before asking for another code.")
        EmailCode.query.filter_by(email=email, purpose=purpose, used=False).update(
            {"used": True}, synchronize_session=False)
        code = f"{secrets.randbelow(10 ** 6):06d}"
        db.session.add(EmailCode(email=email, purpose=purpose, code_hash=cls._hash(email, purpose, code),
                                 payload=json.dumps(payload) if payload is not None else None,
                                 created_at=now(), expires_at=now() + timedelta(minutes=cls.EXPIRY_MINUTES)))
        db.session.flush()
        return code

    @classmethod
    def reissue(cls, email, purpose):
        """New code for a pending registration, keeping its saved details. Returns (code, payload)."""
        last = cls.latest(email, purpose)
        if last is None:
            raise ValueError("Nothing to resend. Please start again.")
        payload = json.loads(last.payload) if last.payload else None
        return cls.issue(email, purpose, payload), payload

    @classmethod
    def verify(cls, email, purpose, code):
        """Returns (ok, message, payload). Wrong guesses are counted and saved."""
        row = (EmailCode.query.filter_by(email=email, purpose=purpose, used=False)
               .order_by(EmailCode.id.desc()).first())
        if row is None:
            return False, "No active code. Please request a new one.", None
        if row.expires_at < now():
            row.used = True
            db.session.commit()
            return False, "That code has expired. Please request a new one.", None
        if row.attempts >= cls.MAX_ATTEMPTS:
            row.used = True
            db.session.commit()
            return False, "Too many wrong attempts. Please request a new code.", None
        row.attempts += 1
        if not hmac.compare_digest(row.code_hash, cls._hash(email, purpose, code)):
            db.session.commit()
            return False, f"Incorrect code. {cls.MAX_ATTEMPTS - row.attempts} attempt(s) left.", None
        row.used = True
        db.session.commit()
        return True, "", (json.loads(row.payload) if row.payload else None)
