# Thesis Project

This repository contains the main software components for a robotic system built
around ROS 2, Docker, and several specialized services.

It covers:

- sensor data acquisition
- communication with the robot microcontroller
- SLAM and map generation
- autonomous navigation
- AI image processing
- ROS 2 bag recording
- PostgreSQL-based storage
- visualization through rosbridge and Foxglove bridge

The operational `docker-compose` stack usually lives in the sibling directory
`../stack/`, while this repository contains the images, scripts, firmware, and
documentation.

## Current Hardware Architecture

The currently supported robot controller architecture is:

```text
Raspberry Pi -> USB -> Nano ESP32 -> DRV8833 -> motors
                           |
                           \-> TCA9548A -> AS5600 LEFT / RIGHT
```

Notes:

- `UNO R4` is no longer part of the main implementation
- `DRV8833` is the current motor driver
- `robot_bridge` typically uses `/dev/ttyACM0`

## Main Components

| Component | Purpose | Key inputs / outputs |
| --- | --- | --- |
| `bridge_cont` | Serial bridge to the Nano ESP32 | Publishes `/imu/arduino`, `/wheel_odom`, `/robot_status`; subscribes to `/cmd_vel` |
| `laser_driver_cont` | ROS 2 driver for RPLidar | Publishes `/scan` |
| `realsense_cont` | Intel RealSense ROS 2 driver | Publishes RGB, depth, camera info, and IMU topics |
| `slam_cont` | `slam_toolbox`, mapping, map save/export, database insertion | Uses `/scan`, `/tf`, odometry, and IMU; publishes `/map` |
| `nav_cont` | Nav2, goal forwarding, and `cmd_vel` multiplexing | Accepts `/move_base_simple/goal`; publishes `/cmd_vel_auto` and final `/cmd_vel` |
| `bag_recorder_cont` | Continuous ROS 2 bag recording | Records topics from `TOPICS_FILE` into `BAG_OUTPUT_DIR` |
| `db_cont` | PostgreSQL/PostGIS database | Stores maps, images, waypoints, and sessions |
| `rosbridge_cont` | ROS 2 to WebSocket bridge for web clients | Typically exposes port `9090` |
| `foxglove_bridge_cont` | ROS 2 bridge for Foxglove Studio | Typically exposes port `8765` |
| `ai_kit_cont` | Hailo AI processing or passthrough overlay publishing | Consumes RealSense images and publishes AI overlay topics |
| `sensor_fusion_cont` | IMU filtering | By default converts RealSense IMU into `/imu/data`; Arduino IMU remains a debug or fallback stream |
| `healthcheck_cont` | Validates containers, ports, devices, and the ROS graph | Writes a health report to logs |

## Architecture Overview

```text
Lidar --------> laser_driver_cont ----\
                                       \
RealSense ----> realsense_cont ---------> sensor_fusion_cont --> /imu/data
                                         \
Microcontroller -> bridge_cont -----------> /wheel_odom, /imu/arduino, /robot_status
            ^               |
            |               +<------------------------------ /cmd_vel
            |
            +-- Nano ESP32 -> DRV8833 -> motors

nav_cont <----- /map, /tf, odometry, /scan
   |
   +--> /cmd_vel_auto --> cmd_vel_mux --> /cmd_vel --> bridge_cont

slam_cont <----- /scan, /tf, odometry, /imu/data
```

## Typical Workflows

### Starting the system

The usual sequence is:

1. Build or pull the images from this repository.
2. Start the runtime stack from `../stack/`.
3. Verify that at least `bridge_cont`, `laser_driver_cont`, and `slam_cont` are running.
4. Verify that the Nano is visible as `/dev/ttyACM0`.

Healthcheck example:

```bash
docker exec -it healthcheck_cont /usr/local/bin/healthcheck.py
```

### Mapping

The main operational mapping script is `slam_cont/run_mapping.sh`.

Useful topics to monitor during mapping:

- `/map`
- `/scan`
- `/tf`
- `/wheel_odom`
- `/imu/data`

Note:

- the bridge currently publishes `/wheel_odom`
- some older configs and scripts still use `/odom` as a legacy name

### Navigation

`nav_cont/start_nav.sh` starts:

- Nav2 bringup
- `goal_forwarder.py`
- `cmd_vel_mux.py`
- optional joystick and teleop support

### AI image processing

`ai_kit_cont` is designed for the Raspberry Pi AI Kit with a Hailo accelerator:

- the Hailo runtime is expected on the host
- without `HAILO_GST_PIPELINE` it runs in passthrough mode
- with a configured pipeline it publishes AI overlay topics

### Bag recording

If you want to record topics independently:

```bash
docker exec -it bag_recorder_cont /app/bag_recorder.sh
```

## Most Important ROS Topics and Services

Topics:

- `/scan`
- `/tf`
- `/tf_static`
- `/wheel_odom`
- `/imu/data`
- `/imu/arduino`
- `/map`
- `/cmd_vel`
- `/cmd_vel_auto`
- `/cmd_vel_joy`

Services and actions:

- `/slam_toolbox/save_map`
- `navigate_to_pose`

## Prerequisites

The project typically assumes:

- ROS 2 Humble for most containers
- Docker and Docker Compose
- lidar and/or camera connected to the host
- Nano ESP32 connected as a serial device
- access to devices such as `/dev/ttyUSB0`, `/dev/ttyACM0`, and `/dev/bus/usb`

Additional requirements for `ai_kit_cont`:

- an arm64 host
- Hailo runtime installed on the host
- bind-mounted Hailo libraries inside the container

## Additional Documentation

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
- [COMMUNICATION_ANALYSIS.md](./COMMUNICATION_ANALYSIS.md)
- [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md)
- [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md)
- [HARDWARE_SETUP_CUSTOM_PROTOCOL.md](./HARDWARE_SETUP_CUSTOM_PROTOCOL.md)
- [bridge_cont/README.md](./bridge_cont/README.md)
- [nav_cont/README.md](./nav_cont/README.md)
- [db_cont/README.md](./db_cont/README.md)
