import pytest
from unittest.mock import Mock, patch
import pybullet as p
from physics_engine.engine import PhysicsEngine

@pytest.fixture
def physics_engine():
    return PhysicsEngine()

def test_connect_success(physics_engine):
    with patch("pybullet.connect") as mock_connect:
        with patch("pybullet.setAdditionalSearchPath"):
            with patch("pybullet.setGravity"):
                mock_connect.return_value = 1 # Mock a successful connection
                physics_engine.connect()
                assert physics_engine.connected is True
                mock_connect.assert_called_once_with(p.GUI)

def test_connect_failure(physics_engine):
    with patch("pybullet.connect") as mock_connect:
        mock_connect.side_effect = Exception("Connection failed")
        with pytest.raises(ConnectionError, match="Failed to connect to PyBullet"):
            physics_engine.connect()
        assert physics_engine.connected is False

def test_disconnect_success(physics_engine):
    physics_engine.connected = True
    physics_engine.physics_client = 1 # Simulate an active connection
    with patch("pybullet.disconnect") as mock_disconnect:
        physics_engine.disconnect()
        assert physics_engine.connected is False
        assert physics_engine.physics_client is None
        mock_disconnect.assert_called_once_with(1)

def test_step_simulation_connected(physics_engine):
    physics_engine.connected = True
    physics_engine.physics_client = 1
    with patch("pybullet.stepSimulation") as mock_step:
        physics_engine.step_simulation()
        mock_step.assert_called_once()

def test_step_simulation_disconnected(physics_engine):
    physics_engine.connected = False
    physics_engine.physics_client = None
    with patch("pybullet.stepSimulation") as mock_step:
        physics_engine.step_simulation()
        mock_step.assert_not_called()

def test_load_urdf_connected(physics_engine):
    physics_engine.connected = True
    physics_engine.physics_client = 1
    with patch("pybullet.loadURDF") as mock_load_urdf:
        mock_load_urdf.return_value = 0 # Mock a body ID
        body_id = physics_engine.load_urdf("test.urdf")
        assert body_id == 0
        mock_load_urdf.assert_called_once_with("test.urdf", basePosition=(0, 0, 0), baseOrientation=(0, 0, 0, 1))

def test_load_urdf_disconnected(physics_engine):
    physics_engine.connected = False
    physics_engine.physics_client = None
    with patch("pybullet.loadURDF") as mock_load_urdf:
        body_id = physics_engine.load_urdf("test.urdf")
        assert body_id is None
        mock_load_urdf.assert_not_called()

def test_reset_simulation_connected(physics_engine):
    physics_engine.connected = True
    physics_engine.physics_client = 1
    with patch("pybullet.resetSimulation") as mock_reset:
        physics_engine.reset_simulation()
        mock_reset.assert_called_once()

def test_reset_simulation_disconnected(physics_engine):
    physics_engine.connected = False
    physics_engine.physics_client = None
    with patch("pybullet.resetSimulation") as mock_reset:
        physics_engine.reset_simulation()
        mock_reset.assert_not_called()
