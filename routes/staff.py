"""Doctor / nurse dashboard."""
from flask import Blueprint, render_template
from flask_login import current_user

from services.stats_service import StatsService
from utils import CLINICAL_ROLES, role_required

bp = Blueprint("staff", __name__, url_prefix="/staff")


@bp.route("/dashboard")
@role_required(*CLINICAL_ROLES)
def dashboard():
    return render_template("staff/dashboard.html", **StatsService.dashboard_data(current_user))
