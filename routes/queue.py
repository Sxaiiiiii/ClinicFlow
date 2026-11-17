"""Queue management: walk-ins, scheduled patients, calling the next patient."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from extensions import db
from models import Appointment, Patient, QueueEntry, Staff, User
from services.patient_service import PatientService
from services.queue_service import QueueService
from utils import CLINICAL_ROLES, STAFF_ROLES, clean, role_required, to_int, today

bp = Blueprint("queue", __name__, url_prefix="/queue")


def _my_staff():
    """Doctors/nurses act as themselves; the admin acts without a staff profile."""
    return current_user.staff if current_user.role in CLINICAL_ROLES else None


@bp.route("/")
@role_required(*STAFF_ROLES)
def index():
    q, status = clean(request.args.get("q")), clean(request.args.get("status"))
    mine = request.args.get("mine") == "1" and current_user.role in CLINICAL_ROLES and current_user.staff
    query = QueueEntry.query.join(Patient).filter(QueueEntry.queue_date == today())
    if mine:
        query = query.filter(or_(QueueEntry.staff_id == current_user.staff.id, QueueEntry.staff_id.is_(None)))
    if q:
        like, digits = f"%{q}%", re.sub(r"\D", "", q)
        conditions = [Patient.first_name.ilike(like), Patient.last_name.ilike(like), Patient.patient_no.ilike(like)]
        if digits and re.fullmatch(r"[Qq]?-?\d+", q):
            conditions.append(QueueEntry.queue_number == int(digits))
        query = query.filter(or_(*conditions))
    if status in QueueEntry.STATUSES:
        query = query.filter(QueueEntry.status == status)
    entries = query.order_by(QueueEntry.queue_number).all()
    groups = {s: [e for e in entries if e.status == s] for s in QueueEntry.STATUSES}

    queued_appt_ids = [row[0] for row in db.session.query(QueueEntry.appointment_id).filter(
        QueueEntry.queue_date == today(), QueueEntry.appointment_id.isnot(None),
        QueueEntry.status != "cancelled")]
    scheduled = Appointment.query.filter(Appointment.appointment_date == today(),
                                         Appointment.status == "confirmed")
    if queued_appt_ids:
        scheduled = scheduled.filter(~Appointment.id.in_(queued_appt_ids))
    doctors = Staff.query.join(User).filter(User.role == "doctor", User.active.is_(True)).order_by(Staff.last_name).all()
    return render_template("manage/queue.html", groups=groups, q=q, status=status, mine=bool(mine),
                           scheduled=scheduled.order_by(Appointment.appointment_time).all(),
                           patients=Patient.query.order_by(Patient.last_name).all(), doctors=doctors,
                           can_serve=current_user.role in CLINICAL_ROLES or current_user.role == "admin")


@bp.route("/walk-in", methods=["POST"])
@role_required(*STAFF_ROLES)
def walk_in():
    f = request.form
    reason = clean(f.get("reason"))
    staff_id = to_int(f.get("staff_id"))
    if not 3 <= len(reason) <= 255:
        flash("Reason for visit must be 3–255 characters.", "danger")
        return redirect(url_for("queue.index"))
    if staff_id and db.session.get(Staff, staff_id) is None:
        flash("Selected doctor does not exist.", "danger")
        return redirect(url_for("queue.index"))
    try:
        if f.get("patient_id"):
            patient = db.session.get(Patient, to_int(f.get("patient_id"), 0))
            if patient is None:
                raise ValueError("Selected patient was not found.")
        else:
            data, errors = PatientService.parse(f)
            if errors:
                raise ValueError(" ".join(errors))
            patient = PatientService.create(data)
        entry = QueueService.add_walk_in(patient, reason, staff_id, current_user)
        db.session.commit()
        flash(f"{patient.full_name} was added to the queue as {entry.code}.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("queue.index"))


@bp.route("/add-scheduled/<int:appointment_id>", methods=["POST"])
@role_required(*STAFF_ROLES)
def add_scheduled(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    try:
        entry = QueueService.add_scheduled(appointment, current_user)
        db.session.commit()
        flash(f"{appointment.patient.full_name} was added to the queue as {entry.code}.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("queue.index"))


@bp.route("/call-next", methods=["POST"])
@role_required(*STAFF_ROLES)
def call_next():
    try:
        entry = QueueService.call_next(_my_staff(), current_user)
        db.session.commit()
        flash(f"Now serving {entry.code} — {entry.patient.full_name}.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    return redirect(url_for("queue.index"))


@bp.route("/<int:entry_id>/<action>", methods=["POST"])
@role_required(*STAFF_ROLES)
def update(entry_id, action):
    entry = db.get_or_404(QueueEntry, entry_id)
    try:
        if action == "serve":
            QueueService.serve(entry, _my_staff(), current_user)
        elif action == "complete":
            QueueService.complete(entry, current_user)
        elif action == "cancel":
            QueueService.cancel(entry, current_user)
        else:
            raise ValueError("Unknown action.")
        db.session.commit()
        flash(f"{entry.code} updated.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("queue.index"))
