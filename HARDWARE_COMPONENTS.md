# Hardware Components

This file lists the hardware that matches the current active implementation.

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

Current bridge configuration:

```env
BRIDGE_MODE=rpi_direct
DRIVER=drv8833
ENCODERS_ENABLED=0
```

Robot pose for navigation comes from LiDAR, SLAM, AMCL/Nav2 and available ROS pose topics.

## Perception and Navigation Sensors

Active sensors:

- RPLidar A1 for `/scan`, SLAM and Nav2
- Intel RealSense camera for RGB/depth/camera_info/IMU topics
- compressed image topics for Jetson inference transport

## AI / Anomaly Detection Hardware

Active anomaly detection hardware:

- Jetson Orin

Jetson responsibilities:

- subscribe to selected Raspberry Pi topics through rosbridge
- run YOLO inference
- save original anomaly images, annotated images, map snapshots and JSONL event logs locally
- publish anomaly visualization topics back through rosbridge

## Visualization / Networking

- `rosbridge_server` on Raspberry Pi, usually port `9090`
- `foxglove_bridge` on Raspberry Pi, usually port `8765`
- Foxglove on laptop or Jetson connects to Raspberry Pi foxglove_bridge
- Jetson communicates with Raspberry Pi through rosbridge WebSocket
