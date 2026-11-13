"""FileLoader: validation and delegation to Simulation.load_model (MuJoCo API)."""
from unittest.mock import Mock

import pytest

from gui.file_loader import FileLoader
from physics_engine.simulation import Simulation


@pytest.fixture
def sim():
    return Mock(spec=Simulation)


@pytest.fixture
def loader(sim, monkeypatch):
    monkeypatch.setattr(FileLoader, "_save_last_path", staticmethod(lambda p: None))
    return FileLoader(sim)


@pytest.mark.parametrize("ext", [".xml", ".urdf", ".mjcf"])
def test_supported_files_delegate(loader, sim, tmp_path, ext):
    f = tmp_path / f"robot{ext}"
    f.write_text("<mujoco/>")
    loader.load_file(str(f))
    sim.load_model.assert_called_once_with(str(f))


def test_missing_file(loader):
    with pytest.raises(FileNotFoundError):
        loader.load_file("does_not_exist.xml")


def test_unsupported_extension(loader, tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        loader.load_file(str(f))


def test_engine_failure_is_wrapped(loader, sim, tmp_path):
    f = tmp_path / "bad.xml"
    f.write_text("<broken")
    sim.load_model.side_effect = Exception("parse error")
    with pytest.raises(RuntimeError, match="parse error"):
        loader.load_file(str(f))


def test_load_multiple_collects_errors(loader, sim, tmp_path):
    good = tmp_path / "a.xml"
    good.write_text("<mujoco/>")
    errors = loader.load_multiple_files([str(good), str(tmp_path / "missing.xml"), str(tmp_path / "x.txt")])
    assert len(errors) == 2
    sim.load_model.assert_called_once_with(str(good))
