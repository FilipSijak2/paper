# Hardware Wiring Guide

This guide describes the recommended wiring for the current
`rpi_direct` implementation (Raspberry Pi drives motors and reads encoders
directly). Legacy `serial_legacy` (Nano ESP32 bridge) is documented at the end.

## System Overview (Recommended: `rpi_direct`)

```text
Raspberry Pi 5
   |
   +-- I2C1 (GPIO2/GPIO3) --> TCA9548A --> CH0 --> AS5600 LEFT
   |                                      \-> CH4 --> AS5600 RIGHT
   |
   +-- GPIO PWM/dir -------> DRV8833 -----> LEFT motor
   |                                     \-> RIGHT motor
   |
   \-- USB (optional sensors only, not required for motor/encoder bridge)

External motor PSU ---> DRV8833 VM/VIN
Common GND ----------> RPi + DRV8833 + TCA9548A + AS5600
```

## 1. Raspberry Pi Header Connections

### I2C to TCA9548A

- `RPi pin 1 (3V3)` -> `TCA9548A VCC`
- `RPi pin 6 (GND)` -> `TCA9548A GND`
- `RPi pin 3 (GPIO2 / SDA1)` -> `TCA9548A SDA`
- `RPi pin 5 (GPIO3 / SCL1)` -> `TCA9548A SCL`

### Motor control to DRV8833 (BCM numbering)

- `RPi pin 12 (GPIO18)` -> `DRV8833 AIN1`
- `RPi pin 16 (GPIO23)` -> `DRV8833 AIN2`
- `RPi pin 35 (GPIO19)` -> `DRV8833 BIN1`
- `RPi pin 18 (GPIO24)` -> `DRV8833 BIN2`
- `RPi pin 11 (GPIO17)` -> `DRV8833 SLP` (recommended)

These match `bridge_cont/robot_rpi_direct_bridge.py` defaults and
`stack/config/bridge_rpi_direct.env`.

## 2. TCA9548A Connections

### Main side

- `SDA` <- Raspberry Pi `GPIO2 / SDA1`
- `SCL` <- Raspberry Pi `GPIO3 / SCL1`
- `VCC` <- Raspberry Pi `3V3`
- `GND` <- Raspberry Pi `GND`

### Address pins

- `A0` -> `GND`
- `A1` -> `GND`
- `A2` -> `GND`
- `RESET` -> `3V3` (must stay HIGH)

This gives the default address:

- `0x70`

### Channel use

- `CH0` -> `AS5600 LEFT`
- `CH4` -> `AS5600 RIGHT`

## 3. AS5600 Encoder Connections

Each AS5600:

- `VCC` -> `3V3`
- `GND` -> common ground
- `SDA/SCL` -> through assigned TCA9548A channel (`CH0` or `CH4`)

Mechanical notes:

- use diametrically magnetized magnet
- center magnet above sensor
- keep small stable air gap

If readings are unstable, check mechanics first, then wiring/pin labels.

## 4. DRV8833 Connections

### Logic inputs

- `AIN1` <- `RPi GPIO18`
- `AIN2` <- `RPi GPIO23`
- `BIN1` <- `RPi GPIO19`
- `BIN2` <- `RPi GPIO24`
- `SLP` <- `RPi GPIO17`

### Motor outputs

Left motor:

- one wire -> `AOUT1`
- second wire -> `AOUT2`

Right motor:

- one wire -> `BOUT1`
- second wire -> `BOUT2`

### Power

- `VM` / `VIN` <- external motor supply positive
- `GND` <- external motor supply negative and common system ground

### Control pins

If breakout exposes `nSLEEP` / `SLP` / `STBY`:

- this must be `HIGH` or outputs stay disabled (AOUT/BOUT remain 0 V)
- preferred wiring: `SLP` -> `RPi GPIO17` (`DRV_SLEEP_PIN=17`)
- alternative wiring: `SLP` -> direct `3V3` (`DRV_SLEEP_PIN=-1`)

If breakout exposes `AS` / `BS` (AISEN/BISEN):

- keep both tied to `GND` (unless you intentionally implement current sensing)

`nFAULT` is optional for basic motion.

## 5. Power and Grounding Rules

Logic rail:

- Raspberry Pi `3V3` feeds TCA9548A and AS5600 boards

Motor rail:

- external supply feeds DRV8833 `VM/VIN`

Critical rule:

- all grounds must be common
- Raspberry Pi GND
- TCA9548A GND
- AS5600 GND
- DRV8833 GND
- motor PSU negative

Without common ground, PWM direction control and I2C behavior are unreliable.

## 6. Software Mode Mapping

- `BRIDGE_MODE=rpi_direct` -> use this wiring
- `BRIDGE_MODE=serial_legacy` -> use Nano ESP32 bridge wiring
- if `SLP` is on GPIO, set `DRV_SLEEP_PIN` to that BCM pin (recommended `17`)
- if `SLP` is hardwired to `3V3`, set `DRV_SLEEP_PIN=-1`

If encoders are temporarily unavailable, software fallback can run with:

- `ENCODERS_ENABLED=0`
- `OPEN_LOOP_ODOM_FROM_CMD=1`

in `stack/config/bridge_rpi_direct.env`. Motors still work, odometry becomes
open-loop estimate.

## 7. Legacy Nano Wiring (Optional)

Use only if intentionally running `serial_legacy` mode:

- `Raspberry Pi USB <-> Nano ESP32 USB-C`
- Nano controls DRV8833 pins directly
- Nano reads TCA9548A + AS5600 on Nano I2C pins

Legacy references:

- `CURRENT_WIRING_DIAGRAM.md`
- `devastator_sensors_nano_esp32/devastator_sensors_nano_esp32.ino`
