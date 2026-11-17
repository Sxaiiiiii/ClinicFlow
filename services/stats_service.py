"""All dashboard and report numbers, calculated from the MySQL data."""
from collections import OrderedDict
from datetime import datetime, timedelta

from flask import url_for
from sqlalchemy import func, or_

from extensions import db
from models import ActivityLog, Appointment, Patient, QueueEntry, Staff, User
from utils import today


class StatsService:
    # ------------------------------------------------------------------ dashboards
    @staticmethod
    def summary():
        t = today()
        queue_today = QueueEntry.query.filter(QueueEntry.queue_date == t)
        return {
            "total_patients": Patient.query.count(),
            "total_staff": Staff.query.join(User).filter(User.role.in_(("doctor", "nurse"))).count(),
            "todays_appointments": Appointment.query.filter(
                Appointment.appointment_date == t,
                Appointment.status.in_(("pending", "confirmed", "completed"))).count(),
            "waiting": queue_today.filter(QueueEntry.status == "waiting").count(),
            "serving": queue_today.filter(QueueEntry.status == "serving").count(),
            "completed": queue_today.filter(QueueEntry.status == "completed").count(),
        }

    @classmethod
    def dashboard_data(cls, user=None):
        t = today()
        return {
            "stats": cls.summary(),
            "appointments": Appointment.query.filter(
                Appointment.appointment_date == t,
                Appointment.status.in_(("pending", "confirmed", "completed"))
            ).order_by(Appointment.appointment_time).limit(6).all(),
            "serving": QueueEntry.query.filter_by(queue_date=t, status="serving")
                                       .order_by(QueueEntry.called_at).all(),
            "waiting_list": QueueEntry.query.filter_by(queue_date=t, status="waiting")
                                            .order_by(QueueEntry.queue_number).limit(5).all(),
            "recent_patients": Patient.query.order_by(Patient.created_at.desc()).limit(5).all(),
            "activities": ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(6).all(),
            "alerts": cls.alerts(user),
        }

    @staticmethod
    def alerts(user=None):
        """Things that need attention. Doctors/nurses only see items that are theirs or unassigned.
        Each alert links to the filtered list so it can be opened in one click."""
        t = today()
        mine = user.staff.id if user is not None and user.role in ("doctor", "nurse") and user.staff else None
        flag = 1 if mine else None            # url_for leaves out None, so admins get the unfiltered link

        def scoped(query, column):
            return query.filter(or_(column == mine, column.is_(None))) if mine else query

        def plural(n, word):
            return f"{n} {word}{'' if n == 1 else 's'}"

        alerts = []
        pending = scoped(Appointment.query.filter(Appointment.status == "pending", Appointment.appointment_date >= t),
                         Appointment.staff_id).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
        if pending:
            first = pending[0]
            alerts.append({"level": "warning", "icon": "bi-calendar-event", "count": len(pending),
                           "title": f"{plural(len(pending), 'appointment request')} to confirm",
                           "detail": f"Earliest: {first.patient.full_name}, {first.appointment_date:%b} {first.appointment_date.day} "
                                     f"at {first.appointment_time:%I:%M %p}",
                           "url": url_for("appointments.index", status="pending", mine=flag)})

        waiting = scoped(QueueEntry.query.filter_by(queue_date=t, status="waiting"),
                         QueueEntry.staff_id).order_by(QueueEntry.queue_number).all()
        long_wait = sorted((e for e in waiting if e.waited_minutes >= 30), key=lambda e: -e.waited_minutes)
        if long_wait:
            worst = long_wait[0]
            alerts.append({"level": "danger", "icon": "bi-hourglass-split", "count": len(long_wait),
                           "title": f"{plural(len(long_wait), 'patient')} waiting 30+ minutes",
                           "detail": f"Longest: {worst.patient.full_name} ({worst.code}), {worst.waited_minutes} min",
                           "url": url_for("queue.index", status="waiting", mine=flag)})

        if mine:
            serving = QueueEntry.query.filter_by(queue_date=t, status="serving", staff_id=mine).count()
        else:
            serving = QueueEntry.query.filter_by(queue_date=t, status="serving").count()
        if waiting and not serving:
            nxt = waiting[0]
            alerts.append({"level": "info", "icon": "bi-megaphone", "count": len(waiting),
                           "title": "You are not serving anyone" if mine else "Nobody is being served",
                           "detail": f"{plural(len(waiting), 'patient')} waiting. Next: {nxt.code} {nxt.patient.full_name}",
                           "url": url_for("queue.index", mine=flag)})

        queued = [r[0] for r in db.session.query(QueueEntry.appointment_id).filter(
            QueueEntry.queue_date == t, QueueEntry.appointment_id.isnot(None), QueueEntry.status != "cancelled")]
        not_queued = scoped(Appointment.query.filter(Appointment.appointment_date == t, Appointment.status == "confirmed"),
                            Appointment.staff_id)
        if queued:
            not_queued = not_queued.filter(~Appointment.id.in_(queued))
        not_queued = not_queued.count()
        if not_queued:
            alerts.append({"level": "info", "icon": "bi-person-check", "count": not_queued,
                           "title": f"{plural(not_queued, 'confirmed appointment')} today not in the queue",
                           "detail": "Add them to the queue when the patient arrives.",
                           "url": url_for("queue.index", mine=flag)})

        if not alerts:
            alerts.append({"level": "success", "icon": "bi-check-circle", "count": 0,
                           "title": "All clear", "detail": "Nothing needs your attention right now.", "url": None})
        return alerts

    # ------------------------------------------------------------------ charts / reports
    @staticmethod
    def _daily_counts(model, date_column, start, end, *extra_filters):
        rows = (db.session.query(date_column, func.count(model.id))
                .filter(date_column >= start, date_column <= end, *extra_filters)
                .group_by(date_column).all())
        return {(d.date() if isinstance(d, datetime) else d): n for d, n in rows}

    @classmethod
    def visits_last_days(cls, days):
        end = today()
        start = end - timedelta(days=days - 1)
        counts = cls._daily_counts(QueueEntry, QueueEntry.queue_date, start, end,
                                   QueueEntry.status != "cancelled")
        labels, values = [], []
        for i in range(days):
            d = start + timedelta(days=i)
            labels.append(f"{d:%b} {d.day}")
            values.append(counts.get(d, 0))
        return {"labels": labels, "values": values}

    @staticmethod
    def _bucket(daily, key_fn, label_fn):
        buckets = OrderedDict()
        for d in sorted(daily):
            k = key_fn(d)
            buckets[k] = buckets.get(k, 0) + daily[d]
        return {"labels": [label_fn(k) for k in buckets], "values": list(buckets.values())}

    @classmethod
    def report(cls, start, end):
        visits = cls._daily_counts(QueueEntry, QueueEntry.queue_date, start, end,
                                   QueueEntry.status != "cancelled")
        days = (end - start).days + 1
        daily = {"labels": [], "values": []}
        for i in range(min(days, 31)):                       # chart the last 31 days at most
            d = end - timedelta(days=min(days, 31) - 1 - i)
            daily["labels"].append(f"{d:%b} {d.day}")
            daily["values"].append(visits.get(d, 0))
        weekly = cls._bucket(visits, lambda d: d - timedelta(days=d.weekday()),
                             lambda k: f"Week of {k:%b} {k.day}")
        monthly = cls._bucket(visits, lambda d: (d.year, d.month),
                              lambda k: datetime(k[0], k[1], 1).strftime("%b %Y"))

        def distribution(model, column, statuses, date_col):
            rows = (db.session.query(column, func.count(model.id))
                    .filter(date_col >= start, date_col <= end).group_by(column).all())
            found = dict(rows)
            return {"labels": [s.title() for s in statuses], "values": [found.get(s, 0) for s in statuses]}

        reg_rows = (db.session.query(func.date(Patient.created_at), func.count(Patient.id))
                    .filter(func.date(Patient.created_at) >= start, func.date(Patient.created_at) <= end)
                    .group_by(func.date(Patient.created_at)).all())
        reg_daily = {(d if not isinstance(d, str) else datetime.strptime(d, "%Y-%m-%d").date()): n
                     for d, n in reg_rows}
        registrations = cls._bucket(reg_daily, lambda d: (d.year, d.month),
                                    lambda k: datetime(k[0], k[1], 1).strftime("%b %Y"))

        appt_status = distribution(Appointment, Appointment.status, Appointment.STATUSES,
                                   Appointment.appointment_date)
        queue_status = distribution(QueueEntry, QueueEntry.status, QueueEntry.STATUSES,
                                    QueueEntry.queue_date)

        waits = []
        for e in QueueEntry.query.filter(QueueEntry.queue_date >= start, QueueEntry.queue_date <= end,
                                         QueueEntry.called_at.isnot(None)).all():
            minutes = (e.called_at - e.created_at).total_seconds() / 60
            if 0 <= minutes <= 480:                          # ignore impossible timestamps
                waits.append(minutes)
        return {
            "daily": daily, "weekly": weekly, "monthly": monthly,
            "appointment_status": appt_status, "queue_status": queue_status,
            "registrations": registrations,
            "total_visits": sum(visits.values()),
            "new_patients": sum(reg_daily.values()),
            "completed_appointments": dict(zip(appt_status["labels"], appt_status["values"])).get("Completed", 0),
            "cancelled_appointments": dict(zip(appt_status["labels"], appt_status["values"])).get("Cancelled", 0),
            "avg_wait": round(sum(waits) / len(waits), 1) if waits else None,
            "wait_samples": len(waits),
        }
