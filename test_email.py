"""Run:  py test_email.py   -> checks your .env and Gmail login, and tells you exactly what is wrong."""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

from config import Config, ENV_PATH, DOTENV_AVAILABLE

print("1) python-dotenv installed:", DOTENV_AVAILABLE)
print("2) .env file:", ENV_PATH, "->", "FOUND" if os.path.exists(ENV_PATH) else "NOT FOUND")
print("3) MAIL_USERNAME:", Config.MAIL_USERNAME or "(empty)")
print("4) MAIL_PASSWORD length:", len(Config.MAIL_PASSWORD), "(a Gmail App Password has 16 characters)")

if not DOTENV_AVAILABLE:
    sys.exit("\n-> Run:  py -m pip install python-dotenv   then try again.")
if not os.path.exists(ENV_PATH):
    sys.exit("\n-> Create the file:  copy .env.example .env   (same folder as app.py), then fill it in.")
if "@" not in Config.MAIL_USERNAME:
    sys.exit("\n-> MAIL_USERNAME must be your FULL Gmail address, like yourname@gmail.com (not just a name).")
if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
    sys.exit("\n-> .env is found but MAIL_USERNAME or MAIL_PASSWORD is empty. Fill them in and SAVE the file.")
if len(Config.MAIL_PASSWORD) != 16:
    print("\n   WARNING: App Passwords are exactly 16 letters. Yours is", len(Config.MAIL_PASSWORD),
          "- did you paste your normal Gmail password?")

print("\nConnecting to", Config.MAIL_SERVER, Config.MAIL_PORT, "...")
try:
    if Config.MAIL_USE_SSL:
        smtp_cm = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=20, context=ssl.create_default_context())
    else:
        smtp_cm = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=20)
    with smtp_cm as smtp:
        smtp.ehlo()
        if not Config.MAIL_USE_SSL:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        smtp.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        print("LOGIN OK")
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = "ClinicFlow test email", Config.MAIL_USERNAME, Config.MAIL_USERNAME
        msg.set_content("If you can read this, ClinicFlow email is working.")
        smtp.send_message(msg)
        print("TEST EMAIL SENT to", Config.MAIL_USERNAME, "- check your inbox (and Spam).")
except smtplib.SMTPAuthenticationError as exc:
    print("\nLOGIN FAILED:", exc.smtp_code, exc.smtp_error.decode(errors="ignore")[:200])
    print("-> Use a Gmail APP PASSWORD (not your normal password).")
    print("-> 2-Step Verification must be ON: https://myaccount.google.com/security")
    print("-> Make a new App Password: https://myaccount.google.com/apppasswords")
except (smtplib.SMTPException, OSError) as exc:
    print("\nCONNECTION PROBLEM:", type(exc).__name__, exc)
    print("-> Try mobile data / hotspot instead of Wi-Fi. Some networks and antivirus block port 587.")
    print("-> Or switch to port 465: in .env set  MAIL_PORT=465  MAIL_USE_TLS=0  MAIL_USE_SSL=1  then run this test again.")
    print("-> Temporarily turn off antivirus 'email shield' / web protection, then try again.")
