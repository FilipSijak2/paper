# Custom Serial Protocol - Legacy Hardware Setup Guide

This guide documents the legacy `Nano-only` hardware architecture used when
`BRIDGE_MODE=serial_legacy` is intentionally enabled. The active runtime stack
in `../stack/.env` currently uses `BRIDGE_MODE=rpi_direct`, so Raspberry Pi
GPIO/I2C wiring is the default deployment path.

## Overview

The serial legacy robot controller architecture is:

```text
Host PC / Raspberry Pi (ROS 2)
    <- custom binary protocol over USB serial ->
Arduino Nano ESP32
    |- I2C -> TCA9548A -> AS5600 LEFT
    |- I2C -> TCA9548A -> AS5600 RIGHT
    \- GPIO -> DRV8833 -> LEFT and RIGHT motors
```

There is no active `UNO R4` motor-controller stage in this version.

## Required Hardware

### Controllers

- `Arduino Nano ESP32` - single robot controller
- `Raspberry Pi` or host PC running the ROS 2 stack

### Sensors

- `TCA9548A` I2C multiplexer
- `2x AS5600` magnetic rotary encoder
- optional `LSM6DSO32` IMU on the Nano I2C bus

### Actuators

- `DRV8833` dual H-bridge motor driver
- `2x DC geared motors`

### Power Wiring

- USB from Raspberry Pi to Nano ESP32
- separate motor supply for `DRV8833`

## Wiring Summary

### Raspberry Pi <-> Nano ESP32

```text
Nano ESP32 USB-C <-> Raspberry Pi USB
- custom binary protocol
- 115200 baud
- also provides Nano logic power
```

### Nano ESP32 <-> TCA9548A

```text
Nano ESP32    ->    TCA9548A
 A4 / D21 SDA ->    SDA
 A5 / D22 SCL ->    SCL
 3V3          ->    VCC
 GND          ->    GND

TCA9548A address:
 A0 -> GND
 A1 -> GND
 A2 -> GND
 address = 0x70
```

### TCA9548A <-> AS5600 encoders

```text
TCA9548A CH0 -> AS5600 LEFT
 SDA/SCL     -> SDA/SCL

TCA9548A CH4 -> AS5600 RIGHT
 SDA/SCL     -> SDA/SCL

Both AS5600 boards:
 VCC -> Nano 3V3
 GND -> common ground
```

Current firmware channel assignment:

- `CH0` = left encoder
- `CH4` = right encoder

### Nano ESP32 <-> DRV8833

```text
Nano ESP32 -> DRV8833
 D5         -> AIN1
 D6         -> AIN2
 D9         -> BIN1
 D10        -> BIN2
```

### DRV8833 <-> Motors

```text
DRV8833 -> LEFT motor
 AOUT1  -> motor wire 1
 AOUT2  -> motor wire 2

DRV8833 -> RIGHT motor
 BOUT1  -> motor wire 1
 BOUT2  -> motor wire 2
```

If a wheel spins in the wrong direction, swap the two motor wires for that
side.

### Power

```text
External motor supply:
 + -> DRV8833 VM / VIN
 - -> DRV8833 GND

Nano power:
 Raspberry Pi USB -> Nano ESP32
```

Important:

- all grounds must be common
- `DRV8833` motor supply does not come from the Raspberry Pi
- a buck converter is not required if Nano is powered over USB and the motor
  driver has its own external supply

## Protocol Packets

### CommandPacket

Direction:

- `Host -> Nano ESP32`

Purpose:

- carries `cmd_vel` style motion commands

Size:

- `22 bytes`

### SensorPacket

Direction:

- `Nano ESP32 -> Host`

Contents:

- IMU data
- left/right encoder angles
- odometry pose
- basic health fields

Size:

- `66 bytes`

Rate:

- `20 Hz`

### StatusPacket

Direction:

- `Nano ESP32 -> Host`

Purpose:

- periodic diagnostics and health summary

Size:

- `38 bytes`

Rate:

- every `2000 ms` in the current firmware

## Software Setup

### 1. Arduino IDE

Install:

- `ESP32 Arduino Core`
- `Adafruit LSM6DS`
- `Adafruit BusIO`

### 2. Upload firmware

Upload:

- `devastator_sensors_nano_esp32/devastator_sensors_nano_esp32.ino`

Board:

- `Arduino Nano ESP32`

### 3. ROS bridge

Serial legacy runtime stack configuration:

- `robot_bridge` container
- `BRIDGE_MODE=serial_legacy`
- serial device: `/dev/ttyACM0`
- baud: `115200`

### 4. Verify topics

```bash
ros2 topic echo /wheel_odom
ros2 topic echo /imu/arduino
ros2 topic echo /robot_status
ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.2}, angular: {z: 0.1}}"
```

## Notes About IMU Usage

The current stack defaults to:

- `RealSense -> sensor_fusion_cont -> /imu/data`

The Nano IMU stream is still useful for:

- debugging
- bag recording
- fallback experiments

## Troubleshooting

### No serial bridge data

- confirm the Nano appears as `/dev/ttyACM0`
- confirm the bridge is using `115200`
- confirm the USB cable supports data, not just power

### No encoder movement

- confirm `TCA9548A` is at `0x70`
- confirm left encoder is on `CH0`
- confirm right encoder is on `CH4`
- confirm the magnet is centered above the AS5600

### Motors do not move

- confirm external motor power is present on `DRV8833 VM`
- confirm `nSLEEP` is high if your breakout requires it
- confirm Nano pins `D5/D6/D9/D10` are wired correctly

### Robot drives opposite direction

- swap the two wires on the affected motor
