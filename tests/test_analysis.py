import io
import sys
sys.path.append(".")

import numpy as np
import pytest
from PIL import Image

from modules.analysis import analyze_xray
from modules.auth import create_user, PROVIDER
from modules.database import init_db, get_connection
from modules.patients import register_patient


class FakeEngine:
    def __init__(self, label="PNEUMONIA", prob=0.9, fail_at=None):
        self.label, self.prob, self.fail_at = label, prob, fail_at

    def prepare_image(self, path):
        return "tensor", np.full((224, 224, 3), 0.5, dtype=np.float32)

    def predict(self, tensor):
        return self.label, 1 if self.label == "PNEUMONIA" else 0, self.prob

    def gradcam(self, tensor, base, target):
        if self.fail_at == "gradcam":
            raise RuntimeError("boom")
        return np.zeros((224, 224, 3), dtype=np.uint8)


def png_bytes():
    buf = io.BytesIO()
    Image.new("L", (64, 64), 128).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def ctx(tmp_path):
    db = tmp_path / "t.db"
    init_db(db)
    uid = create_user("Jo", "Doc", "jo@x.com", "password1", PROVIDER, db_path=db)
    pid, _ = register_patient(uid, "Amina", "Otieno", "2022-03-01", "Female", db_path=db)
    return db, uid, pid, tmp_path / "up"


def count(db, table):
    c = get_connection(db)
    n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    c.close()
    return n


def test_full_pipeline_saves_everything(ctx):
    db, uid, pid, up = ctx
    r = analyze_xray(pid, uid, png_bytes(), "scan.png", FakeEngine(), db_path=db, upload_dir=up)
    assert r["label"] == "PNEUMONIA" and r["confidence"] == 0.9 and not r["low_confidence"]
    for t in ("x_ray_image", "processing_module", "result", "grad_cam_heatmap"):
        assert count(db, t) == 1
    assert r["original_path"].exists() and r["processed_path"].exists() and r["heatmap_path"].exists()


def test_normal_probability_is_flipped(ctx):
    db, uid, pid, up = ctx
    r = analyze_xray(pid, uid, png_bytes(), "s.png", FakeEngine("NORMAL", 0.8), db_path=db, upload_dir=up)
    assert round(r["p_pneumonia"], 2) == 0.2


def test_low_confidence_flag(ctx):
    db, uid, pid, up = ctx
    r = analyze_xray(pid, uid, png_bytes(), "s.png", FakeEngine("NORMAL", 0.55), db_path=db, upload_dir=up)
    assert r["low_confidence"]


def test_rejects_bad_input(ctx):
    db, uid, pid, up = ctx
    with pytest.raises(ValueError):
        analyze_xray(pid, uid, b"data", "notes.txt", FakeEngine(), db_path=db, upload_dir=up)
    with pytest.raises(ValueError):
        analyze_xray(pid, uid, b"not an image", "fake.png", FakeEngine(), db_path=db, upload_dir=up)
    with pytest.raises(ValueError):
        analyze_xray(999, uid, png_bytes(), "s.png", FakeEngine(), db_path=db, upload_dir=up)
    assert count(db, "x_ray_image") == 0


def test_failure_midway_leaves_nothing_behind(ctx):
    db, uid, pid, up = ctx
    with pytest.raises(RuntimeError):
        analyze_xray(pid, uid, png_bytes(), "s.png", FakeEngine(fail_at="gradcam"),
                     db_path=db, upload_dir=up)
    for t in ("x_ray_image", "processing_module", "result", "grad_cam_heatmap"):
        assert count(db, t) == 0
    assert not any(p.is_file() for p in up.rglob("*"))