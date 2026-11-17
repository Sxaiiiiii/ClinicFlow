"""Application configuration. Secrets come from environment variables / .env."""
import os
from datetime import timedelta
from urllib.parse import quote_plus

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

try:  # load values from the .env file that sits next to app.py
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


def _clean_env(name, remove_spaces=False):
    value = os.environ.get(name, "").strip().strip("\"'")
    return value.replace(" ", "") if remove_spaces else value


_MAIL_USER = _clean_env("MAIL_USERNAME")
_MAIL_PASS = _clean_env("MAIL_PASSWORD", remove_spaces=True)   # Gmail shows App Passwords with spaces


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")

    # ---- Database (MySQL via PyMySQL) ----
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "clinicflow")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # ---- Sessions / cookies ----
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # ---- CSRF ----
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 8

    # ---- Uploads (profile photos) ----
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "profiles")

    # ---- Google sign-in (optional). The button only appears when both values are set. ----
    GOOGLE_CLIENT_ID = _clean_env("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _clean_env("GOOGLE_CLIENT_SECRET")
    GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

    # ---- SMTP / Flask-Mail ----
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "0") == "1"      # use with MAIL_PORT=465 and MAIL_USE_TLS=0
    MAIL_USERNAME = _MAIL_USER
    MAIL_PASSWORD = _MAIL_PASS
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_SENDER", "ClinicFlow <no-reply@clinicflow.test>")
    # Registration needs a 6-digit email code. Set REQUIRE_EMAIL_VERIFICATION=0 in .env to switch it off.
    REQUIRE_EMAIL_VERIFICATION = os.environ.get("REQUIRE_EMAIL_VERIFICATION", "1") == "1"
    MAIL_ENABLED = bool(_MAIL_USER and _MAIL_PASS)
