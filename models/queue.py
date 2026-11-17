from datetime import datetime

from extensions import db


class QueueEntry(db.Model):
    __tablename__ = "queue"

    STATUSES = ("waiting", "serving", "completed", "cancelled")
    ACTIVE = ("waiting", "serving")

    id = db.Column(db.Integer, primary_key=True)
    queue_date = db.Column(db.Date, nullable=False, index=True)
    queue_number = db.Column(db.Integer, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id", ondelete="SET NULL"))
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="SET NULL"))
    entry_type = db.Column(db.String(20), nullable=False, default="walk-in")
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="waiting", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    called_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # one queue number per day, enforced by the database
    __table_args__ = (db.UniqueConstraint("queue_date", "queue_number", name="uq_queue_day_number"),)

    patient = db.relationship("Patient", back_populates="queue_entries")
    appointment = db.relationship("Appointment", back_populates="queue_entries")
    staff = db.relationship("Staff", back_populates="queue_entries")
    medical_records = db.relationship("MedicalRecord", back_populates="queue_entry")

    def can_be_managed_by(self, user):
        """Only the assigned staff member (or an admin) may change this once it is assigned."""
        from utils import can_manage_assigned
        return can_manage_assigned(user, self.staff_id)

    @property
    def code(self):
        return f"Q-{self.queue_number:03d}"

    @property
    def waited_minutes(self):
        """Minutes from arrival until called (or until now while still waiting)."""
        end = self.called_at or datetime.now()
        return max(0, int((end - self.created_at).total_seconds() // 60))
