"""ClinicFlow — Clinic Queue & Scheduling System.  Run with:  py app.py"""
import os
from datetime import date, datetime

from flask import Flask, render_template
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from config import Config
from extensions import csrf, db, login_manager, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    import models  # noqa: F401  (registers all tables)
    from models import Appointment, ChatMessage, ClinicSetting
    from routes import (admin, appointments, auth, chat, patient, patients, queue,
                        records, reports, staff)
    for module in (auth, admin, staff, patient, appointments, queue, patients, records, reports, chat):
        app.register_blueprint(module.bp)

    # ------------------------------------------------------------ template helpers
    @app.template_filter("fmt_date")
    def fmt_date(value):
        return f"{value:%b} {value.day}, {value.year}" if value else "—"

    @app.template_filter("fmt_time")
    def fmt_time(value):
        return value.strftime("%I:%M %p") if value else "—"

    @app.template_filter("fmt_dt")
    def fmt_dt(value):
        return f"{value:%b} {value.day}, {value.year} {value:%I:%M %p}" if value else "—"

    @app.context_processor
    def inject_globals():
        try:
            clinic = ClinicSetting.as_dict()
            pending, chat_unread = 0, 0
            if current_user.is_authenticated and current_user.is_staff_member:
                pending = Appointment.query.filter_by(status="pending").count()
            if current_user.is_authenticated and current_user.role in ("patient", "doctor", "nurse"):
                mine = current_user.patient if current_user.role == "patient" else current_user.staff
                if mine is not None:
                    column = ChatMessage.patient_id if current_user.role == "patient" else ChatMessage.staff_id
                    chat_unread = ChatMessage.query.filter(column == mine.id, ChatMessage.read_at.is_(None),
                                                           ChatMessage.sender_user_id != current_user.id).count()
        except Exception:  # database unavailable: keep the page renderable
            db.session.rollback()
            clinic, pending, chat_unread = dict(ClinicSetting.DEFAULTS), 0, 0
        return {"clinic": clinic, "today": date.today(), "now": datetime.now(), "pending_count": pending, "chat_unread": chat_unread}

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if current_user.is_authenticated:          # don't let the back button show private pages after logout
            response.headers["Cache-Control"] = "no-store"
        return response

    # ------------------------------------------------------------ friendly error pages
    def error_page(code, title, message):
        return render_template("errors/error.html", code=code, title=title, message=message), code

    @app.errorhandler(403)
    def forbidden(_):
        return error_page(403, "Access denied", "You do not have permission to open this page.")

    @app.errorhandler(404)
    def not_found(_):
        return error_page(404, "Page not found", "The page you are looking for does not exist.")

    @app.errorhandler(413)
    def too_large(_):
        return error_page(413, "File too large", "Uploads are limited to 2 MB.")

    @app.errorhandler(CSRFError)
    def csrf_failed(_):
        return error_page(400, "Session expired", "Your form expired or was invalid. Go back, refresh the page and try again.")

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return error_page(500, "Something went wrong", "An unexpected error occurred. Please try again.")

    # ------------------------------------------------------------ create tables if missing
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:  # noqa: BLE001
            print("\n[ClinicFlow] Could not connect to MySQL: ", exc)
            print("[ClinicFlow] Start MySQL in XAMPP, create the 'clinicflow' database, "
                  "and check DB_USER / DB_PASSWORD in .env\n")
    # ------------------------------------------------------------ tell the developer if email is ready
    import config as _cfg
    if not os.path.exists(_cfg.ENV_PATH):
        print(f"\n[ClinicFlow] Email: NOT READY. No .env file found at {_cfg.ENV_PATH}")
        print("[ClinicFlow] Copy .env.example to .env (same folder as app.py) and fill in MAIL_USERNAME / MAIL_PASSWORD.\n")
    elif not app.config["MAIL_ENABLED"]:
        print("\n[ClinicFlow] Email: NOT READY. .env was found, but MAIL_USERNAME or MAIL_PASSWORD is empty.\n")
    else:
        print(f"[ClinicFlow] Email: ready, sending as {app.config['MAIL_USERNAME']}")
    print("[ClinicFlow] Google sign-in:", "ready" if app.config["GOOGLE_ENABLED"] else "not set up (optional, the button stays hidden)")
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
