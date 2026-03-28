# Hardware Components

This file lists the hardware that matches the current implementation.

## Core Controller

- `Arduino Nano ESP32`
  - single active robot microcontroller
  - receives commands from the Raspberry Pi over USB serial
  - reads encoders and optional onboard IMU
  - computes wheel odometry
  - directly drives the motor driver

## Motor Stage

- `DRV8833`
  - dual H-bridge motor driver
  - driven directly from Nano GPIO
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

## Host Side

- `Raspberry Pi`
  - runs the Docker stack
  - talks to Nano over USB serial
  - typically exposes the Nano as `/dev/ttyACM0`

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

- USB from Raspberry Pi to Nano ESP32
- external motor power for `DRV8833` and motors
- common ground between Nano, sensors, driver, and motor supply

## Removed From Current Main Path

These items appear in older documents but are not part of the current main
implementation:

- `Arduino UNO R4`
- `BTS7960 / IBT-2`
- `micro-ROS agent`
