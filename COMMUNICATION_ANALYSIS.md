# Current Communication Analysis

This document describes the communication model that matches the current
implementation in this repository.

## Current Architecture

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
  +-- laser_driver -> /scan
  +-- slam_cont / nav_cont consume ROS topics

Physical robot:
  Raspberry Pi <-> USB <-> Nano ESP32
                           |
                           +-- I2C -> TCA9548A -> AS5600 LEFT
                           |                  \-> AS5600 RIGHT
                           |
                           +-- GPIO -> DRV8833 -> LEFT / RIGHT motor
```

Supported alternative (software mode switch):

```text
Raspberry Pi / Docker stack
  |
  +-- robot_bridge (BRIDGE_MODE=rpi_direct)
  |      |
  |      +-- /cmd_vel      -> RPi GPIO -> DRV8833
  |      +-- /wheel_odom   <- RPi I2C (TCA9548A -> AS5600 x2)
  |      +-- /robot_status <- RPi direct bridge
  |
  +-- realsense_cont -> sensor_fusion_cont -> /imu/data
```

## Active Communication Layers

### 1. Raspberry Pi <-> Nano ESP32

Current active transport:

- USB serial
- custom binary protocol
- `115200` baud
- runtime stack default device: `/dev/ttyACM0`

Active bridge container:

- `robot_bridge` in `../stack/docker-compose.yaml`

Published ROS topics from the bridge:

- `/wheel_odom`
- `/imu/arduino`
- `/robot_status`

In `BRIDGE_MODE=rpi_direct`, `/imu/arduino` is not published.

Subscribed ROS topics:

- `/cmd_vel`

### 2. Nano ESP32 internal sensor bus

Current sensor bus on Nano:

- `I2C` on `A4/D21` and `A5/D22`
- `TCA9548A` at `0x70`
- `AS5600 LEFT` on `CH0`
- `AS5600 RIGHT` on `CH4`

The Nano firmware reads both encoders, unwraps their angle, and computes wheel
odometry locally before sending it to the bridge.

### 3. Nano ESP32 direct motor control

Current motor control path:

- `D5  -> DRV8833 AIN1`
- `D6  -> DRV8833 AIN2`
- `D9  -> DRV8833 BIN1`
- `D10 -> DRV8833 BIN2`

There is no active `Nano <-> UNO` link in the current implementation.

## IMU Data Paths

There are two different IMU paths in the project documentation and codebase.
Only one is the default runtime path today.

### Default runtime path

- `RealSense D455 -> sensor_fusion_cont -> /imu/data`

This is the path configured by default in `../stack/docker-compose.yaml`.

### Legacy / debug path

- `Nano ESP32 -> robot_bridge -> /imu/arduino`

This path is still available for debugging and recording, but it is not the
default IMU source for the stack.

## Known Mismatches Still Present In The Project

These are important when reading older documents and configs.

### `/wheel_odom` vs `/odom`

The robot serial bridge currently publishes:

- `/wheel_odom`

Some legacy documents, scripts, and configs still refer to:

- `/odom`

Examples:

- healthcheck and bag recorder already tolerate both names
- some stack configs still expect `/odom`

For documentation purposes, the current bridge output should be treated as
`/wheel_odom`.

### Legacy Arduino IMU listener

The project still contains `sensor_fusion_cont/arduino_listener.py`, which
expects line-based text IMU data such as `IMU,...` or `RAW,...`.

The current Nano firmware in this repository uses a binary packet protocol for
the bridge, so that legacy listener is not the primary path for the current
Nano implementation.

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
2. `robot_bridge` talks to the Nano over USB serial.
3. Nano reads encoders and optional onboard IMU.
4. Nano directly drives the `DRV8833`.
5. RealSense remains the default source for `/imu/data`.

Alternative model (no Nano):

1. Raspberry Pi runs the Docker stack.
2. `robot_bridge` runs with `BRIDGE_MODE=rpi_direct`.
3. RPi directly drives `DRV8833` via GPIO.
4. RPi reads both `AS5600` encoders through `TCA9548A`.
5. RealSense remains the default source for `/imu/data`.

## Practical Checklist

- Use `Nano ESP32` as the only robot microcontroller.
- Connect the Pi to Nano via USB.
- Connect `DRV8833` directly to Nano `D5/D6/D9/D10`.
- Connect both `AS5600` sensors through `TCA9548A`.
- Treat `/wheel_odom` as the current odometry output from the robot bridge.
- Treat `/imu/arduino` as a legacy or debug stream unless you intentionally
  switch the stack away from RealSense IMU.
