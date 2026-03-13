# HermiSim-DynamicsViewer: A Robotics Simulation Suite

![HermiSim Logo](HSlogo.jpg)

## Table of Contents

1.  [Overview](#overview)
2.  [Features](#features)
3.  [Directory Structure](#directory-structure)
4.  [Installation and Usage](#installation-and-usage)
    -   [Prerequisites](#prerequisites)
    -   [Local Installation](#local-installation)
    -   [Running with Docker](#running-with-docker)
5.  [Running Tests](#running-tests)
6.  [Continuous Integration/Continuous Deployment (CI/CD)](#continuous-integrationcontinuous-deployment-cicd)
7.  [Components](#components)
    -   [`main.py`](#mainpy)
    -   [GUI Components](#gui-components)
    -   [Tabs](#tabs)
    -   [Physics Engine](#physics-engine)
8.  [Enhancements and Hardening](#enhancements-and-hardening)
9.  [License](#license)

## Overview

This Robotics Simulation Suite is a sophisticated application designed for loading URDF/XML files, rendering objects in a 3D space, and running robotic simulations using a physics engine. The application supports multiple tabs and functionalities to provide a comprehensive simulation environment. This enhanced version focuses on robustness, maintainability, and production-grade quality.

## Features

-   **Load URDF/XML Files**: Load and parse URDF/XML files to simulate robots.
-   **3D Rendering**: Visualize robots and environments in 3D using PyQt and PyBullet.
-   **Physics Engine**: Leverage PyBullet for realistic physics simulations.
-   **Sensor Data**: Simulate and display data from various sensors like IMU, Lidar, and Camera.
-   **Simulation Controls**: Start, stop, reset simulations, and control simulation speed.
-   **Logs and Debugging**: View logs for debugging and simulation insights.
-   **Modular Design**: The application is modular, allowing easy extension and maintenance.
-   **Robust Error Handling**: Enhanced error handling and logging across critical modules.
-   **Comprehensive Testing**: Unit tests for core functionalities to ensure reliability.
-   **Containerization**: Docker support for easy deployment and environment consistency.
-   **CI/CD Pipeline**: Automated testing and build processes using GitHub Actions.

## Directory Structure

```
HERMISIM/
│
├── .github/
│   └── workflows/
│       └── ci.yml
├── gui/
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
├── physics_engine/
│   ├── engine.py
│   ├── simulation.py
│   ├── sensor.py
├── tests/
│   ├── test_file_loader.py
│   ├── test_physics_engine.py
│   ├── test_sensor.py
│   └── test_simulation.py
├── Dockerfile
├── main.py
├── README.md
├── requirements.txt
└── simulation.log (generated at runtime)
```

## Installation and Usage

### Prerequisites

-   Python 3.9+
-   pip (Python package installer)
-   Git
-   Docker (for containerized deployment)

### Local Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/LoQiseaking69/HermiSim-DynamicsViewer.git
    cd HermiSim-DynamicsViewer
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application**:
    ```bash
    python main.py
    ```

### Running with Docker

1.  **Build the Docker image**:
    ```bash
    docker build -t hermisim-dynamicsviewer .
    ```

2.  **Run the Docker container**:
    ```bash
    docker run -it --rm --name hermisim-app hermisim-dynamicsviewer
    ```
    *Note: Running GUI applications directly in Docker can be complex due to X server forwarding. For development, local installation is recommended. For deployment, consider VNC or X11 forwarding solutions.* 

## Running Tests

To run the unit tests, navigate to the project root directory and execute:

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest
```

## Continuous Integration/Continuous Deployment (CI/CD)

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that automatically builds and tests the application on every push and pull request. It also builds a Docker image of the application.

## Components

#### `main.py`
-   **Entry Point**: Initializes the PyQt application, applies styles, sets up the main window, and configures logging.

#### GUI Components
-   **`styles.py`**: Defines and applies visual styles using PyQt.
-   **`main_window.py`**: Hosts the main window, integrates tabs, manages file loading, and orchestrates the simulation step with a QTimer.
-   **`file_loader.py`**: Loads and parses URDF/XML files for the simulation, with enhanced validation and error handling.
-   **`object_renderer.py`**: Renders robots and environments in a 3D space.
-   **`simulation_controls.py`**: Controls for starting, stopping, resetting simulations, and adjusting speed.
-   **`sensor_data_viewer.py`**: Displays real-time sensor data in a tabular format.

#### Tabs
-   **`render_tab.py`**: Visualization of robots and environments.
-   **`simulation_tab.py`**: Contains elements for controlling the simulation.
-   **`log_tab.py`**: Displays logs and debugging information.
-   **`sensor_tab.py`**: Manages and displays sensor-related data.

#### Physics Engine
-   **`engine.py`**: Manages connection to the PyBullet engine and handles simulation steps, with robust error handling and logging.
-   **`simulation.py`**: Controls simulation operations, including start, stop, reset, and sensor updates. Integrates with the `PhysicsEngine` and `Sensor` modules.
-   **`sensor.py`**: Simulates IMU, Lidar, and Camera sensors, providing realistic data with enhanced error handling and more detailed simulation parameters.

## Enhancements and Hardening

This version of the HermiSim-DynamicsViewer includes several key enhancements to improve its robustness, maintainability, and production readiness:

-   **Centralized Logging**: Implemented a robust logging configuration in `main.py` using `logging.handlers.RotatingFileHandler` for efficient log management and `StreamHandler` for console output. This ensures that all critical application events, errors, and warnings are captured and stored, aiding in debugging and monitoring.
-   **Input Validation and Error Handling**: The `file_loader.py` module has been significantly improved with explicit checks for file existence and supported file types (`.urdf`, `.xml`). Custom exceptions (`FileNotFoundError`, `ValueError`, `RuntimeError`) are raised for invalid inputs, providing clearer feedback and preventing unexpected application behavior. The XML parsing logic now correctly resolves relative URDF paths.
-   **Resource Management in Physics Engine**: The `physics_engine/engine.py` now includes more comprehensive error handling for PyBullet connection and operations. It logs warnings for operations attempted when the physics client is not connected, preventing silent failures.
-   **Decoupled Simulation Loop**: The `physics_engine/simulation.py` module has been refactored to remove the blocking `while` loop from its `start` method. Instead, a `step` method is introduced, allowing the simulation to advance one step at a time. This change enables better integration with event-driven GUI frameworks like PyQt, where the simulation can be stepped periodically by a `QTimer` without freezing the UI.
-   **Enhanced Sensor Simulation**: The `physics_engine/sensor.py` module now includes more realistic simulation parameters for Lidar and Camera sensors, such as `lidar_range`, `lidar_num_rays`, `camera_width`, `camera_height`, `camera_fov`, etc. Error handling for PyBullet sensor data retrieval has also been added.
-   **Unit Testing**: A dedicated `tests/` directory has been created with unit tests for `file_loader.py`, `physics_engine/engine.py`, `physics_engine/simulation.py`, and `physics_engine/sensor.py`. These tests use `pytest` and `unittest.mock` to ensure the correctness and reliability of core functionalities, covering various success and failure scenarios.
-   **Containerization with Docker**: A `Dockerfile` is provided to containerize the application, ensuring consistent environments across different deployment targets and simplifying dependency management.
-   **Automated CI/CD**: A GitHub Actions workflow (`.github/workflows/ci.yml`) automates the build and test process, providing immediate feedback on code changes and ensuring that only passing builds are considered for deployment.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.
