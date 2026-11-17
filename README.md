# ClinicFlow — Clinic Queue & Scheduling System
**Better Care. Smoother Flow.**

A Flask + MySQL web system for clinics: online appointments, automatic daily queue numbers, live queue status,
patient records, reports and activity logs. Built for the Laguna University Final Project (IPT1 / OOP / Web Systems).

## Tech stack
Flask · Flask-SQLAlchemy (ORM) · Flask-Login · Flask-WTF (CSRF) · Flask-Mail (SMTP) · MySQL (PyMySQL) ·
Jinja2 · HTML5 · CSS3 · Bootstrap 5 · vanilla JavaScript · Chart.js

> Bootstrap, Bootstrap Icons and Chart.js load from a CDN, so the browser needs internet access.

## How to run (Windows + XAMPP)
1. Install **Python 3** (tick "Add to PATH").
2. Open **XAMPP Control Panel** → start **MySQL**.
3. Open this folder in **VS Code**, then in the terminal:
   ```
   py -m venv venv
   venv\Scripts\activate
   py -m pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and set `DB_PASSWORD` if your MySQL root has one (XAMPP default is empty).
   Set a long random `SECRET_KEY`.
5. Create the database and import the demo data — pick one:
   * phpMyAdmin → *Import* → choose `database/clinicflow.sql` (it creates the `clinicflow` database), **or**
   * terminal: `mysql -u root < database/clinicflow.sql`
6. Run: `py app.py`
7. Open **http://127.0.0.1:5000**

`py app.py` also creates any missing tables automatically. Re-import the SQL file any time to reset the demo data
(demo dates are relative to the day you import, so the dashboards always look "live").

## Demo accounts (fictional — all data is fake)
The full list is also in [`ACCOUNTS.md`](ACCOUNTS.md).

| Role | Email | Password |
|---|---|---|
| Administrator | admin@clinicflow.test | `Admin@123` |
| Doctor | dr.reyes@clinicflow.test / dr.santos@clinicflow.test | `Staff@123` |
| Nurse | nurse.cruz@clinicflow.test / nurse.garcia@clinicflow.test | `Staff@123` |
| Patient | maria.santos@example.test / juan.delacruz@example.test / ana.reyes@example.test | `Patient@123` |

On the login page choose **Patient** or **Doctor / Nurse** (the administrator also uses "Doctor / Nurse"). Change these passwords before any real use.

## The 13 required features → where to find them
| # | Feature | Where |
|---|---|---|
| 1 | Logo & branding | `static/images/logo.svg`, favicon, `static/css/style.css` (palette variables) |
| 2 | Public home page | `/` → `templates/index.html` |
| 3 | Registration | `/register` (patients); staff accounts are created by the admin |
| 4 | Login | `/login`, `routes/auth.py` |
| 5 | Web security | PBKDF2 hashes, SQLAlchemy ORM (no raw SQL), Jinja auto-escaping (XSS), CSRFProtect (all POST forms), role checks (`utils.role_required`), safe redirects, upload type checks |
| 6 | Sessions | Flask-Login sessions, optional "remember me", POST-only logout, `no-store` cache header on private pages |
| 7 | SMTP email | `services/mail_service.py` + `services/verification_service.py`: emailed 6-digit codes (sign up, password reset), welcome and appointment emails |
| 8 | Dashboard | `/admin/dashboard`, `/staff/dashboard`, `/patient/dashboard` |
| 9 | Profile management | `/profile`: details, password, photo |
| 10 | CRUD | Patients (full CRUD), staff (full CRUD), appointments, queue, medical records |
| 11 | Responsive UI | Bootstrap grid + `static/css/responsive.css` (sidebar becomes a slide-in menu on phones) |
| 12 | Validation & error handling | HTML5 + JavaScript on every form, server re-validation (`PatientService.parse`, route checks), friendly 403/404/500 pages |
| 13 | OOP | See below |

### OOP in this project
* **Models are classes** with attributes *and* behaviour: `User.set_password()/check_password()` (the hash is encapsulated),
  `Patient.full_name/age`, `Appointment.can_become()`, `QueueEntry.code`, `ClinicSetting.slot_times()`.
* **Service classes** hold business rules: `AppointmentService`, `QueueService`, `PatientService`, `StatsService`, `MailService`.
* **Inheritance:** every model extends `db.Model`; `User` also inherits `UserMixin` (Flask-Login).
* **Encapsulation:** routes stay thin and call service methods; rules such as "only one patient served per staff member" live in one place.

## Who can access what
| Area | Admin | Doctor / Nurse | Patient |
|---|---|---|---|
| Appointments & queue | everything | their own assigned items, plus unassigned ones (others' items show a lock) | only their own |
| Medical records | read all | records they wrote + records of patients assigned to them | none |
| Chat | read-only logs (each view is logged) | only their own conversations | only their own conversations |
| Staff accounts, settings, activity logs | yes | no | no |

The rule is enforced in the service classes (not only by hiding buttons), so a forged request is refused too.
If a doctor is absent, the admin can still handle that doctor's queue and appointments.

## Google sign-in (optional)
"Continue with Google" appears on the login and sign-up pages **only after you add Google credentials to `.env`**. Without them nothing changes.

**Set up (once):**
1. Go to https://console.cloud.google.com → create a project.
2. *APIs & Services → OAuth consent screen* → External → fill in the app name and your email. While the app is in **Testing**, add the Gmail addresses that will try it under **Test users**.
3. *Credentials → Create credentials → OAuth client ID → Web application*. Under **Authorized redirect URIs** add exactly `http://127.0.0.1:5000/auth/google/callback`.
4. Copy the Client ID and Client secret into `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) and restart `py app.py`. Always open the site at `http://127.0.0.1:5000` (not `localhost`) so the address matches.

**How it behaves (rules):**
* Existing patient with the same email → the Google account is **linked** to it (no duplicate).
* New person → Google confirms the email, then a short "Almost done" form collects the clinic details; the account is always a **patient**.
* Doctor, nurse and admin accounts **cannot** use Google; they sign in with email and password. Google never changes a role.
* Email and password login is unchanged. The sign-in uses OAuth 2.0 with a `state` check, and only Google-verified emails are accepted.
* Links are stored in a separate `social_accounts` table (created automatically); the existing tables are not modified.

## Chat (patient ↔ doctor/nurse)
* **Chat unlocks only after a completed appointment (or completed queue visit) between that patient and that doctor/nurse**, so patients can ask follow-up questions about their visit. Nobody else can be messaged; the rule is checked on every page, send and refresh request.
* Patients find the chat under **Messages** or with the **Ask a question** button on a completed appointment. Doctors/nurses open it from **Messages** or the **Message** button on the patient's page.
* New messages appear within a few seconds (the page checks every 4 seconds). Unread messages show a red badge in the sidebar.
* **Admin → Chat Logs** is read-only. Every time the admin opens a conversation, it is written to the Activity Logs.
* Chat pages tell users that messages may be reviewed by clinic administrators and are not for emergencies.
* Messages are limited to 1,000 characters, escaped on the page (no HTML/script injection), and CSRF-protected.
* The `chat_messages` table is created automatically when you start `py app.py`.

## Email (SMTP) and the 6-digit verification code
ClinicFlow sends **real emails** through Gmail (Flask-Mail). They are used for:
* **Sign up:** a 6-digit code is emailed; the account is created only after the code is confirmed.
* **Forgot password:** a 6-digit code is emailed, then the user sets a new password.
* Welcome email and appointment updates.

Codes expire in 10 minutes, allow 5 wrong tries, are stored hashed, and can be resent after 60 seconds.

**Set up Gmail (required):**
1. Google Account → Security → turn on **2-Step Verification**.
2. Search "App passwords" → create one → copy the 16-letter password.
3. In `.env` set `MAIL_USERNAME`, `MAIL_PASSWORD` (the App Password, not your normal password) and `MAIL_SENDER`.
4. Restart `py app.py`. The new `email_codes` table is created automatically.

If you need to demo without internet, set `REQUIRE_EMAIL_VERIFICATION=0` in `.env` to skip the sign-up code.

## Folder structure
```
app.py  config.py  extensions.py  utils.py  requirements.txt
models/      one class per table
services/    business logic classes
routes/      auth, admin, staff, patient, appointments, queue, patients, records, reports
templates/   base, layout (app shell), public pages, admin/, staff/, patient/, manage/ (pages shared by admin + staff)
static/      css/, js/, images/, uploads/
database/    clinicflow.sql  (+ build_sql.py that generates it)
docs/        CLIENT_ENGAGEMENT_TEMPLATE.md
```
Differences from the original spec: the pages that admins and staff share (patients, appointments, queue, records, reports)
live once in `templates/manage/` instead of being copied into `admin/` and `staff/`; the sidebar changes by role.
The public home page is `/`, and the split-screen login is one click away at `/login`.

## Manual test checklist (run these before your defense)
- [ ] Register a patient → code arrives in Gmail → enter it → lands on patient dashboard
- [ ] Forgot password → code arrives in Gmail → set a new password → sign in
- [ ] (If Google is set up) Continue with Google: existing patient email links; new email goes to "Almost done"; a staff email is refused
- [ ] Wrong code 5 times is blocked; "resend" works after 60 seconds
- [ ] Wrong password shows a friendly error; deactivated staff cannot sign in
- [ ] Patient tab cannot sign in with a staff account (and vice-versa)
- [ ] Visiting `/admin/dashboard` as a patient → 403; logged out → redirected to login
- [ ] Admin adds a doctor/nurse; edits; deactivates; deletes
- [ ] Patient books an appointment (try a past date, Sunday, and a taken slot — all rejected)
- [ ] Staff confirms → patient sees notification; patient cancels a future appointment
- [ ] Walk-in registered → Q-number increments; adding the same patient twice is blocked
- [ ] Call next → Serving; complete → Completed; a second "call next" while serving is blocked
- [ ] Dr. A cannot confirm/call/complete an item assigned to Dr. B (lock icon + error message); admin can
- [ ] Dr. A cannot see Dr. B's patient records; the patient page says some records are hidden
- [ ] A patient with no completed appointment sees no one in Messages; opening /chat/with/<id> shows the locked message
- [ ] Mark an appointment as completed → the patient gets a notification and can message that doctor, but not other doctors
- [ ] Patient sends a message → doctor sees the badge and replies → patient sees it without refreshing
- [ ] Admin → Chat Logs shows the conversation and cannot send; the view appears in Activity Logs
- [ ] Doctor creates a consultation record; admin can read but not create
- [ ] Reports change when you change the date range; Print works
- [ ] Stop and restart the app: data is still there (MySQL persistence)
- [ ] Resize the browser to phone width; sidebar opens with the menu button

## Troubleshooting
* **"Can't connect to MySQL"** → start MySQL in XAMPP; check `DB_USER`/`DB_PASSWORD` in `.env`.
* **`py` not found** → use `python`.
* **"Session expired" page** → refresh the form page and submit again (CSRF token timed out).
* **"We couldn't send the verification email"** → check `MAIL_USERNAME` / `MAIL_PASSWORD` (must be a Gmail App Password) and your internet connection.
* **Charts empty** → check the browser has internet (Chart.js CDN) and that the SQL demo data was imported.

## Submission checklist (from the guidelines)
GitHub repository link · this README · `requirements.txt` · client documentation (`docs/CLIENT_ENGAGEMENT_TEMPLATE.md`) ·
live demo during the defense (be ready to explain and modify your code).
