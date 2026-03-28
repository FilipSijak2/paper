# bridge_cont

ROS 2 serial bridge container for the current Devastator robot protocol.

## Purpose

The bridge talks to the `Nano ESP32` over USB serial using the project's custom
binary protocol.

It currently:

- subscribes to `/cmd_vel`
- publishes `/wheel_odom`
- publishes `/imu/arduino`
- publishes `/robot_status`

In the current hardware architecture, the Nano is the only active robot
microcontroller and drives the `DRV8833` directly.

## Runtime Defaults

Current stack defaults in `../stack/docker-compose.yaml`:

- `SERIAL_PORT=/dev/ttyACM0`
- `SERIAL_BAUD=115200`
- `IMU_TOPIC=/imu/arduino`

Note:

- the bridge publishes `/wheel_odom`, not `/odom`
- if another consumer expects `/odom`, add a remap or adapter

## Environment Variables

- `SERIAL_PORT`: serial device path
- `SERIAL_BAUD`: baud rate
- `IMU_TOPIC`: ROS topic for the Nano IMU stream
- `RMW_IMPLEMENTATION`: DDS RMW layer

## Docker Compose Example

```yaml
services:
  robot_bridge:
    build: ./bridge_cont
    container_name: robot_bridge_cont
    network_mode: host
    restart: unless-stopped
    environment:
      SERIAL_PORT: /dev/ttyACM0
      SERIAL_BAUD: "115200"
      IMU_TOPIC: /imu/arduino
      RMW_IMPLEMENTATION: rmw_cyclonedds_cpp
    devices:
      - /dev/ttyACM0:/dev/ttyACM0
```

## Data Flow

```text
/cmd_vel
  -> bridge_cont
  -> Nano ESP32
  -> motor control on Nano

Nano ESP32
  -> bridge_cont
  -> /wheel_odom
  -> /imu/arduino
  -> /robot_status
```

## Notes

- Ensure the host user can access the serial device.
- In the stack, the bridge runs with `network_mode: host`.
- The default filtered IMU for the rest of the stack is usually `/imu/data`
  from `sensor_fusion_cont`, while `/imu/arduino` remains useful for debugging
  and bag recording.

## Verifying Data Flow

Inside another ROS container or on the host:

```bash
ros2 topic echo /wheel_odom
ros2 topic echo /imu/arduino
ros2 topic echo /robot_status
ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}" -r 1
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No topics visible | Bridge not running or DDS discovery issue | Confirm container state and ROS network settings |
| `/imu/arduino` empty | Serial not open or Nano not sending packets | Check `/dev/ttyACM0`, baud, USB cable, and firmware |
| `/wheel_odom` missing | Bridge not receiving valid sensor packets | Check serial logs and CRC errors |
| CRC errors climbing | Noise, wrong baud, or protocol mismatch | Confirm `115200`, cable quality, and matching firmware |
