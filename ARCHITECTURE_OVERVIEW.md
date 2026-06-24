# Robot System Architecture Overview

This document summarizes the current project architecture across this repository, the robot runtime stack and the Jetson anomaly stack.

## High-Level Architecture

```text
Raspberry Pi 5
├─ main ROS 2 robot computer
├─ LiDAR, SLAM, localization, navigation and camera publishing
├─ motor bridge in rpi_direct mode
├─ rosbridge_server for selected WebSocket topic exchange
└─ foxglove_bridge for visualization

Jetson Orin
├─ external AI computer
├─ connects to Raspberry Pi through rosbridge WebSocket
├─ runs YOLO inference
├─ detects bottle as the first anomaly class
├─ saves anomaly images, map snapshots and JSONL events locally
└─ publishes anomaly visualization topics back to Raspberry Pi

Foxglove
└─ connects to Raspberry Pi foxglove_bridge and displays robot topics and Jetson anomaly topics
```

The selected Jetson <-> Raspberry Pi communication boundary is rosbridge WebSocket. This keeps Jetson inference traffic controlled and exposes only the topics needed for the thesis anomaly workflow.

## Current Hardware Path

The active motor/control path is:

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motors
```

Current assumptions:

- `BRIDGE_MODE=rpi_direct`
- `GPIOCHIP=/dev/gpiochip4`
- `DRIVER=drv8833`
- `ENCODERS_ENABLED=0`
- motor driver: DRV8833
- motor command interface: Raspberry Pi GPIO through `bridge_cont`
- robot pose sources: LiDAR, SLAM, AMCL/Nav2 and available ROS pose topics

The detailed wiring and pin list are in [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md).

## ROS 2 Runtime Components

| Component | Role |
| --- | --- |
| `bridge_cont` | Direct Raspberry Pi GPIO motor bridge for DRV8833; configured with `ENCODERS_ENABLED=0` |
| `laser_driver_cont` | RPLidar A1 driver publishing `/scan` |
| `slam_cont` | SLAM Toolbox, map generation and map save/export |
| `nav_cont` | Nav2, AMCL, goal forwarding, cmd_vel mux/safety logic |
| `realsense_cont` | RealSense/camera RGB/depth/camera_info/IMU topics |
| `sensor_fusion_cont` | IMU filtering and robot_localization when enabled |
| `rosbridge_cont` | WebSocket bridge on port `9090` for Jetson and selected clients |
| `foxglove_bridge_cont` | WebSocket bridge on port `8765` for Foxglove visualization |
| `ai_kit_cont` | Archived/experimental Hailo path in the repository |

## Anomaly Detection Architecture

The active anomaly detection design is Jetson-based:

```text
RPi camera/map/pose topics
        |
        | rosbridge WebSocket
        v
Jetson YOLO anomaly client
        |
        +--> local Jetson artifact saving
        |    ├─ original image
        |    ├─ annotated image
        |    ├─ map snapshot PNG
        |    └─ events.jsonl
        |
        | rosbridge WebSocket
        v
RPi ROS graph
        |
        v
Foxglove visualization through foxglove_bridge
```

The first real scenario treats `bottle` as the anomaly object. Jetson publishes:

- `/anomaly/events` (`std_msgs/String`, JSON)
- `/anomaly/markers` (`visualization_msgs/MarkerArray`)
- `/anomaly/debug_image/compressed` (`sensor_msgs/CompressedImage`)
- `/anomaly/map_snapshot/compressed` (`sensor_msgs/CompressedImage`)

The marker text is `ANOMALY: bottle` and the marker TTL is 180 seconds.

Detailed anomaly documentation is in [ANOMALY_ROSBRIDGE_PIPELINE.md](./ANOMALY_ROSBRIDGE_PIPELINE.md).

## Data Flow Summary

```text
/cmd_vel / goals
    -> Nav2 / cmd_vel mux
    -> bridge_cont
    -> DRV8833 / motors

/scan
    -> SLAM / AMCL / Nav2
    -> /map and localization

/camera/.../compressed + /map + /robot_pose_map or /amcl_pose
    -> rosbridge
    -> Jetson YOLO anomaly client
    -> anomaly visualization topics
    -> rosbridge
    -> Raspberry Pi ROS graph
    -> foxglove_bridge
    -> Foxglove
```

## Archived / Experimental References

The repository also contains archived or experimental material for earlier prototypes:

- `TCA9548A` I2C multiplexer
- `AS5600` wheel encoders
- `ENCODERS_ENABLED=1`
- `serial_legacy` Nano ESP32 bridge
- Raspberry Pi AI Kit / Hailo anomaly processing

The thesis baseline described in the current documentation is direct Raspberry Pi GPIO motor control plus Jetson-based YOLO anomaly detection through rosbridge.
