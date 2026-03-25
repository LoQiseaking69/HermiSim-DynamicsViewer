"""File loading and model management for MuJoCo-backed simulations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from PySide6.QtCore import QSettings

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".urdf", ".xml", ".mjcf"}
_SETTINGS_KEY = "files/last_model_path"
_DEFAULT_MODEL = Path(__file__).resolve().parent.parent / "models" / "starter_model.xml"
_STATE_DIR = Path(__file__).resolve().parent.parent / ".state"


class FileLoader:
    """Validates and delegates model file loading to a :class:`Simulation`."""

    def __init__(self, simulation: Simulation) -> None:
        self._simulation = simulation

    def load_file(self, file_path: str) -> None:
        """Load a single model file into the simulation.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            ValueError: If the file extension is not supported.
            RuntimeError: If the engine fails to load the file.
        """
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{path.suffix}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            )

        try:
            self._simulation.load_model(str(path))
            logger.info("Loaded model: %s", path)
            self._save_last_path(path)
        except Exception as exc:
            logger.error("Failed to load %s: %s", path, exc)
            raise RuntimeError(f"Failed to load {path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _save_last_path(path: Path) -> None:
        QSettings("HermiSim", "DynamicsViewer").setValue(
            _SETTINGS_KEY, str(path.resolve())
        )

    @staticmethod
    def last_model_path() -> Optional[Path]:
        """Return the last successfully-loaded model path, or *None*."""
        raw = QSettings("HermiSim", "DynamicsViewer").value(_SETTINGS_KEY)
        if raw:
            p = Path(raw)
            if p.is_file():
                return p
        return None

    @staticmethod
    def default_model_path() -> Optional[Path]:
        """Return the bundled starter model path if it exists."""
        if _DEFAULT_MODEL.is_file():
            return _DEFAULT_MODEL
        return None

    @staticmethod
    def save_last_state(state: Dict[str, Any]) -> None:
        """Persist the simulation state snapshot to disk."""
        try:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            np.savez(str(_STATE_DIR / "last_state.npz"), **state)
            logger.info("Saved simulation state to %s", _STATE_DIR)
        except Exception as exc:
            logger.warning("Could not save simulation state: %s", exc)

    @staticmethod
    def load_last_state() -> Optional[Dict[str, Any]]:
        """Load a previously saved simulation state, or *None*."""
        state_file = _STATE_DIR / "last_state.npz"
        if not state_file.is_file():
            return None
        try:
            with np.load(str(state_file), allow_pickle=False) as data:
                return dict(data)
        except Exception as exc:
            logger.warning("Could not load simulation state: %s", exc)
            return None

    def load_multiple_files(self, file_paths: List[str]) -> List[str]:
        """Load several files, returning a list of error messages (if any)."""
        errors: List[str] = []
        for fp in file_paths:
            try:
                self.load_file(fp)
            except Exception as exc:
                errors.append(str(exc))
        return errors
