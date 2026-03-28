# Thesis Project

This repository contains the main software components for a robotic system built around ROS 2, Docker, and several specialized services. It covers:

- sensor data acquisition
- communication with microcontrollers
- SLAM and map generation
- autonomous navigation
- AI image processing
- ROS 2 bag recording
- PostgreSQL-based storage
- visualization through rosbridge and Foxglove bridge

The operational `docker-compose` stack usually lives in the sibling directory `../stack/`, while this repository contains the images, scripts, and application logic.

## Main Components

| Component | Purpose | Key inputs / outputs |
| --- | --- | --- |
| `bridge_cont` | Serial bridge to the robot microcontroller | Publishes `/imu/arduino`, `/wheel_odom`, `/robot_status`; subscribes to `/cmd_vel` |
| `laser_driver_cont` | ROS 2 driver for RPLidar | Publishes `/scan` |
| `realsense_cont` | Intel RealSense ROS 2 driver | Publishes RGB, depth, camera info, and point cloud topics |
| `slam_cont` | `slam_toolbox`, mapping, map save/export, database insertion | Uses `/scan`, `/tf`, `/odom`, `/imu`; publishes `/map` |
| `nav_cont` | Nav2, goal forwarding, and `cmd_vel` multiplexing | Accepts `/move_base_simple/goal`; publishes `/cmd_vel_auto` and anomaly topics |
| `bag_recorder_cont` | Continuous ROS 2 bag recording | Records topics from `TOPICS_FILE` into `BAG_OUTPUT_DIR` |
| `db_cont` | PostgreSQL/PostGIS database | Stores maps, images, waypoints, and sessions |
| `rosbridge_cont` | ROS 2 to WebSocket bridge for web clients | Typically exposes port `9090` |
| `foxglove_bridge_cont` | ROS 2 bridge for Foxglove Studio | Typically exposes port `8765` |
| `ai_kit_cont` | Hailo AI image processing or passthrough overlay publishing | Consumes RealSense images and publishes AI overlay topics |
| `sensor_fusion_cont` | ROS 2 package for IMU ingest and filtering | By default filters RealSense IMU into `/imu/data`; in Arduino mode it publishes `imu/data_raw`, `imu/raw_line`, and `/diagnostics` |
| `camera_cont` | UDP video input and ROS 2 publication | Publishes `/camera/image_raw/compressed` and `/camera/camera_info` |
| `healthcheck_cont` | Validates containers, ports, devices, and the ROS graph | Writes a health report to logs |

## Architecture Overview

```text
Lidar --------> laser_driver_cont ----\
                                       \
RealSense ----> realsense_cont ---------> slam_cont ------> /map
                                         /       \
Microcontroller -> bridge_cont ---------/         \--> db_cont
            |               ^                      \--> bag_recorder_cont
            |               |
            +----- /cmd_vel-+

nav_cont <----- /map, /tf, /odom, /scan
   |
   +--> /cmd_vel_auto --> cmd_vel_mux --> /cmd_vel --> bridge_cont

rosbridge_cont / foxglove_bridge_cont --> RViz / Foxglove / web clients
ai_kit_cont <----- RealSense images -----> AI overlay topics
```

## Typical Workflows

### Starting the system

The usual sequence is:

1. Build or pull the images from this repository.
2. Start the runtime stack from `../stack/`.
3. Verify that at least `bridge_cont`, `laser_driver_cont`, and `slam_cont` are running.
4. Add `realsense_cont`, `nav_cont`, `db_cont`, `ai_kit_cont`, and the other services as needed.

Healthcheck example:

```bash
docker exec -it healthcheck_cont /usr/local/bin/healthcheck.py
```

### Mapping

The main operational mapping script is `slam_cont/run_mapping.sh`. It:

- starts or reuses `slam_toolbox`
- starts `ros2 bag record`
- publishes the live map on `/map` while mapping
- saves the live map on `Ctrl+C`
- attempts occupancy export when mapping ends
- can insert the final result into the database

Example:

```bash
docker exec -it slam_cont bash
bash /app/run_mapping.sh --name mapa1
```

Useful topics to monitor during mapping:

- `/map`
- `/scan`
- `/tf`
- `/odom`

Note: `/map` can exist before the map is saved to disk. That is the live in-memory map. Files are only generated during the save/export step.

### Navigation

`nav_cont/start_nav.sh` starts:

- Nav2 bringup
- `goal_forwarder.py`
- `cmd_vel_mux.py`
- optional joystick and teleop support

If no real map is configured, the script can generate a placeholder map so the services still come up. Real navigation still requires a real `map.yaml`.

### AI image processing

`ai_kit_cont` is designed for the Raspberry Pi AI Kit with a Hailo accelerator:

- the Hailo runtime is expected on the host, not baked into the image
- the container waits for the RealSense image topic before starting the node
- without `HAILO_GST_PIPELINE` it runs in passthrough mode
- with a configured pipeline it publishes AI overlay topics

### Bag recording

If you want to record topics independently:

```bash
docker exec -it bag_recorder_cont /app/bag_recorder.sh
```

In practice, `TOPICS_FILE` is often mounted from `../stack/config/recorded_topics.yaml`.

## Most Important ROS Topics and Services

Topics:

- `/scan`
- `/tf`
- `/tf_static`
- `/odom`
- `/map`
- `/cmd_vel`
- `/cmd_vel_auto`
- `/cmd_vel_joy`
- `/move_base_simple/goal`
- `/navigation/anomaly_on_path`
- `/ai_kit/image_overlay/compressed`

Services and actions:

- `/slam_toolbox/save_map`
- `/set_manual_mode`
- `navigate_to_pose`

## Database

`db_cont/init-db.sql` initializes the `robot_data` schema and the main tables:

- `robot_data.maps`
- `robot_data.camera_images`
- `robot_data.waypoints`
- `robot_data.robot_sessions`

In practice, the most important integration is that `slam_cont` can store the final map and metadata in `robot_data.maps` after mapping.

## Prerequisites

The project typically assumes:

- ROS 2 Humble for most containers
- Docker and Docker Compose
- a lidar and/or camera connected to the host
- a serial device for the robot microcontroller
- access to devices such as `/dev/ttyUSB0`, `/dev/ttyACM0`, and `/dev/bus/usb`

Additional requirements for `ai_kit_cont`:

- an arm64 host
- Hailo runtime installed on the host
- bind-mounted Hailo libraries inside the container

## Additional Documentation

For more technical detail, see:

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
- [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md)
- [HARDWARE_SETUP_CUSTOM_PROTOCOL.md](./HARDWARE_SETUP_CUSTOM_PROTOCOL.md)
- [bridge_cont/README.md](./bridge_cont/README.md)
- [nav_cont/README.md](./nav_cont/README.md)
- [db_cont/README.md](./db_cont/README.md)
