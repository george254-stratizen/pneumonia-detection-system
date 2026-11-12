"""
xray_gate.py

The learned "is this a chest X-ray?" check. It runs AFTER the simple filter (image_check.py)
and catches what that cannot, e.g. a grayscale knee X-ray or a grayscale photo.

Files it needs (made by the Colab notebook XRay_Gate_Training.ipynb), in models/:
    xray_gate.pth    the small network's weights
    xray_gate.json   {"threshold": 0.5, "size": 224, ...}

If those files (or PyTorch) are missing, load_gate() returns None and the app simply skips
this check, so nothing breaks.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_WEIGHTS = ROOT / "models" / "xray_gate.pth"
GATE_CONFIG = ROOT / "models" / "xray_gate.json"

_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)


class XrayGate:
    def __init__(self, model, threshold, size, torch):
        self.model, self.threshold, self.size, self._torch = model, threshold, size, torch

    def probability(self, img):
        """Chance (0 to 1) that the PIL image is a chest X-ray."""
        import numpy as np
        from PIL import Image
        torch = self._torch
        img = img.convert("RGB").resize((self.size, self.size), Image.BILINEAR)
        arr = (np.asarray(img, dtype=np.float32) / 255.0 - _MEAN) / _STD
        x = torch.from_numpy(arr.transpose(2, 0, 1)).float().unsqueeze(0)
        with torch.no_grad():
            return float(torch.sigmoid(self.model(x)).item())

    def check(self, img):
        """(ok, probability). ok is True when it looks like a chest X-ray."""
        p = self.probability(img)
        return p >= self.threshold, p


def load_gate(weights=GATE_WEIGHTS, config=GATE_CONFIG):
    """Returns an XrayGate, or None when the files or PyTorch are not available."""
    weights, config = Path(weights), Path(config)
    if not weights.is_file() or not config.is_file():
        return None
    try:
        import torch
        from torchvision import models
    except ImportError:
        return None
    cfg = json.loads(config.read_text())
    model = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, 1)
    model.load_state_dict(torch.load(weights, map_location="cpu"))
    model.eval()
    return XrayGate(model, float(cfg.get("threshold", 0.5)), int(cfg.get("size", 224)), torch)