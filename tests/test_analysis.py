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
    for t in ("x_ray_image", "processing_module", "result", "grad_cam_heatmap", "diagnosis_record"):
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
    for t in ("x_ray_image", "processing_module", "result", "grad_cam_heatmap", "diagnosis_record"):
        assert count(db, t) == 0
    assert not any(p.is_file() for p in up.rglob("*"))


def test_non_xray_screenshot_is_rejected_and_nothing_saved(ctx):
    db, uid, pid, up = ctx
    shot = Image.new("RGB", (1280, 720), (255, 255, 255))
    buf = io.BytesIO(); shot.save(buf, format="PNG")
    with pytest.raises(ValueError, match="Please upload a chest X-ray image"):
        analyze_xray(pid, uid, buf.getvalue(), "screenshot.png", FakeEngine(), db_path=db, upload_dir=up)
    for t in ("x_ray_image", "processing_module", "result", "grad_cam_heatmap", "diagnosis_record"):
        assert count(db, t) == 0
    assert not any(p.is_file() for p in up.rglob("*"))
    c = get_connection(db)
    logged = c.execute("SELECT description FROM system_log WHERE action = 'IMAGE_REJECTED'").fetchone()
    c.close()
    assert logged and "screenshot.png" in logged[0]            # the reason is kept for the admin


class _StubGate:
    def __init__(self, ok, p): self.ok, self.p = ok, p
    def check(self, img): return self.ok, self.p


def _png_bytes():
    rng = np.random.default_rng(0)
    arr = rng.integers(40, 200, (256, 256), dtype=np.uint8)
    buf = io.BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_gate_rejects_and_logs_probability(ctx):
    db, uid, pid, up = ctx
    eng = FakeEngine(); eng.gate = _StubGate(False, 0.03)
    with pytest.raises(ValueError, match="Please upload a chest X-ray image"):
        analyze_xray(pid, uid, _png_bytes(), "knee.png", eng, db_path=db, upload_dir=up,
                     check_image=True)
    assert count(db, "x_ray_image") == 0
    assert not any(p.is_file() for p in up.rglob("*"))
    c = get_connection(db)
    logged = c.execute("SELECT description FROM system_log WHERE action='IMAGE_REJECTED'").fetchone()
    c.close()
    assert logged and "knee.png" in logged[0] and "0.03" in logged[0]


def test_gate_accepts_real_xray(ctx):
    db, uid, pid, up = ctx
    eng = FakeEngine(); eng.gate = _StubGate(True, 0.98)
    analyze_xray(pid, uid, _png_bytes(), "ok.png", eng, db_path=db, upload_dir=up, check_image=True)
    assert count(db, "result") == 1