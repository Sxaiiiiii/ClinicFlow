from datetime import date, datetime, time, timedelta

from extensions import db


class ClinicSetting(db.Model):
    """Key/value clinic configuration (hours, slot length, contact info)."""
    __tablename__ = "clinic_settings"

    DEFAULTS = {
        "clinic_name": "ClinicFlow",
        "clinic_address": "Pila, Laguna",
        "map_query": "14.2281661,121.3659242",
        "map_link": "https://maps.app.goo.gl/JZSfBw1RrXymS6Lt8",
        "clinic_phone": "09171234567",
        "open_time": "08:00",
        "close_time": "17:00",
        "slot_minutes": "30",
        "operating_days": "0,1,2,3,4,5",   # Monday=0 ... Sunday=6
        "avg_service_minutes": "15",
    }
    DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(50), unique=True, nullable=False)
    setting_value = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    @classmethod
    def as_dict(cls):
        values = dict(cls.DEFAULTS)
        for row in cls.query.all():
            values[row.setting_key] = row.setting_value
        return values

    @classmethod
    def set(cls, key, value):
        row = cls.query.filter_by(setting_key=key).first()
        if row:
            row.setting_value = str(value)
        else:
            db.session.add(cls(setting_key=key, setting_value=str(value)))

    @classmethod
    def operating_days(cls):
        raw = cls.as_dict()["operating_days"]
        return {int(d) for d in raw.split(",") if d.strip().isdigit()}

    @classmethod
    def slot_times(cls):
        """All bookable start times for one day, e.g. 08:00, 08:30 ... 16:30."""
        s = cls.as_dict()
        oh, om = (int(x) for x in s["open_time"].split(":"))
        ch, cm = (int(x) for x in s["close_time"].split(":"))
        step = timedelta(minutes=int(s["slot_minutes"]))
        cursor = datetime.combine(date.today(), time(oh, om))
        end = datetime.combine(date.today(), time(ch, cm))
        slots = []
        while cursor + step <= end:
            slots.append(cursor.time())
            cursor += step
        return slots
