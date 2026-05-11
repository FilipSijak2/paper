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

The currently active runtime architecture in `../stack/.env` is
`BRIDGE_MODE=rpi_direct`:

```text
Raspberry Pi -> GPIO -> DRV8833 -> motors
          |
          \-> I2C -> TCA9548A -> AS5600 LEFT / RIGHT (wired, currently ENCODERS_ENABLED=0)
```

Notes:

- `Nano ESP32` remains supported through `BRIDGE_MODE=serial_legacy`, but it
  is not the active motor/encoder path in the current stack
- `DRV8833` is the current motor driver
- `robot_bridge` in the active stack uses `/dev/i2c-1` and `/dev/gpiochip4`
- `ENCODERS_ENABLED=0`, so the bridge currently does not read AS5600 encoders;
  it uses open-loop `/wheel_odom`, while `slam_cont` starts rf2o odometry
- `UNO R4` is no longer part of the main implementation

## Main Components

| Component | Purpose | Key inputs / outputs |
| --- | --- | --- |
| `bridge_cont` | Robot bridge for motor/encoder control; active `rpi_direct`, supported `serial_legacy` | Publishes `/wheel_odom`, `/robot_status`; in serial mode also `/imu/arduino`; subscribes to `/cmd_vel` |
| `laser_driver_cont` | ROS 2 driver for RPLidar | Publishes `/scan` |
| `realsense_cont` | Intel RealSense ROS 2 driver | Publishes RGB, depth, camera info, and IMU topics |
| `slam_cont` | `slam_toolbox`, mapping, map save/export, database insertion | Uses `/scan`, `/tf`, odometry, and IMU; publishes `/map` |
| `nav_cont` | Nav2, goal forwarding, and `cmd_vel` multiplexing | Accepts `/move_base_simple/goal`; publishes `/cmd_vel_auto` and final `/cmd_vel` |
| `bag_recorder_cont` | Continuous ROS 2 bag recording | Records topics from `TOPICS_FILE` into `BAG_OUTPUT_DIR` |
| `db_cont` | PostgreSQL/PostGIS database | Stores maps, images, waypoints, and sessions |
| `rosbridge_cont` | ROS 2 to WebSocket bridge for web clients | Typically exposes port `9090` |
| `foxglove_bridge_cont` | ROS 2 bridge for Foxglove Studio | Typically exposes port `8765` |
| `ai_kit_cont` | Hailo AI processing or passthrough overlay publishing | Consumes RealSense images and publishes AI overlay topics |
| `sensor_fusion_cont` | IMU filtering | By default converts RealSense IMU into `/imu/data`; Arduino IMU is a debug/fallback stream only in serial legacy mode |
| `healthcheck_cont` | Validates containers, ports, devices, and the ROS graph | Writes a health report to logs |
| `container_log_collector_cont` | Docker log collection | Writes daily logs into `../stack/logs/<day>/<container>.log` |
| `bag_browser_cont` | Web browser for bags and logs | `filebrowser/filebrowser`, port `8080`, read-only `bags/` and `logs/` |
| `camera_cont` | Optional CSI/UDP camera publisher | Currently commented out in compose; RealSense is the main active camera path |

## Container Functionality

This section describes the runtime stack from `../stack/docker-compose.yaml`
and the images built from this repository. Most containers use
`network_mode: host`, `rmw_cyclonedds_cpp`, and the shared `CycloneDDS`
configuration from `../stack/config/cyclonedds.xml`, currently pinned to
`wlan0`.

### `robot_bridge_cont` / `bridge_cont`

The image is built from `bridge_cont/Dockerfile` on top of `ros:humble`.
It installs `python3-serial`, `python3-smbus2`, `python3-lgpio`,
`rpi-lgpio`, and `ros-humble-rmw-cyclonedds-cpp`.

Functionality:

- The Docker image default is `serial_legacy`, but the active runtime stack
  in `../stack/.env` uses `BRIDGE_MODE=rpi_direct`.
- In `rpi_direct` mode, `robot_rpi_direct_bridge.py` drives the `DRV8833`
  directly from Raspberry Pi GPIO PWM and reads `AS5600` encoders through the
  `TCA9548A` I2C mux.
- `serial_legacy` remains supported: `robot_serial_bridge.py` talks to the
  Nano ESP32 through the custom serial protocol.
- Subscribes to `/cmd_vel`.
- Publishes `/wheel_odom`, `/robot_status`, and, in serial mode,
  `/imu/arduino`.
- Active compose maps `/dev/i2c-1` and `/dev/gpiochip4`; serial legacy uses
  `/dev/ttyACM0`.
- `bridge_rpi_direct.env` contains important geometry and pin settings:
  `WHEEL_RADIUS_M=0.033`, `WHEEL_BASE_M=0.20`, `LEFT_MUX_CHANNEL=0`,
  `RIGHT_MUX_CHANNEL=4`, `MAX_LINEAR_VEL=0.5`, `MAX_ANGULAR_VEL=1.0`.

Note: the current bridge odometry output is `/wheel_odom`. If an older
consumer expects `/odom`, add a remap or adapter.

### `laser_driver_cont`

The image is built from `laser_driver_cont/Dockerfile` on top of
`ros:humble`. The driver package is `rplidar_ros`, built from the
`Slamtec/rplidar_ros` GitHub repository on the `ros2` branch.

Functionality:

- Runs `ros2 launch rplidar_ros rplidar_a1_launch.py`.
- Publishes LIDAR scans on `/scan`.
- Uses the serial device from the compose `LIDAR_DEVICE` variable, default
  `/dev/ttyUSB0`.
- Runs with the `dialout` group so it can read the serial port.

### `slam_cont`

The image is built from `slam_cont/Dockerfile` on top of `ros:humble`.
The main SLAM package is `ros-humble-slam-toolbox`; it runs
`async_slam_toolbox_node` with parameters from `/app/slam_params.yaml`.

Important additional packages and tools:

- `ros-humble-nav2-map-server` for occupancy map export.
- `ros-humble-nav2-msgs` for `nav2_msgs/srv/SaveMap`.
- `ros-humble-rosbag2-storage-mcap` for MCAP support.
- `rf2o_laser_odometry` is built from
  `MAPIRlab/rf2o_laser_odometry` source because no Humble arm64 binary is
  available.
- `python3-psycopg2`, `python3-yaml`, `python3-pil`, and `imagemagick` are
  used for map metadata, database insertion, and PNG preview generation.

Functionality:

- `slam_manager.py` keeps `slam_toolbox` alive and publishes the map on
  `/map`.
- `slam_params.yaml` uses `map_frame=map`, `odom_frame=odom`,
  `base_frame=base_link`, `scan_topic=/scan`, `resolution=0.05`, and
  `mode=mapping`.
- Sensor static TF publishers can be started from `static_tf.yaml`.
- `START_RF2O=auto` starts `rf2o_laser_odometry` when encoders are disabled
  (`ENCODERS_ENABLED=0`). In the current stack `ENCODERS_ENABLED=0`, so rf2o
  starts automatically.
- `run_mapping.sh` performs live mapping, can record a rosbag, saves maps
  through `/slam_toolbox/save_map`, can use
  `nav2_map_server map_saver_cli`, generates `pgm/yaml/png`, inserts maps
  into `robot_data.maps`, and updates `MAP_ROOT/latest`.
- Default mapping session names are incremental: `mapa1`, `mapa2`, ...

### `nav_cont`

The image is built from `nav_cont/Dockerfile` on top of `ros:humble`.
It installs `ros-humble-navigation2`, `ros-humble-nav2-bringup`,
`ros-humble-nav2-map-server`, `ros-humble-nav2-amcl`,
`ros-humble-nav2-lifecycle-manager`, `ros-humble-joy`, and
`ros-humble-teleop-twist-joy`.

Functionality:

- `start_nav.sh` starts `nav2_bringup navigation_launch.py` with
  `nav2_params.yaml`.
- The map is selected through `MAP_FILE`, `MAP_SESSION`, `active`, or
  `latest`; if no map exists, a small placeholder map is generated so the
  stack can start.
- `goal_forwarder.py` accepts `PoseStamped` goals on
  `/move_base_simple/goal` and sends them to the Nav2 `navigate_to_pose`
  action.
- `cmd_vel_mux.py` selects between `/cmd_vel_auto` and `/cmd_vel_joy`,
  publishes the final `/cmd_vel`, and exposes `/set_manual_mode`.
- Joystick support is optional through `/dev/input/js0`, `joy_node`, and
  `teleop_twist_joy`; Logitech F710 mapping is in `teleop_f710.yaml`.
- `nav2_params.yaml` uses AMCL, the DWB local planner, the Navfn global
  planner, velocity smoothing, and costmap sources from `/scan` plus the
  RealSense pointcloud `/realsense/depth/color/points`.
- Publishes blockage/anomaly state on `/navigation/anomaly_on_path` and
  details on `/navigation/anomaly_detail`.

### `sensor_fusion_cont`

The image is built from `sensor_fusion_cont/Dockerfile` on top of
`ros:humble`. The important ROS packages are
`ros-humble-imu-filter-madgwick` and `ros-humble-robot-localization`; the
custom Python package is `sensor_fusion_pkg`.

Functionality:

- Default `SF_IMU_SOURCE=realsense`: `imu_filter_madgwick_node` reads the
  RealSense IMU topic (`SF_IMU_INPUT_TOPIC`, default
  `/camera/realsense/imu`) and publishes filtered IMU on `/imu/data`.
- `arduino` mode is a serial-legacy fallback/debug mode:
  `arduino_listener` reads `/imu/arduino`, republishes `imu/data_raw`, and
  the Madgwick filter turns it into `/imu/data`.
- `robot_localization` EKF starts from `/app/robot_localization.yaml` and
  publishes the `odom -> base_link` TF.
- In the current `robot_localization.yaml`, the odometry input is
  `/odom_rf2o`, which matches the current `START_RF2O=auto` +
  `ENCODERS_ENABLED=0` setup. If encoders are enabled again later, either
  keep rf2o enabled or align the EKF odometry input with the active source.

### `realsense_cont`

The image is built from `realsense_cont/Dockerfile` on top of `ros:humble`.
It installs the Intel RealSense apt repository, `librealsense2-utils`,
`librealsense2-dev`, `ros-humble-realsense2-camera`,
`ros-humble-realsense2-description`, and
`ros-humble-image-transport-plugins`.

Functionality:

- `start_realsense.sh` performs a preflight with `rs-enumerate-devices` and
  launches `ros2 launch realsense2_camera rs_launch.py`.
- The camera can be selected with `RS_SERIAL` or `RS_USB_PORT_ID`; when
  multiple cameras are present, a selector is required.
- Runtime defaults from the stack: `RS_CAMERA_NAME=realsense`,
  `RS_BASE_FRAME_ID=realsense_link`, color `640x480x15`, depth
  `640x480x10`, `RS_ALIGN_DEPTH=true`, gyro/accel enabled, and
  `RS_ENABLE_POINTCLOUD=true`.
- Main outputs are RGB/depth/camera_info/IMU topics under
  `/camera/realsense/...`; the pointcloud is required by the Nav2 costmaps.
- `RS_COMPRESSED_JPEG_QUALITY` tunes compressed image transport quality.

### `ai_kit_cont`

The image is built from `ai_kit_cont/Dockerfile` on top of
`ros:jazzy-ros-base`. Jazzy/Ubuntu 24.04 is used for the Hailo/TAPPAS
environment. Hailo runtime is not installed in the image; it is mounted from a
host that has `hailo-all` installed.

Important packages and tools:

- GStreamer plugins and Python GStreamer bindings.
- `ros-jazzy-cv-bridge`, `ros-jazzy-image-transport`,
  `ros-jazzy-compressed-image-transport`, and `ros-jazzy-vision-msgs`.
- `hailo-rpi5-examples` is cloned into the image, while model resources are
  downloaded on first container start into a persistent volume.

Functionality:

- `start_ai_kit.sh` checks Hailo mounts and waits for the RealSense image
  topic.
- `realsense_hailo_node.py` subscribes to RealSense image/depth/camera_info.
- If `HAILO_GST_PIPELINE` is set, the pipeline must contain an `appsrc`
  named `ros_src` and an `appsink` named `ros_sink`.
- If no pipeline is set, the node runs in passthrough mode and republishes an
  overlay without inference. The current stack env uses
  `AI_KIT_REQUIRE_HAILO=0`, so this mode is allowed.
- Publishes `/ai_kit/image_overlay`,
  `/ai_kit/image_overlay/compressed`, `/ai_kit/obstacles`, and, with a
  metadata-capable pipeline, `/ai_kit/detections`.

### `rosbridge_websocket_cont` / `rosbridge_cont`

The image is built from `rosbridge_cont/Dockerfile` on top of `ros:humble`.
It uses the `ros-humble-rosbridge-server` package.

Functionality:

- Runs `ros2 launch rosbridge_server rosbridge_websocket_launch.xml`.
- Exposes the ROS 2 graph to web clients over WebSocket, typically on port
  `9090`.
- Builds a local `/ros_ws` workspace from `rosbridge_cont/src`.

### `foxglove_bridge_cont`

The image is built from `foxglove_bridge_cont/Dockerfile` on top of
`ros:humble`. It uses the `ros-humble-foxglove-bridge` package.

Functionality:

- Runs `ros2 run foxglove_bridge foxglove_bridge`.
- Default endpoint is `0.0.0.0:8765`.
- TLS is optional through `FOXGLOVE_TLS`, `FOXGLOVE_TLS_CERT`, and
  `FOXGLOVE_TLS_KEY`.
- Intended for Foxglove Studio visualization of topics, TF, maps, and images.

### `bag_recorder_cont`

The image is built from `bag_recorder_cont/Dockerfile` on top of
`ros:humble-ros-base`. It uses `ros-humble-ros2bag`,
`ros-humble-rosbag2-storage-default-plugins`, and
`ros-humble-rosbag2-compression-zstd`.

Functionality:

- `bag_recorder.sh` reads a YAML topic list from
  `/config/recorded_topics.yaml`.
- Waits for active publishers before starting a recording.
- Records into `/bags` with default rotation `MAX_BAG_MB=150`.
- Uses file-level Zstd compression.
- Resolves aliases for RealSense topic prefixes, `/odom` vs `/wheel_odom`,
  and some compressed image topic names.
- The current `recorded_topics.yaml` records `/scan`, `/tf`, `/tf_static`,
  `/map`, `/imu/data`, `/imu/arduino`, and the main RealSense image/IMU
  topics; `/imu/arduino` has a publisher only in serial legacy mode, while
  `/wheel_odom` is present as an easy-to-enable entry.

### `database_cont` / `db_cont`

The image is built from `db_cont/Dockerfile` on top of `postgres:15`.
It installs `postgresql-15-postgis-3`; `init-db.sql` enables PostGIS and
`uuid-ossp`.

Functionality:

- Exposes PostgreSQL on port `5432`.
- In the runtime stack, `PGDATA` is set to `/srv/db`.
- The schema is `robot_data`.
- Main tables are `maps`, `camera_images`, `waypoints`, and
  `robot_sessions`.
- `slam_cont/run_mapping.sh` inserts saved maps into `robot_data.maps`
  together with resolution, origin, dimensions, and YAML hash metadata.

### `healthcheck_cont`

The image is built from `healthcheck_cont/Dockerfile` on top of
`ubuntu:22.04`. It installs Docker CLI, `netcat`, `usbutils`, and ROS 2
Humble CLI packages (`ros-humble-ros-base`,
`ros-humble-rmw-cyclonedds-cpp`).

Functionality:

- `healthcheck.py` checks Docker runtime and health status for expected
  containers.
- Checks ports `5432`, `9090`, and `8765`.
- Checks hardware paths for lidar, RealSense USB, and the configured bridge
  device path. In the active `rpi_direct` stack that path is `/dev/null`, so
  the healthcheck currently does not validate I2C/GPIO functionality.
- Checks ROS topics `/scan`, `/wheel_odom`, `/tf`, `/tf_static`,
  `/imu/data`, and `/camera/realsense/color/image_raw`.
- Checks basic host health: load, memory, disk, and CPU temperature.
- Can write reports into `/logs` when `HEALTHCHECK_LOG_TO_FILE=1`.

### `container_log_collector_cont`

Uses the same image as `healthcheck_cont`, but the entrypoint is
`container_log_collector.py`.

Functionality:

- Reads Docker logs through read-only `/var/run/docker.sock`.
- Automatically tracks all containers in the compose project
  `COMPOSE_PROJECT_NAME`.
- Writes daily logs into `/logs/<day>/<container>.log`.
- Persists resume state in `/logs/.container-log-state.json` to avoid
  duplicating lines after restarts.
- Configured through `../stack/config/containers/logging.yaml`.

### `bag_browser_cont`

This is not a local image from the repository; it is a runtime helper from
compose: `filebrowser/filebrowser:latest`.

Functionality:

- Web browser for `../stack/bags` and `../stack/logs`.
- Exposes port `8080`.
- Mounts are read-only.
- Compose starts it without authentication (`--noauth`), so it should only be
  used on a controlled network.

### `camera_cont` (optional)

The image is built from `camera_cont/Dockerfile` on top of
`ros:humble-ros-base`, but the service is currently commented out in
`../stack/docker-compose.yaml` because RealSense is the main active camera
path.

Functionality:

- `camera_node.py` uses OpenCV plus a GStreamer pipeline.
- Default input is a UDP/H264 pipeline on port `5000`, or a custom
  `CAMERA_GSTREAMER_PIPELINE`.
- Publishes JPEG `CompressedImage` on `/camera/image_raw/compressed`.
- Publishes `CameraInfo` on `/camera/camera_info` when `camera_info.yaml` is
  available.

## Architecture Overview

```text
Lidar --------> laser_driver_cont ----\
                                       \
RealSense ----> realsense_cont ---------> sensor_fusion_cont --> /imu/data
                                         \
RPi GPIO/I2C -> bridge_cont --------------> /wheel_odom, /robot_status
      ^                 |
      |                 +<------------------------------ /cmd_vel
      |
      +-- DRV8833 -> motors
      +-- TCA9548A -> AS5600 LEFT / RIGHT (wired, currently disabled)

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
4. For the active `rpi_direct` mode, verify `/dev/i2c-1` and
   `/dev/gpiochip4`. Check Nano `/dev/ttyACM0` only when intentionally using
   `BRIDGE_MODE=serial_legacy`.

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
- `/imu/arduino` (serial legacy/debug only)
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
- for active `rpi_direct` mode, access to `/dev/i2c-1` and `/dev/gpiochip4`
- for legacy `serial_legacy` mode, Nano ESP32 connected as a serial device
- access to devices such as `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/i2c-1`,
  `/dev/gpiochip4`, and `/dev/bus/usb`

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
