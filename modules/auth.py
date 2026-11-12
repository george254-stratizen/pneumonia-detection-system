"""
auth.py

Login logic, user creation and activity logging.
Kept free of Streamlit code so it can be unit-tested.
"""

import secrets
import string

from modules.database import DB_PATH, GENDERS, get_connection, hash_password, verify_password
from modules.validation import (email_error, name_error, password_error, phone_error,
                                raise_if_errors, text_error)

ADMIN = "Administrator"
PROVIDER = "Healthcare Provider"


def log_action(action, description="", user_id=None, db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO system_log (user_id, action, description) VALUES (?, ?, ?)",
            (user_id, action, description),
        )
        conn.commit()
    finally:
        conn.close()


def create_user(first_name, last_name, email, password, role_name,
                phone_no=None, gender=None, license_number=None, profession=None,
                department=None, must_change_password=False, db_path=DB_PATH):
    """Creates a user (and the matching admin / healthcare_provider row). Returns user_id."""
    raise_if_errors([
        name_error(first_name, "First name"),
        name_error(last_name, "Last name"),
        email_error(email),
        phone_error(phone_no),
        password_error(password),
        None if gender is None or gender in GENDERS else "Gender must be Female, Male or Other.",
        text_error(department, "Department", 100),
    ])
    first_name, last_name = first_name.strip(), last_name.strip()
    email = email.strip().lower()
    phone_no = (phone_no or "").strip() or None
    conn = get_connection(db_path)
    try:
        role = conn.execute("SELECT role_id FROM role WHERE role_name = ?", (role_name,)).fetchone()
        if role is None:
            raise ValueError(f"Unknown role: {role_name}")
        cur = conn.execute(
            "INSERT INTO user (role_id, first_name, last_name, gender, email, password, phone_no, "
            "must_change_password) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (role["role_id"], first_name, last_name, gender, email, hash_password(password), phone_no,
             1 if must_change_password else 0),
        )
        uid = cur.lastrowid
        if role_name == ADMIN:
            conn.execute("INSERT INTO admin (user_id) VALUES (?)", (uid,))
        else:
            conn.execute(
                "INSERT INTO healthcare_provider (user_id, license_number, profession, department) "
                "VALUES (?, ?, ?, ?)", (uid, license_number, profession, department))
        conn.commit()
    finally:
        conn.close()
    log_action("CREATE_USER", f"Created {role_name} {email}", db_path=db_path)
    return uid


def authenticate(email, password, db_path=DB_PATH):
    """Returns a dict {user_id, name, email, role} on success, else None.
    Deactivated accounts cannot log in."""
    email = (email or "").strip().lower()
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT u.user_id, u.first_name, u.last_name, u.email, u.password, "
            "u.is_active, u.must_change_password, r.role_name FROM user u JOIN role r ON r.role_id = u.role_id "
            "WHERE u.email = ?", (email,)).fetchone()
    finally:
        conn.close()

    if row is None or not verify_password(password or "", row["password"]):
        log_action("LOGIN_FAILED", f"Failed login for {email}", db_path=db_path)
        return None
    if not row["is_active"]:
        log_action("LOGIN_BLOCKED", f"Deactivated account {email}", row["user_id"], db_path)
        return None

    log_action("LOGIN", "User logged in", row["user_id"], db_path)
    return {"user_id": row["user_id"],
            "name": f"{row['first_name']} {row['last_name']}",
            "email": row["email"],
            "role": row["role_name"],
            "must_change_password": bool(row["must_change_password"])}


# ---------- passwords ----------

_TEMP_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "O0oIl1")


def generate_temp_password(length=10):
    """Random temporary password, without look-alike characters (0/O, 1/l/I)."""
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))


def change_password(user_id, current_password, new_password, db_path=DB_PATH):
    """A user changes their own password. Needs the current password."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT password FROM user WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("User not found.")
        if not verify_password(current_password or "", row["password"]):
            conn.close()
            log_action("PASSWORD_CHANGE_FAILED", "Wrong current password", user_id, db_path)
            raise ValueError("Current password is incorrect.")
        raise_if_errors([
            password_error(new_password),
            "New password must be different from the current one."
            if verify_password(new_password or "", row["password"]) else None,
        ])
        conn.execute("UPDATE user SET password = ?, must_change_password = 0 WHERE user_id = ?",
                     (hash_password(new_password), user_id))
        conn.commit()
    finally:
        conn.close()
    log_action("PASSWORD_CHANGED", "User changed their password", user_id, db_path)


def reset_password(target_user_id, acting_user_id, db_path=DB_PATH):
    """An administrator sets a random temporary password for another user.
    The user must choose a new one at next login. Returns the temporary password (show it once)."""
    if target_user_id == acting_user_id:
        raise ValueError("Use 'Change password' for your own account.")
    conn = get_connection(db_path)
    try:
        if conn.execute("SELECT 1 FROM admin WHERE user_id = ?", (acting_user_id,)).fetchone() is None:
            raise ValueError("Only administrators can reset passwords.")
        if conn.execute("SELECT 1 FROM user WHERE user_id = ?", (target_user_id,)).fetchone() is None:
            raise ValueError("User not found.")
        temp = generate_temp_password()
        conn.execute("UPDATE user SET password = ?, must_change_password = 1 WHERE user_id = ?",
                     (hash_password(temp), target_user_id))
        conn.commit()
    finally:
        conn.close()
    log_action("PASSWORD_RESET", f"Reset password for user {target_user_id}", acting_user_id, db_path)
    return temp


# ---------- admin helpers ----------

def list_users(db_path=DB_PATH):
    conn = get_connection(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT u.user_id, u.first_name, u.last_name, u.gender, u.email, u.phone_no, "
            "r.role_name, u.is_active, hp.department "
            "FROM user u JOIN role r ON r.role_id = u.role_id "
            "LEFT JOIN healthcare_provider hp ON hp.user_id = u.user_id "
            "ORDER BY u.user_id")]
    finally:
        conn.close()


def set_user_active(user_id, active, acting_user_id, db_path=DB_PATH):
    """Activates/deactivates a user. An admin cannot deactivate their own account."""
    if user_id == acting_user_id and not active:
        raise ValueError("You cannot deactivate your own account.")
    conn = get_connection(db_path)
    try:
        cur = conn.execute("UPDATE user SET is_active = ? WHERE user_id = ?",
                           (1 if active else 0, user_id))
        if cur.rowcount == 0:
            raise ValueError("User not found.")
        conn.commit()
    finally:
        conn.close()
    log_action("ACTIVATE_USER" if active else "DEACTIVATE_USER",
               f"User {user_id}", acting_user_id, db_path)


def get_logs(limit=200, db_path=DB_PATH):
    """Latest log entries, newest first, with Nairobi-time stamps."""
    from modules.database import to_nairobi
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT l.log_id, l.date_time, l.action, l.description, "
            "COALESCE(u.email, '-') AS user_email "
            "FROM system_log l LEFT JOIN user u ON u.user_id = l.user_id "
            "ORDER BY l.log_id DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["date_time"] = to_nairobi(d["date_time"])
        out.append(d)
    return out