"""Appointment business rules: validation, creation and status changes."""
from datetime import datetime

from extensions import db
from models import ActivityLog, Appointment, ClinicSetting
from utils import now


class AppointmentService:
    @staticmethod
    def validate(appt_date, appt_time, patient_id, staff_id=None, exclude_id=None):
        """Return a list of problems (empty list = the slot is valid)."""
        if appt_date is None or appt_time is None:
            return ["Please choose a valid date and time."]
        errors = []
        if datetime.combine(appt_date, appt_time) <= now():
            errors.append("Appointments cannot be set in the past.")
        if appt_date.weekday() not in ClinicSetting.operating_days():
            errors.append("The clinic is closed on the selected day.")
        if appt_time not in ClinicSetting.slot_times():
            errors.append("Choose a time slot within the clinic's operating hours.")

        same_slot = Appointment.query.filter(
            Appointment.appointment_date == appt_date,
            Appointment.appointment_time == appt_time,
            Appointment.status.in_(Appointment.ACTIVE))
        if exclude_id:
            same_slot = same_slot.filter(Appointment.id != exclude_id)
        if staff_id and same_slot.filter(Appointment.staff_id == staff_id).first():
            errors.append("That doctor/nurse already has an appointment at this time.")
        if patient_id and same_slot.filter(Appointment.patient_id == patient_id).first():
            errors.append("This patient already has an appointment at that time.")
        return errors

    @staticmethod
    def create(patient, appt_date, appt_time, reason, staff_id, actor, status="pending"):
        appointment = Appointment(patient_id=patient.id, staff_id=staff_id,
                                  appointment_date=appt_date, appointment_time=appt_time,
                                  reason=reason, status=status, created_by=actor.id)
        db.session.add(appointment)
        db.session.flush()
        action = "Appointment requested" if status == "pending" else "Appointment created"
        ActivityLog.record(action, f"{patient.full_name} — {appt_date:%b %d} {appt_time:%I:%M %p}",
                           actor, patient)
        return appointment

    LOG_TEXT = {
        "confirmed": ("Appointment confirmed", "Your appointment has been confirmed."),
        "rejected": ("Appointment rejected", "Sorry, your appointment request could not be accepted."),
        "cancelled": ("Appointment cancelled", "Your appointment has been cancelled."),
        "completed": ("Appointment completed", "Your appointment is marked as completed."),
    }

    @classmethod
    def set_status(cls, appointment, new_status, actor):
        """Change status if the transition is allowed; raises ValueError otherwise."""
        if actor.is_staff_member and not appointment.can_be_managed_by(actor):
            raise ValueError(f"This appointment is assigned to {appointment.staff.title_name}. "
                             "Only they or an admin can change it.")
        if not appointment.can_become(new_status):
            raise ValueError(f"A {appointment.status} appointment cannot become {new_status}.")
        appointment.status = new_status
        action, message = cls.LOG_TEXT[new_status]
        details = (f"{appointment.patient.full_name} — "
                   f"{appointment.appointment_date:%b %d} {appointment.appointment_time:%I:%M %p}")
        if new_status == "completed" and appointment.staff is not None:
            details = f"Visit completed. You can now message {appointment.staff.title_name} for follow-up questions."
        ActivityLog.record(action, details, actor, appointment.patient)
        return message

    @staticmethod
    def reschedule(appointment, appt_date, appt_time, actor):
        if not appointment.can_be_managed_by(actor):
            raise ValueError(f"This appointment is assigned to {appointment.staff.title_name}. "
                             "Only they or an admin can change it.")
        if not appointment.is_active:
            raise ValueError("Only pending or confirmed appointments can be rescheduled.")
        errors = AppointmentService.validate(appt_date, appt_time, appointment.patient_id,
                                             appointment.staff_id, exclude_id=appointment.id)
        if errors:
            raise ValueError(" ".join(errors))
        appointment.appointment_date, appointment.appointment_time = appt_date, appt_time
        ActivityLog.record("Appointment rescheduled",
                           f"{appointment.patient.full_name} — now {appt_date:%b %d} {appt_time:%I:%M %p}",
                           actor, appointment.patient)
