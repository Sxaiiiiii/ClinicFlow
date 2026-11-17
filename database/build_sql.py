"""Generates clinicflow.sql (schema + fictional demo data + hashed passwords).
Run:  py database/build_sql.py
Dates use CURDATE()/NOW() so the demo data is always "today" when you import it."""
import os, random
from werkzeug.security import generate_password_hash

random.seed(7)
H = lambda pw: generate_password_hash(pw, method="pbkdf2:sha256")
q = lambda s: "NULL" if s is None else "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"
D = lambda off: f"DATE_ADD(CURDATE(), INTERVAL {off} DAY)"
T = lambda off, hhmm: f"TIMESTAMP({D(off)}, '{hhmm}:00')"

SCHEMA = """
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS social_accounts, chat_messages, email_codes, medical_records, activity_logs, queue, appointments, patients, staff, clinic_settings, users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  profile_photo VARCHAR(255) NULL,
  created_at DATETIME NOT NULL,
  last_login DATETIME NULL,
  UNIQUE KEY uq_users_email (email),
  KEY ix_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE patients (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  patient_no VARCHAR(20) NOT NULL,
  first_name VARCHAR(50) NOT NULL,
  middle_name VARCHAR(50) NULL,
  last_name VARCHAR(50) NOT NULL,
  date_of_birth DATE NOT NULL,
  gender VARCHAR(20) NOT NULL,
  contact_number VARCHAR(20) NOT NULL,
  email VARCHAR(120) NULL,
  address VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_patients_user (user_id),
  UNIQUE KEY uq_patients_no (patient_no),
  KEY ix_patients_last (last_name),
  KEY ix_patients_contact (contact_number),
  KEY ix_patients_created (created_at),
  CONSTRAINT fk_patients_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE staff (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  employee_no VARCHAR(20) NOT NULL,
  first_name VARCHAR(50) NOT NULL,
  last_name VARCHAR(50) NOT NULL,
  specialization VARCHAR(100) NULL,
  contact_number VARCHAR(20) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_staff_user (user_id),
  UNIQUE KEY uq_staff_no (employee_no),
  KEY ix_staff_last (last_name),
  CONSTRAINT fk_staff_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE appointments (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  patient_id INT NOT NULL,
  staff_id INT NULL,
  appointment_date DATE NOT NULL,
  appointment_time TIME NOT NULL,
  reason VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_by INT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  KEY ix_appt_patient (patient_id),
  KEY ix_appt_status (status),
  KEY ix_appt_slot (appointment_date, appointment_time),
  KEY ix_appt_staff_slot (staff_id, appointment_date, appointment_time),
  CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
  CONSTRAINT fk_appt_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE SET NULL,
  CONSTRAINT fk_appt_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE queue (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  queue_date DATE NOT NULL,
  queue_number INT NOT NULL,
  patient_id INT NOT NULL,
  appointment_id INT NULL,
  staff_id INT NULL,
  entry_type VARCHAR(20) NOT NULL DEFAULT 'walk-in',
  reason VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'waiting',
  created_at DATETIME NOT NULL,
  called_at DATETIME NULL,
  completed_at DATETIME NULL,
  UNIQUE KEY uq_queue_day_number (queue_date, queue_number),
  KEY ix_queue_date (queue_date),
  KEY ix_queue_patient (patient_id),
  KEY ix_queue_status (status),
  CONSTRAINT fk_queue_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
  CONSTRAINT fk_queue_appt FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
  CONSTRAINT fk_queue_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE medical_records (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  patient_id INT NOT NULL,
  staff_id INT NOT NULL,
  queue_id INT NULL,
  consultation_date DATETIME NOT NULL,
  chief_complaint TEXT NOT NULL,
  diagnosis TEXT NOT NULL,
  treatment TEXT NOT NULL,
  recommendations TEXT NULL,
  notes TEXT NULL,
  created_at DATETIME NOT NULL,
  KEY ix_rec_patient (patient_id),
  KEY ix_rec_staff (staff_id),
  KEY ix_rec_date (consultation_date),
  CONSTRAINT fk_rec_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
  CONSTRAINT fk_rec_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE RESTRICT,
  CONSTRAINT fk_rec_queue FOREIGN KEY (queue_id) REFERENCES queue(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE activity_logs (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  patient_id INT NULL,
  action VARCHAR(60) NOT NULL,
  details VARCHAR(255) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  KEY ix_log_user (user_id),
  KEY ix_log_patient (patient_id),
  KEY ix_log_created (created_at),
  CONSTRAINT fk_log_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_log_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE social_accounts (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  provider VARCHAR(20) NOT NULL,
  provider_user_id VARCHAR(64) NOT NULL,
  email VARCHAR(120) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_social_provider_id (provider, provider_user_id),
  KEY ix_social_user (user_id),
  CONSTRAINT fk_social_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE chat_messages (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  patient_id INT NOT NULL,
  staff_id INT NOT NULL,
  sender_user_id INT NULL,
  body TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  read_at DATETIME NULL,
  KEY ix_chat_conversation (patient_id, staff_id, id),
  CONSTRAINT fk_chat_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
  CONSTRAINT fk_chat_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE RESTRICT,
  CONSTRAINT fk_chat_sender FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE email_codes (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(120) NOT NULL,
  purpose VARCHAR(20) NOT NULL,
  code_hash VARCHAR(64) NOT NULL,
  payload TEXT NULL,
  attempts INT NOT NULL DEFAULT 0,
  used TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  expires_at DATETIME NOT NULL,
  KEY ix_email_codes_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE clinic_settings (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  setting_key VARCHAR(50) NOT NULL,
  setting_value VARCHAR(255) NOT NULL,
  updated_at DATETIME NOT NULL,
  UNIQUE KEY uq_setting_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

out = ["-- ClinicFlow database export (fictional demo data only)", "-- Generated by database/build_sql.py",
       "CREATE DATABASE IF NOT EXISTS clinicflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
       "USE clinicflow;", SCHEMA]

def insert(table, cols, rows):
    out.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n" + ",\n".join("  (" + ", ".join(r) + ")" for r in rows) + ";\n")

# ---------------- users + staff
admin_pw, staff_pw, patient_pw = H("Admin@123"), H("Staff@123"), H("Patient@123")
users = [(1, "admin@clinicflow.test", admin_pw, "admin"), (2, "dr.reyes@clinicflow.test", staff_pw, "doctor"),
         (3, "dr.santos@clinicflow.test", staff_pw, "doctor"), (4, "nurse.cruz@clinicflow.test", staff_pw, "nurse"),
         (5, "nurse.garcia@clinicflow.test", staff_pw, "nurse"), (6, "maria.santos@example.test", patient_pw, "patient"),
         (7, "juan.delacruz@example.test", patient_pw, "patient"), (8, "ana.reyes@example.test", patient_pw, "patient")]
insert("users", ["id", "email", "password_hash", "role", "active", "created_at"],
       [[str(i), q(e), q(p), q(r), "1", T(-30, "08:00")] for i, e, p, r in users])
staff = [(1, 1, "Clinic", "Administrator", None, "09171230001"), (2, 2, "Elena", "Reyes", "General Medicine", "09171230002"),
         (3, 3, "Miguel", "Santos", "Pediatrics", "09171230003"), (4, 4, "Carmela", "Cruz", "Triage Nurse", "09171230004"),
         (5, 5, "Rico", "Garcia", "Staff Nurse", "09171230005")]
insert("staff", ["id", "user_id", "employee_no", "first_name", "last_name", "specialization", "contact_number", "created_at"],
       [[str(i), str(u), q(f"EMP-{i:03d}"), q(f), q(l), q(s), q(c), T(-30, "08:00")] for i, u, f, l, s, c in staff])

# ---------------- patients (fictional)
P = [("Maria", "Isabel", "Santos", "1990-03-14", "Female", 6), ("Juan", None, "Dela Cruz", "1985-07-22", "Male", 7),
     ("Ana", "Marie", "Reyes", "1998-11-02", "Female", 8), ("Carlos", None, "Lopez", "1979-01-30", "Male", None),
     ("Bea", None, "Cruz", "2001-05-19", "Female", None), ("Juan", None, "Santos", "1966-09-09", "Male", None),
     ("Pedro", "Luis", "Ramos", "1992-12-25", "Male", None), ("Lea", None, "Mendoza", "2015-04-08", "Female", None),
     ("Paolo", None, "Aquino", "1988-08-17", "Male", None), ("Isabel", None, "Navarro", "1973-06-11", "Female", None)]
email_for = {6: "maria.santos@example.test", 7: "juan.delacruz@example.test", 8: "ana.reyes@example.test"}
insert("patients", ["id", "user_id", "patient_no", "first_name", "middle_name", "last_name", "date_of_birth", "gender",
                    "contact_number", "email", "address", "created_at"],
       [[str(i), str(u) if u else "NULL", q(f"PT-{i:05d}"), q(f), q(m), q(l), q(d), q(g), q(f"091712345{i:02d}"),
         q(email_for.get(u)), q(f"{10 + i} Mabini Street, Sta. Cruz, Laguna"), T(-(25 - i * 2), "09:00")]
        for i, (f, m, l, d, g, u) in enumerate(P, 1)])

# ---------------- appointments
A = []  # (id, patient, staff, day_offset, time, reason, status)
today_appts = [(1, 2, "09:00", "General Checkup", "confirmed"), (2, 3, "09:30", "Fever", "confirmed"),
               (3, 2, "10:00", "Follow-up", "pending"), (4, 3, "10:30", "Check-up", "pending"), (5, 2, "11:00", "Consultation", "pending")]
for p, s, t, r, st in today_appts:
    A.append((len(A) + 1, p, s, 0, t, r, st))
for off, p, s, t, r, st in [(1, 6, 2, "09:00", "Hypertension monitoring", "confirmed"), (2, 8, 3, "14:00", "Vaccination", "pending"),
                            (3, 9, 2, "10:30", "Back pain", "pending"), (-1, 7, 2, "09:00", "Cough and colds", "completed"),
                            (-2, 10, 3, "13:30", "Annual check-up", "completed"), (-3, 5, 2, "11:30", "Skin rash", "cancelled"),
                            (-4, 4, 3, "15:00", "Dizziness", "rejected"),
                            (-9, 1, 2, "09:00", "Headache and dizziness", "completed")]:
    A.append((len(A) + 1, p, s, off, t, r, st))
insert("appointments", ["id", "patient_id", "staff_id", "appointment_date", "appointment_time", "reason", "status", "created_by", "created_at", "updated_at"],
       [[str(i), str(p), str(s), D(o), q(t + ":00"), q(r), q(st), "1", T(min(o, 0) - 2, "08:30"), T(min(o, 0) - 1, "08:30")] for i, p, s, o, t, r, st in A])

# ---------------- queue: today + the last 7 days of completed visits (for charts/reports)
Q = []  # id, day, number, patient, appt, staff, type, reason, status, created, called, completed
qid = 0
def addq(day, num, pat, appt, staff_id, typ, reason, status, created, called=None, done=None):
    global qid
    qid += 1
    Q.append((qid, day, num, pat, appt, staff_id, typ, reason, status, created, called, done))
    return qid
reasons = ["Fever", "Cough and colds", "Check-up", "Follow-up", "Headache", "Wound dressing", "Vaccination"]
for day in range(-7, 0):
    for n in range(1, random.randint(4, 8)):
        h, m = 8 + n // 2, (n % 2) * 30
        addq(day, n, random.randint(1, 10), None, random.choice([2, 3]), random.choice(["walk-in", "scheduled"]),
             random.choice(reasons), "cancelled" if n == 5 and day % 2 else "completed",
             T(day, f"{h:02d}:{m:02d}"), T(day, f"{h:02d}:{m + 12:02d}"), T(day, f"{h:02d}:{m + 25:02d}"))
first = {}
first[1] = addq(0, 1, 7, None, 2, "walk-in", "Cough and colds", "completed", T(0, "07:50"), T(0, "08:05"), T(0, "08:25"))
first[2] = addq(0, 2, 8, None, 3, "walk-in", "Fever", "completed", T(0, "08:00"), T(0, "08:30"), T(0, "08:50"))
addq(0, 3, 1, 1, 2, "scheduled", "General Checkup", "serving", T(0, "08:40"), T(0, "09:00"))
addq(0, 4, 2, 2, None, "scheduled", "Fever", "waiting", T(0, "08:55"))
addq(0, 5, 4, None, None, "walk-in", "Check-up", "waiting", T(0, "09:05"))
addq(0, 6, 9, None, None, "walk-in", "Back pain", "waiting", T(0, "09:10"))
nz = lambda v: "NULL" if v is None else (v if isinstance(v, str) and v.startswith("TIMESTAMP") else str(v))
insert("queue", ["id", "queue_date", "queue_number", "patient_id", "appointment_id", "staff_id", "entry_type", "reason", "status", "created_at", "called_at", "completed_at"],
       [[str(i), D(d), str(n), str(p), nz(a), nz(s), q(t), q(r), q(st), c, nz(ca), nz(co)] for i, d, n, p, a, s, t, r, st, c, ca, co in Q])

# ---------------- medical records
insert("medical_records", ["patient_id", "staff_id", "queue_id", "consultation_date", "chief_complaint", "diagnosis", "treatment", "recommendations", "notes", "created_at"],
       [[str(p), str(s), nz(qq), T(d, "09:15"), q(c), q(dx), q(tx), q(rec), q(note), T(d, "09:30")] for p, s, qq, d, c, dx, tx, rec, note in [
        (7, 2, first[1], 0, "Cough and colds for 3 days", "Acute upper respiratory infection", "Paracetamol 500 mg every 6 hours; carbocisteine", "Rest, fluids, return if fever persists beyond 3 days", "No known drug allergies reported"),
        (8, 3, first[2], 0, "Fever since last night", "Viral fever", "Oral rehydration, paracetamol syrup", "Monitor temperature; avoid cold drinks", None),
        (10, 3, None, -2, "Annual check-up", "Healthy; mild elevated blood pressure", "Lifestyle counselling", "Low-salt diet, repeat BP check in 2 weeks", None),
        (1, 2, None, -9, "Headache and dizziness", "Tension headache", "Rest and hydration; paracetamol as needed", "Reduce screen time; sleep 7–8 hours", None),
        (2, 2, None, -12, "Stomach pain after meals", "Gastritis", "Antacid after meals", "Avoid spicy food and coffee", "Follow-up if pain persists"),
        (4, 3, None, -15, "Persistent cough", "Bronchitis", "Cough suppressant, rest", "Chest X-ray if no improvement in 1 week", None)]])

# ---------------- activity logs
logs = [(1, None, "Login", "Clinic Administrator signed in (admin)", "09:55"), (6, 1, "Appointment confirmed", "Maria Isabel Santos — today 09:00 AM", "09:45"),
        (4, 7, "Queue registration", "Pedro Luis Ramos is now Q-001", "07:50"), (2, 7, "Medical record created", "Pedro Luis Ramos: Acute upper respiratory infection", "08:30"),
        (4, 8, "Patient called", "Q-002 — Lea Mendoza", "08:30"), (4, 1, "Patient called", "Q-003 — Maria Isabel Santos", "09:00"),
        (4, 9, "Queue registration", "Paolo Aquino is now Q-006", "09:10"), (6, 3, "Patient registration", "New patient registered: Ana Marie Reyes", "08:20"),
        (7, 2, "Appointment requested", "Juan Dela Cruz — today 09:30 AM", "08:10")]
insert("activity_logs", ["user_id", "patient_id", "action", "details", "created_at"],
       [[str(u), nz(p), q(a), q(d), T(0, t)] for u, p, a, d, t in logs])

# ---------------- chat (demo conversation: patient Maria Santos and Dr. Elena Reyes)
chat = [(6, -1, "09:10", "Good morning doctor, I still have a cough after 3 days. Should I come in?", True),
        (2, -1, "09:25", "Good morning Maria. Yes, please book a check-up this week so I can listen to your lungs.", True),
        (6, -1, "09:27", "Okay po, I will book online. Thank you!", True),
        (2, 0, "08:45", "Reminder: please bring your previous prescription when you come in today.", False)]
insert("chat_messages", ["patient_id", "staff_id", "sender_user_id", "body", "created_at", "read_at"],
       [["1", "2", str(u), q(b), T(d, t), T(d, t) if read else "NULL"] for u, d, t, b, read in chat])

# ---------------- settings
insert("clinic_settings", ["setting_key", "setting_value", "updated_at"],
       [[q(k), q(v), "NOW()"] for k, v in [("clinic_name", "ClinicFlow"), ("clinic_address", "Pila, Laguna"),
        ("map_query", "14.2281661,121.3659242"), ("map_link", "https://maps.app.goo.gl/JZSfBw1RrXymS6Lt8"),
        ("clinic_phone", "09171234567"), ("open_time", "08:00"), ("close_time", "17:00"), ("slot_minutes", "30"),
        ("operating_days", "0,1,2,3,4,5"), ("avg_service_minutes", "15")]])

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clinicflow.sql")
open(path, "w", encoding="utf-8").write("\n".join(out))
print("wrote", path)
