"""
gradcam.py

Generates a Grad-CAM heatmap showing which regions of the X-ray influenced
the model's prediction.
"""

import numpy as np
import torch.nn as nn
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget


def generate_gradcam(model: nn.Module, input_tensor, overlay_base: np.ndarray,
                     target_class: int) -> np.ndarray:
    """Returns an RGB image (uint8) with the heatmap drawn over the X-ray."""
    target_layers = [model.layer4[-1]]   # last convolutional block of ResNet50

    with GradCAM(model=model, target_layers=target_layers) as cam:
        heatmap = cam(input_tensor=input_tensor,
                      targets=[ClassifierOutputTarget(target_class)])[0]

    return show_cam_on_image(overlay_base, heatmap, use_rgb=True)