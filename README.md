# HermiSim — Dynamics Viewer

![img](https://github.com/LoQiseaking69/HermiSim-DynamicsViewer/blob/main/IMG_1637.png)
___

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Directory Structure](#directory-structure)
5. [Installation and Usage](#installation-and-usage)
6. [Components](#components)
    - [main.py](#mainpy)
    - [GUI Components](#gui-components)
    - [Tabs](#tabs)
    - [Physics Engine](#physics-engine)
7. [Model Builder](#model-builder)
8. [Keyboard Shortcuts](#keyboard-shortcuts)
9. [Additional Notes](#additional-notes)
___
![hsl](https://github.com/LoQiseaking69/HermiSim-DynamicsViewer/blob/main/HSlogo.jpg)
___

## Overview

HermiSim is an institutional-grade robotics simulation suite powered by **MuJoCo** (Multi-Joint dynamics with Contact) — the physics engine used by DeepMind, OpenAI, and leading robotics research labs worldwide. The application provides a **PySide6** (LGPL-licensed Qt for Python) interface for loading MJCF/URDF models, building models from scratch, running physics simulations, and visualizing results in real time.

## Features

- **MuJoCo Physics Engine**: High-fidelity contact dynamics, fast simulation, and accurate rigid-body physics via MuJoCo 3.x
- **MJCF & URDF Support**: Load MuJoCo native XML (MJCF) and URDF robot description files
- **High-Quality 3D Rendering**: MuJoCo's built-in offscreen renderer with camera selection
- **Real-Time Sensor Data**: Live display of all model-defined sensors (accelerometers, gyroscopes, force/torque, etc.)
- **Thread-Safe Simulation Loop**: Physics stepping on a dedicated `QThread` — GUI never blocks
- **State-Aware Controls**: Start, pause, stop, reset, single-step with automatic button state management
- **Configurable Playback**: Variable speed (0.01x – 2.0x real-time) and adjustable timestep
- **Step-by-Step Model Builder**: 6-step wizard for creating MJCF models from scratch — world, bodies, joints, actuators, sensors, and live XML preview with direct simulation loading
- **Structured Logging**: Full Python `logging` integration with level filtering and in-app log viewer
- **Signal-Driven Architecture**: Qt signal/slot communication between engine and UI — no polling
- **Type-Safe Codebase**: Full type annotations throughout all modules
- **Proper Error Handling**: Custom exception hierarchy with clear error propagation
- **Resource Lifecycle Management**: Clean startup/shutdown with proper cleanup on exit
- **Refined Dark Theme**: GitHub-inspired dark palette with violet accents, rounded borders, custom scrollbars, and full widget styling
- **Commercially Friendly**: PySide6 (LGPL) + MuJoCo (Apache 2.0) — no license fees for commercial distribution

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    MainWindow                        │
│  ┌─────────┬─────────┬─────────┬────────────┬────────┐│
│  │RenderTab│ SimTab  │SensorTab│ModelBuilder │LogTab  ││
│  │         │         │         │  (wizard)   │        ││
│  │ObjRender│SimCtrls │SensView │ 6-step MJCF│QtLogHnd││
│  └───┬─────┴───┬─────┴───┬─────┴──────┬─────┴────────┘│
│       │          │          │                        │
│       └──────────┼──────────┘                        │
│            Qt Signals                                │
│       ┌──────────┴──────────┐                        │
│       │    Simulation       │◄── QThread worker      │
│       │  (state machine)    │                        │
│       └──────────┬──────────┘                        │
│       ┌──────────┴──────────┐                        │
│       │   PhysicsEngine     │◄── Thread-safe (RLock) │
│       │   (MuJoCo wrapper)  │                        │
│       └─────────────────────┘                        │
└─────────────────────────────────────────────────────┘
```

## Directory Structure

```
HermiSim-DynamicsViewer/
├── main.py                         # Application entry point
├── requirements.txt                # Pinned dependencies
├── README.md
├── LICENSE
├── gui/
│   ├── __init__.py
│   ├── styles.py                   # Dark theme palette & stylesheet
│   ├── main_window.py              # Top-level window, menus, status bar
│   ├── file_loader.py              # MJCF/URDF file loading
│   ├── object_renderer.py          # MuJoCo offscreen render → QLabel
│   ├── sensor_data_viewer.py       # Signal-driven sensor data table
│   ├── simulation_controls.py      # Transport & speed controls
│   └── tabs/
│       ├── __init__.py
│       ├── render_tab.py           # 3D visualization + camera selector
│       ├── simulation_tab.py       # Simulation control panel
│       ├── sensor_tab.py           # Live sensor readings
│       ├── model_builder_tab.py    # Step-by-step MJCF model builder
│       └── log_tab.py              # Log viewer with level filtering
└── physics_engine/
    ├── __init__.py
    ├── exceptions.py               # Custom exception hierarchy
    ├── engine.py                   # MuJoCo wrapper (model, step, render)
    ├── simulation.py               # State machine + QThread worker
    └── sensor.py                   # Sensor manager with history tracking
```

## Installation and Usage

1. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2. **Run the application**:
    ```bash
    python main.py
    ```

3. **Load a model**: Use `File → Load Model` (or `Ctrl+O`) to open an MJCF XML or URDF file.

4. **Run the simulation**: Use the Simulation tab controls or the keyboard shortcuts below.

## Components

#### `main.py`
- Application entry point with structured logging configuration.

#### GUI Components
- **`styles.py`**: Dark theme palette and comprehensive Qt stylesheet.
- **`main_window.py`**: Top-level window with tabbed interface, menus (File, Simulation, Help), and status bar.
- **`file_loader.py`**: Validates and loads MJCF/URDF model files into the simulation.
- **`object_renderer.py`**: Converts MuJoCo offscreen-rendered frames to `QPixmap` for display.
- **`simulation_controls.py`**: State-aware transport buttons (Start/Pause/Stop/Reset/Step), speed slider, and timestep control.
- **`sensor_data_viewer.py`**: Signal-driven table that updates automatically from simulation sensor data.

#### Tabs
- **`render_tab.py`**: 3D visualization with model-defined camera selection.
- **`simulation_tab.py`**: Embeds the simulation control panel.
- **`sensor_tab.py`**: Live sensor data table with dimension and value columns.
- **`model_builder_tab.py`**: 6-step wizard for MJCF model creation with live XML preview, syntax highlighting, and direct simulation loading.
- **`log_tab.py`**: Real-time log viewer with a Python `logging.Handler` bridge and level-based filtering.

#### Physics Engine
- **`engine.py`**: Thread-safe MuJoCo wrapper — model loading, physics stepping, offscreen rendering, body/joint queries, sensor data access, and force application.
- **`simulation.py`**: Simulation lifecycle controller with `QThread`-based worker. Manages states: `IDLE → RUNNING ↔ PAUSED → IDLE`. Emits signals for time, sensor data, rendered frames, and state changes.
- **`sensor.py`**: `SensorManager` class providing named sensor lookups, rolling history tracking, and metadata queries over MuJoCo's sensor system.
- **`exceptions.py`**: Custom exception hierarchy (`PhysicsEngineError`, `EngineNotInitializedError`, `ModelLoadError`, `SimulationStateError`, `SensorError`).

## Model Builder

The **Model Builder** tab provides a guided, step-by-step workflow for creating MuJoCo MJCF models without writing XML by hand:

| Step | Name | Description |
|------|------|-------------|
| 1 | **World** | Model name, timestep, gravity vector, integrator, ground plane toggle |
| 2 | **Bodies** | Add/update/remove rigid bodies with position, orientation, mass, geometry type/size/color, and parent hierarchy |
| 3 | **Joints** | Attach hinge, slide, ball, or free joints to bodies with axis, range, and damping |
| 4 | **Actuators** | Define motor, position, velocity, or general actuators linked to joints |
| 5 | **Sensors** | Configure joint-level and body-level sensors (position, velocity, force, accelerometer, gyro, etc.) |
| 6 | **Preview** | Live syntax-highlighted XML preview — edit directly, **Load into Simulation**, or **Save as File** |

Navigation is via the sidebar step list or Back/Next buttons. A **Reset All** button clears the model to start fresh.

## Keyboard Shortcuts

| Shortcut | Action         |
|----------|----------------|
| Ctrl+O   | Load model     |
| Ctrl+Q   | Quit           |
| F5       | Start          |
| F6       | Pause          |
| F7       | Stop           |
| F8       | Reset          |

## Additional Notes

- Requires **MuJoCo ≥ 3.0** and **PySide6 ≥ 6.5**.
- **PySide6** is the official Qt for Python binding (LGPL v2.1) — free for commercial use without a separate license.
- **MuJoCo** is open-source (Apache 2.0) and installs via `pip install mujoco`.
- The application is modular — new tabs, sensors, and rendering modes can be added with minimal changes.
- All physics engine operations are thread-safe through a reentrant lock.

