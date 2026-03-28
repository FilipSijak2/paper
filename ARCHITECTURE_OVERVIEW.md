# Robot System Architecture Overview

This document summarizes the current project architecture as implemented in this
repository and the sibling runtime stack in `../stack/`.

## 1. Current High-Level Model

The project is a ROS 2 Humble based robot stack orchestrated with Docker
Compose on the host side, with a single active robot microcontroller on the
hardware side.

Current control chain:

```text
Raspberry Pi / Docker stack
  |
  +-- robot_bridge <-> Nano ESP32 <-> DRV8833 <-> motors
  |                    |
  |                    \-> TCA9548A -> AS5600 LEFT / RIGHT
  |
  +-- laser_driver -> /scan
  +-- realsense_cont -> sensor_fusion_cont -> /imu/data
  +-- slam_cont / nav_cont / rosbridge / foxglove / database
```

## 2. Hardware Architecture

### Active controller

- `Arduino Nano ESP32`
  - receives motion commands over USB serial
  - reads wheel encoders
  - optionally reads onboard IMU
  - computes wheel odometry
  - directly controls the `DRV8833`

### Motor stage

- `DRV8833`
  - dual H-bridge
  - wired directly to Nano GPIO
  - powered from an external motor supply

### Encoder stage

- `TCA9548A`
- `2x AS5600`

Current firmware channel mapping:

- `CH0` = left encoder
- `CH1` = right encoder

### Host-side sensors

- `RPLidar` for `/scan`
- `RealSense D455` as the default source path for `/imu/data`

## 3. Runtime Services

Current runtime stack in `../stack/docker-compose.yaml` includes at least:

- `robot_bridge`
- `laser_driver`
- `slam_cont`
- `nav_cont`
- `sensor_fusion_cont`
- `realsense_cont`
- `rosbridge_websocket`
- `foxglove_bridge`
- `database_cont`
- `bag_recorder_cont`
- `healthcheck_cont`

## 4. Main Data Flows

### Motion commands

```text
/cmd_vel
  -> robot_bridge
  -> Nano ESP32
  -> DRV8833
  -> motors
```

### Robot feedback

```text
Nano ESP32
  -> robot_bridge
  -> /wheel_odom
  -> /imu/arduino
  -> /robot_status
```

### Default IMU path for navigation and SLAM

```text
RealSense
  -> sensor_fusion_cont
  -> /imu/data
```

### Mapping path

```text
/scan + /tf + odometry + /imu/data
  -> slam_cont
  -> /map
  -> saved map artifacts
  -> database insert
```

## 5. Important Current Topics

### Robot bridge topics

- `/cmd_vel`
- `/wheel_odom`
- `/imu/arduino`
- `/robot_status`

### Mapping and navigation topics

- `/scan`
- `/tf`
- `/tf_static`
- `/map`
- `/imu/data`

## 6. Important Current Notes

### `/wheel_odom` vs `/odom`

The current serial bridge publishes:

- `/wheel_odom`

Some legacy configs and older documents still mention:

- `/odom`

When documenting the current implementation, `/wheel_odom` is the correct
bridge output topic. If a consumer expects `/odom`, use a remap or adapter.

### RealSense IMU vs Nano IMU

Default stack behavior:

- `/imu/data` comes from `sensor_fusion_cont` using RealSense IMU input

The Arduino/Nano IMU stream:

- remains available on `/imu/arduino`
- is useful for debugging and recording
- is not the default fused IMU source

### Legacy items no longer in the main path

The following appear in older project notes but are not part of the current
main implementation:

- `UNO R4` as active motor controller
- `Nano <-> UNO` UART chain
- `BTS7960 / IBT-2`
- `micro-ROS agent`

## 7. Deployment Summary

Typical deployment:

1. Build or pull images for the runtime services.
2. Start the stack from `../stack/`.
3. Confirm the Nano is visible as `/dev/ttyACM0`.
4. Confirm `robot_bridge` receives packets from the Nano.
5. Verify `/wheel_odom`, `/imu/arduino`, and `/scan`.
6. Run mapping or navigation workflows.

## 8. Related Documents

- `README.hr.md`
- `README.en.md`
- `CURRENT_WIRING_DIAGRAM.md`
- `HARDWARE_WIRING_GUIDE.md`
- `HARDWARE_SETUP_CUSTOM_PROTOCOL.md`
- `COMMUNICATION_ANALYSIS.md`
