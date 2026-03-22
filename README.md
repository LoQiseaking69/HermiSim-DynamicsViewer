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
6.  [Components](#components)
    -   [`main.py`](#mainpy)
    -   [GUI Components](#gui-components)
    -   [Tabs](#tabs)
    -   [Physics Engine](#physics-engine)
7.  [Enhancements and Hardening](#enhancements-and-hardening)
8.  [License](#license)

## Overview

HermiSim-DynamicsViewer is a robotics simulation suite built with **MuJoCo** and **PySide6**. It supports loading MJCF/URDF/XML model files, rendering scenes in 3D, and running physics-based simulations in a non-blocking threaded architecture. The application provides a multi-tab GUI for real-time simulation control, sensor data visualization, log inspection, and an interactive MJCF model builder. This suite focuses on robustness, maintainability, and production-grade quality.

## Features

-   **Load MJCF/URDF/XML Models**: Load and parse MuJoCo-compatible model files (`.xml`, `.mjcf`, `.urdf`).
-   **3D Rendering**: Visualize robots and environments in 3D using MuJoCo's built-in renderer via PySide6.
-   **MuJoCo Physics Engine**: Leverage MuJoCo for high-fidelity physics simulations with thread-safe lifecycle management.
-   **Threaded Simulation Loop**: Physics stepping runs on a dedicated `QThread` so the GUI always stays responsive.
-   **Sensor Data**: Read and display data from any sensors defined in the loaded MJCF model, with rolling history tracking.
-   **Simulation Controls**: Start, pause, stop, reset simulations, perform single-step advances, and control playback speed.
-   **MJCF Model Builder**: Interactively construct MJCF models step-by-step with a live XML preview and syntax highlighting.
-   **Logs and Debugging**: View application logs in a dedicated tab; logs are also written to `hermisim.log`.
-   **Modular Design**: The application is modular, allowing easy extension and maintenance.
-   **Robust Error Handling**: Custom exception hierarchy and comprehensive error handling across all modules.
-   **Comprehensive Testing**: Unit tests for core functionalities using `pytest`.
-   **Containerization**: Docker support for easy deployment and environment consistency.

## Directory Structure

```
HermiSim-DynamicsViewer/
│
├── gui/
│   ├── styles.py
│   ├── main_window.py
│   ├── file_loader.py
│   ├── object_renderer.py
│   ├── simulation_controls.py
│   ├── sensor_data_viewer.py
│   └── tabs/
│       ├── render_tab.py
│       ├── simulation_tab.py
│       ├── log_tab.py
│       ├── sensor_tab.py
│       └── model_builder_tab.py
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
├── Dockerfile
├── main.py
├── README.md
├── requirements.txt
└── hermisim.log (generated at runtime)
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
    *Note: Running GUI applications directly in Docker requires X server forwarding. For development, local installation is recommended. For deployment, consider VNC or X11 forwarding solutions.*

## Running Tests

To run the unit tests, navigate to the project root directory and execute:

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest
```

## Components

#### `main.py`
-   **Entry Point**: Applies a MuJoCo Windows DLL workaround, configures rotating-file and console logging, initializes the PySide6 application, applies styles, and launches the main window.

#### GUI Components
-   **`styles.py`**: Defines and applies visual styles using PySide6.
-   **`main_window.py`**: Hosts the main window, integrates all tabs, manages file loading, and orchestrates the simulation lifecycle.
-   **`file_loader.py`**: Loads and validates MJCF/URDF/XML model files with explicit file-existence and format checks.
-   **`object_renderer.py`**: Renders MuJoCo scenes in a 3D viewport within the GUI.
-   **`simulation_controls.py`**: Controls for starting, pausing, stopping, resetting simulations, and adjusting playback speed.
-   **`sensor_data_viewer.py`**: Displays real-time sensor data in a tabular format.

#### Tabs
-   **`render_tab.py`**: Visualization of robots and environments using the MuJoCo renderer.
-   **`simulation_tab.py`**: Contains elements for controlling the simulation (start, pause, stop, reset, speed).
-   **`log_tab.py`**: Displays application logs and debugging information.
-   **`sensor_tab.py`**: Manages and visualizes sensor data from the loaded model.
-   **`model_builder_tab.py`**: Step-by-step MJCF model builder with a live XML preview pane and syntax highlighting.

#### Physics Engine
-   **`engine.py`**: Thread-safe MuJoCo wrapper providing model loading (from path or XML string), simulation stepping, rendering (RGB and depth), body/joint queries, actuator control, force application, and sensor data access.
-   **`simulation.py`**: High-level simulation controller. Manages the `PhysicsEngine` lifecycle and delegates continuous physics stepping to a background `_SimulationWorker` on a dedicated `QThread`. Communicates state changes, sensor updates, and rendered frames to the GUI via Qt signals.
-   **`sensor.py`**: `SensorManager` class that reads MuJoCo's built-in sensor system, maintains per-sensor rolling history, and provides named access and metadata queries.
-   **`exceptions.py`**: Custom exception hierarchy (`PhysicsEngineError`, `EngineNotInitializedError`, `ModelLoadError`, `SimulationStateError`, `SensorError`) for structured error handling throughout the engine.

## Enhancements and Hardening

-   **MuJoCo Integration**: Replaced PyBullet with MuJoCo (`mujoco>=3.0`) as the physics backend, providing higher-fidelity simulation, built-in sensor support, and a unified rendering pipeline.
-   **PySide6 UI Framework**: Migrated from PyQt to PySide6 (`PySide6>=6.5`) for an actively maintained Qt binding with an LGPL-compatible license.
-   **Threaded Physics Loop**: The `physics_engine/simulation.py` module uses a dedicated `QThread` and `_SimulationWorker` for non-blocking simulation. This replaces the earlier `QTimer`-based approach, providing smoother real-time stepping and accurate speed-multiplier control.
-   **Custom Exception Hierarchy**: `physics_engine/exceptions.py` defines a structured set of exceptions (`PhysicsEngineError` and subclasses) that replace generic Python built-ins, enabling precise error handling and cleaner user-facing messages throughout the codebase.
-   **MJCF Model Builder**: A new `model_builder_tab.py` allows users to construct MJCF models interactively within the application, with a live XML preview pane featuring syntax highlighting, reducing the need for an external editor.
-   **Sensor History Tracking**: `SensorManager` in `physics_engine/sensor.py` maintains a configurable rolling deque of historical readings per sensor, enabling trend visualization and post-hoc analysis without external data stores.
-   **Centralized Logging**: `main.py` configures a root logger with a `RotatingFileHandler` (writing to `hermisim.log`, max 5 MB, 3 backups) and a `StreamHandler` for console output, capturing all application events across modules.
-   **Input Validation**: `file_loader.py` and `engine.py` perform explicit checks for file existence and supported formats (`.xml`, `.mjcf`, `.urdf`), raising descriptive custom exceptions on invalid input.
-   **Unit Testing**: `tests/` contains `pytest`-based unit tests for `file_loader.py`, `physics_engine/engine.py`, `physics_engine/simulation.py`, and `physics_engine/sensor.py`, covering success and failure scenarios with `unittest.mock`.
-   **Containerization**: A `Dockerfile` containerizes the application using `python:3.9-slim-buster`, ensuring reproducible environments across development and deployment targets.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.
