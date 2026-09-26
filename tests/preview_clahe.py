import sys
sys.path.append(".")

import glob
import matplotlib.pyplot as plt
import cv2
from modules.preprocessing import ProcessingModule

sample_path = glob.glob("data/raw/chest_xray/train/PNEUMONIA/*.jpeg")[0]

processor = ProcessingModule()
original = cv2.imread(sample_path, cv2.IMREAD_GRAYSCALE)
output_path = processor.preprocess_image(sample_path)
enhanced = processor.get_processed_image()

fig, axes = plt.subplots(1, 2, figsize=(10, 5))
axes[0].imshow(original, cmap="gray"); axes[0].set_title("Original"); axes[0].axis("off")
axes[1].imshow(enhanced, cmap="gray"); axes[1].set_title("After CLAHE"); axes[1].axis("off")
plt.savefig("data/processed/clahe_test_comparison.png")
print(f"Saved to data/processed/clahe_test_comparison.png (processed file: {output_path})")