"""
auth.py

Login logic, user creation and activity logging.
Kept free of Streamlit code so it can be unit-tested.
"""

from modules.database import DB_PATH, get_connection, hash_password, verify_password

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
                phone_no=None, license_number=None, profession=None,
                department=None, db_path=DB_PATH):
    """Creates a user (and the matching admin / healthcare_provider row). Returns user_id."""
    email = email.strip().lower()
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    conn = get_connection(db_path)
    try:
        role = conn.execute("SELECT role_id FROM role WHERE role_name = ?", (role_name,)).fetchone()
        if role is None:
            raise ValueError(f"Unknown role: {role_name}")
        cur = conn.execute(
            "INSERT INTO user (role_id, first_name, last_name, email, password, phone_no) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (role["role_id"], first_name, last_name, email, hash_password(password), phone_no),
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
            "u.is_active, r.role_name FROM user u JOIN role r ON r.role_id = u.role_id "
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
            "role": row["role_name"]}