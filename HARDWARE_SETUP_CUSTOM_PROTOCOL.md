# Custom Serial Protocol - Hardware Setup Guide

## Overview
Custom serial protocol system for reliable robot communication without micro-ROS complexity.

## Architecture
```
Host PC (ROS 2) ↔ USB ↔ Nano ESP32 ↔ UART ↔ UNO R4 WiFi
                     ↓ I2C sensors      ↓ Motors+LEDs
                   IMU + Encoders    BTS7960 + Matrix
```

## Required Hardware

### Controllers
- **Arduino Nano ESP32** (ESP32-S3, ~320KB SRAM) - Main controller
- **Arduino UNO R4 WiFi** (RA4M1, 32KB SRAM) - Motor controller

### Sensors  
- **LSM6DSO32** - 6-axis IMU (I2C)
- **2x AS5600** - Magnetic encoders (I2C)
- **TCA9548A** - I2C multiplexer (resolves AS5600 address conflict)

### Actuators
- **2x IBT-2/BTS7960** - Motor driver modules
- **2x DC Motors** - Geared motors with magnets for encoders
- **LED Matrix** - Built-in UNO R4 8x12 matrix

## Wiring Connections

### Nano ESP32 ↔ Host PC
```
Nano ESP32 USB-C ←→ Host PC USB-A/C
- Protocol: Custom binary packets over USB serial
- Baud rate: 115200
- No micro-ROS agent needed!
```

### Nano ESP32 ↔ UNO R4 Communication
```
Nano ESP32    →    UNO R4
   TX1 (D17)  →    RX (D0)
   RX1 (D18)  →    TX (D1)  
   GND        →    GND
```

### Nano ESP32 ↔ I2C Sensors
```
Nano ESP32    →    TCA9548A Multiplexer
   SDA (D21)  →    SDA
   SCL (D22)  →    SCL
   3.3V       →    VCC
   GND        →    GND

TCA9548A Ch0  →    LSM6DSO32 IMU
   SDA        →    SDA  
   SCL        →    SCL
   3.3V       →    VCC/VIN
   GND        →    GND

TCA9548A Ch1  →    AS5600 Encoder #1 (Left)
   SDA        →    SDA
   SCL        →    SCL  
   3.3V       →    VCC
   GND        →    GND

TCA9548A Ch2  →    AS5600 Encoder #2 (Right)
   SDA        →    SDA
   SCL        →    SCL
   3.3V       →    VCC  
   GND        →    GND
```

### UNO R4 ↔ Motor Drivers
```
UNO R4        →    IBT-2 Module #1 (Left Motor)
   D2         →    L_PWM
   D3         →    R_PWM  
   D4         →    L_EN
   D5         →    R_EN
   5V         →    VCC
   GND        →    GND

UNO R4        →    IBT-2 Module #2 (Right Motor)  
   D6         →    L_PWM
   D7         →    R_PWM
   D8         →    L_EN
   D9         →    R_EN
   5V         →    VCC (shared)
   GND        →    GND (shared)

IBT-2 #1      →    Left DC Motor
   M+         →    Motor positive
   M-         →    Motor negative

IBT-2 #2      →    Right DC Motor
   M+         →    Motor positive  
   M-         →    Motor negative
```

### Power Supply
```
12V Power Supply:
   +12V  →  IBT-2 Motor Supply (both modules)
   GND   →  Common ground

USB Power:
   Host PC USB  →  Nano ESP32 (powers Nano + sensors)
   USB/Barrel   →  UNO R4 (powers UNO + logic)
```

## Protocol Packets

### 1. SensorPacket (Nano ESP32 → Host PC)
```
64 bytes total:
- Header: 0xDEADBEEF
- Version: 1
- Sequence number
- Flags (sensor status)
- Timestamp (ms)
- IMU: accel_xyz, gyro_xyz (6 floats)
- Encoders: left_angle, right_angle (2 floats)  
- Odometry: x, y, yaw (3 floats)
- Battery voltage (mV)
- Temperature (°C)
- CRC-16/CCITT
- Tail: 0xCAFEBABE

Rate: 20 Hz
```

### 2. CommandPacket (Host PC → Nano ESP32 → UNO R4)
```
20 bytes total:
- Header: 0xFEEDFACE
- Version: 1
- Sequence number  
- Timeout (ms)
- Linear velocity X (m/s)
- Angular velocity Z (rad/s)
- CRC-16/CCITT
- Tail: 0xDEADC0DE

Rate: On cmd_vel updates
```

### 3. StatusPacket (Nano ESP32 → Host PC)
```
32 bytes total:
- Header: 0xABCDEF01
- Diagnostic info
- Error codes
- System health
- CRC-16/CCITT
- Tail: 0x12345678

Rate: 1 Hz
```

## Software Setup

### 1. Arduino IDE Setup
```bash
# Install boards:
- ESP32 Arduino Core (for Nano ESP32)
- Arduino UNO R4 boards

# Libraries needed:
- Adafruit LSM6DSO32 (IMU)
- ArduinoGraphics (LED matrix)
- Arduino_LED_Matrix (UNO R4)
```

### 2. Upload Firmware
```bash
# Upload to Nano ESP32:
File → Open → devastator_sensors_nano/devastator_sensors_nano.ino
Board: "Arduino Nano ESP32"
Upload

# Upload to UNO R4:
File → Open → devastator_controler_r4/devastator_controler_r4.ino  
Board: "Arduino UNO R4 WiFi"
Upload
```

### 3. ROS 2 Bridge Setup
```bash
# Install Python dependencies
pip install -r bridge_requirements.txt

# Run bridge (Linux example)
python3 robot_serial_bridge.py --port /dev/ttyUSB0 --baud 115200

# Windows example
python robot_serial_bridge.py --port COM3 --baud 115200
```

### 4. Test ROS Topics
```bash
# View sensor data
ros2 topic echo /imu/data
ros2 topic echo /wheel_odom
ros2 topic echo /robot_status

# Send movement commands  
ros2 topic pub /cmd_vel geometry_msgs/Twist "{linear: {x: 0.2}, angular: {z: 0.1}}"
```

## Debugging Features

### Serial Monitor (Arduino IDE)
- Connect to Nano ESP32
- View sensor readings, packet stats, errors
- Debug I2C communication issues

### ROS Bridge Logging
- CRC validation errors
- Packet sync issues  
- Serial connection status
- Communication statistics

### LED Matrix Status (UNO R4)
- Movement patterns show cmd_vel activity
- Error patterns indicate communication problems  
- Heartbeat shows system alive

## Advantages vs micro-ROS

✅ **Stability**: No XRCE-DDS transport issues  
✅ **Memory**: 32KB UNO R4 RAM sufficient  
✅ **Debugging**: Hex dump analysis, clear error codes  
✅ **Latency**: Direct serial, no middleware overhead  
✅ **Reliability**: CRC validation, timeout handling  
✅ **Simplicity**: Standard Arduino Serial, no agents

## Troubleshooting

### Serial Connection Issues
```bash
# Linux: Check device permissions
sudo usermod -a -G dialout $USER
ls -l /dev/ttyUSB*

# Windows: Check COM port in Device Manager
# Verify cable supports data (not just power)
```

### I2C Sensor Issues
```
# Check TCA9548A multiplexer channels:
- LSM6DSO32 should appear on channel 0
- AS5600 #1 should appear on channel 1  
- AS5600 #2 should appear on channel 2
```

### Motor Control Issues
```
# Verify IBT-2 connections:
- Check PWM signal generation (oscilloscope)
- Verify enable pins are HIGH
- Check 12V motor supply voltage
```

This custom protocol provides the same functionality as micro-ROS but with much better reliability and debugging capabilities!