"""
results.py

Reading saved results, recording the clinician's final diagnosis (confirm / override),
and patient history. No Streamlit code, so it can be unit-tested.
"""

from modules.auth import log_action
from modules.database import DB_PATH, get_connection, to_nairobi

FINAL_OPTIONS = ["PNEUMONIA", "NORMAL", "OTHER"]

_DETAIL_SQL = """
SELECT r.result_id, r.patient_id, r.prediction, r.probability, r.confidence, r.date,
       p.patient_number, p.first_name, p.last_name, p.date_of_birth, p.gender,
       m.model_name, m.version AS model_version,
       pm.technique, pm.processed_image_path,
       x.file_name, x.file_path, x.upload_date,
       g.heatmap_path,
       d.diagnosis_id, d.final_diagnosis, d.diagnosis_notes, d.diagnosis_date,
       du.first_name || ' ' || du.last_name AS diagnosed_by
FROM result r
JOIN patient p            ON p.patient_id = r.patient_id
JOIN model m              ON m.model_id = r.model_id
JOIN processing_module pm ON pm.processing_id = r.processing_id
JOIN x_ray_image x        ON x.xray_id = pm.xray_id
LEFT JOIN grad_cam_heatmap g ON g.result_id = r.result_id
LEFT JOIN diagnosis_record d ON d.result_id = r.result_id
LEFT JOIN user du            ON du.user_id = d.provider_id
"""


def _finish(row):
    d = dict(row)
    d["date"] = to_nairobi(d["date"])
    d["upload_date"] = to_nairobi(d["upload_date"])
    if d["diagnosis_date"]:
        d["diagnosis_date"] = to_nairobi(d["diagnosis_date"])
    d["agreed"] = (None if d["final_diagnosis"] is None
                   else d["final_diagnosis"] == d["prediction"])
    return d


def get_result(result_id, db_path=DB_PATH):
    """Everything about one result (patient, images, AI output, diagnosis). None if missing."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(_DETAIL_SQL + " WHERE r.result_id = ?", (result_id,)).fetchone()
    finally:
        conn.close()
    return _finish(row) if row else None


def patient_history(patient_id, db_path=DB_PATH):
    """All results for a patient, newest first."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(_DETAIL_SQL + " WHERE r.patient_id = ? ORDER BY r.result_id DESC",
                            (patient_id,)).fetchall()
    finally:
        conn.close()
    return [_finish(r) for r in rows]


def save_diagnosis(result_id, provider_id, final_diagnosis, notes="", db_path=DB_PATH):
    """Records (or updates) the provider's final diagnosis for a result.
    Returns True if it agrees with the AI, False if it overrides it."""
    if final_diagnosis not in FINAL_OPTIONS:
        raise ValueError("Please choose a final diagnosis.")
    conn = get_connection(db_path)
    try:
        res = conn.execute("SELECT patient_id, prediction FROM result WHERE result_id = ?",
                           (result_id,)).fetchone()
        if res is None:
            raise ValueError("Result not found.")
        if conn.execute("SELECT 1 FROM healthcare_provider WHERE user_id = ?",
                        (provider_id,)).fetchone() is None:
            raise ValueError("Only healthcare providers can record a diagnosis.")
        existing = conn.execute("SELECT diagnosis_id FROM diagnosis_record WHERE result_id = ?",
                                (result_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE diagnosis_record SET provider_id=?, final_diagnosis=?, diagnosis_notes=?, "
                "diagnosis_date=CURRENT_TIMESTAMP WHERE diagnosis_id=?",
                (provider_id, final_diagnosis, notes or None, existing["diagnosis_id"]))
        else:
            conn.execute(
                "INSERT INTO diagnosis_record (patient_id, result_id, provider_id, "
                "final_diagnosis, diagnosis_notes) VALUES (?, ?, ?, ?, ?)",
                (res["patient_id"], result_id, provider_id, final_diagnosis, notes or None))
        conn.commit()
    finally:
        conn.close()
    agreed = final_diagnosis == res["prediction"]
    log_action("CONFIRM_DIAGNOSIS" if agreed else "OVERRIDE_DIAGNOSIS",
               f"Result {result_id}: AI {res['prediction']} -> final {final_diagnosis}",
               provider_id, db_path)
    return agreed