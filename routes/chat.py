"""Chat between a patient and a doctor/nurse they have been seen by. Admins only read logs (routes/admin.py)."""
from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db
from models import ChatMessage, Patient, Staff
from services.chat_service import ChatService
from utils import clean, role_required

bp = Blueprint("chat", __name__, url_prefix="/chat")

CHAT_ROLES = ("patient", "doctor", "nurse")
LOCKED = "Chat opens after an appointment with that doctor or nurse has been completed."


def _participants(other_id):
    """Work out (patient, staff) for this conversation. The visit rule is checked separately."""
    if current_user.role == "patient":
        patient = current_user.patient
        if patient is None:
            abort(403)
        staff = db.get_or_404(Staff, other_id)
        if staff.user.role not in ("doctor", "nurse") or not staff.user.active:
            abort(404)
    else:
        staff = current_user.staff
        if staff is None:
            abort(403)
        patient = db.get_or_404(Patient, other_id)
        if patient.user_id is None:          # walk-in patients have no account, so they cannot chat
            abort(404)
    return patient, staff


def _allowed(patient, staff):
    return ChatService.has_visit(patient.id, staff.id)


def _conversation(patient, staff):
    return ChatMessage.query.filter_by(patient_id=patient.id, staff_id=staff.id)


def _mark_read(patient, staff):
    """Messages written by the other person are now read."""
    (_conversation(patient, staff)
     .filter(ChatMessage.read_at.is_(None), ChatMessage.sender_user_id != current_user.id)
     .update({"read_at": datetime.now()}, synchronize_session=False))


@bp.route("/")
@role_required(*CHAT_ROLES)
def index():
    is_patient = current_user.role == "patient"
    mine = current_user.patient if is_patient else current_user.staff
    if mine is None:
        abort(403)
    people = ChatService.contacts_for_patient(mine) if is_patient else ChatService.contacts_for_staff(mine)
    allowed_ids = {p["id"] for p in people}

    column = ChatMessage.patient_id if is_patient else ChatMessage.staff_id
    rows = ChatMessage.query.filter(column == mine.id).order_by(ChatMessage.id.desc()).limit(500).all()
    conversations = {}
    for msg in rows:                                   # newest first, so the first one we see is the latest
        other = msg.staff if is_patient else msg.patient
        if other.id not in allowed_ids:
            continue
        entry = conversations.setdefault(other.id, {"other": other, "last": msg, "unread": 0})
        if msg.read_at is None and msg.sender_user_id != current_user.id:
            entry["unread"] += 1
    return render_template("chat/index.html", conversations=list(conversations.values()), people=people,
                           is_patient=is_patient)


@bp.route("/with/<int:other_id>")
@role_required(*CHAT_ROLES)
def thread(other_id):
    patient, staff = _participants(other_id)
    if not _allowed(patient, staff):
        flash(LOCKED, "warning")
        return redirect(url_for("chat.index"))
    latest = _conversation(patient, staff).order_by(ChatMessage.id.desc()).limit(300).all()
    _mark_read(patient, staff)
    db.session.commit()
    messages = [m.to_dict(current_user.id) for m in reversed(latest)]
    other_name = staff.title_name if current_user.role == "patient" else patient.full_name
    other_role = staff.user.role_label if current_user.role == "patient" else "Patient"
    return render_template("chat/thread.html", messages=messages, other_id=other_id, other_name=other_name,
                           other_role=other_role, last_id=messages[-1]["id"] if messages else 0,
                           last_date=messages[-1]["date"] if messages else "")


@bp.route("/with/<int:other_id>/send", methods=["POST"])
@role_required(*CHAT_ROLES)
def send(other_id):
    patient, staff = _participants(other_id)
    wants_json = request.headers.get("X-Requested-With") == "fetch"
    body = clean(request.form.get("body"))
    error, status = None, 400
    if not _allowed(patient, staff):
        error, status = LOCKED, 403
    elif not body:
        error = "Type a message first."
    elif len(body) > ChatMessage.MAX_LENGTH:
        error = f"Messages are limited to {ChatMessage.MAX_LENGTH} characters."
    if error:
        if wants_json:
            return jsonify(ok=False, error=error), status
        flash(error, "danger")
        return redirect(url_for("chat.thread", other_id=other_id))
    message = ChatMessage(patient_id=patient.id, staff_id=staff.id, sender_user_id=current_user.id, body=body)
    db.session.add(message)
    db.session.commit()
    if wants_json:
        return jsonify(ok=True, message=message.to_dict(current_user.id))
    return redirect(url_for("chat.thread", other_id=other_id))


@bp.route("/with/<int:other_id>/messages")
@role_required(*CHAT_ROLES)
def messages(other_id):
    """Polled by the page every few seconds to pick up new messages."""
    patient, staff = _participants(other_id)
    if not _allowed(patient, staff):
        abort(403)
    after = request.args.get("after", 0, type=int)
    new = _conversation(patient, staff).filter(ChatMessage.id > after).order_by(ChatMessage.id).all()
    if new:
        _mark_read(patient, staff)
        db.session.commit()
    return jsonify(messages=[m.to_dict(current_user.id) for m in new])
