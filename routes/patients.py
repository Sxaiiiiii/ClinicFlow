"""Patient management (staff side): list, search, register, edit, view, delete."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from extensions import db
from models import ActivityLog, MedicalRecord, Patient
from services.chat_service import ChatService
from services.patient_service import PatientService
from utils import CLINICAL_ROLES, STAFF_ROLES, clean, role_required

bp = Blueprint("patients", __name__, url_prefix="/patients")


@bp.route("/")
@role_required(*STAFF_ROLES)
def index():
    q = clean(request.args.get("q"))
    query = Patient.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Patient.first_name.ilike(like), Patient.last_name.ilike(like),
                                 Patient.patient_no.ilike(like), Patient.contact_number.ilike(like),
                                 Patient.email.ilike(like)))
    return render_template("manage/patients.html", patients=query.order_by(Patient.last_name, Patient.first_name).limit(300).all(), q=q)


@bp.route("/new", methods=["GET", "POST"])
@role_required(*STAFF_ROLES)
def create():
    if request.method == "POST":
        data, errors = PatientService.parse(request.form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("manage/patient_form.html", patient=None, form=request.form)
        patient = PatientService.create(data)
        ActivityLog.record("Patient registration", f"New patient registered: {patient.full_name}", current_user, patient)
        db.session.commit()
        flash(f"{patient.full_name} was registered as {patient.patient_no}.", "success")
        return redirect(url_for("patients.detail", patient_id=patient.id))
    return render_template("manage/patient_form.html", patient=None, form={})


@bp.route("/<int:patient_id>")
@role_required(*STAFF_ROLES)
def detail(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    records = (MedicalRecord.visible_to(current_user).filter(MedicalRecord.patient_id == patient.id)
               .order_by(MedicalRecord.consultation_date.desc()).all())
    return render_template("manage/patient_detail.html", patient=patient, records=records,
                           hidden_records=len(patient.medical_records) - len(records),
                           can_chat=bool(patient.user_id and current_user.role in CLINICAL_ROLES and current_user.staff
                                         and ChatService.has_visit(patient.id, current_user.staff.id)))


@bp.route("/<int:patient_id>/edit", methods=["GET", "POST"])
@role_required(*STAFF_ROLES)
def edit(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    if request.method == "POST":
        data, errors = PatientService.parse(request.form)
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("manage/patient_form.html", patient=patient, form=request.form)
        PatientService.apply(patient, data)
        ActivityLog.record("Patient updated", f"{patient.full_name} ({patient.patient_no})", current_user, patient)
        db.session.commit()
        flash("Patient information updated.", "success")
        return redirect(url_for("patients.detail", patient_id=patient.id))
    return render_template("manage/patient_form.html", patient=patient, form={})


@bp.route("/<int:patient_id>/delete", methods=["POST"])
@role_required("admin")
def delete(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    name, account = patient.full_name, patient.user
    db.session.delete(patient)
    if account is not None:
        db.session.delete(account)
    ActivityLog.record("Patient deleted", name, current_user)
    db.session.commit()
    flash(f"{name} and all linked records were deleted.", "success")
    return redirect(url_for("patients.index"))
