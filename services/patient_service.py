"""Patient form parsing/validation and creation, shared by registration, staff and queue."""
import uuid
from datetime import date, timedelta

from extensions import db
from models import Patient
from utils import clean, parse_date, valid_email, valid_name, valid_phone


class PatientService:
    @staticmethod
    def parse(form, require_email=False):
        """Return (clean_data, errors) from a submitted patient form."""
        errors = []
        data = {
            "first_name": clean(form.get("first_name")),
            "middle_name": clean(form.get("middle_name")),
            "last_name": clean(form.get("last_name")),
            "gender": clean(form.get("gender")),
            "contact_number": clean(form.get("contact_number")).replace(" ", ""),
            "email": clean(form.get("email")).lower(),
            "address": clean(form.get("address")),
        }
        if not valid_name(data["first_name"]):
            errors.append("Enter a valid first name (letters only, 2–50 characters).")
        if data["middle_name"] and not valid_name(data["middle_name"]):
            errors.append("Middle name may only contain letters.")
        if not valid_name(data["last_name"]):
            errors.append("Enter a valid last name (letters only, 2–50 characters).")

        dob = parse_date(form.get("date_of_birth"))
        if dob is None:
            errors.append("Date of birth is required.")
        elif dob > date.today():
            errors.append("Date of birth cannot be in the future.")
        elif dob < date.today() - timedelta(days=365 * 120):
            errors.append("Date of birth is not realistic.")
        data["date_of_birth"] = dob

        if data["gender"] not in Patient.GENDERS:
            errors.append("Select a gender.")
        if not valid_phone(data["contact_number"]):
            errors.append("Contact number must be a Philippine mobile number (e.g. 09171234567).")
        if data["email"] and not valid_email(data["email"]):
            errors.append("Enter a valid email address.")
        if require_email and not data["email"]:
            errors.append("Email address is required.")
        if not 5 <= len(data["address"]) <= 255:
            errors.append("Address must be between 5 and 255 characters.")
        return data, errors

    @staticmethod
    def apply(patient, data):
        for field in ("first_name", "middle_name", "last_name", "date_of_birth", "gender",
                      "contact_number", "email", "address"):
            setattr(patient, field, data[field] or None if field in ("middle_name", "email") else data[field])

    @classmethod
    def create(cls, data, user=None):
        """Create a patient and give it a unique number like PT-00012 (caller commits)."""
        patient = Patient(patient_no="TMP-" + uuid.uuid4().hex[:12], user_id=getattr(user, "id", None))
        cls.apply(patient, data)
        db.session.add(patient)
        db.session.flush()                       # gives us patient.id
        patient.patient_no = f"PT-{patient.id:05d}"
        return patient
