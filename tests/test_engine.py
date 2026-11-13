"""MuJoCo engine + bundled models."""
from pathlib import Path

import pytest

mujoco = pytest.importorskip("mujoco")
from physics_engine.engine import PhysicsEngine  # noqa: E402
from physics_engine.exceptions import ModelLoadError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("model", ["starter_model.xml", "morty.xml"])
def test_models_load_and_step(model):
    e = PhysicsEngine()
    e.load_model_from_path(str(ROOT / "models" / model))
    t0 = e.simulation_time
    for _ in range(50):
        e.step()
    assert e.simulation_time > t0
    assert e.model.nu > 0


def test_morty_shape():
    e = PhysicsEngine()
    e.load_model_from_path(str(ROOT / "models" / "morty.xml"))
    assert e.model.nu == 18          # 12 leg + 6 arm actuators
    assert e.model.nsensor >= 60


def test_bad_paths():
    e = PhysicsEngine()
    with pytest.raises(ModelLoadError):
        e.load_model_from_path(str(ROOT / "nope.xml"))
    with pytest.raises(ModelLoadError):
        e.load_model_from_path(str(ROOT / "README.md"))
