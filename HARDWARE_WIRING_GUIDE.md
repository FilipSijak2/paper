# Hardware Wiring Guide

This guide describes the current active wiring for the robot.

## Current Active Wiring

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motors
```

Current assumptions:

- Raspberry Pi 5 is the motor-control computer.
- `bridge_cont` runs in `BRIDGE_MODE=rpi_direct`.
- The motor driver is DRV8833.
- Bridge configuration uses `ENCODERS_ENABLED=0`.
- Robot pose for navigation comes from LiDAR, SLAM, AMCL/Nav2 and available ROS pose topics.

## DRV8833 Pin Mapping

| Raspberry Pi signal | Physical pin | DRV8833 pin / function | Role |
| --- | ---: | --- | --- |
| GPIO17 | 11 | `SLP` / `nSLEEP` | enables DRV8833 |
| GPIO24 | 18 | `BIN2` | right motor input 2 |
| GPIO19 | 35 | `BIN1` | right motor input 1 |
| GPIO23 | 16 | `AIN2` | left motor input 2 |
| GPIO18 | 12 | `AIN1` | left motor input 1 |
| GND | e.g. 6 | `GND` | common ground |

## DRV8833 Wiring Notes

- Connect Raspberry Pi GPIO outputs to the DRV8833 input pins listed above.
- Connect `AOUT1` / `AOUT2` to the left motor.
- Connect `BOUT1` / `BOUT2` to the right motor.
- Power the motors from a motor-suitable external supply.
- Connect Raspberry Pi GND, DRV8833 logic GND and motor supply GND together.
- Hold `SLP` / `nSLEEP` on DRV8833 HIGH through GPIO17.
- Keep motor voltage isolated from Raspberry Pi GPIO pins.

## Power Safety

Use a stable supply for the Raspberry Pi and SSD. Before disconnecting power, run:

```bash
sudo shutdown -h now
```

Then wait until the system has stopped before disconnecting the powerbank or power supply.

## Jetson Wiring / Networking

Jetson Orin is an external AI computer for anomaly detection. It communicates with the Raspberry Pi through rosbridge WebSocket:

```text
Raspberry Pi camera/map/pose topics -> rosbridge WebSocket -> Jetson YOLO
Jetson anomaly topics -> rosbridge WebSocket -> Raspberry Pi -> Foxglove
```

Jetson can connect over Wi-Fi, Ethernet or Tailscale. Foxglove connects to the Raspberry Pi `foxglove_bridge` endpoint.

## Current Visualization Topics

Jetson publishes these anomaly topics back to the Raspberry Pi ROS graph through rosbridge:

- `/anomaly/events`
- `/anomaly/markers`
- `/anomaly/debug_image/compressed`
- `/anomaly/map_snapshot/compressed`
