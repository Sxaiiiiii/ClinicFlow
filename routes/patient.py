"""Patient portal: dashboard, booking, own appointments and own queue status."""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db
from models import ActivityLog, Appointment, ClinicSetting, QueueEntry, Staff, User
from services.appointment_service import AppointmentService
from services.mail_service import MailService
from services.queue_service import QueueService
from utils import clean, parse_date, parse_time, role_required, to_int, today

bp = Blueprint("patient", __name__, url_prefix="/patient")


def _me():
    patient = current_user.patient
    if patient is None:
        abort(403)
    return patient


def _my_queue_entry(patient):
    return (QueueEntry.query.filter(QueueEntry.patient_id == patient.id, QueueEntry.queue_date == today(),
                                    QueueEntry.status.in_(QueueEntry.ACTIVE))
            .order_by(QueueEntry.queue_number).first())


@bp.route("/dashboard")
@role_required("patient")
def dashboard():
    patient = _me()
    now_ = datetime.now()
    upcoming = (Appointment.query.filter(Appointment.patient_id == patient.id,
                                         Appointment.status.in_(Appointment.ACTIVE),
                                         Appointment.appointment_date >= today())
                .order_by(Appointment.appointment_date, Appointment.appointment_time).all())
    upcoming = next((a for a in upcoming if a.scheduled_at >= now_), None)
    entry = _my_queue_entry(patient)
    history = (Appointment.query.filter_by(patient_id=patient.id)
               .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).limit(5).all())
    notifications = (ActivityLog.query.filter(ActivityLog.patient_id == patient.id,
                                              ActivityLog.action.in_(ActivityLog.NOTIFY))
                     .order_by(ActivityLog.created_at.desc()).limit(6).all())
    return render_template("patient/dashboard.html", patient=patient, upcoming=upcoming, entry=entry,
                           ahead=QueueService.position_of(entry) if entry else None,
                           history=history, notifications=notifications)


@bp.route("/book", methods=["GET", "POST"])
@role_required("patient")
def book():
    patient = _me()
    doctors = (Staff.query.join(User).filter(User.role == "doctor", User.active.is_(True))
               .order_by(Staff.last_name).all())
    if request.method == "POST":
        appt_date, appt_time = parse_date(request.form.get("appointment_date")), parse_time(request.form.get("appointment_time"))
        reason = clean(request.form.get("reason"))
        staff_id = to_int(request.form.get("staff_id"))
        errors = []
        if not 3 <= len(reason) <= 255:
            errors.append("Please describe the reason for your visit (3–255 characters).")
        if staff_id and staff_id not in {d.id for d in doctors}:
            errors.append("Please choose a valid doctor.")
        errors += AppointmentService.validate(appt_date, appt_time, patient.id, staff_id)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("patient/book_appointment.html", doctors=doctors, form=request.form)
        appointment = AppointmentService.create(patient, appt_date, appt_time, reason, staff_id,
                                                current_user, status="pending")
        db.session.commit()
        MailService.appointment_update(appointment, "We received your appointment request. "
                                       "The clinic will confirm it shortly.")
        flash("Appointment requested! You'll be notified once the clinic confirms it.", "success")
        return redirect(url_for("patient.appointments"))
    return render_template("patient/book_appointment.html", doctors=doctors, form={})


@bp.route("/appointments")
@role_required("patient")
def appointments():
    patient = _me()
    items = (Appointment.query.filter_by(patient_id=patient.id)
             .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all())
    return render_template("patient/appointments.html", items=items)


@bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@role_required("patient")
def cancel(appointment_id):
    patient = _me()
    appointment = db.get_or_404(Appointment, appointment_id)
    if appointment.patient_id != patient.id:          # patients may only touch their own records
        abort(403)
    if not appointment.can_patient_cancel:
        flash("This appointment can no longer be cancelled.", "warning")
    else:
        AppointmentService.set_status(appointment, "cancelled", current_user)
        db.session.commit()
        flash("Your appointment was cancelled.", "success")
    return redirect(url_for("patient.appointments"))


@bp.route("/queue")
@role_required("patient")
def queue_status():
    patient = _me()
    entry = _my_queue_entry(patient)
    serving = (QueueEntry.query.filter_by(queue_date=today(), status="serving")
               .order_by(QueueEntry.called_at.desc()).first())
    ahead = QueueService.position_of(entry) if entry else None
    avg = int(ClinicSetting.as_dict()["avg_service_minutes"])
    todays = (Appointment.query.filter(Appointment.patient_id == patient.id,
                                       Appointment.appointment_date == today(),
                                       Appointment.status.in_(Appointment.ACTIVE)).first())
    return render_template("patient/queue_status.html", entry=entry, serving=serving, ahead=ahead,
                           eta=(ahead + (1 if entry and entry.status == "waiting" else 0)) * avg if entry else None,
                           todays=todays)
