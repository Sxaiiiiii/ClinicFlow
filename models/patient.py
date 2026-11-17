from datetime import date, datetime

from extensions import db


class Patient(db.Model):
    __tablename__ = "patients"

    GENDERS = ("Male", "Female", "Other")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"),
                        unique=True)  # walk-in patients have no login account
    patient_no = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50), nullable=False, index=True)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120))
    address = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)

    user = db.relationship("User", back_populates="patient")
    appointments = db.relationship("Appointment", back_populates="patient",
                                   cascade="all, delete-orphan",
                                   order_by="Appointment.appointment_date.desc()")
    queue_entries = db.relationship("QueueEntry", back_populates="patient",
                                    cascade="all, delete-orphan",
                                    order_by="QueueEntry.queue_date.desc()")
    chat_messages = db.relationship("ChatMessage", back_populates="patient", cascade="all, delete-orphan")
    medical_records = db.relationship("MedicalRecord", back_populates="patient",
                                      cascade="all, delete-orphan",
                                      order_by="MedicalRecord.consultation_date.desc()")

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def age(self):
        today = date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def __repr__(self):
        return f"<Patient {self.patient_no} {self.full_name}>"
