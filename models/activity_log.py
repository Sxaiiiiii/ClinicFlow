from datetime import datetime

from extensions import db


class ActivityLog(db.Model):
    """Audit trail. Rows with a patient_id also act as that patient's notifications."""
    __tablename__ = "activity_logs"

    # actions shown to patients as notifications
    NOTIFY = ("Appointment requested", "Appointment confirmed", "Appointment rejected",
              "Appointment cancelled", "Appointment rescheduled", "Queue registration",
              "Patient called", "Queue completed", "Appointment completed")
    ICONS = {
        "Login": "bi-box-arrow-in-right", "Patient registration": "bi-person-plus-fill",
        "Appointment requested": "bi-calendar-plus", "Appointment created": "bi-calendar-plus",
        "Appointment confirmed": "bi-calendar-check", "Appointment cancelled": "bi-calendar-x",
        "Appointment rejected": "bi-calendar-x", "Appointment rescheduled": "bi-calendar-event",
        "Appointment completed": "bi-calendar-check", "Queue registration": "bi-people",
        "Patient called": "bi-megaphone", "Queue completed": "bi-check-circle",
        "Medical record created": "bi-file-earmark-medical",
    }

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(60), nullable=False)
    details = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    user = db.relationship("User", back_populates="activity_logs", foreign_keys=[user_id])
    patient = db.relationship("Patient", foreign_keys=[patient_id])

    @property
    def icon(self):
        return self.ICONS.get(self.action, "bi-lightning-charge")

    @classmethod
    def record(cls, action, details="", user=None, patient=None):
        """Add a log row to the session. The caller commits."""
        db.session.add(cls(action=action, details=(details or "")[:255],
                           user_id=getattr(user, "id", None),
                           patient_id=getattr(patient, "id", None)))
