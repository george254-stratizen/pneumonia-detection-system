import sys
sys.path.append(".")

import glob
import random
import matplotlib.pyplot as plt

from modules.prediction import load_model, prepare_image, predict
from modules.gradcam import generate_gradcam

random.seed(0)
model = load_model()

samples = []
for cls in ["NORMAL", "PNEUMONIA"]:
    paths = sorted(glob.glob(f"data/raw/chest_xray/test/{cls}/*.jpeg"))
    samples += [(cls, p) for p in random.sample(paths, 4)]

fig, axes = plt.subplots(2, 4, figsize=(16, 8))
for ax, (true_cls, path) in zip(axes.flat, samples):
    input_tensor, base = prepare_image(path)
    label, idx, prob = predict(model, input_tensor)
    overlay = generate_gradcam(model, input_tensor, base, idx)
    ax.imshow(overlay)
    verdict = "correct" if label == true_cls else "WRONG"
    ax.set_title(f"True: {true_cls}\nPred: {label} ({prob:.0%}) {verdict}", fontsize=10)
    ax.axis("off")

plt.tight_layout()
plt.savefig("data/processed/gradcam_grid.png", dpi=150)
print("Saved to data/processed/gradcam_grid.png")