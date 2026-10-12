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