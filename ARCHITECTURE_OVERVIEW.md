# Robot System Architecture Overview

This document summarizes the **current** project architecture as implemented across this repository, the sibling runtime stack and the Jetson anomaly stack.

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
└─ connects to Raspberry Pi foxglove_bridge and displays both normal robot topics and Jetson anomaly topics
```

The Jetson does **not** join the ROS 2 DDS graph directly. Earlier testing showed that direct DDS participation from Jetson unnecessarily overloaded the Raspberry Pi, especially when image topics were involved.

## Current Hardware Path

The active motor/control path is:

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motors
```

Active assumptions:

- `BRIDGE_MODE=rpi_direct`
- `GPIOCHIP=/dev/gpiochip4`
- `DRIVER=drv8833`
- wheel encoders are disabled and not used in the active setup
- TCA9548A I2C multiplexer is not used
- AS5600 encoders are not used
- serial legacy firmware for Nano ESP32 is not the active motor path

The robot navigation stack uses LiDAR/SLAM/AMCL/Nav2 and available ROS pose sources rather than wheel encoder feedback.

## ROS 2 Runtime Components

| Component | Role |
| --- | --- |
| `bridge_cont` | Direct Raspberry Pi GPIO motor bridge for DRV8833; publishes bridge status and wheel odometry placeholder/open-loop data if configured |
| `laser_driver_cont` | RPLidar A1 driver publishing `/scan` |
| `slam_cont` | SLAM Toolbox, map generation and map save/export |
| `nav_cont` | Nav2, AMCL, goal forwarding, cmd_vel mux/safety logic |
| `realsense_cont` | RealSense/camera RGB/depth/camera_info/IMU topics |
| `sensor_fusion_cont` | IMU filtering and robot_localization when enabled |
| `rosbridge_cont` | WebSocket bridge on port `9090` for Jetson and selected clients |
| `foxglove_bridge_cont` | WebSocket bridge on port `8765` for Foxglove visualization |
| `ai_kit_cont` | Legacy/experimental Hailo path; not the active anomaly pipeline |

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

The marker text should be `ANOMALY: bottle` and remain visible in Foxglove for 180 seconds.

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

## Legacy / Deprecated References

The repository still contains some code and documentation for earlier experiments:

- `TCA9548A` I2C multiplexer
- `AS5600` wheel encoders
- `ENCODERS_ENABLED=1`
- `serial_legacy` Nano ESP32 bridge
- Raspberry Pi AI Kit / Hailo anomaly processing

These references are retained for history or optional experiments but should not be treated as the current thesis architecture. The current architecture is direct RPi GPIO motor control plus Jetson-based YOLO anomaly detection through rosbridge.
