"""Reports and analytics (real MySQL data) plus the small JSON feed for dashboard charts."""
from datetime import timedelta

from flask import Blueprint, flash, jsonify, render_template, request

from services.stats_service import StatsService
from utils import STAFF_ROLES, parse_date, role_required, to_int, today

bp = Blueprint("reports", __name__)


@bp.route("/reports")
@role_required(*STAFF_ROLES)
def index():
    end = parse_date(request.args.get("end")) or today()
    start = parse_date(request.args.get("start")) or end - timedelta(days=29)
    if start > end:
        flash("Start date must be on or before the end date. Showing the default range.", "warning")
        end = today()
        start = end - timedelta(days=29)
    if (end - start).days > 730:
        flash("Date range is limited to 2 years.", "warning")
        start = end - timedelta(days=730)
    return render_template("manage/reports.html", report=StatsService.report(start, end), start=start, end=end)


@bp.route("/api/visits")
@role_required(*STAFF_ROLES)
def visits():
    days = to_int(request.args.get("days"), 7)
    days = days if days in (7, 14, 30) else 7
    return jsonify(StatsService.visits_last_days(days))
