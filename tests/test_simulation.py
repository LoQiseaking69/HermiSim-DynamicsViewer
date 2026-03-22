import pytest
from unittest.mock import Mock, patch
import pybullet as p
from physics_engine.simulation import Simulation
from physics_engine.engine import PhysicsEngine
from physics_engine.sensor import Sensor

@pytest.fixture
def mock_physics_engine():
    return Mock(spec=PhysicsEngine)

@pytest.fixture
def mock_sensor():
    mock = Mock(spec=Sensor)
    mock.sensor_type = "MockSensor" # Set a default sensor_type for the mock
    return mock

@pytest.fixture
def simulation(mock_physics_engine):
    sim = Simulation()
    sim.engine = mock_physics_engine # Inject mock engine
    return sim

def test_simulation_init(simulation, mock_physics_engine):
    assert simulation.engine == mock_physics_engine
    assert simulation.robot is None
    assert simulation.simulation_speed == 1
    assert simulation.sensors == []
    assert simulation.running is False

def test_start_simulation(simulation, mock_physics_engine):
    with patch.object(simulation, "_load_environment") as mock_load_env:
        simulation.start()
        mock_physics_engine.connect.assert_called_once()
        mock_load_env.assert_called_once()
        assert simulation.running is True

def test_stop_simulation(simulation, mock_physics_engine):
    simulation.running = True
    simulation.stop()
    mock_physics_engine.disconnect.assert_called_once()
    assert simulation.running is False

def test_reset_simulation(simulation, mock_physics_engine):
    with patch.object(simulation, "stop") as mock_stop:
        with patch.object(simulation, "start") as mock_start:
            simulation.reset()
            mock_stop.assert_called_once()
            mock_start.assert_called_once()

def test_load_robot(simulation, mock_physics_engine):
    mock_physics_engine.load_urdf.return_value = 123
    simulation.load_robot("test.urdf")
    mock_physics_engine.load_urdf.assert_called_once_with("test.urdf", (0, 0, 1))
    assert simulation.robot == 123

def test_set_speed(simulation):
    simulation.set_speed(2.5)
    assert simulation.simulation_speed == 2.5

def test_add_sensor(simulation, mock_sensor):
    simulation.add_sensor(mock_sensor)
    assert mock_sensor in simulation.sensors

def test_get_sensor_data(simulation, mock_sensor):
    mock_sensor.sensor_type = "IMU"
    simulation.add_sensor(mock_sensor)
    mock_sensor.get_data.return_value = {"accel": [1, 2, 3]}
    
    data = simulation.get_sensor_data()
    mock_sensor.update.assert_called_once()
    assert data == {"IMU": {"accel": [1, 2, 3]}}

def test_step_method(simulation, mock_physics_engine, mock_sensor):
    simulation.running = True
    mock_sensor.sensor_type = "MockSensor"
    simulation.add_sensor(mock_sensor)
    with patch("pybullet.setTimeStep") as mock_set_time_step:
        simulation.step()
        mock_physics_engine.step_simulation.assert_called_once()
        mock_sensor.update.assert_called_once()
        mock_set_time_step.assert_called_once()
