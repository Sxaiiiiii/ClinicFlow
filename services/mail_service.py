"""Email (SMTP) helper. If SMTP is not configured, emails are printed to the terminal."""
from flask import current_app
from flask_mail import Message

from extensions import mail


class MailService:
    @staticmethod
    def configured():
        return bool(current_app.config.get("MAIL_ENABLED"))

    @staticmethod
    def send(to, subject, body):
        """Send one plain-text email. Returns True only if it was really sent. Never raises."""
        if not to:
            return False
        if not current_app.config.get("MAIL_ENABLED"):
            current_app.logger.warning("Email not sent: set MAIL_USERNAME and MAIL_PASSWORD in .env")
            return False
        try:
            mail.send(Message(subject=f"[ClinicFlow] {subject}", recipients=[to], body=body))
            return True
        except Exception as exc:  # noqa: BLE001 - network/SMTP errors vary widely
            current_app.logger.warning("Email to %s failed: %s", to, exc)
            return False

    @classmethod
    def verification_code(cls, to, name, code, purpose):
        if purpose == "register":
            subject, intro = "Verify your email", "Use this code to finish creating your ClinicFlow account:"
        else:
            subject, intro = "Your password reset code", "Use this code to reset your ClinicFlow password:"
        return cls.send(to, subject,
                        f"Hello {name},\n\n{intro}\n\n    {code}\n\n"
                        "The code expires in 10 minutes. If you did not request it, you can ignore this email.\n\n— ClinicFlow")

    @classmethod
    def welcome(cls, user):
        return cls.send(user.email, "Welcome to ClinicFlow",
                        f"Hello {user.short_name},\n\nYour ClinicFlow patient account is ready. "
                        "You can now book appointments and follow your queue status online.\n\n"
                        "Better Care. Smoother Flow.\n— ClinicFlow")

    @classmethod
    def appointment_update(cls, appointment, message):
        patient = appointment.patient
        when = f"{appointment.appointment_date:%B %d, %Y} at {appointment.appointment_time:%I:%M %p}"
        return cls.send(patient.email, "Appointment update",
                        f"Hello {patient.first_name},\n\n{message}\n\nDate/time: {when}\n"
                        f"Reason: {appointment.reason}\n\n— ClinicFlow")
