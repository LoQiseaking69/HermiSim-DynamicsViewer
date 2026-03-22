import pytest
from unittest.mock import Mock, patch
import pybullet as p
import numpy as np
from physics_engine.sensor import Sensor

@pytest.fixture
def mock_robot():
    return Mock()

@pytest.fixture
def sensor_imu(mock_robot):
    return Sensor(mock_robot, "IMU", [0, 0, 0], [0, 0, 0, 1])

@pytest.fixture
def sensor_lidar(mock_robot):
    return Sensor(mock_robot, "Lidar", [0, 0, 0], [0, 0, 0, 1])

@pytest.fixture
def sensor_camera(mock_robot):
    return Sensor(mock_robot, "Camera", [0, 0, 0], [0, 0, 0, 1])

def test_sensor_init_no_robot():
    with pytest.raises(ValueError, match="Robot object cannot be None."):
        Sensor(None, "IMU", [0, 0, 0], [0, 0, 0, 1])

def test_imu_update(sensor_imu):
    with patch("pybullet.getBaseVelocity") as mock_get_base_velocity:
        mock_get_base_velocity.return_value = ([1, 2, 3], [4, 5, 6])
        sensor_imu.update()
        assert sensor_imu.get_data() == {
            "acceleration": [1, 2, 3],
            "gyro": [4, 5, 6]
        }

def test_imu_update_error(sensor_imu):
    with patch("pybullet.getBaseVelocity") as mock_get_base_velocity:
        mock_get_base_velocity.side_effect = p.error("PyBullet IMU error")
        sensor_imu.update()
        assert sensor_imu.get_data() is None

def test_lidar_update(sensor_lidar):
    with patch("pybullet.rayTestBatch") as mock_ray_test_batch:
        # Simulate some hits and misses
        mock_ray_test_batch.return_value = [
            (1, -1, 0.5, [0.5, 0, 0], [0, 0, 0]), # Hit at half range
            (1, -1, 1.0, [0, 0, 0], [0, 0, 0])  # Miss
        ] + [(1, -1, 1.0, [0, 0, 0], [0, 0, 0])] * (sensor_lidar.lidar_num_rays - 2)
        sensor_lidar.update()
        data = sensor_lidar.get_data()
        assert "distances" in data
        assert len(data["distances"]) == sensor_lidar.lidar_num_rays
        assert data["distances"][0] == 0.5 * sensor_lidar.lidar_range
        assert data["distances"][1] == sensor_lidar.lidar_range

def test_lidar_update_error(sensor_lidar):
    with patch("pybullet.rayTestBatch") as mock_ray_test_batch:
        mock_ray_test_batch.side_effect = p.error("PyBullet Lidar error")
        sensor_lidar.update()
        assert sensor_lidar.get_data() is None

def test_camera_update(sensor_camera):
    with patch("pybullet.computeViewMatrixFromYawPitchRoll") as mock_view_matrix:
        with patch("pybullet.computeProjectionMatrixFOV") as mock_projection_matrix:
            with patch("pybullet.getCameraImage") as mock_get_camera_image:
                mock_view_matrix.return_value = [1]*16
                mock_projection_matrix.return_value = [1]*16
                mock_get_camera_image.return_value = (640, 480, np.zeros((480, 640, 4)), np.zeros((480, 640)), np.zeros((480, 640)))
                sensor_camera.update()
                data = sensor_camera.get_data()
                assert "image" in data
                assert "depth" in data
                assert "segmentation" in data

def test_camera_update_error(sensor_camera):
    with patch("pybullet.getCameraImage") as mock_get_camera_image:
        mock_get_camera_image.side_effect = p.error("PyBullet Camera error")
        sensor_camera.update()
        assert sensor_camera.get_data() is None

def test_unknown_sensor_type(mock_robot):
    sensor = Sensor(mock_robot, "Unknown", [0, 0, 0], [0, 0, 0, 1])
    with pytest.raises(ValueError, match="Unknown sensor type"):
        sensor.update()
