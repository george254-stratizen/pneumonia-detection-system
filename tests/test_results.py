import io
import sys
sys.path.append(".")

import numpy as np
import pytest
from PIL import Image

import modules.analysis as analysis
from modules.analysis import analyze_xray
from modules.auth import create_user, ADMIN, PROVIDER
from modules.database import init_db
from modules.patients import register_patient
from modules.report import build_pdf
from modules.results import get_result, patient_history, save_diagnosis


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
    b = io.BytesIO()
    Image.new("L", (64, 64), 128).save(b, format="PNG")
    return b.getvalue()


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(analysis, "ROOT", tmp_path)          # so stored relative paths resolve
    import modules.report as report
    monkeypatch.setattr(report, "ROOT", tmp_path)
    db = tmp_path / "t.db"
    init_db(db)
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=db)
    adm = create_user("Ann", "Admin", "a@x.com", "password1", ADMIN, db_path=db)
    pid, _ = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", db_path=db)
    r = analyze_xray(pid, uid, png(), "s.png", FakeEngine(), db_path=db, upload_dir=tmp_path / "uploads")
    return db, uid, adm, pid, r["result_id"]


def test_get_result_has_everything(ctx):
    db, uid, adm, pid, rid = ctx
    d = get_result(rid, db_path=db)
    assert d["prediction"] == "PNEUMONIA" and d["patient_number"].startswith("PT-")
    assert d["heatmap_path"] and d["processed_image_path"] and d["final_diagnosis"] is None
    assert get_result(999, db_path=db) is None


def test_confirm_then_override(ctx):
    db, uid, adm, pid, rid = ctx
    assert save_diagnosis(rid, uid, "PNEUMONIA", "cough 3 days", db_path=db) is True
    d = get_result(rid, db_path=db)
    assert d["agreed"] is True and d["diagnosed_by"] == "Jo Doc"
    assert save_diagnosis(rid, uid, "NORMAL", "re-read", db_path=db) is False
    d = get_result(rid, db_path=db)
    assert d["final_diagnosis"] == "NORMAL" and d["agreed"] is False
    assert len(patient_history(pid, db_path=db)) == 1       # updated, not duplicated


def test_diagnosis_validation(ctx):
    db, uid, adm, pid, rid = ctx
    with pytest.raises(ValueError):
        save_diagnosis(rid, uid, "BANANA", db_path=db)
    with pytest.raises(ValueError):
        save_diagnosis(rid, adm, "NORMAL", db_path=db)       # admins can't diagnose
    with pytest.raises(ValueError):
        save_diagnosis(999, uid, "NORMAL", db_path=db)


def test_history_newest_first(ctx, tmp_path):
    db, uid, adm, pid, rid = ctx
    r2 = analyze_xray(pid, uid, png(), "s2.png", FakeEngine("NORMAL", 0.8),
                      db_path=db, upload_dir=tmp_path / "uploads")
    h = patient_history(pid, db_path=db)
    assert [x["result_id"] for x in h] == [r2["result_id"], rid]


def test_pdf_report(ctx):
    db, uid, adm, pid, rid = ctx
    save_diagnosis(rid, uid, "PNEUMONIA", "notes here", db_path=db)
    pdf = build_pdf(get_result(rid, db_path=db), "Jo Doc")
    assert pdf.startswith(b"%PDF") and len(pdf) > 3000
    # also works before any diagnosis exists
    r2 = ctx  # reuse fixture data
    assert build_pdf({**get_result(rid, db_path=db), "final_diagnosis": None, "agreed": None}, "Jo")