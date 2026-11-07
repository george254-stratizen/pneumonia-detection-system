import io
import sys
sys.path.append(".")

import numpy as np
import pytest
from PIL import Image, ImageDraw

from modules.image_check import check_chest_xray


def xray_like(w=480, h=560, seed=0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    base = 90 + 90 * np.exp(-(((xx - w / 2) / (w / 3)) ** 2 + ((yy - h / 2) / (h / 3)) ** 2))
    return Image.fromarray(np.clip(base + rng.normal(0, 18, (h, w)), 0, 255).astype(np.uint8), "L")


def screenshot(dark=False):
    im = Image.new("RGB", (1280, 720), (20, 20, 20) if dark else (255, 255, 255))
    d = ImageDraw.Draw(im)
    for y in range(40, 680, 30):
        d.rectangle([40, y, 700, y + 10], fill=(220, 220, 220) if dark else (0, 0, 0))
    d.rectangle([900, 60, 1200, 200], fill=(30, 100, 220))
    return im


def test_xray_like_image_accepted():
    ok, reasons = check_chest_xray(xray_like())
    assert ok and reasons == []


def test_rgb_saved_grayscale_xray_accepted():
    assert check_chest_xray(xray_like().convert("RGB"))[0]       # many X-ray JPEGs are stored as RGB


def test_path_input_works(tmp_path):
    p = tmp_path / "x.png"
    xray_like().save(p)
    assert check_chest_xray(p)[0]


@pytest.mark.parametrize("name,img", [
    ("white screenshot", screenshot()),
    ("dark screenshot", screenshot(dark=True)),
    ("solid grey", Image.new("L", (500, 500), 128)),
    ("colour photo-like", Image.fromarray(np.random.default_rng(1).integers(0, 255, (500, 500, 3), dtype=np.uint8))),
    ("tiny image", xray_like(64, 64)),
    ("phone-shaped", xray_like(400, 900)),
])
def test_non_xrays_rejected(name, img):
    ok, reasons = check_chest_xray(img)
    assert not ok and reasons