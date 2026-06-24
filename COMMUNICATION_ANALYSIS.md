# Current Communication Analysis

This document describes the communication model that matches the current robot architecture.

## Summary

The active system is split into two main computers:

- Raspberry Pi 5: robot control, ROS 2 graph, LiDAR, SLAM, Nav2, camera publishing, rosbridge and foxglove_bridge
- Jetson Orin: YOLO anomaly detection and anomaly artifact generation

Jetson should **not** join the Raspberry Pi ROS 2 DDS graph directly. Earlier tests showed that direct DDS participation, especially with image topics, overloaded the Raspberry Pi. The current design uses rosbridge WebSocket for controlled topic exchange.

## Raspberry Pi Communication

Raspberry Pi hosts:

- ROS 2 robot graph
- `rosbridge_server`, usually `ws://raspberry.local:9090`
- `foxglove_bridge`, usually `ws://raspberry.local:8765`

Raspberry Pi publishes the robot topics needed by Jetson:

- `/camera/.../compressed` for YOLO input
- `/map` for map snapshot generation
- `/robot_pose_map` or `/amcl_pose` for anomaly localization

Raspberry Pi also receives anomaly visualization topics from Jetson through rosbridge:

- `/anomaly/events`
- `/anomaly/markers`
- `/anomaly/debug_image/compressed`
- `/anomaly/map_snapshot/compressed`

## Jetson Communication

Jetson connects to Raspberry Pi rosbridge as a WebSocket client.

Jetson subscribes to:

- compressed camera image topic
- map topic
- robot pose topic

Jetson publishes back:

- JSON anomaly events
- visualization markers in `map` frame
- annotated camera image preview
- map snapshot preview

Jetson saves the actual artifact files locally:

- original image
- annotated image
- map snapshot PNG
- events JSONL

## Foxglove Communication

Foxglove should connect to the Raspberry Pi foxglove_bridge endpoint, not to Jetson DDS:

```text
ws://raspberry.local:8765
```

Foxglove can then display normal robot topics and the anomaly topics that Jetson has published back to the Raspberry Pi through rosbridge.

Recommended Foxglove topics:

- `/map`
- `/tf`
- `/tf_static`
- `/scan` or `/scan_filtered`
- `/odom`
- `/robot_pose_map` if available
- `/anomaly/markers`
- `/anomaly/events`
- `/anomaly/debug_image/compressed`
- `/anomaly/map_snapshot/compressed`

## Motor / Sensor Communication

The active motor path is direct Raspberry Pi GPIO:

```text
Raspberry Pi GPIO -> DRV8833 -> motors
```

The active runtime does not use:

- wheel encoder feedback
- AS5600 encoders
- TCA9548A I2C multiplexer
- Nano ESP32 serial bridge as the main motor path

Legacy serial and encoder-related code may remain in the repository, but it is not part of the current communication model.

## AI Kit / Hailo Status

Raspberry Pi AI Kit / Hailo inference is not the active anomaly detection path. The active path is Jetson YOLO over rosbridge.

## Recommended Runtime Boundaries

- Keep Raspberry Pi responsible for navigation and ROS robot state.
- Keep Jetson responsible for YOLO and anomaly artifacts.
- Do not stream raw images over rosbridge; use compressed image topics.
- Do not connect Jetson to the DDS graph unless there is a specific controlled test.
- Use Foxglove only through Raspberry Pi foxglove_bridge.
