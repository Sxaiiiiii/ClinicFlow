"""Appointment management for staff, plus the shared time-slot lookup."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from extensions import db
from models import Appointment, ClinicSetting, Patient, Staff, User
from services.appointment_service import AppointmentService
from services.mail_service import MailService
from utils import (STAFF_ROLES, clean, now, parse_date, parse_time, role_required,
                   to_int, today)

bp = Blueprint("appointments", __name__, url_prefix="/appointments")

ACTION_TO_STATUS = {"confirm": "confirmed", "reject": "rejected", "cancel": "cancelled", "complete": "completed"}


def _clinicians():
    return (Staff.query.join(User).filter(User.role.in_(("doctor", "nurse")), User.active.is_(True))
            .order_by(Staff.last_name).all())


@bp.route("/")
@role_required(*STAFF_ROLES)
def index():
    status = clean(request.args.get("status"))
    day = parse_date(request.args.get("date"))
    q = clean(request.args.get("q"))
    mine = request.args.get("mine") == "1" and current_user.role in ("doctor", "nurse") and current_user.staff
    query = Appointment.query.join(Patient)
    if mine:
        query = query.filter(or_(Appointment.staff_id == current_user.staff.id, Appointment.staff_id.is_(None)))
    if status in Appointment.STATUSES:
        query = query.filter(Appointment.status == status)
    if day:
        query = query.filter(Appointment.appointment_date == day)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Patient.first_name.ilike(like), Patient.last_name.ilike(like),
                                 Patient.patient_no.ilike(like), Appointment.reason.ilike(like)))
    items = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).limit(200).all()
    return render_template("manage/appointments.html", items=items, status=status, mine=bool(mine), day=request.args.get("date", ""),
                           q=q, patients=Patient.query.order_by(Patient.last_name).all(), clinicians=_clinicians())


@bp.route("/create", methods=["POST"])
@role_required(*STAFF_ROLES)
def create():
    f = request.form
    patient = db.session.get(Patient, to_int(f.get("patient_id"), 0))
    appt_date, appt_time = parse_date(f.get("appointment_date")), parse_time(f.get("appointment_time"))
    reason = clean(f.get("reason"))
    staff_id = to_int(f.get("staff_id"))
    errors = []
    if patient is None:
        errors.append("Select a patient.")
    if not 3 <= len(reason) <= 255:
        errors.append("Reason for visit must be 3–255 characters.")
    if staff_id and db.session.get(Staff, staff_id) is None:
        errors.append("Selected staff member does not exist.")
    if patient is not None:
        errors += AppointmentService.validate(appt_date, appt_time, patient.id, staff_id)
    if errors:
        for message in errors:
            flash(message, "danger")
    else:
        appointment = AppointmentService.create(patient, appt_date, appt_time, reason, staff_id,
                                                current_user, status="confirmed")
        db.session.commit()
        MailService.appointment_update(appointment, "Your appointment has been booked and confirmed.")
        flash("Appointment booked and confirmed.", "success")
    return redirect(url_for("appointments.index"))


@bp.route("/<int:appointment_id>/status", methods=["POST"])
@role_required(*STAFF_ROLES)
def change_status(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    new_status = ACTION_TO_STATUS.get(request.form.get("action"))
    if new_status is None:
        flash("Unknown action.", "danger")
    else:
        try:
            message = AppointmentService.set_status(appointment, new_status, current_user)
            db.session.commit()
            if new_status != "completed":
                MailService.appointment_update(appointment, message)
            flash(f"Appointment {new_status}.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return redirect(request.referrer or url_for("appointments.index"))


@bp.route("/<int:appointment_id>/reschedule", methods=["POST"])
@role_required(*STAFF_ROLES)
def reschedule(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    try:
        AppointmentService.reschedule(appointment, parse_date(request.form.get("appointment_date")),
                                      parse_time(request.form.get("appointment_time")), current_user)
        db.session.commit()
        MailService.appointment_update(appointment, "Your appointment has been rescheduled.")
        flash("Appointment rescheduled.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("appointments.index"))


@bp.route("/slots")
@login_required
def slots():
    """JSON list of time slots for a date (used by the booking forms)."""
    day = parse_date(request.args.get("date"))
    staff_id, exclude = request.args.get("staff_id", type=int), request.args.get("exclude", type=int)
    if day is None:
        return jsonify(closed=True, message="Choose a date first.", slots=[])
    if day < today():
        return jsonify(closed=True, message="That date has already passed.", slots=[])
    if day.weekday() not in ClinicSetting.operating_days():
        return jsonify(closed=True, message="The clinic is closed on that day.", slots=[])
    taken = set()
    if staff_id:
        rows = Appointment.query.filter(Appointment.appointment_date == day, Appointment.staff_id == staff_id,
                                        Appointment.status.in_(Appointment.ACTIVE))
        if exclude:
            rows = rows.filter(Appointment.id != exclude)
        taken = {r.appointment_time for r in rows}
    current = now().time()
    out = [{"value": t.strftime("%H:%M"), "label": t.strftime("%I:%M %p"),
            "available": not (day == today() and t <= current) and t not in taken}
           for t in ClinicSetting.slot_times()]
    return jsonify(closed=False, message="", slots=out)
