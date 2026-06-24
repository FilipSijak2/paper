# Hardware Components

This file lists the hardware that matches the **current active** implementation.

## Main Robot Computer

- Raspberry Pi 5
- Ubuntu / ROS 2 runtime
- Docker-based robot stack
- SSD storage for robot stack and logs

## Motor Control

Current active motor path:

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motors
```

Active components:

- Raspberry Pi 5 GPIO
- DRV8833 motor driver
- left and right DC motors
- separate motor power supply
- common ground between Raspberry Pi, motor driver and motor supply

Not active:

- AS5600 wheel encoders
- TCA9548A I2C multiplexer
- encoder-based odometry
- Nano ESP32 serial bridge as the main motor path
- UNO R4 as the main motor path

## Perception and Navigation Sensors

Active / planned sensors:

- RPLidar A1 for `/scan`, SLAM and Nav2
- Intel RealSense camera for RGB/depth/camera_info/IMU topics
- optional camera topics for compressed image transport

The navigation stack should rely on LiDAR/SLAM/AMCL/Nav2 and available ROS pose sources, not on wheel encoders.

## AI / Anomaly Detection Hardware

Active anomaly detection hardware:

- Jetson Orin

Jetson responsibilities:

- subscribe to selected Raspberry Pi topics through rosbridge
- run YOLO inference
- detect `bottle` as the first anomaly class
- save original anomaly images, annotated images, map snapshots and JSONL event logs locally
- publish anomaly visualization topics back through rosbridge

Legacy/experimental anomaly hardware:

- Raspberry Pi AI Kit / Hailo

The AI Kit / Hailo path is not the current anomaly detection architecture. It can remain in the repository as an experiment, but thesis documentation should describe the Jetson YOLO path as the active design.

## Visualization / Networking

- `rosbridge_server` on Raspberry Pi, usually port `9090`
- `foxglove_bridge` on Raspberry Pi, usually port `8765`
- Foxglove on laptop or Jetson connects to Raspberry Pi foxglove_bridge
- Jetson communicates with Raspberry Pi through rosbridge, not direct DDS

## Legacy Components

The repository may still contain references to:

- `TCA9548A`
- `AS5600`
- `ENCODERS_ENABLED=1`
- `serial_legacy`
- Hailo / AI Kit inference

These should be treated as legacy/experimental unless explicitly re-enabled in future work.
