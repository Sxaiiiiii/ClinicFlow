"""Medical records / consultations. Visible to clinic staff only; only doctors/nurses write."""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from extensions import db
from models import ActivityLog, MedicalRecord, Patient, QueueEntry
from services.queue_service import QueueService
from utils import CLINICAL_ROLES, STAFF_ROLES, clean, role_required, to_int

bp = Blueprint("records", __name__, url_prefix="/records")


@bp.route("/")
@role_required(*STAFF_ROLES)
def index():
    q = clean(request.args.get("q"))
    query = MedicalRecord.visible_to(current_user).join(Patient)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Patient.first_name.ilike(like), Patient.last_name.ilike(like),
                                 Patient.patient_no.ilike(like), MedicalRecord.diagnosis.ilike(like),
                                 MedicalRecord.chief_complaint.ilike(like)))
    return render_template("manage/records.html", records=query.order_by(MedicalRecord.consultation_date.desc()).limit(200).all(), q=q)


@bp.route("/new", methods=["GET", "POST"])
@role_required(*CLINICAL_ROLES)
def create():
    patients = Patient.query.order_by(Patient.last_name, Patient.first_name).all()
    preset = {"patient_id": request.args.get("patient_id", ""), "queue_id": request.args.get("queue_id", "")}
    if request.method == "POST":
        f = request.form
        patient = db.session.get(Patient, to_int(f.get("patient_id"), 0))
        fields = {k: clean(f.get(k)) for k in ("chief_complaint", "diagnosis", "treatment", "recommendations", "notes")}
        errors = []
        if patient is None:
            errors.append("Select a patient.")
        for key, label in (("chief_complaint", "Chief complaint"), ("diagnosis", "Diagnosis"), ("treatment", "Treatment")):
            if len(fields[key]) < 3:
                errors.append(f"{label} is required.")
        if any(len(v) > 5000 for v in fields.values()):
            errors.append("Each field must be under 5,000 characters.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("manage/record_form.html", patients=patients, form=f)
        queue_entry = db.session.get(QueueEntry, to_int(f.get("queue_id"), 0))
        record = MedicalRecord(patient_id=patient.id, staff_id=current_user.staff.id,
                               queue_id=queue_entry.id if queue_entry and queue_entry.patient_id == patient.id else None,
                               consultation_date=datetime.now(), recommendations=fields["recommendations"] or None,
                               notes=fields["notes"] or None, chief_complaint=fields["chief_complaint"],
                               diagnosis=fields["diagnosis"], treatment=fields["treatment"])
        db.session.add(record)
        ActivityLog.record("Medical record created", f"{patient.full_name}: {fields['diagnosis'][:80]}", current_user, patient)
        if f.get("complete_queue") and record.queue_id and queue_entry.status == "serving":
            QueueService.complete(queue_entry, current_user)
        db.session.commit()
        flash("Consultation record saved.", "success")
        return redirect(url_for("patients.detail", patient_id=patient.id))
    return render_template("manage/record_form.html", patients=patients, form=preset)
