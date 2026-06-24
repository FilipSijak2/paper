# Thesis Project

This repository contains documentation and software components for the ROS 2 robot system used in the thesis project. The Raspberry Pi remains the main robot computer for motion, SLAM, Nav2, mapping, LiDAR and camera publishing, while anomaly detection has been moved to the Jetson Orin.

## Current Architecture Decision

The active architecture is:

```text
Raspberry Pi 5
├─ ROS 2 robot stack
├─ LiDAR, SLAM, AMCL/Nav2, /map, /tf, /scan, /odom
├─ RealSense/camera publisher
├─ rosbridge_server :9090
└─ foxglove_bridge :8765

Jetson Orin
├─ connects to the Raspberry Pi through rosbridge WebSocket
├─ receives compressed camera images, map and robot pose
├─ runs YOLO anomaly detection
├─ treats bottle as the first anomaly test class
├─ saves original images, annotated images, map snapshots and JSONL logs locally
└─ publishes only anomaly visualization topics back to the Raspberry Pi

Foxglove
└─ connects to Raspberry Pi foxglove_bridge and visualizes the map, robot and anomaly topics
```

The Jetson should **not** join the ROS 2 DDS network directly because this overloaded the Raspberry Pi in earlier tests. The selected communication method is rosbridge WebSocket.

## Current Hardware Architecture

The active motor architecture no longer uses wheel encoders or an I2C multiplexer:

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motors
```

Notes:

- `BRIDGE_MODE=rpi_direct` is the active bridge mode.
- `DRV8833` is the current motor driver.
- Wheel encoders are currently **not used**.
- The `TCA9548A` I2C multiplexer is currently **not used**.
- AS5600 encoders and encoder mux documents are legacy/experimental.
- The `UNO R4` and `Nano ESP32 serial_legacy` path are not the main active motor path.
- Navigation and localization rely on LiDAR/SLAM/AMCL/Nav2 and existing ROS pose sources, not wheel encoders.

## AI / Anomaly Detection

The active decision is that anomaly detection is no longer performed on the Raspberry Pi AI Kit / Hailo. AI Kit/Hailo documentation and containers should be treated as legacy/experimental.

The active anomaly workflow is:

```text
Raspberry Pi compressed camera + map + robot pose
        |
        v
Jetson Orin YOLO
        |
        +--> saves images and logs locally on Jetson
        |
        v
/anomaly/events
/anomaly/markers
/anomaly/debug_image/compressed
/anomaly/map_snapshot/compressed
        |
        v
Raspberry Pi rosbridge -> foxglove_bridge -> Foxglove visualization
```

The detailed pipeline is documented in [ANOMALY_ROSBRIDGE_PIPELINE.md](./ANOMALY_ROSBRIDGE_PIPELINE.md).

## Main Components

| Component | Current role |
| --- | --- |
| `bridge_cont` | Raspberry Pi direct GPIO motor bridge for DRV8833; no active wheel encoders |
| `laser_driver_cont` | RPLidar ROS 2 driver, publishes `/scan` |
| `realsense_cont` | RealSense/camera topics for RGB/depth/camera_info/IMU |
| `slam_cont` | SLAM Toolbox, `/map`, map save/export |
| `nav_cont` | Nav2, AMCL, goal forwarder, cmd_vel mux/safety logic |
| `sensor_fusion_cont` | IMU/filter/robot_localization depending on active sources |
| `rosbridge_cont` | WebSocket access to selected ROS topics, port `9090` |
| `foxglove_bridge_cont` | Foxglove visualization over WebSocket, port `8765` |
| `ai_kit_cont` | Legacy/experimental Hailo path; not the active anomaly pipeline |
| `bag_recorder_cont` | ROS bag recording |
| `db_cont` | PostgreSQL/PostGIS database |
| `healthcheck_cont` | Container and ROS graph health checks |

## Important Documents

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) - current architecture overview.
- [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md) - current wiring without encoders/multiplexer.
- [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md) - recommended wiring.
- [HARDWARE_COMPONENTS.md](./HARDWARE_COMPONENTS.md) - current hardware components.
- [ANOMALY_ROSBRIDGE_PIPELINE.md](./ANOMALY_ROSBRIDGE_PIPELINE.md) - Jetson YOLO anomaly pipeline.
- [COMMUNICATION_ANALYSIS.md](./COMMUNICATION_ANALYSIS.md) - communication model between RPi, Jetson and Foxglove.

## Legacy Notes

If a document or source file mentions `TCA9548A`, `AS5600`, `ENCODERS_ENABLED=1`, `Hailo`, `AI Kit` or `serial_legacy`, it should not be interpreted as the current active system direction. The active direction is:

```text
Raspberry Pi: navigation + sensors + ROS bridge
Jetson: YOLO anomaly detection + image/snapshot/log saving
Foxglove: visualization through Raspberry Pi foxglove_bridge
```
