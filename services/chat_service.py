"""Chat rule: a patient and a doctor/nurse can message each other only after a visit between them
was completed (a completed appointment, or a completed queue visit served by that staff member)."""
from sqlalchemy import func

from extensions import db
from models import Appointment, Patient, QueueEntry, Staff, User


class ChatService:
    @staticmethod
    def has_visit(patient_id, staff_id):
        done_appointment = Appointment.query.filter_by(
            patient_id=patient_id, staff_id=staff_id, status="completed").first()
        done_queue = QueueEntry.query.filter_by(
            patient_id=patient_id, staff_id=staff_id, status="completed").first()
        return done_appointment is not None or done_queue is not None

    @staticmethod
    def _last_visits(patient_id=None, staff_id=None):
        """{other person's id: date of the last completed visit}. Pass patient_id OR staff_id."""
        by_patient = patient_id is not None
        visits = {}
        queries = (
            db.session.query(Appointment.staff_id if by_patient else Appointment.patient_id,
                             func.max(Appointment.appointment_date))
            .filter(Appointment.status == "completed",
                    (Appointment.patient_id == patient_id) if by_patient else (Appointment.staff_id == staff_id))
            .group_by(Appointment.staff_id if by_patient else Appointment.patient_id),
            db.session.query(QueueEntry.staff_id if by_patient else QueueEntry.patient_id,
                             func.max(QueueEntry.queue_date))
            .filter(QueueEntry.status == "completed",
                    (QueueEntry.patient_id == patient_id) if by_patient else (QueueEntry.staff_id == staff_id))
            .group_by(QueueEntry.staff_id if by_patient else QueueEntry.patient_id),
        )
        for query in queries:
            for other_id, day in query.all():
                if other_id is not None:
                    visits[other_id] = max(visits.get(other_id, day), day)
        return visits

    @classmethod
    def contacts_for_patient(cls, patient):
        """Doctors/nurses this patient has actually been seen by, newest visit first."""
        visits = cls._last_visits(patient_id=patient.id)
        if not visits:
            return []
        staff = (Staff.query.join(User).filter(Staff.id.in_(list(visits)), User.role.in_(("doctor", "nurse")),
                                               User.active.is_(True)).all())
        rows = [{"id": s.id, "label": f"{s.title_name} ({s.user.role_label})", "last_visit": visits[s.id]} for s in staff]
        return sorted(rows, key=lambda r: r["last_visit"], reverse=True)

    @classmethod
    def contacts_for_staff(cls, staff):
        """Patients (with an online account) this doctor/nurse has completed a visit with."""
        visits = cls._last_visits(staff_id=staff.id)
        if not visits:
            return []
        patients = Patient.query.filter(Patient.id.in_(list(visits)), Patient.user_id.isnot(None)).all()
        rows = [{"id": p.id, "label": f"{p.last_name}, {p.first_name} ({p.patient_no})", "last_visit": visits[p.id]}
                for p in patients]
        return sorted(rows, key=lambda r: r["last_visit"], reverse=True)
