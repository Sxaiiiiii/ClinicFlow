from datetime import datetime

from extensions import db


class ChatMessage(db.Model):
    """One message in a private conversation between a patient and a doctor/nurse."""
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    read_at = db.Column(db.DateTime)                 # set when the other person opens the conversation

    __table_args__ = (db.Index("ix_chat_conversation", "patient_id", "staff_id", "id"),)

    patient = db.relationship("Patient", back_populates="chat_messages")
    staff = db.relationship("Staff", back_populates="chat_messages")

    MAX_LENGTH = 1000

    def to_dict(self, my_user_id):
        """Shape sent to the browser. `mine` tells the page which side the bubble goes on."""
        return {"id": self.id, "mine": self.sender_user_id == my_user_id, "body": self.body,
                "time": self.created_at.strftime("%I:%M %p"),
                "date": f"{self.created_at:%b} {self.created_at.day}, {self.created_at.year}"}
