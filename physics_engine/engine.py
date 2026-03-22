# physics_engine/engine.py
import pybullet as p
import logging
import pybullet_data

class PhysicsEngine:
    def __init__(self):
        self.physics_client = None
        self.connected = False
        self.logger = logging.getLogger(__name__)

    def connect(self, mode=p.GUI):
        """Connect to the PyBullet physics server."""
        try:
            self.physics_client = p.connect(mode)
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
            p.setGravity(0, 0, -9.81)
            self.connected = True
            self.logger.info("Connected to PyBullet physics server.")
        except Exception as e:
            self.logger.error(f"Failed to connect to PyBullet: {e}")
            raise ConnectionError(f"Failed to connect to PyBullet: {e}")

    def disconnect(self):
        """Disconnect from the PyBullet physics server."""
        if self.physics_client is not None and self.connected:
            p.disconnect(self.physics_client)
            self.physics_client = None
            self.connected = False
            self.logger.info("Disconnected from PyBullet physics server.")

    def step_simulation(self):
        """Step the simulation forward."""
        if self.physics_client is not None and self.connected:
            p.stepSimulation()
        else:
            self.logger.warning("Cannot step simulation. Physics client is not connected.")

    def load_urdf(self, urdf_file, base_position=(0, 0, 0), base_orientation=(0, 0, 0, 1)):
        """Load a URDF file into the simulation."""
        if self.physics_client is not None and self.connected:
            return p.loadURDF(urdf_file, basePosition=base_position, baseOrientation=base_orientation)
        else:
            self.logger.warning("Cannot load URDF. Physics client is not connected.")
            return None

    def get_body_info(self, body_id):
        """Get information about a body in the simulation."""
        if self.physics_client is not None and self.connected:
            return p.getBodyInfo(body_id)
        else:
            self.logger.warning("Cannot get body info. Physics client is not connected.")
            return None

    def apply_force(self, body_id, link_index, force, position, flags=p.WORLD_FRAME):
        """Apply a force to a body in the simulation."""
        if self.physics_client is not None and self.connected:
            p.applyExternalForce(body_id, link_index, force, position, flags)
        else:
            self.logger.warning("Cannot apply force. Physics client is not connected.")

    def reset_simulation(self):
        """Reset the simulation."""
        if self.physics_client is not None and self.connected:
            p.resetSimulation()
            self.logger.info("Simulation reset.")
        else:
            self.logger.warning("Cannot reset simulation. Physics client is not connected.")
