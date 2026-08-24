# Raspberry Pi Motor Bridge

The deployed bridge drives a DRV8833 directly from Raspberry Pi 5 GPIO.

```env
BRIDGE_MODE=rpi_direct
ENCODERS_ENABLED=0
```

The exact GPIO pins, velocity limits and motor-assist values are maintained in `robot-stack/config/containers/bridge_rpi_direct.env`. That file is the runtime source of truth.

## ROS interfaces

- subscribes to `/cmd_vel`
- publishes bridge status and open-loop odometry
- reads corrected yaw-rate feedback from `/imu/base_link_corrected` for adaptive rotation power

Because wheel encoders are disabled, the bridge integrates open-loop odometry from commanded velocity. Navigation uses LiDAR, SLAM, AMCL and corrected IMU data to constrain localization.

## Hardware

- Raspberry Pi 5
- DRV8833 motor driver
- left and right DC motors
- separate motor supply with a common ground

See [the current wiring diagram](../CURRENT_WIRING_DIAGRAM.md) for the deployed pin mapping.
