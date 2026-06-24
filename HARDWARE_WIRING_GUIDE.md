# Hardware Wiring Guide

This guide describes the **current active** wiring for the robot. Earlier documentation described an encoder-based setup with AS5600 sensors and a TCA9548A I2C multiplexer. That is no longer the active configuration.

## Current Active Wiring

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motors
```

Current assumptions:

- Raspberry Pi 5 is the motor-control computer.
- `bridge_cont` runs in `BRIDGE_MODE=rpi_direct`.
- The motor driver is DRV8833.
- Wheel encoders are not used.
- The TCA9548A multiplexer is not used.
- AS5600 sensors are not used in the active runtime.
- Nano ESP32 / serial bridge is legacy only.

## DRV8833 Wiring Notes

The exact GPIO pin mapping is defined in the active bridge configuration, not hardcoded in this document. The important electrical rules are:

- connect Raspberry Pi GPIO outputs to the DRV8833 input pins used by the active config
- connect DRV8833 motor outputs to the left and right motors
- power the motors from a motor-suitable supply, not from the Raspberry Pi 5V rail
- connect Raspberry Pi GND, DRV8833 logic GND and motor supply GND together
- ensure `SLP` / `nSLEEP` on DRV8833 is held HIGH
- avoid connecting motor voltage directly to Raspberry Pi GPIO pins

## Power Safety

Use a stable supply for the Raspberry Pi and SSD. Avoid pulling power while Linux is running. Before disconnecting power, run:

```bash
sudo shutdown -h now
```

Then wait until the system has stopped before disconnecting the powerbank or power supply.

## Not Used In The Active Setup

Do not wire these as part of the current baseline configuration:

- TCA9548A I2C multiplexer
- AS5600 left/right wheel encoders
- encoder magnet assemblies
- encoder-related I2C wiring
- Nano ESP32 serial bridge for normal motor control

These are legacy/experimental references only. If they are reintroduced later, the architecture and documentation should be updated again.

## Jetson Wiring / Networking

Jetson Orin is not wired into the Raspberry Pi GPIO path. It is an external AI computer:

```text
Raspberry Pi camera/map/pose topics -> rosbridge WebSocket -> Jetson YOLO
Jetson anomaly topics -> rosbridge WebSocket -> Raspberry Pi -> Foxglove
```

Jetson should connect over Wi-Fi, Ethernet or Tailscale. It should not join the Raspberry Pi ROS 2 DDS graph directly for the anomaly pipeline.
