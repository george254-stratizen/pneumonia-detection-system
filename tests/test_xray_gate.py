import sys
sys.path.append(".")
import pytest

torch = pytest.importorskip("torch")
torchvision = pytest.importorskip("torchvision")

from PIL import Image
from modules.xray_gate import load_gate, XrayGate


def test_load_gate_returns_none_without_files(tmp_path):
    assert load_gate(tmp_path / "no.pth", tmp_path / "no.json") is None


def test_gate_round_trip(tmp_path):
    import json
    from torchvision import models
    m = models.resnet18(weights=None)
    m.fc = torch.nn.Linear(m.fc.in_features, 1)
    torch.save(m.state_dict(), tmp_path / "g.pth")
    (tmp_path / "g.json").write_text(json.dumps({"threshold": 0.5, "size": 224}))
    gate = load_gate(tmp_path / "g.pth", tmp_path / "g.json")
    assert isinstance(gate, XrayGate)
    ok, p = gate.check(Image.new("L", (300, 300), 100))
    assert 0.0 <= p <= 1.0 and isinstance(ok, bool)