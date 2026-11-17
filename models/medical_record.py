from datetime import datetime

from sqlalchemy import or_

from extensions import db


class MedicalRecord(db.Model):
    __tablename__ = "medical_records"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="RESTRICT"),
                         nullable=False, index=True)
    queue_id = db.Column(db.Integer, db.ForeignKey("queue.id", ondelete="SET NULL"))
    consultation_date = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    chief_complaint = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    treatment = db.Column(db.Text, nullable=False)
    recommendations = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    @classmethod
    def visible_to(cls, user):
        """Query of the records this user may read: admin sees all; a doctor/nurse sees the records they wrote
        plus records of patients who are (or were) assigned to them through an appointment or queue entry."""
        from .appointment import Appointment
        from .queue import QueueEntry
        if user.role == "admin":
            return cls.query
        staff = getattr(user, "staff", None)
        if staff is None:
            return cls.query.filter(cls.id < 0)
        cared = {r[0] for r in db.session.query(Appointment.patient_id).filter(Appointment.staff_id == staff.id)}
        cared |= {r[0] for r in db.session.query(QueueEntry.patient_id).filter(QueueEntry.staff_id == staff.id)}
        return cls.query.filter(or_(cls.staff_id == staff.id, cls.patient_id.in_(cared or {-1})))

    patient = db.relationship("Patient", back_populates="medical_records")
    staff = db.relationship("Staff", back_populates="medical_records")
    queue_entry = db.relationship("QueueEntry", back_populates="medical_records")
