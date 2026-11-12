"""
Tests the learned X-ray gate on folders of images.

    python scripts/check_xray_gate.py "data\\raw\\chest_xray\\test" "C:\\path\\to\\knee_xrays"

For each folder it prints how many images the gate ACCEPTS as chest X-rays.
Real chest X-ray folders should be about 100% accepted; other images should be about 0%.
"""
import sys
from pathlib import Path
sys.path.append(".")

from PIL import Image
from modules.xray_gate import load_gate

EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def main(folders):
    gate = load_gate()
    if gate is None:
        sys.exit("Gate not available: put xray_gate.pth and xray_gate.json in models/ and install torch.")
    print(f"threshold = {gate.threshold}")
    for folder in folders:
        files = [p for p in Path(folder).rglob("*") if p.suffix.lower() in EXT]
        if not files:
            print(f"{folder}: no images found"); continue
        accepted, rejected = 0, []
        for f in files:
            with Image.open(f) as im:
                ok, p = gate.check(im)
            accepted += ok
            if not ok: rejected.append((f.name, p))
        print(f"{folder}: {accepted}/{len(files)} accepted ({100*accepted/len(files):.1f}%)")
        for name, p in rejected[:10]:
            print(f"   rejected: {name}  p={p:.3f}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if not args: sys.exit(__doc__)
    main(args)