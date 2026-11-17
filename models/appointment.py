from datetime import datetime

from extensions import db


class Appointment(db.Model):
    __tablename__ = "appointments"

    STATUSES = ("pending", "confirmed", "completed", "cancelled", "rejected")
    ACTIVE = ("pending", "confirmed")
    # which status changes are allowed from each status
    TRANSITIONS = {
        "pending": ("confirmed", "rejected", "cancelled"),
        "confirmed": ("completed", "cancelled"),
    }

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="SET NULL"))
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now,
                           onupdate=datetime.now)

    __table_args__ = (
        db.Index("ix_appt_slot", "appointment_date", "appointment_time"),
        db.Index("ix_appt_staff_slot", "staff_id", "appointment_date", "appointment_time"),
    )

    patient = db.relationship("Patient", back_populates="appointments")
    staff = db.relationship("Staff", back_populates="appointments")
    queue_entries = db.relationship("QueueEntry", back_populates="appointment")

    @property
    def scheduled_at(self):
        return datetime.combine(self.appointment_date, self.appointment_time)

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    @property
    def can_patient_cancel(self):
        return self.is_active and self.scheduled_at > datetime.now()

    def can_be_managed_by(self, user):
        """Only the assigned staff member (or an admin) may change this once it is assigned."""
        from utils import can_manage_assigned
        return can_manage_assigned(user, self.staff_id)

    def can_become(self, new_status):
        return new_status in self.TRANSITIONS.get(self.status, ())
