import sqlite3
import sys
sys.path.append(".")

import pytest
from modules.database import init_db, get_connection, hash_password, verify_password, to_nairobi

EXPECTED_TABLES = {
    "role", "user", "admin", "healthcare_provider", "system_log", "patient",
    "x_ray_image", "processing_module", "model", "result",
    "grad_cam_heatmap", "diagnosis_record",
}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    conn = get_connection(path)
    yield conn
    conn.close()


def test_all_tables_created(db):
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert EXPECTED_TABLES <= {r["name"] for r in rows}


def test_roles_and_model_seeded(db):
    assert db.execute("SELECT COUNT(*) FROM role").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM model").fetchone()[0] == 1


def test_init_is_repeatable(tmp_path):
    path = tmp_path / "again.db"
    init_db(path)
    init_db(path)
    conn = get_connection(path)
    assert conn.execute("SELECT COUNT(*) FROM role").fetchone()[0] == 2
    conn.close()


def test_foreign_keys_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO user (role_id, first_name, last_name, email, password) "
            "VALUES (999, 'A', 'B', 'a@b.com', 'x')"
        )


def test_password_hashing():
    stored = hash_password("secret123")
    assert "secret123" not in stored
    assert verify_password("secret123", stored)
    assert not verify_password("wrong", stored)


def _make_provider(db):
    db.execute("INSERT INTO user (role_id, first_name, last_name, email, password) VALUES (2,'Jane','Doe','j@x.com','x')")
    uid = db.execute("SELECT user_id FROM user WHERE email='j@x.com'").fetchone()[0]
    db.execute("INSERT INTO healthcare_provider (user_id) VALUES (?)", (uid,))
    return uid


def test_user_active_by_default_and_deactivate(db):
    uid = _make_provider(db)
    assert db.execute("SELECT is_active FROM user WHERE user_id=?", (uid,)).fetchone()[0] == 1
    db.execute("UPDATE user SET is_active=0 WHERE user_id=?", (uid,))
    assert db.execute("SELECT is_active FROM user WHERE user_id=?", (uid,)).fetchone()[0] == 0


def test_invalid_prediction_rejected(db):
    uid = _make_provider(db)
    db.execute("INSERT INTO patient (patient_number, provider_id, first_name, last_name) VALUES ('P001',?,'A','B')", (uid,))
    db.execute("INSERT INTO x_ray_image (patient_id, file_name, file_path) VALUES (1,'a.png','p')")
    db.execute("INSERT INTO processing_module (xray_id, technique) VALUES (1,'CLAHE')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO result (processing_id, patient_id, model_id, prediction) VALUES (1,1,1,'BANANA')")


def test_patient_number_unique(db):
    uid = _make_provider(db)
    db.execute("INSERT INTO patient (patient_number, provider_id, first_name, last_name) VALUES ('P001',?,'A','B')", (uid,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO patient (patient_number, provider_id, first_name, last_name) VALUES ('P001',?,'C','D')", (uid,))


def test_full_workflow(db):
    uid = _make_provider(db)
    db.execute("INSERT INTO patient (patient_number, provider_id, first_name, last_name) VALUES ('P001',?,'A','B')", (uid,))
    db.execute("INSERT INTO x_ray_image (patient_id, file_name, file_path, uploaded_by) VALUES (1,'a.png','p',?)", (uid,))
    db.execute("INSERT INTO processing_module (xray_id, technique) VALUES (1,'CLAHE')")
    db.execute("INSERT INTO result (processing_id, patient_id, model_id, prediction, probability, confidence) VALUES (1,1,1,'PNEUMONIA',0.91,0.91)")
    db.execute("INSERT INTO grad_cam_heatmap (result_id, heatmap_path) VALUES (1,'h.png')")
    db.execute("INSERT INTO diagnosis_record (patient_id, result_id, provider_id, final_diagnosis, diagnosis_notes) VALUES (1,1,?,'PNEUMONIA','ok')", (uid,))
    row = db.execute("""SELECT p.first_name, r.prediction, d.final_diagnosis
                        FROM diagnosis_record d JOIN result r USING(result_id)
                        JOIN patient p ON p.patient_id = d.patient_id""").fetchone()
    assert tuple(row) == ("A", "PNEUMONIA", "PNEUMONIA")


def test_to_nairobi():
    assert to_nairobi("2026-01-01 22:30:00") == "2026-01-02 01:30:00"


def test_user_has_gender_column(db):
    cols = {r["name"] for r in db.execute("PRAGMA table_info(user)")}
    assert "gender" in cols
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO user (role_id, first_name, last_name, gender, email, password) "
                   "VALUES (1, 'A', 'B', 'Robot', 'r@x.com', 'x')")


def test_old_database_is_upgraded_in_place(tmp_path):
    """A database made before the gender column existed gets it added, keeping its users."""
    path = tmp_path / "old.db"
    init_db(path)
    c = get_connection(path)
    c.execute("INSERT INTO user (role_id, first_name, last_name, email, password) "
              "VALUES (1, 'Old', 'User', 'old@x.com', 'x')")
    c.commit()
    c.execute("ALTER TABLE user DROP COLUMN gender")        # simulate the old schema
    c.commit(); c.close()
    init_db(path)                                           # upgrade
    c = get_connection(path)
    assert "gender" in {r["name"] for r in c.execute("PRAGMA table_info(user)")}
    assert c.execute("SELECT first_name FROM user WHERE email='old@x.com'").fetchone()[0] == "Old"
    c.close()


def test_must_change_password_column_added_to_old_database(tmp_path):
    path = tmp_path / "old2.db"
    init_db(path)
    c = get_connection(path)
    c.execute("INSERT INTO user (role_id, first_name, last_name, email, password) "
              "VALUES (1, 'Old', 'User', 'old@x.com', 'x')")
    c.commit()
    c.execute("ALTER TABLE user DROP COLUMN must_change_password")      # simulate the older schema
    c.commit(); c.close()
    init_db(path)
    c = get_connection(path)
    assert c.execute("SELECT must_change_password FROM user WHERE email='old@x.com'").fetchone()[0] == 0
    c.close()


def test_lockout_columns_added_to_old_database(tmp_path):
    path = tmp_path / "old3.db"
    init_db(path)
    c = get_connection(path)
    c.execute("INSERT INTO user (role_id, first_name, last_name, email, password) "
              "VALUES (1, 'Old', 'User', 'old@x.com', 'x')")
    c.commit()
    c.execute("ALTER TABLE user DROP COLUMN failed_attempts")
    c.execute("ALTER TABLE user DROP COLUMN locked_until")
    c.commit(); c.close()
    init_db(path)
    c = get_connection(path)
    row = c.execute("SELECT failed_attempts, locked_until FROM user WHERE email='old@x.com'").fetchone()
    assert row[0] == 0 and row[1] is None
    c.close()