# A Robotics Simulation Suite

![img](https://github.com/LoQiseaking69/HermiSim-DynamicsViewer/blob/main/IMG_1637.png)
___
## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Directory Structure](#directory-structure)
4. [Installation and Usage](#installation-and-usage)
5. [Components](#components)
    - [main.py](#mainpy)
    - [GUI Components](#gui-components)
        - [styles.py](#stylespy)
        - [main_window.py](#main_windowpy)
        - [file_loader.py](#file_loaderpy)
        - [object_renderer.py](#object_rendererpy)
        - [simulation_controls.py](#simulation_controlspy)
        - [sensor_data_viewer.py](#sensor_data_viewerpy)
    - [Tabs](#tabs)
        - [render_tab.py](#render_tabpy)
        - [simulation_tab.py](#simulation_tabpy)
        - [log_tab.py](#log_tabpy)
        - [sensor_tab.py](#sensor_tabpy)
    - [Physics Engine](#physics-engine)
        - [engine.py](#enginepy)
        - [simulation.py](#simulationpy)
        - [sensor.py](#sensorpy)
6. [Additional Notes](#additional-notes)
___
![hsl](https://github.com/LoQiseaking69/HermiSim-DynamicsViewer/blob/main/HSlogo.jpg)
___

## Directory Structure

```
HERMISIM/
│
├──gui/
│   ├── styles.py
│   ├── main_window.py
│   ├── file_loader.py
│   ├── object_renderer.py
│   ├── simulation_controls.py
│   ├── sensor_data_viewer.py
│   ├── tabs/
│   │   ├── render_tab.py
│   │   ├── simulation_tab.py
│   │   ├── log_tab.py
│   │   ├── sensor_tab.py
physics_engine/
│   ├── engine.py
│   ├── simulation.py
│   ├── sensor.py
tests/
main.py
README.md
```

## Overview

This Robotics Simulation Suite is a sophisticated application designed for loading URDF/XML files, rendering objects in a 3D space, and running robotic simulations using a physics engine. The application supports multiple tabs and functionalities to provide a comprehensive simulation environment.

## Features

- **Load URDF/XML Files**: Load and parse URDF/XML files to simulate robots.
- **3D Rendering**: Visualize robots and environments in 3D using PyQt and PyBullet.
- **Physics Engine**: Leverage PyBullet for realistic physics simulations.
- **Sensor Data**: Simulate and display data from various sensors like IMU, Lidar, and Camera.
- **Simulation Controls**: Start, stop, reset simulations, and control simulation speed.
- **Logs and Debugging**: View logs for debugging and simulation insights.
- **Modular Design**: The application is modular, allowing easy extension and maintenance.

## Installation and Usage

1. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2. **Run the application**:
    ```bash
    python main.py
    ```

## Components

#### `main.py`
- **Entry Point**: Initializes the PyQt application, applies styles, and sets up the main window.

#### GUI Components
- **`styles.py`**: Defines and applies visual styles using PyQt.
- **`main_window.py`**: Hosts the main window, integrates tabs, and manages file loading.
- **`file_loader.py`**: Loads and parses URDF/XML files for the simulation.
- **`object_renderer.py`**: Renders robots and environments in a 3D space.
- **`simulation_controls.py`**: Controls for starting, stopping, resetting simulations, and adjusting speed.
- **`sensor_data_viewer.py`**: Displays real-time sensor data in a tabular format.

#### Tabs
- **`render_tab.py`**: Visualization of robots and environments.
- **`simulation_tab.py`**: Contains elements for controlling the simulation.
- **`log_tab.py`**: Displays logs and debugging information.
- **`sensor_tab.py`**: Manages and displays sensor-related data.

#### Physics Engine
- **`engine.py`**: Manages connection to the PyBullet engine and handles simulation steps.
- **`simulation.py`**: Controls simulation operations, including start, stop, reset, and sensor updates.
- **`sensor.py`**: Simulates IMU, Lidar, Camera sensors, and provides realistic data.

## Additional Notes

- Ensure that PyBullet and PyQt5 are correctly installed.
- The application is designed to be modular, so new features and sensors can be easily added.

