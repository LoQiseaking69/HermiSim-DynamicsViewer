"""Custom exceptions for the HermiSim physics engine."""


class PhysicsEngineError(Exception):
    """Base exception for all physics engine errors."""


class EngineNotInitializedError(PhysicsEngineError):
    """Raised when operations are attempted on an uninitialized engine."""


class ModelLoadError(PhysicsEngineError):
    """Raised when a model file cannot be loaded or parsed."""


class SimulationStateError(PhysicsEngineError):
    """Raised on invalid simulation state transitions."""


class SensorError(PhysicsEngineError):
    """Raised on sensor-related errors."""
