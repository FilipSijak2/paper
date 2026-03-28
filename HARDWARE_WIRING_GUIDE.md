# Hardware Wiring Guide

This guide describes the recommended wiring for the current `Nano-only`
implementation.

## System Overview

Current hardware topology:

```text
Raspberry Pi
   |
   +-- USB --> Nano ESP32
                  |
                  +-- I2C --> TCA9548A --> AS5600 LEFT
                  |                   \-> AS5600 RIGHT
                  |
                  +-- GPIO --> DRV8833 --> LEFT motor
                  |                    \-> RIGHT motor
                  |
                  \-- optional IMU on I2C
```

## 1. Nano ESP32 Connections

### USB

- `Nano USB-C <-> Raspberry Pi USB`
- carries serial data and Nano logic power

### I2C bus

- `A4 / D21` -> `SDA`
- `A5 / D22` -> `SCL`
- `3V3` -> sensor power rail
- `GND` -> sensor ground rail

## 2. TCA9548A Connections

### Main side

- `SDA` <- Nano `A4 / D21`
- `SCL` <- Nano `A5 / D22`
- `VCC` <- Nano `3V3`
- `GND` <- Nano `GND`

### Address pins

- `A0` -> `GND`
- `A1` -> `GND`
- `A2` -> `GND`

This gives the default address:

- `0x70`

### Channel use

- `CH0` -> `AS5600 LEFT`
- `CH1` -> `AS5600 RIGHT`

## 3. AS5600 Encoder Connections

Each AS5600 uses:

- `VCC` -> Nano `3V3`
- `GND` -> common ground
- `SDA/SCL` -> through its assigned TCA9548A channel

### Mechanical note

Each AS5600 needs:

- a diametrically magnetized magnet
- the magnet centered above the sensor
- a small air gap

If the reading is unstable, the first thing to check is mechanical alignment.

## 4. DRV8833 Connections

### Logic inputs

- `AIN1` <- Nano `D5`
- `AIN2` <- Nano `D6`
- `BIN1` <- Nano `D9`
- `BIN2` <- Nano `D10`

### Motor outputs

For the left motor:

- one motor wire -> `AOUT1`
- the other motor wire -> `AOUT2`

For the right motor:

- one motor wire -> `BOUT1`
- the other motor wire -> `BOUT2`

### Power

- `VM` or `VIN` <- external motor supply positive
- `GND` <- external motor supply negative and common system ground

### Optional control pins

If your breakout exposes `nSLEEP`, `SLP`, or `STBY`:

- keep it at `HIGH`

If your breakout already has a pull-up for that pin, no extra wire is needed.

`nFAULT` is optional and not required for basic operation.

## 5. Power Distribution

### Logic side

- Raspberry Pi USB powers the Nano
- Nano `3V3` powers `TCA9548A` and `AS5600` boards

### Motor side

- external supply powers `DRV8833 VM`
- motors are powered through `DRV8833`

### Ground rule

All grounds must be connected together:

- Raspberry Pi USB ground
- Nano ground
- TCA9548A ground
- AS5600 ground
- DRV8833 ground
- external motor supply ground

## 6. Practical Notes

### Buck converter

A buck converter is not required if:

- Nano is powered by Raspberry Pi USB
- DRV8833 uses its own external motor supply

### Motor direction

If a motor spins opposite to what you expect:

- swap the two motor wires on that side

### Current implementation references

This guide matches:

- `CURRENT_WIRING_DIAGRAM.md`
- `devastator_sensors_nano_esp32/devastator_sensors_nano_esp32.ino`
- `../stack/docker-compose.yaml`
