# Current Communication Analysis

This document describes the communication model that matches the current
runtime stack in `../stack/`. The active bridge mode in `../stack/.env` is
`BRIDGE_MODE=rpi_direct`.

## Current Architecture

```text
Raspberry Pi / Docker stack
  |
  +-- robot_bridge (BRIDGE_MODE=rpi_direct)
  |      |
  |      +-- /cmd_vel      -> RPi GPIO -> DRV8833
  |      +-- /wheel_odom   <- open-loop cmd_vel integration (ENCODERS_ENABLED=0)
  |      +-- /robot_status <- RPi direct bridge
  |
  +-- realsense_cont -> sensor_fusion_cont -> /imu/data
  +-- laser_driver -> /scan
  +-- slam_cont / nav_cont consume ROS topics

Physical robot:
  Raspberry Pi
      |- I2C -> TCA9548A -> AS5600 LEFT / RIGHT (wired, currently disabled)
      \- GPIO -> DRV8833 -> LEFT / RIGHT motor
```

Supported legacy alternative (software mode switch):

```text
Raspberry Pi / Docker stack
  |
  +-- robot_bridge (custom binary protocol over USB serial)
  |      |
  |      +-- /cmd_vel      -> Nano ESP32
  |      +-- /wheel_odom   <- Nano ESP32
  |      +-- /imu/arduino  <- Nano ESP32
  |      +-- /robot_status <- Nano ESP32
  |
  +-- realsense_cont -> sensor_fusion_cont -> /imu/data
```

## Active Communication Layers

### 1. Raspberry Pi direct motor/encoder bridge

Current active transport:

- GPIO for `DRV8833` motor control
- I2C on `/dev/i2c-1` for `TCA9548A` and `AS5600`
- GPIO chip `/dev/gpiochip4` on Raspberry Pi 5
- `BRIDGE_MODE=rpi_direct`

Active bridge container:

- `robot_bridge` in `../stack/docker-compose.yaml`

Published ROS topics from the bridge:

- `/wheel_odom`
- `/robot_status`

In `BRIDGE_MODE=rpi_direct`, `/imu/arduino` is not published.

Subscribed ROS topics:

- `/cmd_vel`

### 2. Raspberry Pi I2C sensor bus

Current sensor bus hardware:

- `I2C1` on Raspberry Pi `GPIO2/GPIO3`
- `TCA9548A` at `0x70`
- `AS5600 LEFT` on `CH0`
- `AS5600 RIGHT` on `CH4`

With `ENCODERS_ENABLED=0`, `robot_rpi_direct_bridge.py` does not read the
encoder bus and instead publishes open-loop `/wheel_odom` from `/cmd_vel`.
When `ENCODERS_ENABLED=1`, it reads both encoders, unwraps their angle, and
computes wheel odometry inside the bridge process.

### 3. Raspberry Pi direct motor control

Current motor control path:

- `GPIO18 -> DRV8833 AIN1`
- `GPIO23 -> DRV8833 AIN2`
- `GPIO19 -> DRV8833 BIN1`
- `GPIO24 -> DRV8833 BIN2`
- `GPIO17 -> DRV8833 SLP` when software sleep control is used

There is no active `Nano <-> UNO` link in the current implementation.

### 4. Legacy Nano serial mode

When `BRIDGE_MODE=serial_legacy` is intentionally enabled:

- Raspberry Pi talks to Nano ESP32 over USB serial, usually `/dev/ttyACM0`
- serial baud is `115200`
- Nano reads `TCA9548A` and `AS5600`
- Nano drives `DRV8833` using pins `D5/D6/D9/D10`
- bridge also publishes `/imu/arduino`

## IMU Data Paths

There are two different IMU paths in the project documentation and codebase.
Only one is the default runtime path today.

### Default runtime path

- `RealSense D455 -> sensor_fusion_cont -> /imu/data`

This is the path configured by default in `../stack/docker-compose.yaml`.

### Legacy / debug path

- `Nano ESP32 -> robot_bridge -> /imu/arduino`

This path is still available for debugging and recording, but it is not the
default IMU source for the stack and it is only present in serial legacy mode.

## Known Mismatches Still Present In The Project

These are important when reading older documents and configs.

### `/wheel_odom` vs `/odom`

The robot bridge publishes:

- `/wheel_odom`

Some legacy documents, scripts, and configs still refer to:

- `/odom`

Examples:

- healthcheck and bag recorder already tolerate both names
- some stack configs still expect `/odom`

For documentation purposes, the current bridge output should be treated as
`/wheel_odom`.

### EKF odometry input

The active stack now has `ENCODERS_ENABLED=0` in both
`bridge_rpi_direct.env` and `slam_cont.env`. That means `robot_bridge` runs
open-loop `/wheel_odom` from `/cmd_vel`, while `slam_cont` starts
`rf2o_laser_odometry` automatically because `START_RF2O=auto`.
`../stack/config/containers/robot_localization.yaml` points EKF `odom0` at
`/odom_rf2o`, so the EKF odometry input now matches the rf2o path.

### Legacy Arduino IMU listener

The current `sensor_fusion_pkg` Arduino mode reads ROS IMU messages from
`/imu/arduino`; it does not open the serial port directly. That keeps serial
ownership in `robot_bridge`.

### Older UNO / micro-ROS documents

Any document that still mentions:

- `UNO R4` as the active motor controller
- `Nano <-> UNO` UART as the main robot architecture
- `BTS7960 / IBT-2`
- `micro-ROS agent`

should be treated as historical unless explicitly marked otherwise.

## Current Recommended Integration Model

The simplest and most consistent current setup is:

1. Raspberry Pi runs the Docker stack.
2. `robot_bridge` runs with `BRIDGE_MODE=rpi_direct`.
3. Raspberry Pi drives `DRV8833` via GPIO.
4. Raspberry Pi reads both `AS5600` encoders through `TCA9548A`.
5. RealSense remains the default source for `/imu/data`.

Legacy serial model:

1. Raspberry Pi runs the Docker stack.
2. `robot_bridge` talks to the Nano over USB serial.
3. Nano reads encoders and optional onboard IMU.
4. Nano directly drives the `DRV8833`.
5. RealSense remains the default source for `/imu/data`.

## Practical Checklist

- Use `BRIDGE_MODE=rpi_direct` for the current stack.
- Connect `DRV8833` directly to Raspberry Pi `GPIO18/GPIO23/GPIO19/GPIO24`.
- Connect both `AS5600` sensors through `TCA9548A` on Raspberry Pi I2C.
- Treat `/wheel_odom` as the current odometry output from the robot bridge.
- Treat `/imu/arduino` as a legacy or debug stream unless you intentionally
  switch the stack away from RealSense IMU.
