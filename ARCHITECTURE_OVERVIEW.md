# Robot System Architecture Overview

This document summarizes the current project architecture as implemented in this
repository and the sibling runtime stack in `../stack/`.

## 1. Current High-Level Model

The project is a ROS 2 based robot stack orchestrated with Docker Compose on
the host side. The active runtime in `../stack/.env` is currently
`BRIDGE_MODE=rpi_direct`, so the Raspberry Pi drives the motor driver
directly. Encoder hardware is present in the wiring, but the current stack has
`ENCODERS_ENABLED=0`, so runtime odometry relies on open-loop bridge odometry
and rf2o laser odometry.

Current control chain:

```text
Raspberry Pi / Docker stack
  |
  +-- robot_bridge (BRIDGE_MODE=rpi_direct) <-> DRV8833 <-> motors
  |                                    |
  |                                    \-> TCA9548A -> AS5600 LEFT / RIGHT
  |
  +-- laser_driver -> /scan
  +-- realsense_cont -> sensor_fusion_cont -> /imu/data
  +-- slam_cont / nav_cont / rosbridge / foxglove / database
```

Legacy serial control chain still supported in software:

```text
Raspberry Pi / Docker stack
  |
  +-- robot_bridge (BRIDGE_MODE=serial_legacy) <-> Nano ESP32 <-> DRV8833 <-> motors
  |                                                     |
  |                                                     \-> TCA9548A -> AS5600 LEFT / RIGHT
  |
  +-- laser_driver -> /scan
  +-- realsense_cont -> sensor_fusion_cont -> /imu/data
  +-- slam_cont / nav_cont / rosbridge / foxglove / database
```

## 2. Hardware Architecture

### Active controller path

- `Raspberry Pi 5`
  - runs the Docker stack
  - `robot_bridge` drives `DRV8833` through GPIO PWM
  - encoder I2C wiring is available, but current config disables encoder reads

### Legacy controller path

- `Arduino Nano ESP32`
  - supported by `BRIDGE_MODE=serial_legacy`
  - receives motion commands over USB serial when that mode is used
  - reads wheel encoders
  - optionally reads onboard IMU
  - computes wheel odometry
  - directly controls the `DRV8833`

### Motor stage

- `DRV8833`
  - dual H-bridge
  - in the active stack, wired to Raspberry Pi GPIO
  - in serial legacy mode, wired to Nano GPIO
  - powered from an external motor supply

### Encoder stage

- `TCA9548A`
- `2x AS5600`

Current channel mapping:

- `CH0` = left encoder
- `CH4` = right encoder

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
- `ai_kit_cont`
- `rosbridge_websocket`
- `foxglove_bridge`
- `database_cont`
- `bag_recorder_cont`
- `bag_browser_cont`
- `container_log_collector_cont`
- `healthcheck_cont`

## 4. Main Data Flows

### Motion commands

```text
/cmd_vel
  -> robot_bridge
  -> Raspberry Pi GPIO PWM
  -> DRV8833
  -> motors
```

### Robot feedback

```text
Raspberry Pi I2C
  -> TCA9548A
  -> AS5600 LEFT / RIGHT
  -> robot_bridge
  -> /wheel_odom
  -> /robot_status
```

In `serial_legacy` mode, the Nano publishes the same `/wheel_odom` and
`/robot_status` feedback through the bridge, plus `/imu/arduino`.

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
- `/robot_status`

In active `rpi_direct` mode, `/imu/arduino` is not published by
`robot_bridge`. It exists only in serial legacy mode.

### Mapping and navigation topics

- `/scan`
- `/tf`
- `/tf_static`
- `/map`
- `/imu/data`

## 6. Important Current Notes

### `/wheel_odom` vs `/odom`

The robot bridge publishes:

- `/wheel_odom`

Some legacy configs and older documents still mention:

- `/odom`

When documenting the current implementation, `/wheel_odom` is the correct
bridge output topic. If a consumer expects `/odom`, use a remap or adapter.

### EKF odometry input

The active stack now has `ENCODERS_ENABLED=0` in both
`bridge_rpi_direct.env` and `slam_cont.env`. That means
`robot_bridge` runs open-loop wheel odometry from `/cmd_vel`, while
`slam_cont` starts `rf2o_laser_odometry` automatically because
`START_RF2O=auto`. This matches
`../stack/config/containers/robot_localization.yaml`, where EKF `odom0` is
`/odom_rf2o`.

### RealSense IMU vs Nano IMU

Default stack behavior:

- `/imu/data` comes from `sensor_fusion_cont` using RealSense IMU input

The Arduino/Nano IMU stream in serial legacy mode:

- is available on `/imu/arduino`
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
3. Confirm `/dev/i2c-1` and `/dev/gpiochip4` are available on the host.
4. Confirm `robot_bridge` starts in `rpi_direct` mode.
5. Verify `/wheel_odom`, `/robot_status`, and `/scan`.
6. Run mapping or navigation workflows.

If intentionally using serial legacy mode, confirm the Nano is visible as
`/dev/ttyACM0` and verify `/imu/arduino`.

## 8. Related Documents

- `README.hr.md`
- `README.en.md`
- `CURRENT_WIRING_DIAGRAM.md`
- `HARDWARE_WIRING_GUIDE.md`
- `HARDWARE_SETUP_CUSTOM_PROTOCOL.md`
- `COMMUNICATION_ANALYSIS.md`
