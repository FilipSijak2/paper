# Raspberry Pi Motor Bridge

The deployed bridge drives a DRV8833 directly from Raspberry Pi 5 GPIO.

```env
BRIDGE_MODE=rpi_direct
ENCODERS_ENABLED=0
```

GPIO pins, velocity limits and motor-assist values are maintained in
`robot-stack/config/containers/bridge_rpi_direct.env`. Surface dynamics are
loaded afterward from `robot-stack/config/drive_profiles/<profile>.env`, so the
selected profile can override transition behavior without duplicating hardware
configuration.

The bridge can apply a per-wheel PWM slew limit. Explicit zero commands still
stop immediately, while a direction reversal ramps through zero and observes a
short neutral interval before energizing the opposite direction. It publishes
the final signed normalized outputs on `/motor_pwm` for calibration and bag
analysis.

Both transition behaviors are controlled by one switch:

```env
MOTOR_SLEW_ENABLED=1  # PWM ramp + reversal neutral interlock enabled
MOTOR_SLEW_ENABLED=0  # both disabled; target PWM is applied immediately
```

`MOTOR_SLEW_RATE_UP`, `MOTOR_SLEW_RATE_DOWN` and
`MOTOR_REVERSAL_NEUTRAL_S` are ignored while the switch is disabled. Immediate
zero-command stopping is independent of the switch.

## ROS interfaces

- subscribes to `/cmd_vel`
- publishes bridge status and open-loop odometry
- publishes final signed left/right normalized motor output on `/motor_pwm`
- reads corrected yaw-rate feedback from `/imu/base_link_corrected` for adaptive rotation power

Because wheel encoders are disabled, the bridge integrates open-loop odometry from commanded velocity. Navigation uses LiDAR, SLAM, AMCL and corrected IMU data to constrain localization.

## Hardware

- Raspberry Pi 5
- DRV8833 motor driver
- left and right DC motors
- separate motor supply with a common ground

See [the current wiring diagram](../CURRENT_WIRING_DIAGRAM.md) for the deployed pin mapping.
