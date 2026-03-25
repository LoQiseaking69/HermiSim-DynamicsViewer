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

This Robotics Simulation Suite is a sophisticated application designed for loading MJCF/URDF model files, rendering objects in a 3D space, and running robotic simulations powered by MuJoCo. The application provides multiple tabs and functionalities for a comprehensive simulation environment, with a focus on robustness, maintainability, and production-grade quality.

## Features

-   **Load MJCF/URDF Models**: Load `.xml`, `.mjcf`, and `.urdf` model files for simulation.
-   **Interactive 3D Rendering**: Visualise models in an interactive viewport with orbit, pan, and zoom camera controls (MuJoCo offscreen renderer + PySide6).
-   **Physics Engine**: Leverage MuJoCo for realistic rigid-body dynamics.
-   **Bundled Starter Model**: Ships with a complete bipedal robot (`models/starter_model.xml`) loaded automatically on first launch.
-   **Session Persistence**: Remembers the last-loaded model **and** its simulation state (joint positions, velocities, controls, time) across sessions.
-   **Model Builder**: Visual wizard for composing MJCF models from scratch (bodies, joints, actuators, sensors, cameras).
-   **Sensor Data**: Real-time display of joint, actuator, and contact sensor readings.
-   **Simulation Controls**: Start, pause, stop, reset, single-step, and adjustable playback speed / timestep.
-   **Logs and Debugging**: Rotating file + console logging with a dedicated Logs tab.
-   **Modular Design**: Clean separation of GUI, physics engine, and file I/O layers.
-   **Comprehensive Testing**: Unit tests for core modules.
-   **Containerization**: Docker support for reproducible environments.
-   **CI/CD Pipeline**: GitHub Actions for automated builds and tests.

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
│   │   └── model_builder_tab.py
├── models/
│   └── starter_model.xml
├── physics_engine/
│   ├── engine.py
│   ├── simulation.py
│   ├── sensor.py
│   └── exceptions.py
├── tests/
│   ├── test_file_loader.py
│   ├── test_physics_engine.py
│   ├── test_sensor.py
│   └── test_simulation.py
├── .state/                (generated — persisted simulation state)
├── Dockerfile
├── main.py
├── README.md
├── requirements.txt
└── hermisim.log           (generated at runtime)
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
-   **Entry Point**: Applies a MuJoCo Windows DLL workaround, configures rotating-file + console logging, and launches the main window.

#### GUI Components
-   **`styles.py`**: Defines and applies visual styles using PySide6.
-   **`main_window.py`**: Hosts the main window, integrates tabs, manages file loading, auto-loads the last (or default) model on startup, and persists simulation state on exit.
-   **`file_loader.py`**: Validates and loads MJCF/URDF files into the simulation. Tracks the last-loaded model path via `QSettings` and saves/restores simulation state snapshots to disk.
-   **`object_renderer.py`**: Interactive 3D viewport — renders the scene via MuJoCo's offscreen renderer and supports orbit, pan, and zoom with mouse controls.
-   **`simulation_controls.py`**: Transport buttons (start/pause/stop/reset/step), playback speed slider, and timestep editor.
-   **`sensor_data_viewer.py`**: Displays real-time sensor data in a tabular format.

#### Tabs
-   **`render_tab.py`**: Interactive 3D viewport with camera selection dropdown.
-   **`simulation_tab.py`**: Contains simulation transport and speed controls.
-   **`log_tab.py`**: Displays logs and debugging information.
-   **`sensor_tab.py`**: Manages and displays sensor-related data.
-   **`model_builder_tab.py`**: Multi-page wizard for composing MJCF models (bodies, joints, actuators, sensors, cameras) and previewing/exporting the generated XML.

#### Models
-   **`starter_model.xml`**: Bundled bipedal robot with 2-DOF hips, knees, ankles, 8 actuators, and 32 sensors (joint pos/vel, actuator forces, contact, IMU).

#### Physics Engine
-   **`engine.py`**: Thread-safe MuJoCo wrapper providing model loading, stepping, rendering (with interactive `MjvCamera` support), state snapshot/restore, body/joint/sensor queries, and force application.
-   **`simulation.py`**: Qt-based state machine (idle/running/paused/error) managing a background worker thread for real-time physics stepping, with signals for state changes, sensor data, and rendered frames.
-   **`sensor.py`**: Sensor simulation utilities.
-   **`exceptions.py`**: Custom exception types (`ModelLoadError`, `EngineNotInitializedError`).

## Enhancements and Hardening

This version includes several key improvements:

-   **MuJoCo Backend**: Migrated from PyBullet to MuJoCo for higher-fidelity rigid-body dynamics and native MJCF support.
-   **PySide6 UI**: Modern Qt 6 interface with dark theme, tab-based layout, and interactive 3D viewport.
-   **Interactive Camera Controls**: Orbit (left-drag), pan (middle-drag / Shift+left), and zoom (scroll / right-drag) directly in the Render tab.
-   **Bundled Bipedal Robot**: A complete starter model (`models/starter_model.xml`) with torso, legs, actuators, and 32 sensors — loaded automatically on first launch.
-   **Session Persistence**: The last-loaded model path is saved via `QSettings`, and the full simulation state (qpos, qvel, ctrl, time) is serialised to `.state/last_state.npz` on exit and restored on next launch.
-   **Model Builder Wizard**: Multi-page GUI for composing MJCF models without hand-editing XML.
-   **Centralized Logging**: Rotating file handler (5 MB, 3 backups) + console output with timestamped format.
-   **Thread-Safe Engine**: All `PhysicsEngine` methods are guarded by a reentrant lock; simulation runs on a dedicated `QThread`.
-   **Unit Testing**: `pytest` + `unittest.mock` tests for file loading, engine, simulation, and sensors.
-   **Containerization**: Dockerfile for reproducible builds.
-   **CI/CD**: GitHub Actions workflow for automated testing on push/PR.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.
