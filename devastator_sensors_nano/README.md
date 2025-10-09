# Devastator Sensors & Control (Nano ESP32)

Role: Central micro-ROS client + sensor fusion + command distribution to UNO R4 (motor actuator).

Hardware used:
- Board: Arduino Nano ESP32
- IMU: LSM6DSO32 (I2C)
- Encoders: 2x AS5600 (I2C, distinct addresses via ADDR variant or multiplexer / alt wiring)
- Motor driver (handled on UNO R4): IBT-2 / BTS7960 modules
- Link to UNO R4: UART (3.3V <-> 5V level shift if needed; R4 is 5V tolerant on RX? If not, use divider.)

## Architecture
Nano ESP32 responsibilities:
- micro-ROS node
- Subscribe: /cmd_vel
- Publish: /imu/data (sensor_msgs/Imu)
- Publish: /wheel_odom (nav_msgs/Odometry) (computed from AS5600 angles)
- Publish: /joint_states (sensor_msgs/JointState) (optional)
- Publish: /system_status (std_msgs/String) (optional minimal heartbeat)
- Send motor command packet over UART to UNO R4 (linear, angular)
- Receive feedback (ticks / angles / optional status) from UNO (not strictly needed if encoders wired to Nano directly)

UNO R4 responsibilities (existing minimal sketch to be replaced later):
- Receive motor command packet (binary)
- Drive BTS7960 bridges (PWM + direction per side)
- Optional: emergency stop logic if timeout
- LED feedback

## Encoder Wiring (AS5600)
Two AS5600 options:
1. Different I2C bus (use Wire and Wire1 if board supports) – simpler if modules fixed at same address.
2. Use PWM or analog output mode on one encoder and I2C on the other.
3. Hardware address hack (if breakout supports ADDR pad) – set one to alternative address (not all boards support).

For this reference implementation we assume:
- Both encoders on I2C using a TCA9548A (I2C multiplexer) OR we sequentially select via powering one at a time (simpler code would just assume a multiplexer; adapt as needed).
- Provided code shows a simple dual-read using two I2C buses abstraction (can be adapted).

If you only have same-address encoders without multiplexer:
- Easiest: Put them on separate microcontrollers OR use analog mode on one.

## Serial Protocol (Nano ESP32 -> UNO R4)
Binary little-endian frames.

CommandPacket (sent at 20 Hz or on change):
- uint32_t header = 0xA55AA55A
- float linear_mps
- float angular_rps
- uint16_t crc16 (over bytes from header to angular)
- uint16_t tail = 0x55AA
Total: 4 + 4 + 4 + 2 + 2 = 16 bytes

(UNO just needs speeds; odometry closed on Nano from encoders.)

FeedbackPacket (if UNO used for any sensing) could mirror similar structure.

CRC: CRC-16/IBM (poly 0xA001) or CRC-16/CCITT (0x1021). Implementation provided in code.

## micro-ROS Memory Notes
ESP32 has enough RAM, but still keep entities minimal. We'll use:
- 1 subscription (cmd_vel)
- 3 publishers (imu, wheel_odom, optionally status)
Add more only if required.

## Build & Flash
PlatformIO `platformio.ini` will be added for Nano ESP32 environment.

## Next Steps
1. Flash Nano ESP32 code.
2. Start micro-ROS agent (serial over USB) on host.
3. Send /cmd_vel and verify UART packets leaving Nano (logic analyzer or Serial debug).
4. Integrate UNO R4 firmware to parse command packets.

---
Adapt wiring details & I2C addressing before deployment.
