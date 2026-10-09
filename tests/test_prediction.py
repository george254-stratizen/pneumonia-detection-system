import sys
sys.path.append(".")

import glob
import pytest

from modules.prediction import load_model, prepare_image, predict, CLASS_NAMES
from modules.gradcam import generate_gradcam

SAMPLE = sorted(glob.glob("data/raw/chest_xray/test/PNEUMONIA/*.jpeg"))[0]


@pytest.fixture(scope="module")
def model():
    return load_model()


def test_prepare_image_shape():
    tensor, base = prepare_image(SAMPLE)
    assert tuple(tensor.shape) == (1, 3, 224, 224)
    assert base.shape == (224, 224, 3)
    assert 0.0 <= base.min() and base.max() <= 1.0


def test_prepare_image_missing_file():
    with pytest.raises(FileNotFoundError):
        prepare_image("does_not_exist.jpeg")


def test_predict_output(model):
    tensor, _ = prepare_image(SAMPLE)
    label, idx, prob = predict(model, tensor)
    assert label in CLASS_NAMES
    assert idx in (0, 1)
    assert 0.5 <= prob <= 1.0   # winning class of a 2-class softmax


def test_gradcam_output(model):
    tensor, base = prepare_image(SAMPLE)
    _, idx, _ = predict(model, tensor)
    overlay = generate_gradcam(model, tensor, base, idx)
    assert overlay.shape == (224, 224, 3)
    assert overlay.dtype == "uint8"