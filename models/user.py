from datetime import datetime

from flask import url_for
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


class User(UserMixin, db.Model):
    """A login account. Every account has exactly one patient OR staff profile."""
    __tablename__ = "users"

    ROLES = ("admin", "doctor", "nurse", "patient")
    ROLE_LABELS = {"admin": "Administrator", "doctor": "Doctor",
                   "nurse": "Nurse", "patient": "Patient"}
    DASHBOARDS = {"admin": "admin.dashboard", "doctor": "staff.dashboard",
                  "nurse": "staff.dashboard", "patient": "patient.dashboard"}

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    _password_hash = db.Column("password_hash", db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    profile_photo = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    last_login = db.Column(db.DateTime)

    patient = db.relationship("Patient", back_populates="user", uselist=False)
    staff = db.relationship("Staff", back_populates="user", uselist=False,
                            cascade="all, delete-orphan")
    social_accounts = db.relationship("SocialAccount", back_populates="user", cascade="all, delete-orphan")
    activity_logs = db.relationship("ActivityLog", back_populates="user",
                                    foreign_keys="ActivityLog.user_id")

    # ---- password handling (encapsulated: the hash is never exposed) ----
    def set_password(self, raw_password):
        self._password_hash = generate_password_hash(raw_password, method="pbkdf2:sha256")

    def adopt_password_hash(self, hashed):
        """Use a hash that was already made (registration waits for email verification first)."""
        self._password_hash = hashed

    def check_password(self, raw_password):
        return check_password_hash(self._password_hash, raw_password)

    @property
    def password_fingerprint(self):
        """Changes whenever the password changes (used to make reset links single-use)."""
        return self._password_hash[-12:]

    # ---- Flask-Login ----
    @property
    def is_active(self):
        return self.active

    # ---- convenience ----
    @property
    def profile(self):
        return self.patient if self.role == "patient" else self.staff

    @property
    def display_name(self):
        profile = self.profile
        return profile.full_name if profile else self.email

    @property
    def short_name(self):
        profile = self.profile
        return profile.first_name if profile else self.email.split("@")[0]

    @property
    def initial(self):
        return (self.short_name or "?")[0].upper()

    @property
    def role_label(self):
        return self.ROLE_LABELS.get(self.role, self.role.title())

    @property
    def dashboard_endpoint(self):
        return self.DASHBOARDS[self.role]

    @property
    def is_staff_member(self):
        return self.role in ("admin", "doctor", "nurse")

    @property
    def photo_url(self):
        if self.profile_photo:
            return url_for("static", filename="uploads/profiles/" + self.profile_photo)
        return None

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
