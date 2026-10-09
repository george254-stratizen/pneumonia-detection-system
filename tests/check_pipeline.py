import sys
sys.path.append(".")

import glob
from sklearn.metrics import confusion_matrix

from modules.prediction import load_model, prepare_image, predict

model = load_model()

y_true, y_pred = [], []
for label, cls in enumerate(["NORMAL", "PNEUMONIA"]):
    paths = sorted(glob.glob(f"data/raw/chest_xray/test/{cls}/*.jpeg"))
    for i, path in enumerate(paths, 1):
        input_tensor, _ = prepare_image(path)
        _, class_index, _ = predict(model, input_tensor)
        y_true.append(label)
        y_pred.append(class_index)
        if i % 100 == 0:
            print(f"{cls}: {i}/{len(paths)}")

tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
print(f"\nConfusion matrix: TN={tn} FP={fp} FN={fn} TP={tp}")
print(f"Accuracy:    {(tp + tn) / len(y_true):.4f}")
print(f"Sensitivity: {tp / (tp + fn):.4f}")
print(f"Specificity: {tn / (tn + fp):.4f}")