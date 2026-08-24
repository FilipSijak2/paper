# ROS 2 Thesis Robot

This repository contains the container source code and tests for the Raspberry Pi side of a ROS 2 mobile robot. Runtime orchestration and configuration live in the separate `robot-stack` repository. Jetson anomaly detection lives in the separate `jetson-stack` repository.

## Active architecture

```text
Raspberry Pi 5
├── DRV8833 motor control through GPIO
├── RPLidar, RealSense, SLAM, AMCL and Nav2
├── rosbridge WebSocket on port 9090
└── Foxglove bridge on port 8765

Jetson Orin
└── YOLO anomaly detection through rosbridge
```

The active motor path is `rpi_direct`. Wheel encoders, the TCA9548A multiplexer and Arduino serial motor control are not part of the deployed configuration.

## Containers

| Directory | Active responsibility |
| --- | --- |
| `bridge_cont` | Direct Raspberry Pi GPIO motor control through DRV8833 |
| `laser_driver_cont` | RPLidar ROS 2 driver |
| `realsense_cont` | RealSense RGB, depth and IMU streams |
| `slam_cont` | Mapping, map persistence and laser odometry fallback |
| `nav_cont` | Nav2, AMCL, command multiplexing and safety filtering |
| `sensor_fusion_cont` | IMU correction and robot localization |
| `rosbridge_cont` | ROS topic access for the Jetson client |
| `foxglove_bridge_cont` | Foxglove visualization endpoint |
| `bag_recorder_cont` | MCAP experiment recording |
| `db_cont` | PostgreSQL/PostGIS storage |
| `healthcheck_cont` | Runtime and ROS graph health checks |

`ai_kit_cont` and `camera_cont` remain source components but are not part of the documented anomaly-detection path.

## Runtime configuration

Do not configure this repository directly for deployment. Use the files mounted by `robot-stack/docker-compose.yaml`, especially:

- `config/containers/bridge_rpi_direct.env`
- `config/containers/nav_cont.env`
- `config/containers/slam_cont.env`
- `config/containers/realsense_cont.env`
- `config/containers/sensor_fusion_cont.env`
- `config/containers/nav2_params.yaml`

The active Jetson topic and inference configuration is stored in `jetson-stack/config`.

## Documentation

- [Active hardware](./HARDWARE_COMPONENTS.md)
- [Current wiring](./CURRENT_WIRING_DIAGRAM.md)
- [Jetson anomaly pipeline](./ANOMALY_ROSBRIDGE_PIPELINE.md)
- [Navigation container](./nav_cont/README.md)
- [Motor bridge](./bridge_cont/README.md)
- [Database container](./db_cont/README.md)

## Validation

```bash
python -m pip install -r tests/requirements-ci.txt
pytest -q tests
```

Shell syntax and Python compilation are also checked by GitHub Actions.
