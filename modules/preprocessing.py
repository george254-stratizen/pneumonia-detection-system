"""
preprocessing.py

Implements the ProcessingModule from the system design: applies CLAHE
(Contrast Limited Adaptive Histogram Equalization) to chest X-ray images
before they are passed to the classification model.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


class ProcessingModule:
    """Applies CLAHE preprocessing to chest X-ray images.

    Mirrors the ProcessingModule class in the system design: `technique`,
    `processed_image_path`, and `processed_at` are set once an image has
    been processed.
    """

    def __init__(self, clip_limit: float = 2.0, tile_grid_size: tuple[int, int] = (8, 8)) -> None:
        self.technique = "CLAHE"
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self.processed_image_path: str | None = None
        self.processed_at: datetime | None = None

    def apply_clahe(self, image: np.ndarray) -> np.ndarray:
        """Applies CLAHE to an already-loaded image array (grayscale or color)."""
        if image is None:
            raise ValueError("Image array is None — nothing to process.")

        if image.ndim == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=self.tile_grid_size)
        return clahe.apply(image)

    def preprocess_image(self, image_path: str, save_dir: str = "data/processed") -> str:
        """Loads an image from disk, applies CLAHE, saves the result, and
        returns the path to the processed file."""
        image_path = Path(image_path)
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

        if image is None:
            raise FileNotFoundError(f"Could not read image at {image_path}")

        enhanced = self.apply_clahe(image)

        save_dir_path = Path(save_dir)
        save_dir_path.mkdir(parents=True, exist_ok=True)
        output_path = save_dir_path / f"clahe_{image_path.name}"
        cv2.imwrite(str(output_path), enhanced)

        self.processed_image_path = str(output_path)
        self.processed_at = datetime.now()

        return self.processed_image_path

    def get_processed_image(self) -> np.ndarray:
        """Loads and returns the most recently processed image."""
        if self.processed_image_path is None:
            raise RuntimeError("No image has been processed yet — call preprocess_image() first.")
        return cv2.imread(self.processed_image_path, cv2.IMREAD_GRAYSCALE)