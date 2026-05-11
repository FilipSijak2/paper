# Hardware Components

This file lists the hardware that matches the current implementation.

## Core Controller

- `Raspberry Pi 5`
  - runs the Docker stack
  - active `robot_bridge` mode is `rpi_direct`
  - drives the motor driver through GPIO PWM
  - can read wheel encoders through I2C
  - current stack has `ENCODERS_ENABLED=0`, so encoder reads are disabled and
    odometry comes from open-loop bridge odometry plus rf2o in `slam_cont`

- `Arduino Nano ESP32` (legacy / optional)
  - used only when intentionally running `BRIDGE_MODE=serial_legacy`
  - receives commands from the Raspberry Pi over USB serial
  - reads encoders and optional onboard IMU in that mode
  - computes wheel odometry in that mode
  - directly drives the motor driver in that mode

## Motor Stage

- `DRV8833`
  - dual H-bridge motor driver
  - driven directly from Raspberry Pi GPIO in the active stack
  - driven from Nano GPIO only in serial legacy mode
  - powered from an external motor supply

- `2x DC geared motors`
  - one left motor
  - one right motor

## Encoder Stage

- `2x AS5600`
  - magnetic absolute rotary encoders
  - one encoder per wheel

- `TCA9548A`
  - I2C multiplexer
  - required because both AS5600 sensors use the same I2C address
  - active stack address: `0x70`
  - active stack channels: left `CH0`, right `CH4`

## Host Side

- `Raspberry Pi`
  - runs the Docker stack
  - exposes I2C as `/dev/i2c-1`
  - exposes the GPIO chip as `/dev/gpiochip4` on Raspberry Pi 5
  - exposes the Nano as `/dev/ttyACM0` only in serial legacy mode

## Additional Sensors

- `RPLidar`
  - primary laser source for `/scan`

- `Intel RealSense D455`
  - default IMU source for `/imu/data` in the current stack
  - also provides camera streams

- optional `LSM6DSO32`
  - can be connected to the Nano
  - the Nano firmware can include IMU data in the custom bridge stream
  - not the default `/imu/data` source in the current stack

## Power

- USB from Raspberry Pi to Nano ESP32 only when using serial legacy mode
- external motor power for `DRV8833` and motors
- common ground between Raspberry Pi, sensors, driver, and motor supply
- if using serial legacy mode, Nano ground must also be common

## Removed From Current Main Path

These items appear in older documents but are not part of the current main
implementation:

- `Arduino UNO R4`
- `BTS7960 / IBT-2`
- `micro-ROS agent`
