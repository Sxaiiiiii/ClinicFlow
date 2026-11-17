"""Queue business rules: numbering, calling the next patient and status changes."""
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ActivityLog, Appointment, QueueEntry
from utils import now, today


class QueueService:
    @staticmethod
    def next_number(queue_date):
        last = (db.session.query(func.max(QueueEntry.queue_number))
                .filter(QueueEntry.queue_date == queue_date).scalar())
        return (last or 0) + 1

    @classmethod
    def _add(cls, patient, reason, entry_type, appointment, staff_id, actor):
        existing = QueueEntry.query.filter(
            QueueEntry.patient_id == patient.id, QueueEntry.queue_date == today(),
            QueueEntry.status.in_(QueueEntry.ACTIVE)).first()
        if existing:
            raise ValueError(f"{patient.full_name} is already in today's queue as {existing.code}.")
        if appointment is not None and QueueEntry.query.filter(
                QueueEntry.appointment_id == appointment.id,
                QueueEntry.status != "cancelled").first():
            raise ValueError("This appointment is already in the queue.")

        entry = None
        for _ in range(3):  # retry if two people grab the same number at once
            try:
                with db.session.begin_nested():
                    entry = QueueEntry(queue_date=today(), queue_number=cls.next_number(today()),
                                       patient_id=patient.id, appointment_id=getattr(appointment, "id", None),
                                       staff_id=staff_id, entry_type=entry_type, reason=reason,
                                       status="waiting", created_at=now())
                    db.session.add(entry)
                    db.session.flush()
                break
            except IntegrityError:
                entry = None
        if entry is None:
            raise ValueError("Could not generate a queue number. Please try again.")
        ActivityLog.record("Queue registration", f"{patient.full_name} is now {entry.code}", actor, patient)
        return entry

    @classmethod
    def add_walk_in(cls, patient, reason, staff_id, actor):
        return cls._add(patient, reason, "walk-in", None, staff_id, actor)

    @classmethod
    def add_scheduled(cls, appointment, actor):
        if appointment.appointment_date != today():
            raise ValueError("Only today's appointments can be added to the queue.")
        if appointment.status != "confirmed":
            raise ValueError("Confirm the appointment before adding it to the queue.")
        return cls._add(appointment.patient, appointment.reason, "scheduled", appointment,
                        appointment.staff_id, actor)

    @staticmethod
    def _check_owner(entry, actor):
        if not entry.can_be_managed_by(actor):
            raise ValueError(f"{entry.code} is assigned to {entry.staff.title_name}. Only they or an admin can change it.")

    @staticmethod
    def _assert_free(staff):
        if staff is None:
            return
        busy = QueueEntry.query.filter_by(queue_date=today(), staff_id=staff.id, status="serving").first()
        if busy:
            raise ValueError(f"You are still serving {busy.code}. Complete it before calling the next patient.")

    @classmethod
    def serve(cls, entry, staff, actor):
        """Start serving one specific waiting entry."""
        cls._check_owner(entry, actor)
        if entry.status != "waiting":
            raise ValueError("Only waiting patients can be called.")
        cls._assert_free(staff)
        entry.status, entry.called_at = "serving", now()
        if staff is not None:
            entry.staff_id = staff.id
        ActivityLog.record("Patient called", f"{entry.code} — {entry.patient.full_name}", actor, entry.patient)
        return entry

    @classmethod
    def call_next(cls, staff, actor):
        cls._assert_free(staff)
        query = QueueEntry.query.filter_by(queue_date=today(), status="waiting")
        if staff is not None:
            query = query.filter(or_(QueueEntry.staff_id.is_(None), QueueEntry.staff_id == staff.id))
        entry = query.order_by(QueueEntry.queue_number).first()
        if entry is None:
            raise ValueError("No patients are waiting.")
        return cls.serve(entry, staff, actor)

    @staticmethod
    def complete(entry, actor):
        QueueService._check_owner(entry, actor)
        if entry.status != "serving":
            raise ValueError("Only a patient who is being served can be completed.")
        entry.status, entry.completed_at = "completed", now()
        if entry.appointment is not None and entry.appointment.status == "confirmed":
            entry.appointment.status = "completed"
        details = f"{entry.code} — {entry.patient.full_name}"
        if entry.staff is not None:
            details = f"Visit completed. You can now message {entry.staff.title_name} for follow-up questions."
        ActivityLog.record("Queue completed", details, actor, entry.patient)

    @staticmethod
    def cancel(entry, actor):
        QueueService._check_owner(entry, actor)
        if entry.status not in QueueEntry.ACTIVE:
            raise ValueError("Only waiting or serving entries can be cancelled.")
        entry.status = "cancelled"
        ActivityLog.record("Queue cancelled", f"{entry.code} — {entry.patient.full_name}", actor, entry.patient)

    @staticmethod
    def position_of(entry):
        """How many waiting patients are ahead of this one today."""
        return QueueEntry.query.filter(
            QueueEntry.queue_date == entry.queue_date, QueueEntry.status == "waiting",
            QueueEntry.queue_number < entry.queue_number).count()
