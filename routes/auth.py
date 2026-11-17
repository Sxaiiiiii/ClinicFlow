"""Public pages, registration, login/logout, password reset and profile management."""
import hmac
import os
import re
import secrets
import time
import uuid
from datetime import date

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import MultiDict
from werkzeug.security import generate_password_hash

from extensions import db
from models import ActivityLog, SocialAccount, User
from services.google_auth_service import GoogleAuthError, GoogleAuthService
from services.mail_service import MailService
from services.patient_service import PatientService
from services.verification_service import VerificationService
from utils import (clean, now, password_errors, safe_next_url, valid_email,
                   valid_name, valid_phone)

bp = Blueprint("auth", __name__)

ALLOWED_PHOTO_TYPES = {"png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "jpeg": b"\xff\xd8\xff"}


def _flash_all(errors, category="danger"):
    for message in errors:
        flash(message, category)


# --------------------------------------------------------------------------- public
@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.dashboard_endpoint))
    return render_template("index.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.dashboard_endpoint))
    login_as = request.form.get("login_as", request.args.get("as", "patient"))
    if login_as not in ("patient", "staff"):
        login_as = "patient"

    if request.method == "POST":
        email = clean(request.form.get("email")).lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first() if email else None

        if not email or not password:
            flash("Please enter your email and password.", "danger")
        elif user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
        elif not user.active:
            flash("This account has been deactivated. Please contact the clinic.", "danger")
        elif (login_as == "patient") != (user.role == "patient"):
            who = "a staff account — choose “Doctor / Nurse”" if user.role != "patient" \
                else "a patient account — choose “Patient”"
            flash(f"That is {who} before signing in.", "warning")
        else:
            login_user(user, remember=bool(request.form.get("remember")))
            user.last_login = now()
            ActivityLog.record("Login", f"{user.display_name} signed in ({user.role})", user)
            db.session.commit()
            target = request.args.get("next")
            return redirect(target if safe_next_url(target) else url_for(user.dashboard_endpoint))
    return render_template("login.html", login_as=login_as)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


def _finish_registration(data, password_hash):
    """Create the login account + patient profile (used after the email code is confirmed)."""
    user = User(email=data["email"], role="patient")
    user.adopt_password_hash(password_hash)
    db.session.add(user)
    db.session.flush()
    patient = PatientService.create(data, user=user)
    ActivityLog.record("Patient registration", f"New patient registered: {patient.full_name}", user, patient)
    db.session.commit()
    return user


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.dashboard_endpoint))
    if request.method == "POST":
        data, errors = PatientService.parse(request.form, require_email=True)
        password = request.form.get("password", "")
        errors += password_errors(password)
        if password != request.form.get("confirm_password", ""):
            errors.append("Passwords do not match.")
        if data["email"] and User.query.filter_by(email=data["email"]).first():
            errors.append("That email address is already registered.")
        if errors:
            _flash_all(errors)
            return render_template("register.html", form=request.form)

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        if not current_app.config["REQUIRE_EMAIL_VERIFICATION"]:
            try:
                user = _finish_registration(data, password_hash)
            except IntegrityError:
                db.session.rollback()
                flash("That email address is already registered.", "danger")
                return render_template("register.html", form=request.form)
            MailService.welcome(user)
            login_user(user)
            flash("Welcome to ClinicFlow! Your account has been created.", "success")
            return redirect(url_for("patient.dashboard"))

        # Step 1: email a 6-digit code. The account is only created after the code is confirmed.
        try:
            payload = {"data": {**data, "date_of_birth": data["date_of_birth"].isoformat()},
                       "password_hash": password_hash}
            code = VerificationService.issue(data["email"], "register", payload)
        except ValueError as exc:
            flash(str(exc), "warning")
            return render_template("register.html", form=request.form)
        if not MailService.verification_code(data["email"], data["first_name"], code, "register"):
            db.session.rollback()
            flash("We couldn't send the verification email. Check the email address, and make sure the clinic's "
                  "email settings (MAIL_USERNAME / MAIL_PASSWORD) are set.", "danger")
            return render_template("register.html", form=request.form)
        db.session.commit()
        session["pending_email"] = data["email"]
        flash(f"We sent a 6-digit code to {data['email']}.", "info")
        return redirect(url_for("auth.verify_email"))
    return render_template("register.html", form={})


@bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    email = session.get("pending_email")
    if not email:
        flash("Please fill in the sign-up form first.", "warning")
        return redirect(url_for("auth.register"))
    if request.method == "POST":
        code = clean(request.form.get("code"))
        if not re.fullmatch(r"\d{6}", code):
            flash("Enter the 6-digit code from your email.", "danger")
        else:
            ok, message, payload = VerificationService.verify(email, "register", code)
            if not ok:
                flash(message, "danger")
            else:
                data = dict(payload["data"])
                data["date_of_birth"] = date.fromisoformat(data["date_of_birth"])
                if User.query.filter_by(email=email).first():
                    session.pop("pending_email", None)
                    flash("That email is already registered. Please sign in.", "warning")
                    return redirect(url_for("auth.login"))
                try:
                    user = _finish_registration(data, payload["password_hash"])
                except IntegrityError:
                    db.session.rollback()
                    flash("That email address is already registered.", "danger")
                    return redirect(url_for("auth.login"))
                session.pop("pending_email", None)
                MailService.welcome(user)
                login_user(user)
                flash("Email verified. Welcome to ClinicFlow!", "success")
                return redirect(url_for("patient.dashboard"))
    return render_template("verify_code.html", email=email, heading="Verify your email",
                           resend_url=url_for("auth.resend_register_code"),
                           back_url=url_for("auth.register"), back_label="Use a different email")


@bp.route("/verify-email/resend", methods=["POST"])
def resend_register_code():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("auth.register"))
    try:
        code, payload = VerificationService.reissue(email, "register")
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("auth.verify_email"))
    if MailService.verification_code(email, payload["data"]["first_name"], code, "register"):
        db.session.commit()
        flash("A new code was sent. Check your inbox (and spam folder).", "success")
    else:
        db.session.rollback()
        flash("We couldn't send the email. Please try again.", "danger")
    return redirect(url_for("auth.verify_email"))


# --------------------------------------------------------------------------- Google sign-in (optional)
@bp.route("/auth/google")
def google_login():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.dashboard_endpoint))
    if not GoogleAuthService.enabled():
        flash("Google sign-in is not set up yet.", "warning")
        return redirect(url_for("auth.login"))
    state = secrets.token_urlsafe(32)                       # proves the answer comes back to the same browser
    session["google_state"] = state
    return redirect(GoogleAuthService.authorization_url(url_for("auth.google_callback", _external=True), state))


@bp.route("/auth/google/callback")
def google_callback():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.dashboard_endpoint))
    if not GoogleAuthService.enabled():
        return redirect(url_for("auth.login"))
    if request.args.get("error"):
        flash("Google sign-in was cancelled.", "info")
        return redirect(url_for("auth.login"))
    expected, received = session.pop("google_state", None), request.args.get("state", "")
    if not expected or not hmac.compare_digest(expected, received):
        flash("Your Google sign-in expired. Please try again.", "danger")
        return redirect(url_for("auth.login"))
    code = request.args.get("code", "")
    if not code:
        flash("Google did not send a sign-in code. Please try again.", "danger")
        return redirect(url_for("auth.login"))
    try:
        profile = GoogleAuthService.fetch_profile(code, url_for("auth.google_callback", _external=True))
    except GoogleAuthError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("auth.login"))

    link = SocialAccount.query.filter_by(provider="google", provider_user_id=profile["sub"]).first()
    user = link.user if link else User.query.filter_by(email=profile["email"]).first()
    if user is not None:
        if user.role != "patient":                          # Google never grants or touches staff/admin access
            flash("Doctor, nurse and admin accounts must sign in with their email and password.", "warning")
            return redirect(url_for("auth.login", **{"as": "staff"}))
        if not user.active:
            flash("This account has been deactivated. Please contact the clinic.", "danger")
            return redirect(url_for("auth.login"))
        try:
            if link is None:                                # same email as an existing patient: link, don't duplicate
                db.session.add(SocialAccount(user_id=user.id, provider="google",
                                             provider_user_id=profile["sub"], email=profile["email"]))
            user.last_login = now()
            ActivityLog.record("Login", f"{user.display_name} signed in with Google (patient)", user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Could not link your Google account. Please try again.", "danger")
            return redirect(url_for("auth.login"))
        login_user(user)
        return redirect(url_for("patient.dashboard"))

    # brand-new person: Google proves the email, we still need the clinic details
    session["google_pending"] = {"sub": profile["sub"], "email": profile["email"], "at": time.time(),
                                 "given_name": profile["given_name"], "family_name": profile["family_name"]}
    return redirect(url_for("auth.google_complete"))


@bp.route("/auth/google/complete", methods=["GET", "POST"])
def google_complete():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.dashboard_endpoint))
    pending = session.get("google_pending")
    if not pending or time.time() - pending.get("at", 0) > 15 * 60:
        session.pop("google_pending", None)
        flash("Please continue with Google again.", "warning")
        return redirect(url_for("auth.login"))
    email = pending["email"]

    if request.method == "POST":
        form = MultiDict(request.form)
        form["email"] = email                               # the email always comes from Google, never from the form
        data, errors = PatientService.parse(form, require_email=True)
        if User.query.filter_by(email=email).first():
            session.pop("google_pending", None)
            flash("That email is already registered. Please sign in.", "warning")
            return redirect(url_for("auth.login"))
        if errors:
            _flash_all(errors)
            return render_template("google_complete.html", form=request.form, email=email)
        try:
            user = User(email=email, role="patient")        # always a patient; nobody becomes staff through Google
            user.adopt_password_hash(generate_password_hash(secrets.token_urlsafe(32), method="pbkdf2:sha256"))
            db.session.add(user)
            db.session.flush()
            patient = PatientService.create(data, user=user)
            db.session.add(SocialAccount(user_id=user.id, provider="google",
                                         provider_user_id=pending["sub"], email=email))
            ActivityLog.record("Patient registration", f"New patient registered with Google: {patient.full_name}",
                               user, patient)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email address is already registered.", "danger")
            return redirect(url_for("auth.login"))
        session.pop("google_pending", None)
        MailService.welcome(user)
        login_user(user)
        flash("Welcome to ClinicFlow! Your account has been created.", "success")
        return redirect(url_for("patient.dashboard"))

    form = {"first_name": pending.get("given_name", ""), "last_name": pending.get("family_name", "")}
    return render_template("google_complete.html", form=form, email=email)


# --------------------------------------------------------------------------- password reset (email code)
@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = clean(request.form.get("email")).lower()
        if not valid_email(email):
            flash("Enter a valid email address.", "danger")
            return render_template("forgot_password.html")
        if not MailService.configured():
            flash("The email service is not set up yet. Please contact the clinic.", "danger")
            return render_template("forgot_password.html")
        user = User.query.filter_by(email=email).first()
        if user and user.active:
            try:
                code = VerificationService.issue(email, "reset")
            except ValueError as exc:
                flash(str(exc), "warning")
                return render_template("forgot_password.html")
            if not MailService.verification_code(email, user.short_name, code, "reset"):
                db.session.rollback()
                flash("We couldn't send the email. Please try again.", "danger")
                return render_template("forgot_password.html")
            db.session.commit()
        # same message and next page either way, so nobody can discover which emails are registered
        session["reset_email"] = email
        flash("If that email is registered, we sent a 6-digit code. It expires in 10 minutes.", "info")
        return redirect(url_for("auth.verify_reset"))
    return render_template("forgot_password.html")


@bp.route("/forgot-password/code", methods=["GET", "POST"])
def verify_reset():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        code = clean(request.form.get("code"))
        if not re.fullmatch(r"\d{6}", code):
            flash("Enter the 6-digit code from your email.", "danger")
        else:
            ok, message, _ = VerificationService.verify(email, "reset", code)
            user = User.query.filter_by(email=email).first()
            if not ok or user is None:
                flash(message or "Incorrect code.", "danger")
            else:
                session["reset_user_id"] = user.id
                session["reset_at"] = time.time()
                return redirect(url_for("auth.reset_password"))
    return render_template("verify_code.html", email=email, heading="Enter your reset code",
                           resend_url=url_for("auth.resend_reset_code"),
                           back_url=url_for("auth.forgot_password"), back_label="Use a different email")


@bp.route("/forgot-password/resend", methods=["POST"])
def resend_reset_code():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))
    user = User.query.filter_by(email=email).first()
    if user and user.active:
        try:
            code = VerificationService.issue(email, "reset")
            if MailService.verification_code(email, user.short_name, code, "reset"):
                db.session.commit()
            else:
                db.session.rollback()
                flash("We couldn't send the email. Please try again.", "danger")
                return redirect(url_for("auth.verify_reset"))
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("auth.verify_reset"))
    flash("If that email is registered, a new code was sent.", "info")
    return redirect(url_for("auth.verify_reset"))


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id, started = session.get("reset_user_id"), session.get("reset_at", 0)
    user = db.session.get(User, user_id) if user_id else None
    if user is None or time.time() - started > 15 * 60:
        session.pop("reset_user_id", None)
        flash("Please confirm your email code first.", "warning")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        errors = password_errors(password)
        if password != request.form.get("confirm_password", ""):
            errors.append("Passwords do not match.")
        if errors:
            _flash_all(errors)
        else:
            user.set_password(password)
            ActivityLog.record("Password reset", f"{user.display_name} reset their password", user)
            db.session.commit()
            for key in ("reset_user_id", "reset_at", "reset_email"):
                session.pop(key, None)
            flash("Password updated. You can sign in now.", "success")
            return redirect(url_for("auth.login"))
    return render_template("reset_password.html")


# --------------------------------------------------------------------------- profile
def _photo_ok(file):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    head = file.stream.read(12)
    file.stream.seek(0)
    if ext == "webp":
        return ext if head[:4] == b"RIFF" and head[8:12] == b"WEBP" else None
    magic = ALLOWED_PHOTO_TYPES.get(ext)
    return ext if magic and head.startswith(magic) else None


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user
    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "details":
            if user.role == "patient":
                data, errors = PatientService.parse(request.form, require_email=True)
                new_email = data["email"]
            else:
                new_email = clean(request.form.get("email")).lower()
                data = {"first_name": clean(request.form.get("first_name")),
                        "last_name": clean(request.form.get("last_name")),
                        "contact_number": clean(request.form.get("contact_number")).replace(" ", ""),
                        "specialization": clean(request.form.get("specialization"))}
                errors = []
                if not valid_name(data["first_name"]) or not valid_name(data["last_name"]):
                    errors.append("Enter a valid first and last name.")
                if data["contact_number"] and not valid_phone(data["contact_number"]):
                    errors.append("Contact number must be a Philippine mobile number (e.g. 09171234567).")
                if not valid_email(new_email):
                    errors.append("Enter a valid email address.")
            if new_email and User.query.filter(User.email == new_email, User.id != user.id).first():
                errors.append("That email address is used by another account.")
            if errors:
                _flash_all(errors)
            else:
                if user.role == "patient":
                    PatientService.apply(user.patient, data)
                else:
                    staff = user.staff
                    staff.first_name, staff.last_name = data["first_name"], data["last_name"]
                    staff.contact_number = data["contact_number"] or None
                    if user.role != "admin":
                        staff.specialization = data["specialization"] or None
                user.email = new_email
                db.session.commit()
                flash("Profile updated.", "success")

        elif form_type == "password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("password", "")
            errors = password_errors(new_pw)
            if not user.check_password(current_pw):
                errors.append("Your current password is incorrect.")
            if new_pw != request.form.get("confirm_password", ""):
                errors.append("New passwords do not match.")
            if errors:
                _flash_all(errors)
            else:
                user.set_password(new_pw)
                ActivityLog.record("Password changed", f"{user.display_name} changed their password", user)
                db.session.commit()
                flash("Password changed.", "success")

        elif form_type == "photo":
            file = request.files.get("photo")
            if not file or not file.filename:
                flash("Choose a photo first.", "warning")
            else:
                ext = _photo_ok(file)
                if not ext:
                    flash("Photo must be a real PNG, JPG or WEBP image (max 2 MB).", "danger")
                else:
                    folder = current_app.config["UPLOAD_FOLDER"]
                    os.makedirs(folder, exist_ok=True)
                    name = f"{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                    file.save(os.path.join(folder, name))
                    if user.profile_photo:
                        old = os.path.join(folder, os.path.basename(user.profile_photo))
                        if os.path.exists(old):
                            os.remove(old)
                    user.profile_photo = name
                    db.session.commit()
                    flash("Profile photo updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html")
