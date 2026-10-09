"""
prediction.py

Loads the trained ResNet50 and classifies a chest X-ray. Preprocessing must
match the training notebook exactly.
"""

from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms

from modules.preprocessing import ProcessingModule

CLASS_NAMES = ["NORMAL", "PNEUMONIA"]
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "resnet50_pneumonia.pth"

_transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def load_model(model_path: Path = MODEL_PATH) -> nn.Module:
    """Builds ResNet50 with a 2-class output layer and loads the trained weights."""
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(CLASS_NAMES))
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    return model


def prepare_image(image_path: str):
    """Returns (input_tensor, rgb_image) for one X-ray.

    input_tensor: shape (1, 3, 224, 224), ready for the model.
    rgb_image: float array in [0, 1], used later to draw the Grad-CAM overlay.
    """
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")

    enhanced = ProcessingModule().apply_clahe(gray)
    rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)

    input_tensor = _transform(rgb).unsqueeze(0)
    overlay_base = cv2.resize(rgb, (224, 224)).astype(np.float32) / 255.0
    return input_tensor, overlay_base


def predict(model: nn.Module, input_tensor: torch.Tensor):
    """Returns (label, class_index, probability_of_that_class)."""
    with torch.no_grad():
        probabilities = torch.softmax(model(input_tensor), dim=1)[0]
    class_index = int(probabilities.argmax())
    return CLASS_NAMES[class_index], class_index, float(probabilities[class_index])