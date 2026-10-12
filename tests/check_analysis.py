"""Smoke test with your REAL model:  python tests/check_analysis.py <path to an X-ray image>"""
import sys
import tempfile
from pathlib import Path
sys.path.append(".")

from modules.analysis import RealEngine, analyze_xray
from modules.auth import create_user, PROVIDER
from modules.database import init_db
from modules.patients import register_patient

img = Path(sys.argv[1])
tmp = Path(tempfile.mkdtemp())
db = tmp / "smoke.db"
init_db(db)
uid = create_user("Smoke", "Test", "smoke@x.com", "password1", PROVIDER, db_path=db)
pid, _ = register_patient(uid, "Test", "Patient", "2022-01-01", "Male", db_path=db)
r = analyze_xray(pid, uid, img.read_bytes(), img.name, RealEngine(), db_path=db, upload_dir=tmp / "up")
print(f"{r['label']} ({r['confidence']:.1%})")
print("Files saved in:", tmp / "up")