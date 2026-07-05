# bridge_cont

ROS 2 robot bridge container for the Devastator robot.

## Active Runtime Mode

The active thesis runtime uses:

```env
BRIDGE_MODE=rpi_direct
DRIVER=drv8833
GPIOCHIP=/dev/gpiochip4
ENCODERS_ENABLED=0
```

In this mode Raspberry Pi drives the DRV8833 motor driver directly through GPIO.

## Current Hardware Assumptions

Active:

- Raspberry Pi 5 GPIO
- DRV8833 motor driver
- left and right motors
- common ground between Raspberry Pi, motor driver and motor supply

Not active in the current setup:

- AS5600 wheel encoders
- TCA9548A I2C multiplexer
- encoder-based odometry
- Nano ESP32 serial bridge as the main motor path
- UNO R4 as the main motor path

If older code still contains encoder-related parameters, treat them as legacy/optional. The current robot should be documented and tested with `ENCODERS_ENABLED=0`.

## ROS Interfaces

Typical interfaces:

- subscribes to `/cmd_vel`
- publishes bridge/motor status topics
- may publish open-loop or placeholder wheel odometry depending on configuration

The navigation/localization stack should not assume reliable wheel encoder odometry in the active configuration. It should use the current LiDAR/SLAM/AMCL/Nav2 pose sources.

## Carpet traction assist

`LINEAR_TRACTION_ASSIST_ENABLED=1` enables command-based static-friction
compensation. After a low-speed linear command remains active for
`LINEAR_TRACTION_DELAY_S`, the bridge gradually raises the minimum motor PWM up
to `LINEAR_TRACTION_MAX_MOTOR_CMD`. Nav2's requested linear and angular
velocities are not changed.

Because the active setup has `ENCODERS_ENABLED=0`, this feature cannot measure a
real wheel stall; it infers that extra torque may be needed from a sustained
drive command. Encoder or motor-current feedback is required for true
resistance detection. Runtime values live in
`stack/config/containers/bridge_rpi_direct.env`.

## Legacy Modes

`serial_legacy` support can remain in the repository for historical or debugging purposes, but it is not the active thesis implementation.

The legacy hardware references include:

- Nano ESP32 custom serial protocol
- AS5600 encoder handling
- TCA9548A multiplexer handling

Do not describe these as the current robot architecture unless they are intentionally reintroduced and tested again.
