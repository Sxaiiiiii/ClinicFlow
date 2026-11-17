"""Import every model so SQLAlchemy knows about all tables."""
from .user import User
from .patient import Patient
from .staff import Staff
from .appointment import Appointment
from .queue import QueueEntry
from .medical_record import MedicalRecord
from .activity_log import ActivityLog
from .clinic_setting import ClinicSetting
from .email_code import EmailCode
from .chat_message import ChatMessage
from .social_account import SocialAccount

__all__ = ["User", "Patient", "Staff", "Appointment", "QueueEntry",
           "MedicalRecord", "ActivityLog", "ClinicSetting", "EmailCode", "ChatMessage", "SocialAccount"]
