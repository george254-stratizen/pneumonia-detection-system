import sys
sys.path.append(".")

import glob
import cv2
import matplotlib.pyplot as plt

from modules.prediction import load_model, prepare_image, predict
from modules.gradcam import generate_gradcam

sample_path = glob.glob("data/raw/chest_xray/test/PNEUMONIA/*.jpeg")[0]

model = load_model()
input_tensor, overlay_base = prepare_image(sample_path)
label, class_index, probability = predict(model, input_tensor)
overlay = generate_gradcam(model, input_tensor, overlay_base, class_index)

print(f"Prediction: {label} ({probability:.1%})")

fig, axes = plt.subplots(1, 2, figsize=(10, 5))
axes[0].imshow(overlay_base); axes[0].set_title("X-ray after CLAHE"); axes[0].axis("off")
axes[1].imshow(overlay); axes[1].set_title(f"Grad-CAM: {label}"); axes[1].axis("off")
plt.savefig("data/processed/gradcam_test.png")
print("Saved to data/processed/gradcam_test.png")