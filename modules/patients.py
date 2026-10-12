"""
patients.py

Patient registration, search and editing (used by healthcare providers).
No Streamlit code here so it can be unit-tested.
"""

from datetime import date, datetime

from modules.auth import log_action
from modules.database import DB_PATH, get_connection

GENDERS = ["Female", "Male"]


def _validate(first_name, last_name, date_of_birth, gender):
    if not first_name.strip() or not last_name.strip():
        raise ValueError("First and last name are required.")
    if gender not in GENDERS:
        raise ValueError("Please select a gender.")
    if date_of_birth is not None:
        dob = date_of_birth if isinstance(date_of_birth, date) else \
            datetime.strptime(str(date_of_birth), "%Y-%m-%d").date()
        if dob > date.today():
            raise ValueError("Date of birth cannot be in the future.")


def register_patient(provider_id, first_name, last_name, date_of_birth, gender,
                     phone_no=None, address=None, db_path=DB_PATH):
    """Adds a patient and gives them a number like PT-00007. Returns (patient_id, patient_number)."""
    _validate(first_name, last_name, date_of_birth, gender)
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO patient (provider_id, first_name, last_name, date_of_birth, "
            "gender, phone_no, address) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (provider_id, first_name.strip(), last_name.strip(),
             str(date_of_birth) if date_of_birth else None, gender, phone_no, address))
        pid = cur.lastrowid
        number = f"PT-{pid:05d}"
        conn.execute("UPDATE patient SET patient_number = ? WHERE patient_id = ?", (number, pid))
        conn.commit()
    finally:
        conn.close()
    log_action("REGISTER_PATIENT", f"Registered {number}", provider_id, db_path)
    return pid, number


def search_patients(query="", limit=200, db_path=DB_PATH):
    """Matches patient number, first name, last name or phone (partial, case-insensitive)."""
    like = f"%{query.strip()}%"
    conn = get_connection(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM patient WHERE patient_number LIKE ? OR first_name LIKE ? "
            "OR last_name LIKE ? OR (first_name || ' ' || last_name) LIKE ? "
            "OR phone_no LIKE ? ORDER BY last_name, first_name LIMIT ?",
            (like, like, like, like, like, limit))]
    finally:
        conn.close()


def get_patient(patient_id, db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM patient WHERE patient_id = ?", (patient_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_patient(patient_id, acting_user_id, first_name, last_name, date_of_birth,
                   gender, phone_no=None, address=None, db_path=DB_PATH):
    _validate(first_name, last_name, date_of_birth, gender)
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE patient SET first_name=?, last_name=?, date_of_birth=?, gender=?, "
            "phone_no=?, address=? WHERE patient_id=?",
            (first_name.strip(), last_name.strip(),
             str(date_of_birth) if date_of_birth else None, gender,
             phone_no, address, patient_id))
        if cur.rowcount == 0:
            raise ValueError("Patient not found.")
        conn.commit()
    finally:
        conn.close()
    log_action("UPDATE_PATIENT", f"Updated patient {patient_id}", acting_user_id, db_path)


def age_text(date_of_birth):
    """'3 yrs 4 mths' style age from a YYYY-MM-DD string; '-' if unknown."""
    if not date_of_birth:
        return "-"
    dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
    t = date.today()
    months = (t.year - dob.year) * 12 + (t.month - dob.month) - (t.day < dob.day)
    y, m = divmod(max(months, 0), 12)
    return f"{y} yrs {m} mths" if y else f"{m} mths"