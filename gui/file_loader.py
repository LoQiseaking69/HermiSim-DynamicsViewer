"""File loading and model management for the simulation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from physics_engine.simulation import Simulation

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".urdf", ".xml", ".mjcf"}


class FileLoader:
    """Loads model files (MJCF, URDF) into the simulation."""

    def __init__(self, simulation: Simulation) -> None:
        self._simulation = simulation

    def load_file(self, file_path: str) -> None:
        """Load a single model file into the simulation."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{suffix}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            )

        self._simulation.load_model(str(path))
        logger.info("Loaded model file: %s", path)

    def load_multiple_files(self, file_paths: list[str]) -> list[str]:
        """Load multiple files, returning a list of any that failed."""
        errors: list[str] = []
        for fp in file_paths:
            try:
                self.load_file(fp)
            except Exception as exc:
                logger.error("Failed to load '%s': %s", fp, exc)
                errors.append(f"{fp}: {exc}")
        return errors

    @staticmethod
    def load_initial_data() -> dict:
        """Return default initial configuration."""
        return {"robot_urdf": "r2d2.urdf"}