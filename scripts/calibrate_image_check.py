"""
Checks the "is this a chest X-ray?" filter against real images.

    python scripts/calibrate_image_check.py "data\\raw\\chest_xray\\test"                 # real X-rays
    python scripts/calibrate_image_check.py "data\\raw\\chest_xray\\test" "C:\\path\\to\\screenshots"

First folder  = genuine chest X-rays  -> we want ~0% rejected.
Second folder = anything that is NOT an X-ray (screenshots, photos...) -> we want ~100% rejected.
Both folders are searched recursively. At most 400 images are sampled from each.
"""

import random
import sys
from pathlib import Path

sys.path.append(".")

from PIL import Image

from modules.image_check import check_chest_xray, image_stats

EXT = {".png", ".jpg", ".jpeg"}


def scan(folder, limit=400):
    files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in EXT]
    random.seed(0)
    random.shuffle(files)
    files = files[:limit]
    rejected, reasons, stats = 0, {}, {"colour_spread": [], "flat_fraction": [], "entropy": [], "aspect": []}
    shown = 0
    for f in files:
        try:
            with Image.open(f) as im:
                ok, why = check_chest_xray(im)
                s = image_stats(im)
        except Exception as e:
            print("  could not read", f.name, e)
            continue
        for k in stats:
            stats[k].append(s[k])
        if not ok:
            rejected += 1
            for r in why:
                reasons[r] = reasons.get(r, 0) + 1
            if shown < 5:
                print("  rejected:", f.name, "->", "; ".join(why))
                shown += 1
    return len(files), rejected, reasons, stats


def summary(name, folder, want):
    n, rej, reasons, stats = scan(folder)
    print(f"\n=== {name}: {folder}")
    if n == 0:
        print("  no images found")
        return
    print(f"  images checked: {n}   rejected: {rej} ({rej / n:.1%})   target: {want}")
    for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {c:4d} x {r}")
    for k, v in stats.items():
        v = sorted(v)
        print(f"  {k:14} min {v[0]:7.2f}   median {v[len(v)//2]:7.2f}   max {v[-1]:7.2f}")


summary("REAL X-RAYS", sys.argv[1], "about 0% rejected")
if len(sys.argv) > 2:
    summary("NOT X-RAYS", sys.argv[2], "about 100% rejected")