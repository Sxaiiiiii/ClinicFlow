from datetime import datetime

from extensions import db


class Staff(db.Model):
    """Profile for admins, doctors and nurses."""
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        unique=True, nullable=False)
    employee_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False, index=True)
    specialization = db.Column(db.String(100))
    contact_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User", back_populates="staff")
    appointments = db.relationship("Appointment", back_populates="staff")
    queue_entries = db.relationship("QueueEntry", back_populates="staff")
    medical_records = db.relationship("MedicalRecord", back_populates="staff")
    chat_messages = db.relationship("ChatMessage", back_populates="staff")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def title_name(self):
        """'Dr. Elena Reyes' for doctors, plain name otherwise."""
        if self.user and self.user.role == "doctor":
            return f"Dr. {self.full_name}"
        return self.full_name

    def __repr__(self):
        return f"<Staff {self.employee_no} {self.full_name}>"
