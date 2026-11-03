"""
analytics.py

Business-intelligence queries for the dashboards. Each function answers one question
with one query on the database; the dashboard page only draws what these return.

days=None means all time. provider_id limits results to X-rays that provider uploaded.
Dates returned are in Nairobi time (UTC+3).
"""

from modules.database import DB_PATH, get_connection

LOW_CONFIDENCE = 0.70

_FROM = """
FROM result r
JOIN processing_module pm ON pm.processing_id = r.processing_id
JOIN x_ray_image x        ON x.xray_id = pm.xray_id
WHERE 1 = 1
"""


def _filters(days, provider_id):
    sql, params = "", []
    if days:
        sql += " AND r.date >= datetime('now', ?)"
        params.append(f"-{int(days)} days")
    if provider_id:
        sql += " AND x.uploaded_by = ?"
        params.append(provider_id)
    return sql, params


def _all(query, params, db_path):
    conn = get_connection(db_path)
    try:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def kpi_counts(days=None, provider_id=None, db_path=DB_PATH):
    """Headline numbers: analyses, pneumonia/normal split, low-confidence."""
    f, p = _filters(days, provider_id)
    return _all(
        "SELECT COUNT(*) AS analyses, "
        "COALESCE(SUM(r.prediction = 'PNEUMONIA'), 0) AS pneumonia, "
        "COALESCE(SUM(r.prediction = 'NORMAL'), 0) AS normal, "
        f"COALESCE(SUM(r.confidence < {LOW_CONFIDENCE}), 0) AS low_confidence "
        + _FROM + f, p, db_path)[0]


def patient_count(provider_id=None, db_path=DB_PATH):
    """Patients registered (by one provider, or everyone). Patients have no date, so all time."""
    if provider_id:
        q, p = "SELECT COUNT(*) AS n FROM patient WHERE provider_id = ?", [provider_id]
    else:
        q, p = "SELECT COUNT(*) AS n FROM patient", []
    return _all(q, p, db_path)[0]["n"]


def analyses_per_day(days=None, provider_id=None, db_path=DB_PATH):
    """[{day, pneumonia, normal}] in Nairobi dates, oldest first (days with no data are absent)."""
    f, p = _filters(days, provider_id)
    return _all(
        "SELECT date(r.date, '+3 hours') AS day, "
        "SUM(r.prediction = 'PNEUMONIA') AS pneumonia, "
        "SUM(r.prediction = 'NORMAL') AS normal "
        + _FROM + f + " GROUP BY day ORDER BY day", p, db_path)


def usage_per_provider(days=None, db_path=DB_PATH):
    """[{provider, analyses}] busiest first (admin view)."""
    f, p = _filters(days, None)
    return _all(
        "SELECT u.first_name || ' ' || u.last_name AS provider, COUNT(*) AS analyses "
        + _FROM.replace("WHERE 1 = 1", "JOIN user u ON u.user_id = x.uploaded_by WHERE 1 = 1")
        + f + " GROUP BY x.uploaded_by ORDER BY analyses DESC", p, db_path)


def login_activity(days=None, db_path=DB_PATH):
    """[{day, logins, failed}] per Nairobi day, from the system log (admin view)."""
    where, p = "", []
    if days:
        where, p = " AND date_time >= datetime('now', ?)", [f"-{int(days)} days"]
    return _all(
        "SELECT date(date_time, '+3 hours') AS day, "
        "SUM(action = 'LOGIN') AS logins, SUM(action = 'LOGIN_FAILED') AS failed "
        "FROM system_log WHERE action IN ('LOGIN', 'LOGIN_FAILED')" + where +
        " GROUP BY day ORDER BY day", p, db_path)


def account_status(db_path=DB_PATH):
    """{'active': n, 'inactive': n}"""
    rows = _all("SELECT is_active, COUNT(*) AS n FROM user GROUP BY is_active", [], db_path)
    out = {"active": 0, "inactive": 0}
    for r in rows:
        out["active" if r["is_active"] else "inactive"] = r["n"]
    return out