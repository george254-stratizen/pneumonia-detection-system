"""
analysis.py

Runs one X-ray through the whole pipeline and records everything in the database:
save upload -> CLAHE + resize -> ResNet50 prediction -> Grad-CAM -> save to DB.

The AI parts (prepare_image, predict, generate_gradcam, model) are passed in as an
"engine" so this file can be unit-tested without PyTorch. The default engine uses
your real modules.
"""

import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from modules.auth import log_action
from modules.database import DB_PATH, get_connection

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_EXT = {".png", ".jpg", ".jpeg"}
MAX_BYTES = 10 * 1024 * 1024
LOW_CONFIDENCE = 0.70


class RealEngine:
    """Wraps your real model code. PyTorch is only imported when this is first used."""

    def __init__(self, model=None):
        from modules import prediction, gradcam
        self._prediction = prediction
        self._gradcam = gradcam
        self.model = model or prediction.load_model()

    def prepare_image(self, path):
        return self._prediction.prepare_image(path)

    def predict(self, tensor):
        return self._prediction.predict(self.model, tensor)

    def gradcam(self, tensor, base, target_class):
        return self._gradcam.generate_gradcam(self.model, tensor, base, target_class)


def _to_uint8(img):
    arr = np.asarray(img)
    if arr.dtype != np.uint8:
        arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8) if arr.max() <= 1.0 else arr.astype(np.uint8)
    return arr


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def analyze_xray(patient_id, user_id, file_bytes, original_name, engine,
                 db_path=DB_PATH, upload_dir=ROOT / "uploads"):
    """Returns a dict describing the saved result. Raises ValueError for bad input.
    If anything fails midway, no database rows or files are left behind."""
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Only PNG or JPEG images are accepted.")
    if len(file_bytes) == 0 or len(file_bytes) > MAX_BYTES:
        raise ValueError("Image must be between 1 byte and 10 MB.")

    upload_dir = Path(upload_dir)
    dirs = {k: upload_dir / k for k in ("xrays", "processed", "gradcam")}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    saved = []
    try:
        patient = conn.execute("SELECT patient_number FROM patient WHERE patient_id = ?",
                               (patient_id,)).fetchone()
        if patient is None:
            raise ValueError("Patient not found.")

        stem = f"{patient['patient_number']}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        original = dirs["xrays"] / f"{stem}{ext}"
        original.write_bytes(file_bytes)
        saved.append(original)
        try:
            with Image.open(original) as im:
                im.verify()
        except (UnidentifiedImageError, OSError):
            raise ValueError("That file is not a readable image.")

        cur = conn.execute(
            "INSERT INTO x_ray_image (patient_id, file_name, file_path, file_type, uploaded_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (patient_id, original_name, _rel(original), ext.lstrip("."), user_id))
        xray_id = cur.lastrowid

        tensor, base = engine.prepare_image(str(original))
        processed = dirs["processed"] / f"{stem}_clahe.png"
        Image.fromarray(_to_uint8(base)).save(processed)
        saved.append(processed)
        cur = conn.execute(
            "INSERT INTO processing_module (xray_id, technique, processed_image_path) VALUES (?, 'CLAHE', ?)",
            (xray_id, _rel(processed)))
        processing_id = cur.lastrowid

        label, idx, prob = engine.predict(tensor)
        p_pneumonia = prob if label == "PNEUMONIA" else 1 - prob
        model_id = conn.execute("SELECT model_id FROM model ORDER BY model_id DESC LIMIT 1").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO result (processing_id, patient_id, model_id, prediction, probability, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (processing_id, patient_id, model_id, label, float(p_pneumonia), float(prob)))
        result_id = cur.lastrowid

        heat = engine.gradcam(tensor, base, idx)
        heatmap = dirs["gradcam"] / f"{stem}_gradcam.png"
        Image.fromarray(_to_uint8(heat)).save(heatmap)
        saved.append(heatmap)
        conn.execute("INSERT INTO grad_cam_heatmap (result_id, heatmap_path) VALUES (?, ?)",
                     (result_id, _rel(heatmap)))
        conn.commit()
    except Exception:
        conn.rollback()
        for f in saved:
            f.unlink(missing_ok=True)
        raise
    finally:
        conn.close()

    log_action("ANALYZE_XRAY", f"{patient['patient_number']}: {label} ({prob:.1%})", user_id, db_path)
    return {
        "result_id": result_id, "xray_id": xray_id, "patient_id": patient_id,
        "label": label, "confidence": float(prob), "p_pneumonia": float(p_pneumonia),
        "low_confidence": prob < LOW_CONFIDENCE,
        "original_path": original, "processed_path": processed, "heatmap_path": heatmap,
    }