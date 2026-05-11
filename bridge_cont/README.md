# bridge_cont

ROS 2 robot bridge container for Devastator, with two runtime modes:

- `serial_legacy` (default): Nano ESP32 custom serial protocol
- `rpi_direct`: direct Raspberry Pi GPIO + I2C hardware control

The Docker image default is `serial_legacy`, but the current runtime stack in
`../stack/.env` uses `BRIDGE_MODE=rpi_direct`.

## Purpose

`bridge_cont` subscribes to `/cmd_vel` and publishes robot feedback topics.

### `serial_legacy` mode

Uses `robot_serial_bridge.py`:

- subscribes to `/cmd_vel`
- publishes `/wheel_odom`
- publishes `/imu/arduino`
- publishes `/robot_status`

### `rpi_direct` mode

Uses `robot_rpi_direct_bridge.py`:

- subscribes to `/cmd_vel`
- drives `DRV8833` directly from RPi GPIO PWM
- reads `AS5600` encoders through `TCA9548A` on I2C
- publishes `/wheel_odom`
- publishes `/robot_status`

Note:

- `rpi_direct` does not publish `/imu/arduino`
- bridge output odometry topic remains `/wheel_odom`
- motors must stay on external supply (`DRV8833 VM/VIN`), with common GND to RPi

## Runtime Defaults

Image defaults:

- `BRIDGE_MODE=serial_legacy`
- `SERIAL_PORT=/dev/ttyUSB0`
- `SERIAL_BAUD=115200`
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`

Current stack overrides:

- `BRIDGE_MODE=rpi_direct`
- `BRIDGE_SERIAL_DEVICE=/dev/null`
- `BRIDGE_I2C_DEVICE=/dev/i2c-1`
- `BRIDGE_GPIOMEM_DEVICE=/dev/gpiochip4`
- `ENCODERS_ENABLED=0`
- `OPEN_LOOP_ODOM_FROM_CMD=0` (`robot_rpi_direct_bridge.py` still forces
  open-loop odometry when encoders are disabled)

## Environment Variables

### Common

- `BRIDGE_MODE`: `serial_legacy` or `rpi_direct`
- `RMW_IMPLEMENTATION`: DDS RMW layer
- `STATUS_PERIOD_S`: status publish period

### `serial_legacy`

- `SERIAL_PORT`: serial device path
- `SERIAL_BAUD`: baud rate
- `IMU_TOPIC`: ROS topic for Nano IMU stream
- `COMMAND_TIMEOUT_MS`
- `WATCHDOG_TIMEOUT_S`
- `SERIAL_RETRY_DELAY_S`

### `rpi_direct`

- `I2C_BUS` (default `1`)
- `I2C_MUX_ADDR` (default `0x70`)
- `AS5600_ADDR` (default `0x36`)
- `LEFT_MUX_CHANNEL` (default `0`)
- `RIGHT_MUX_CHANNEL` (default `4`)
- `WHEEL_RADIUS_M` (default `0.033`)
- `WHEEL_BASE_M` (default `0.20`)
- `CONTROL_PERIOD_S` (default `0.02`)
- `COMMAND_TIMEOUT_MS` (default `1200`)
- `PWM_FREQUENCY_HZ` (default `1000`)
- `DRV_AIN1_PIN` (default `18`, BCM)
- `DRV_AIN2_PIN` (default `23`, BCM)
- `DRV_BIN1_PIN` (default `19`, BCM)
- `DRV_BIN2_PIN` (default `24`, BCM)
- `DRV_SLEEP_PIN` (default `-1`, disabled)
- `LEFT_MOTOR_INVERTED` (`0`/`1`)
- `RIGHT_MOTOR_INVERTED` (`0`/`1`)
- `LEFT_ENCODER_INVERTED` (`0`/`1`)
- `RIGHT_ENCODER_INVERTED` (`0`/`1`)
- `RPI_LGPIO_CHIP` (optional, recommended `4` on Raspberry Pi 5)
- `ENCODERS_ENABLED` (`1`/`0`, default `1`)
- `OPEN_LOOP_ODOM_FROM_CMD` (`1`/`0`, default `0`, auto-enabled when encoders are disabled)

No-encoder fallback mode:

- set `ENCODERS_ENABLED=0`
- keep motor pins configured
- bridge still publishes `/wheel_odom` from integrated `/cmd_vel` (open-loop estimate)

## Docker Compose Examples

### Legacy Nano (serial)

```yaml
services:
  robot_bridge:
    build: ./bridge_cont
    container_name: robot_bridge_cont
    network_mode: host
    restart: unless-stopped
    environment:
      BRIDGE_MODE: serial_legacy
      SERIAL_PORT: /dev/ttyACM0
      SERIAL_BAUD: "115200"
      IMU_TOPIC: /imu/arduino
      RMW_IMPLEMENTATION: rmw_cyclonedds_cpp
    devices:
      - /dev/ttyACM0:/dev/ttyACM0
```

### Direct RPi hardware

```yaml
services:
  robot_bridge:
    build: ./bridge_cont
    container_name: robot_bridge_cont
    network_mode: host
    restart: unless-stopped
    environment:
      BRIDGE_MODE: rpi_direct
      I2C_BUS: "1"
      I2C_MUX_ADDR: "0x70"
      AS5600_ADDR: "0x36"
      LEFT_MUX_CHANNEL: "0"
      RIGHT_MUX_CHANNEL: "4"
      DRV_AIN1_PIN: "18"
      DRV_AIN2_PIN: "23"
      DRV_BIN1_PIN: "19"
      DRV_BIN2_PIN: "24"
      ENCODERS_ENABLED: "0"
      OPEN_LOOP_ODOM_FROM_CMD: "1"
      WHEEL_RADIUS_M: "0.033"
      WHEEL_BASE_M: "0.20"
      RMW_IMPLEMENTATION: rmw_cyclonedds_cpp
    devices:
      - /dev/i2c-1:/dev/i2c-1
      - /dev/gpiochip4:/dev/gpiochip4
```

## Data Flow

### Data Flow: `serial_legacy`

```text
/cmd_vel
  -> bridge_cont
  -> Nano ESP32
  -> DRV8833 + encoders on Nano

Nano ESP32
  -> bridge_cont
  -> /wheel_odom
  -> /imu/arduino
  -> /robot_status
```

### Data Flow: `rpi_direct`

```text
/cmd_vel
  -> bridge_cont
  -> RPi GPIO (DRV8833)

RPi I2C (TCA9548A -> AS5600 x2)
  -> bridge_cont
  -> /wheel_odom
  -> /robot_status
```

## Verifying Data Flow

Inside another ROS container or on the host:

```bash
ros2 topic echo /wheel_odom
ros2 topic echo /robot_status
ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}" -r 1
```

For legacy serial mode only:

```bash
ros2 topic echo /imu/arduino
```
