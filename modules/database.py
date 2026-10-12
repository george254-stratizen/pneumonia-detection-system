"""
database.py

Creates the SQLite database from the system's database schema and provides
helpers for connecting and hashing passwords.
"""

import hashlib
import hmac
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "pneumonia.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS role (
    role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name   VARCHAR NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS user (
    user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id    INTEGER NOT NULL REFERENCES role(role_id),
    first_name VARCHAR NOT NULL,
    last_name  VARCHAR NOT NULL,
    email      VARCHAR NOT NULL UNIQUE,
    password   VARCHAR NOT NULL,          -- salted hash, never plain text
    phone_no   VARCHAR,
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS admin (
    user_id INTEGER PRIMARY KEY REFERENCES user(user_id)
);

CREATE TABLE IF NOT EXISTS healthcare_provider (
    user_id        INTEGER PRIMARY KEY REFERENCES user(user_id),
    license_number VARCHAR,
    profession     VARCHAR,
    department     VARCHAR
);

CREATE TABLE IF NOT EXISTS system_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES user(user_id),
    action      VARCHAR NOT NULL,
    description TEXT,
    date_time   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patient (
    patient_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_number VARCHAR UNIQUE,         -- hospital/clinic ID shown to staff
    provider_id   INTEGER NOT NULL REFERENCES healthcare_provider(user_id),  -- registered by
    first_name    VARCHAR NOT NULL,
    last_name     VARCHAR NOT NULL,
    date_of_birth DATE,
    gender        VARCHAR,
    phone_no      VARCHAR,
    address       VARCHAR
);

CREATE TABLE IF NOT EXISTS x_ray_image (
    xray_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL REFERENCES patient(patient_id),
    file_name   VARCHAR NOT NULL,
    file_path   VARCHAR NOT NULL,
    file_type   VARCHAR,
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    uploaded_by INTEGER REFERENCES user(user_id)
);

CREATE TABLE IF NOT EXISTS processing_module (
    processing_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    xray_id              INTEGER NOT NULL REFERENCES x_ray_image(xray_id),
    technique            VARCHAR NOT NULL,
    processed_image_path VARCHAR,
    processing_date      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model (
    model_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name  VARCHAR NOT NULL,
    model_type  VARCHAR,
    version     VARCHAR,
    description TEXT
);

CREATE TABLE IF NOT EXISTS result (
    result_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_id INTEGER NOT NULL REFERENCES processing_module(processing_id),
    patient_id    INTEGER NOT NULL REFERENCES patient(patient_id),
    model_id      INTEGER NOT NULL REFERENCES model(model_id),
    prediction    VARCHAR NOT NULL CHECK (prediction IN ('NORMAL', 'PNEUMONIA')),
    probability   FLOAT,
    confidence    FLOAT,
    date          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS grad_cam_heatmap (
    heatmap_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id      INTEGER NOT NULL REFERENCES result(result_id),
    heatmap_path   VARCHAR NOT NULL,
    generated_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnosis_record (
    diagnosis_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL REFERENCES patient(patient_id),
    result_id       INTEGER NOT NULL REFERENCES result(result_id),
    provider_id     INTEGER NOT NULL REFERENCES healthcare_provider(user_id),
    final_diagnosis VARCHAR CHECK (final_diagnosis IN ('NORMAL', 'PNEUMONIA', 'OTHER')),
    diagnosis_notes TEXT,
    diagnosis_date  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_name    ON patient(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_xray_patient    ON x_ray_image(patient_id);
CREATE INDEX IF NOT EXISTS idx_result_patient  ON result(patient_id);
CREATE INDEX IF NOT EXISTS idx_log_date        ON system_log(date_time);
"""


def get_connection(db_path=DB_PATH) -> sqlite3.Connection:
    """Opens a connection with foreign keys enforced and rows accessible by name."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def to_nairobi(utc_text: str) -> str:
    """Converts a stored UTC timestamp ('YYYY-MM-DD HH:MM:SS') to Nairobi time (UTC+3)."""
    from datetime import datetime, timedelta
    return (datetime.strptime(utc_text, "%Y-%m-%d %H:%M:%S") + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Returns 'salt$hash' (PBKDF2-SHA256) suitable for storing in user.password."""
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split("$")
    candidate = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, stored)


def init_db(db_path=DB_PATH) -> None:
    """Creates all tables and seeds the roles and the model record."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO role (role_name, description) VALUES (?, ?)",
            [("Administrator", "Manages users and views system logs"),
             ("Healthcare Provider", "Registers patients and runs X-ray classification")],
        )
        if conn.execute("SELECT COUNT(*) FROM model").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO model (model_name, model_type, version, description) VALUES (?, ?, ?, ?)",
                ("ResNet50", "CNN (transfer learning)", "1.0",
                 "Pneumonia vs normal chest X-ray classifier with CLAHE preprocessing"),
            )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")