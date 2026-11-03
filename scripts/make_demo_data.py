"""
Creates data/demo.db filled with GENERATED sample data for the dashboard demo.
It never touches your real database (data/pneumonia.db).

    python scripts/make_demo_data.py

Then run the app on the demo data:
    PowerShell:   $env:PNEUMONIA_DB = "data/demo.db"; streamlit run app.py
Back to real data: close the window, or  Remove-Item Env:PNEUMONIA_DB

Demo logins (password for all: demo12345):
    admin@demo.com, provider1@demo.com, provider2@demo.com, provider3@demo.com

The sample X-ray image files do not exist, so result screens say "image file not found".
"""

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(".")

from modules.auth import ADMIN, PROVIDER, create_user
from modules.database import get_connection, init_db
from modules.patients import register_patient

DEMO_DB = Path(__file__).resolve().parents[1] / "data" / "demo.db"
PASSWORD = "demo12345"
random.seed(2026)

FIRST = ["Amina", "Brian", "Cynthia", "David", "Esther", "Faith", "Grace", "Hassan", "Irene",
         "James", "Kevin", "Lucy", "Mercy", "Nelson", "Olivia", "Peter", "Ruth", "Samuel",
         "Tabitha", "Victor", "Wanjiru", "Yusuf", "Zawadi", "Ian", "Joy"]
LAST = ["Otieno", "Kamau", "Wanjiku", "Mwangi", "Achieng", "Odhiambo", "Njeri", "Kiprop",
        "Mutua", "Akinyi", "Omondi", "Chebet", "Ndungu", "Barasa", "Kariuki"]

if DEMO_DB.exists():
    DEMO_DB.unlink()
init_db(DEMO_DB)

create_user("Demo", "Admin", "admin@demo.com", PASSWORD, ADMIN, gender="Other", db_path=DEMO_DB)
providers = []
for i, (f, l, g, dept) in enumerate([("Grace", "Wambui", "Female", "Paediatrics"),
                                     ("Peter", "Otieno", "Male", "Outpatient"),
                                     ("Mary", "Chebet", "Female", "Radiology")], start=1):
    providers.append(create_user(f, l, f"provider{i}@demo.com", PASSWORD, PROVIDER,
                                 gender=g, department=dept, db_path=DEMO_DB))

patients = []
for i in range(40):
    uploader = random.choice(providers)
    dob = (datetime.now() - timedelta(days=random.randint(365, 365 * 5 + 200))).date()
    pid, _ = register_patient(uploader, FIRST[i % len(FIRST)], random.choice(LAST), str(dob),
                              random.choice(["Female", "Male"]), db_path=DEMO_DB)
    patients.append(pid)

conn = get_connection(DEMO_DB)
now = datetime.now(timezone.utc).replace(tzinfo=None)
fmt = "%Y-%m-%d %H:%M:%S"


def ts(day_offset, hour_utc):
    t = now - timedelta(days=day_offset)
    return t.replace(hour=hour_utc, minute=random.randint(0, 59), second=random.randint(0, 59)).strftime(fmt)


def log(user_id, action, desc, when):
    conn.execute("INSERT INTO system_log (user_id, action, description, date_time) VALUES (?, ?, ?, ?)",
                 (user_id, action, desc, when))


# 60 days of activity; weekdays busier; providers have different workloads
weights = {providers[0]: 5, providers[1]: 3, providers[2]: 2}
n_results = 0
for day in range(59, -1, -1):
    weekday = (now - timedelta(days=day)).weekday()
    n = random.randint(0, 1) if weekday >= 5 else random.randint(2, 5)
    for _ in range(n):
        uploader = random.choices(list(weights), weights=list(weights.values()))[0]
        patient = random.choice(patients)
        when = ts(day, random.randint(6, 14))                      # 09:00-17:00 Nairobi

        # Truth ~55% pneumonia. Model roughly like the real one: sensitivity ~96%, specificity ~73%.
        truth = "PNEUMONIA" if random.random() < 0.55 else "NORMAL"
        pred = ("PNEUMONIA" if random.random() < 0.96 else "NORMAL") if truth == "PNEUMONIA" \
            else ("NORMAL" if random.random() < 0.73 else "PNEUMONIA")
        correct = pred == truth
        conf = min(0.995, max(0.52, random.gauss(0.90 if correct else 0.68, 0.08)))
        p_pneu = conf if pred == "PNEUMONIA" else 1 - conf

        xid = conn.execute(
            "INSERT INTO x_ray_image (patient_id, file_name, file_path, file_type, upload_date, uploaded_by) "
            "VALUES (?, ?, ?, 'png', ?, ?)",
            (patient, f"demo_{n_results}.png", f"uploads/xrays/demo_{n_results}.png", when, uploader)).lastrowid
        prid = conn.execute(
            "INSERT INTO processing_module (xray_id, technique, processed_image_path, processing_date) "
            "VALUES (?, 'CLAHE', ?, ?)", (xid, f"uploads/processed/demo_{n_results}.png", when)).lastrowid
        rid = conn.execute(
            "INSERT INTO result (processing_id, patient_id, model_id, prediction, probability, confidence, date) "
            "VALUES (?, ?, 1, ?, ?, ?, ?)", (prid, patient, pred, p_pneu, conf, when)).lastrowid
        conn.execute("INSERT INTO grad_cam_heatmap (result_id, heatmap_path, generated_date) VALUES (?, ?, ?)",
                     (rid, f"uploads/gradcam/demo_{n_results}.png", when))
        log(uploader, "ANALYZE_XRAY", f"Demo result {rid}: {pred} ({conf:.1%})", when)

        conn.execute(
            "INSERT INTO diagnosis_record (patient_id, result_id, provider_id, final_diagnosis, diagnosis_date) "
            "VALUES (?, ?, ?, ?, ?)", (patient, rid, uploader, pred, when))
        n_results += 1

# logins, with a few failed attempts
for day in range(59, -1, -1):
    for _ in range(random.randint(2, 6)):
        log(random.choice(providers), "LOGIN", "User logged in", ts(day, random.randint(5, 14)))
    if random.random() < 0.25:
        log(None, "LOGIN_FAILED", "Failed login for someone@demo.com", ts(day, random.randint(5, 18)))

conn.commit()
conn.close()
print(f"Demo database created: {DEMO_DB}  ({n_results} analyses, {len(patients)} patients)")
print(f"Logins (password {PASSWORD}): admin@demo.com, provider1@demo.com ...")