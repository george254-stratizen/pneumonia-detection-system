import sys
sys.path.append(".")

import pytest

from modules import analytics as an
from modules.auth import create_user, authenticate, ADMIN, PROVIDER
from modules.database import init_db, get_connection
from modules.patients import register_patient


def add_result(db, uploader, patient_id, prediction, confidence, days_ago, final=None):
    """Inserts one X-ray + result (+ optional diagnosis) dated `days_ago` days back (UTC)."""
    c = get_connection(db)
    ts = f"datetime('now', '-{days_ago} days')"
    xid = c.execute(f"INSERT INTO x_ray_image (patient_id, file_name, file_path, uploaded_by, upload_date) "
                    f"VALUES (?, 'a.png', 'p', ?, {ts})", (patient_id, uploader)).lastrowid
    pid = c.execute("INSERT INTO processing_module (xray_id, technique) VALUES (?, 'CLAHE')", (xid,)).lastrowid
    rid = c.execute(f"INSERT INTO result (processing_id, patient_id, model_id, prediction, probability, "
                    f"confidence, date) VALUES (?, ?, 1, ?, ?, ?, {ts})",
                    (pid, patient_id, prediction, confidence, confidence)).lastrowid
    if final:
        c.execute("INSERT INTO diagnosis_record (patient_id, result_id, provider_id, final_diagnosis) "
                  "VALUES (?, ?, ?, ?)", (patient_id, rid, uploader, final))
    c.commit(); c.close()
    return rid


@pytest.fixture
def ctx(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    adm = create_user("Ann", "Admin", "a@x.com", "password1", ADMIN, db_path=db)
    jo = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=db)
    li = create_user("Li", "Nurse", "li@x.com", "password1", PROVIDER, db_path=db)
    p1, _ = register_patient(jo, "Amina", "Otieno", "2022-03-01", "Female", db_path=db)
    p2, _ = register_patient(li, "Brian", "Kamau", "2021-06-10", "Male", db_path=db)
    # Jo: 4 results. Li: 1 result, old (100 days ago).
    add_result(db, jo, p1, "PNEUMONIA", 0.95, 1, final="PNEUMONIA")   # TP, agreed
    add_result(db, jo, p1, "PNEUMONIA", 0.60, 2, final="NORMAL")      # FP, differed, low conf
    add_result(db, jo, p1, "NORMAL", 0.90, 3, final="NORMAL")         # TN, agreed
    add_result(db, jo, p1, "NORMAL", 0.80, 3)                         # pending
    add_result(db, li, p2, "NORMAL", 0.85, 100, final="PNEUMONIA")    # FN, old
    return db, adm, jo, li


def test_kpis_all_time_and_window(ctx):
    db, adm, jo, li = ctx
    k = an.kpi_counts(db_path=db)
    assert (k["analyses"], k["pneumonia"], k["normal"]) == (5, 2, 3)
    assert k["low_confidence"] == 1
    assert an.kpi_counts(days=30, db_path=db)["analyses"] == 4      # old one excluded


def test_kpis_per_provider_and_empty(ctx, tmp_path):
    db, adm, jo, li = ctx
    assert an.kpi_counts(provider_id=jo, db_path=db)["analyses"] == 4
    assert an.kpi_counts(provider_id=li, db_path=db)["analyses"] == 1
    empty = tmp_path / "e.db"; init_db(empty)
    k = an.kpi_counts(db_path=empty)
    assert k["analyses"] == 0 and k["pneumonia"] == 0               # zeros, not None


def test_patient_count(ctx):
    db, adm, jo, li = ctx
    assert an.patient_count(db_path=db) == 2
    assert an.patient_count(provider_id=jo, db_path=db) == 1


def test_analyses_per_day_is_nairobi_dates(ctx):
    db, adm, jo, li = ctx
    rows = an.analyses_per_day(days=30, db_path=db)
    assert sum(r["pneumonia"] + r["normal"] for r in rows) == 4
    assert rows == sorted(rows, key=lambda r: r["day"])


def test_usage_per_provider(ctx):
    db, adm, jo, li = ctx
    u = an.usage_per_provider(db_path=db)
    assert u[0] == {"provider": "Jo Doc", "analyses": 4} and u[1]["analyses"] == 1


def test_login_activity_and_accounts(ctx):
    db, adm, jo, li = ctx
    authenticate("jo@x.com", "password1", db_path=db)
    authenticate("jo@x.com", "wrong", db_path=db)
    authenticate("jo@x.com", "wrong", db_path=db)
    row = an.login_activity(days=7, db_path=db)[0]
    assert row["logins"] == 1 and row["failed"] == 2
    c = get_connection(db); c.execute("UPDATE user SET is_active=0 WHERE user_id=?", (li,)); c.commit(); c.close()
    assert an.account_status(db_path=db) == {"active": 2, "inactive": 1}