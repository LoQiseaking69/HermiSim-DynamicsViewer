"""File loading and model management for MuJoCo-backed simulations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".urdf", ".xml", ".mjcf"}


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
        except Exception as exc:
            logger.error("Failed to load %s: %s", path, exc)
            raise RuntimeError(f"Failed to load {path}: {exc}") from exc

    def load_multiple_files(self, file_paths: List[str]) -> List[str]:
        """Load several files, returning a list of error messages (if any)."""
        errors: List[str] = []
        for fp in file_paths:
            try:
                self.load_file(fp)
            except Exception as exc:
                errors.append(str(exc))
        return errors
