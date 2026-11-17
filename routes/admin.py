"""Administrator-only pages: dashboard, staff management, settings, activity logs."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (ActivityLog, ChatMessage, ClinicSetting, MedicalRecord, Patient, Staff, User)
from services.stats_service import StatsService
from utils import (clean, password_errors, role_required, to_int, valid_email,
                   valid_name, valid_phone)

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/dashboard")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html", **StatsService.dashboard_data())


# --------------------------------------------------------------------------- staff
@bp.route("/staff")
@role_required("admin")
def staff_list():
    q = clean(request.args.get("q"))
    query = Staff.query.join(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Staff.first_name.ilike(like), Staff.last_name.ilike(like),
                                 User.email.ilike(like), Staff.employee_no.ilike(like)))
    members = query.order_by(User.role, Staff.last_name).all()
    return render_template("admin/staff.html", members=members, q=q)


@bp.route("/staff/save", methods=["POST"])
@role_required("admin")
def staff_save():
    f = request.form
    staff = None
    staff_id = to_int(f.get("staff_id"))
    if staff_id:
        staff = db.get_or_404(Staff, staff_id)

    first, last = clean(f.get("first_name")), clean(f.get("last_name"))
    email = clean(f.get("email")).lower()
    role = clean(f.get("role"))
    contact = clean(f.get("contact_number")).replace(" ", "")
    spec = clean(f.get("specialization"))
    password = f.get("password", "")

    errors = []
    if not valid_name(first) or not valid_name(last):
        errors.append("Enter a valid first and last name.")
    if not valid_email(email):
        errors.append("Enter a valid email address.")
    if contact and not valid_phone(contact):
        errors.append("Contact number must be a Philippine mobile number (e.g. 09171234567).")
    if staff is None or (staff.user.role != "admin"):
        if role not in ("doctor", "nurse"):
            errors.append("Role must be Doctor or Nurse.")
    if staff is None or password:
        errors += password_errors(password)
    duplicate = User.query.filter(User.email == email)
    if staff:
        duplicate = duplicate.filter(User.id != staff.user_id)
    if duplicate.first():
        errors.append("That email address is already used by another account.")
    if errors:
        for message in errors:
            flash(message, "danger")
        return redirect(url_for("admin.staff_list"))

    try:
        if staff is None:
            user = User(email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            staff = Staff(user_id=user.id, employee_no="TMP", first_name=first, last_name=last,
                          specialization=spec or None, contact_number=contact or None)
            db.session.add(staff)
            db.session.flush()
            staff.employee_no = f"EMP-{staff.id:03d}"
            ActivityLog.record("Staff created", f"{staff.title_name} ({role})", current_user)
            flash(f"{staff.title_name} was added.", "success")
        else:
            staff.first_name, staff.last_name = first, last
            staff.specialization, staff.contact_number = spec or None, contact or None
            staff.user.email = email
            if staff.user.role != "admin":
                staff.user.role = role
            if password:
                staff.user.set_password(password)
            ActivityLog.record("Staff updated", staff.full_name, current_user)
            flash("Staff account updated.", "success")
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Could not save: that email is already in use.", "danger")
    return redirect(url_for("admin.staff_list"))


@bp.route("/staff/<int:staff_id>/toggle", methods=["POST"])
@role_required("admin")
def staff_toggle(staff_id):
    staff = db.get_or_404(Staff, staff_id)
    if staff.user_id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
    else:
        staff.user.active = not staff.user.active
        state = "activated" if staff.user.active else "deactivated"
        ActivityLog.record("Staff " + state, staff.full_name, current_user)
        db.session.commit()
        flash(f"{staff.full_name} was {state}.", "success")
    return redirect(url_for("admin.staff_list"))


@bp.route("/staff/<int:staff_id>/delete", methods=["POST"])
@role_required("admin")
def staff_delete(staff_id):
    staff = db.get_or_404(Staff, staff_id)
    if staff.user.role == "admin":
        flash("Administrator accounts cannot be deleted.", "danger")
    elif MedicalRecord.query.filter_by(staff_id=staff.id).first() or ChatMessage.query.filter_by(staff_id=staff.id).first():
        staff.user.active = False
        db.session.commit()
        flash(f"{staff.full_name} has consultation records or chat history, so the account was deactivated instead of deleted.",
              "warning")
    else:
        name = staff.full_name
        db.session.delete(staff.user)       # cascades to the staff profile
        ActivityLog.record("Staff deleted", name, current_user)
        db.session.commit()
        flash(f"{name} was deleted.", "success")
    return redirect(url_for("admin.staff_list"))


# --------------------------------------------------------------------------- settings & logs
@bp.route("/settings", methods=["GET", "POST"])
@role_required("admin")
def settings():
    if request.method == "POST":
        f = request.form
        errors = []
        name, address, phone = clean(f.get("clinic_name")), clean(f.get("clinic_address")), clean(f.get("clinic_phone"))
        open_t, close_t = clean(f.get("open_time")), clean(f.get("close_time"))
        slot, avg = to_int(f.get("slot_minutes")), to_int(f.get("avg_service_minutes"))
        map_query, map_link = clean(f.get("map_query")), clean(f.get("map_link"))
        if map_query and not re.fullmatch(r"-?\d{1,3}(\.\d+)?,\s*-?\d{1,3}(\.\d+)?", map_query):
            errors.append("Map location must be coordinates like 14.2281661,121.3659242.")
        if map_link and not map_link.startswith("https://"):
            errors.append("Google Maps link must start with https://")
        days = [d for d in f.getlist("operating_days") if d in list("0123456")]
        if not 2 <= len(name) <= 100:
            errors.append("Clinic name is required.")
        if not open_t or not close_t or open_t >= close_t:
            errors.append("Closing time must be later than opening time.")
        if slot is None or not 10 <= slot <= 120:
            errors.append("Slot length must be between 10 and 120 minutes.")
        if avg is None or not 1 <= avg <= 120:
            errors.append("Average service time must be between 1 and 120 minutes.")
        if not days:
            errors.append("Select at least one operating day.")
        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            for key, value in (("clinic_name", name), ("clinic_address", address), ("clinic_phone", phone), ("map_query", map_query), ("map_link", map_link),
                               ("open_time", open_t), ("close_time", close_t), ("slot_minutes", slot),
                               ("avg_service_minutes", avg), ("operating_days", ",".join(sorted(days)))):
                ClinicSetting.set(key, value)
            ActivityLog.record("Settings updated", "Clinic settings were changed", current_user)
            db.session.commit()
            flash("Clinic settings saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", s=ClinicSetting.as_dict(),
                           days=ClinicSetting.DAY_NAMES, active_days=ClinicSetting.operating_days())


@bp.route("/logs")
@role_required("admin")
def logs():
    q = clean(request.args.get("q"))
    query = ActivityLog.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ActivityLog.action.ilike(like), ActivityLog.details.ilike(like)))
    return render_template("admin/logs.html",
                           logs=query.order_by(ActivityLog.created_at.desc()).limit(300).all(), q=q)


# --------------------------------------------------------------------------- chat logs (read-only)
@bp.route("/chats")
@role_required("admin")
def chat_logs():
    q = clean(request.args.get("q")).lower()
    rows = (db.session.query(ChatMessage.patient_id, ChatMessage.staff_id, func.count(ChatMessage.id),
                             func.max(ChatMessage.id))
            .group_by(ChatMessage.patient_id, ChatMessage.staff_id)
            .order_by(func.max(ChatMessage.id).desc()).limit(300).all())
    conversations = []
    for patient_id, staff_id, count, last_id in rows:
        patient, staff = db.session.get(Patient, patient_id), db.session.get(Staff, staff_id)
        if q and q not in patient.full_name.lower() and q not in staff.full_name.lower():
            continue
        conversations.append({"patient": patient, "staff": staff, "count": count,
                              "last": db.session.get(ChatMessage, last_id)})
    return render_template("admin/chat_logs.html", conversations=conversations, q=q)


@bp.route("/chats/<int:patient_id>/<int:staff_id>")
@role_required("admin")
def chat_thread(patient_id, staff_id):
    patient, staff = db.get_or_404(Patient, patient_id), db.get_or_404(Staff, staff_id)
    messages = (ChatMessage.query.filter_by(patient_id=patient.id, staff_id=staff.id)
                .order_by(ChatMessage.id).all())
    if not messages:
        abort(404)
    # opening someone's conversation is itself recorded, so admin access is accountable
    ActivityLog.record("Chat log viewed", f"Viewed chat: {patient.full_name} and {staff.full_name}", current_user)
    db.session.commit()
    return render_template("admin/chat_thread.html", patient=patient, staff=staff, messages=messages)
