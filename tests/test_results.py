import io
import sys
sys.path.append(".")

import numpy as np
import pytest
from PIL import Image

import modules.analysis as analysis
from modules.analysis import analyze_xray
from modules.auth import create_user, PROVIDER
from modules.database import init_db
from modules.patients import register_patient
from modules.report import build_pdf
from modules.results import get_result, patient_history


class FakeEngine:
    def __init__(self, label="PNEUMONIA", prob=0.9):
        self.label, self.prob = label, prob

    def prepare_image(self, path):
        return "t", np.full((224, 224, 3), 0.5, dtype=np.float32)

    def predict(self, tensor):
        return self.label, 1 if self.label == "PNEUMONIA" else 0, self.prob

    def gradcam(self, tensor, base, target):
        return np.zeros((224, 224, 3), dtype=np.uint8)


def png():
    return _xray_like_bytes()

def _xray_like_bytes():
    rng = np.random.default_rng(0)
    h, w = 560, 480
    yy, xx = np.mgrid[0:h, 0:w]
    base = 90 + 90 * np.exp(-(((xx - w / 2) / (w / 3)) ** 2 + ((yy - h / 2) / (h / 3)) ** 2))
    arr = np.clip(base + rng.normal(0, 18, (h, w)), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "L").save(buf, format="PNG")
    return buf.getvalue()



@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(analysis, "ROOT", tmp_path)          # so stored relative paths resolve
    import modules.report as report
    monkeypatch.setattr(report, "ROOT", tmp_path)
    db = tmp_path / "t.db"
    init_db(db)
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=db)
    pid, _ = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", db_path=db)
    r = analyze_xray(pid, uid, png(), "s.png", FakeEngine(), db_path=db, upload_dir=tmp_path / "uploads")
    return db, uid, pid, r["result_id"], tmp_path


def test_diagnosis_is_recorded_automatically(ctx):
    db, uid, pid, rid, _ = ctx
    d = get_result(rid, db_path=db)
    assert d["prediction"] == "PNEUMONIA"
    assert d["final_diagnosis"] == "PNEUMONIA" and d["diagnosed_by"] == "Jo Doc"
    assert d["heatmap_path"] and d["processed_image_path"] and d["patient_number"].startswith("PT-")
    assert get_result(999, db_path=db) is None


def test_normal_result_is_recorded_as_normal(ctx):
    db, uid, pid, rid, tmp = ctx
    r2 = analyze_xray(pid, uid, png(), "n.png", FakeEngine("NORMAL", 0.8), db_path=db, upload_dir=tmp / "uploads")
    assert get_result(r2["result_id"], db_path=db)["final_diagnosis"] == "NORMAL"


def test_history_newest_first_one_diagnosis_each(ctx):
    db, uid, pid, rid, tmp = ctx
    r2 = analyze_xray(pid, uid, png(), "s2.png", FakeEngine("NORMAL", 0.8), db_path=db, upload_dir=tmp / "uploads")
    h = patient_history(pid, db_path=db)
    assert [x["result_id"] for x in h] == [r2["result_id"], rid]
    assert all(x["final_diagnosis"] for x in h)


@pytest.mark.parametrize("label", ["PNEUMONIA", "NORMAL"])
def test_pdf_report(ctx, label):
    db, uid, pid, rid, tmp = ctx
    r = analyze_xray(pid, uid, png(), "x.png", FakeEngine(label, 0.9), db_path=db, upload_dir=tmp / "uploads")
    pdf = build_pdf(get_result(r["result_id"], db_path=db), "Jo Doc")
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000