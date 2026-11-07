"""
image_check.py

A cheap first filter that rejects images that clearly are not chest X-rays
(screenshots, documents, colour photos, tiny or oddly shaped pictures) BEFORE the AI sees them.

Why it is needed: the model only knows two answers, Normal and Pneumonia. Given any picture
at all it must pick one, so a random screenshot can come back as "Normal".

Limits: this is a set of simple image-statistics rules. It will not catch a grayscale picture
of something else that looks X-ray-like (e.g. a knee X-ray or a black-and-white photo).
Thresholds were calibrated on the real test X-rays with scripts/calibrate_image_check.py
(re-run it if you change them).
"""

import numpy as np
from PIL import Image

MIN_SIDE = 128                  # pixels
ASPECT_RANGE = (0.5, 3.5)       # width / height (real X-rays in the dataset reach about 2.6)
MAX_COLOUR_SPREAD = 15.0        # mean (max channel - min channel), 0-255. X-rays are grey.
MAX_FLAT_FRACTION = 0.45        # share of pixels with the single most common grey level (real X-rays: up to ~0.30)
MIN_ENTROPY = 5.0               # bits. Flat screenshots/documents score low, X-rays high.


def image_stats(img: Image.Image) -> dict:
    """The numbers the rules look at."""
    w, h = img.size
    small = img.convert("RGB")
    small.thumbnail((256, 256))
    rgb = np.asarray(small, dtype=np.int16)
    colour_spread = float((rgb.max(axis=2) - rgb.min(axis=2)).mean())
    gray = np.asarray(small.convert("L"))
    p = np.bincount(gray.ravel(), minlength=256).astype(float)
    p /= p.sum()
    nz = p[p > 0]
    return {
        "width": w, "height": h, "aspect": w / h,
        "colour_spread": colour_spread,
        "flat_fraction": float(p.max()),
        "entropy": float(-(nz * np.log2(nz)).sum()),
    }


def check_chest_xray(img) -> tuple:
    """Returns (ok, reasons). `img` is a PIL image or a file path."""
    if not isinstance(img, Image.Image):
        with Image.open(img) as opened:
            return check_chest_xray(opened.copy())
    s = image_stats(img)
    reasons = []
    if min(s["width"], s["height"]) < MIN_SIDE:
        reasons.append("the image is too small")
    if not ASPECT_RANGE[0] <= s["aspect"] <= ASPECT_RANGE[1]:
        reasons.append("its shape is unusual for a chest X-ray")
    if s["colour_spread"] > MAX_COLOUR_SPREAD:
        reasons.append("it is a colour image (X-rays are grey)")
    if s["flat_fraction"] > MAX_FLAT_FRACTION:
        reasons.append("it has large flat areas, like a screenshot or document")
    if s["entropy"] < MIN_ENTROPY:
        reasons.append("it has too little tonal detail")
    return (not reasons), reasons