import re
from datetime import date, datetime, time
from functools import wraps

from flask import abort, current_app
from flask_login import current_user

STAFF_ROLES = ("admin", "doctor", "nurse")
CLINICAL_ROLES = ("doctor", "nurse")

NAME_RE = re.compile(r"^[A-Za-zÀ-ÿñÑ][A-Za-zÀ-ÿñÑ .'\-]{0,48}[A-Za-zÀ-ÿñÑ.]$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^(\+63|0)9\d{9}$")


def now():
    return datetime.now()


def today():
    return date.today()


def clean(value):
    """Trim a form value; None becomes an empty string."""
    return (value or "").strip()


def role_required(*roles):
    """Allow only signed-in users whose role is in `roles` (403 otherwise)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def parse_date(value):
    try:
        return datetime.strptime(clean(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_time(value):
    try:
        return datetime.strptime(clean(value), "%H:%M").time()
    except ValueError:
        return None


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def valid_name(value):
    return bool(NAME_RE.match(value or ""))


def valid_email(value):
    return bool(EMAIL_RE.match(value or "")) and len(value) <= 120


def valid_phone(value):
    return bool(PHONE_RE.match(value or ""))


def password_errors(password):
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password needs at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password needs at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password needs at least one number.")
    return errors


def can_manage_assigned(user, staff_id):
    """Admin, the assigned doctor/nurse, or anyone (when nobody is assigned) may change an item."""
    if user.role == "admin" or staff_id is None:
        return True
    staff = getattr(user, "staff", None)
    return staff is not None and staff.id == staff_id


def safe_next_url(target):
    """Only allow redirects to local paths (prevents open-redirect attacks)."""
    return bool(target) and target.startswith("/") and not target.startswith("//")
