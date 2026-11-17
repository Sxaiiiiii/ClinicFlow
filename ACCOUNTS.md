# ClinicFlow demo accounts

These are **fictional accounts** that come with `database/clinicflow.sql`. Change the passwords before any real use.

On the login page, choose **Patient** or **Doctor / Nurse** first (the administrator also uses "Doctor / Nurse").

| Role | Name | Email | Password | Login toggle |
|---|---|---|---|---|
| Administrator | Clinic Administrator | `admin@clinicflow.test` | `Admin@123` | Doctor / Nurse |
| Doctor | Dr. Elena Reyes (General Medicine) | `dr.reyes@clinicflow.test` | `Staff@123` | Doctor / Nurse |
| Doctor | Dr. Miguel Santos (Pediatrics) | `dr.santos@clinicflow.test` | `Staff@123` | Doctor / Nurse |
| Nurse | Carmela Cruz (Triage Nurse) | `nurse.cruz@clinicflow.test` | `Staff@123` | Doctor / Nurse |
| Nurse | Rico Garcia (Staff Nurse) | `nurse.garcia@clinicflow.test` | `Staff@123` | Doctor / Nurse |
| Patient | Maria Isabel Santos | `maria.santos@example.test` | `Patient@123` | Patient |
| Patient | Juan Dela Cruz | `juan.delacruz@example.test` | `Patient@123` | Patient |
| Patient | Ana Marie Reyes | `ana.reyes@example.test` | `Patient@123` | Patient |

Other patients in the demo data (Carlos Lopez, Bea Cruz, Juan Santos, Pedro Ramos, Lea Mendoza, Paolo Aquino, Isabel Navarro) are walk-in patients without a login account.

## Notes
- Doctor and nurse accounts are created by the administrator: **Staff Management → Add staff**.
- Patients create their own account on the **Sign up** page. A 6-digit code is emailed to confirm the email address.
- Importing `database/clinicflow.sql` again resets everything back to these demo accounts and deletes any data you added.
