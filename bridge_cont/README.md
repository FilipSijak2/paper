# bridge_cont

ROS 2 Serial Bridge container for custom Devastator robot protocol.

## Purpose
Bridges custom binary protocol over USB serial from Nano ESP32 into ROS 2 topics (/imu/data, /wheel_odom, /robot_status) and subscribes to /cmd_vel.

## Environment Variables
- SERIAL_PORT: Path to serial device (default /dev/ttyUSB0)
- SERIAL_BAUD: Baud rate (default 115200)
- RMW_IMPLEMENTATION: DDS RMW layer (default rmw_cyclonedds_cpp)

## Docker Compose Snippet
```
services:
  bridge:
    build: ./bridge_cont
    container_name: bridge_cont
    restart: unless-stopped
    environment:
      SERIAL_PORT: /dev/ttyUSB0
      SERIAL_BAUD: "115200"
      RMW_IMPLEMENTATION: rmw_cyclonedds_cpp
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    networks:
      - ros
    healthcheck:
      test: ["CMD", "bash", "-c", "source /opt/ros/humble/setup.bash && ros2 topic list >/dev/null 2>&1"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

## Notes
Ensure user on host has permission to access the serial device (dialout group on Linux). All ROS 2 nodes must share network/subnet for DDS discovery (Compose bridge network is fine).

### Integration / DDS Discovery
ROS 2 (CycloneDDS) performs peer discovery via multicast on the Docker network. Using a single user-defined bridge network (e.g. `networks: ros`) allows automatic discovery; no manual ROS_DOMAIN_ID changes required unless you want isolation.

If other containers already set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, they will communicate transparently. If using mixed RMW implementations, align them by setting the same env var in each container.

### Windows / WSL2 Considerations
If running Docker Desktop with WSL2 and the serial device is on Windows host (COMx):
1. Enable serial device passthrough (Docker Desktop Settings → Resources → "Use the WSL 2 based engine").
2. Use a USB-to-serial adapter visible to WSL (check `dmesg | grep ttyUSB`).
3. Map the discovered `/dev/ttyUSB*` into the container's `/dev/ttyUSB0`.

If the device only appears as `COM3` in Windows, use a tool like `usbipd-win` to attach it into WSL:
```
usbipd list
usbipd attach --busid <BUSID>
```
Then re-run `ls /dev/ttyUSB*` inside WSL to find the mapped port.

### Verifying Data Flow
Inside any other ROS container (same network):
```
source /opt/ros/humble/setup.bash
ros2 topic echo /wheel_odom
ros2 topic echo /imu/data
ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}" -r 1
```

### Troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| No topics visible | Different networks | Put all containers on same compose network |
| /imu/data empty | Serial not open | Check device mapping & permissions |
| CRC errors climbing | Noise / wrong baud | Confirm 115200 on firmware & cable quality |
| Discovery delay | Multicast blocked | Avoid host network isolation or custom firewall |