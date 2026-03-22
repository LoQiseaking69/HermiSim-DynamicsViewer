import pybullet as p
import logging
import numpy as np

class Sensor:
    def __init__(self, robot, sensor_type, position, orientation):
        self.robot = robot
        self.sensor_type = sensor_type
        self.position = position
        self.orientation = orientation
        self.data = None
        self.logger = logging.getLogger(__name__)

        if self.robot is None:
            self.logger.error("Sensor initialized with a None robot object.")
            raise ValueError("Robot object cannot be None.")

        # Initialize sensor-specific parameters
        if self.sensor_type == 'Lidar':
            self.lidar_range = 5.0  # meters
            self.lidar_num_rays = 100
            self.lidar_ray_length = 1.0
            self.lidar_debug = False
        elif self.sensor_type == 'Camera':
            self.camera_width = 640
            self.camera_height = 480
            self.camera_fov = 60
            self.camera_near = 0.1
            self.camera_far = 100

    def update(self):
        if self.sensor_type == 'IMU':
            self.data = self._get_imu_data()
        elif self.sensor_type == 'Lidar':
            self.data = self._get_lidar_data()
        elif self.sensor_type == 'Camera':
            self.data = self._get_camera_data()
        else:
            self.logger.error(f"Unknown sensor type: {self.sensor_type}")
            raise ValueError(f"Unknown sensor type: {self.sensor_type}")

    def get_data(self):
        return self.data

    def _get_imu_data(self):
        try:
            linear_acceleration, angular_velocity = p.getBaseVelocity(self.robot)
            return {
                'acceleration': linear_acceleration,
                'gyro': angular_velocity
            }
        except p.error as e:
            self.logger.error(f"PyBullet error getting IMU data: {e}")
            return None

    def _get_lidar_data(self):
        try:
            # Simulate lidar rays
            ray_from = []
            ray_to = []
            for i in range(self.lidar_num_rays):
                # Simple circular pattern for now, can be improved
                angle = 2 * np.pi * i / self.lidar_num_rays
                ray_from.append([self.position[0], self.position[1], self.position[2]])
                ray_to.append([self.position[0] + self.lidar_range * np.cos(angle), 
                               self.position[1] + self.lidar_range * np.sin(angle), 
                               self.position[2]])
            
            results = p.rayTestBatch(ray_from, ray_to)
            distances = []
            for hit_object_uid, hit_link_index, hit_fraction, hit_position, hit_normal in results:
                if hit_fraction < 1.0: # If ray hit something
                    distances.append(hit_fraction * self.lidar_range)
                else:
                    distances.append(self.lidar_range) # No hit, return max range
            
            return {
                'distances': distances
            }
        except p.error as e:
            self.logger.error(f"PyBullet error getting Lidar data: {e}")
            return None

    def _get_camera_data(self):
        try:
            view_matrix = p.computeViewMatrixFromYawPitchRoll(
                cameraTargetPosition=self.position,
                distance=1.0,
                yaw=0,
                pitch=-30,
                roll=0,
                upAxisIndex=2
            )
            projection_matrix = p.computeProjectionMatrixFOV(
                fov=self.camera_fov,
                aspect=float(self.camera_width) / self.camera_height,
                nearVal=self.camera_near,
                farVal=self.camera_far
            )
            
            width, height, rgb_img, depth_img, seg_img = p.getCameraImage(
                width=self.camera_width,
                height=self.camera_height,
                viewMatrix=view_matrix,
                projectionMatrix=projection_matrix
            )
            return {
                'image': rgb_img,
                'depth': depth_img,
                'segmentation': seg_img
            }
        except p.error as e:
            self.logger.error(f"PyBullet error getting Camera data: {e}")
            return None
