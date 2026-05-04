#include <Arduino.h>
#include <Wire.h>
#include <math.h>

// Single AS5600 test for Arduino UNO R4 WiFi (direct I2C, no mux).
static const uint8_t AS5600_ADDR = 0x36;
static const uint8_t REG_STATUS = 0x0B;
static const uint8_t REG_RAW_ANGLE = 0x0C;

static const unsigned long SAMPLE_INTERVAL_MS = 50;
static const unsigned long STATUS_INTERVAL_MS = 1000;

struct EncoderSample {
  bool ok = false;
  uint16_t raw = 0;
  uint8_t status = 0;
  bool magnetDetected = false;
  bool magnetTooWeak = false;
  bool magnetTooStrong = false;
};

struct UnwrapState {
  bool initialized = false;
  uint16_t previousRaw = 0;
  int32_t turns = 0;
};

static unsigned long lastSampleMs = 0;
static unsigned long lastStatusMs = 0;
static UnwrapState unwrapState;

bool pingAddress(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool readRegister8(uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(AS5600_ADDR, (uint8_t)1) != 1) {
    return false;
  }
  value = Wire.read();
  return true;
}

bool readRegister12(uint8_t reg, uint16_t &value) {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(AS5600_ADDR, (uint8_t)2) != 2) {
    return false;
  }

  const uint8_t hi = Wire.read();
  const uint8_t lo = Wire.read();
  value = (((uint16_t)hi << 8) | lo) & 0x0FFF;
  return true;
}

bool readEncoder(EncoderSample &sample) {
  sample = EncoderSample{};

  uint8_t status = 0;
  uint16_t raw = 0;
  if (!readRegister8(REG_STATUS, status)) {
    return false;
  }
  if (!readRegister12(REG_RAW_ANGLE, raw)) {
    return false;
  }

  sample.ok = true;
  sample.status = status;
  sample.raw = raw;
  sample.magnetDetected = (status & 0b00100000) != 0;
  sample.magnetTooWeak = (status & 0b00010000) != 0;
  sample.magnetTooStrong = (status & 0b00001000) != 0;
  return true;
}

int32_t unwrapRaw(uint16_t raw, UnwrapState &state) {
  if (!state.initialized) {
    state.initialized = true;
    state.previousRaw = raw;
    return raw;
  }

  const int32_t delta = (int32_t)raw - (int32_t)state.previousRaw;
  if (delta > 2048) {
    state.turns--;
  } else if (delta < -2048) {
    state.turns++;
  }

  state.previousRaw = raw;
  return (state.turns * 4096L) + raw;
}

float rawToDeg(uint16_t raw) {
  return (raw * 360.0f) / 4096.0f;
}

float countsToDeg(int32_t counts) {
  return (counts * 360.0f) / 4096.0f;
}

void resetUnwrap(UnwrapState &state) {
  state.initialized = false;
  state.previousRaw = 0;
  state.turns = 0;
}

void scanI2CBus() {
  Serial.println(F("I2C scan:"));
  bool foundAny = false;
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      foundAny = true;
      Serial.print(F("  found 0x"));
      if (address < 16) Serial.print('0');
      Serial.println(address, HEX);
    }
  }
  if (!foundAny) {
    Serial.println(F("  no I2C devices found"));
  }
}

void printStartupInfo() {
  Serial.println(F("Single AS5600 test (UNO R4 WiFi)"));
  Serial.println(F("Baud: 115200"));
  Serial.println(F("CSV: cont_deg,raw_deg,ok,magnet_ok"));
  Serial.println(F("Use Arduino Serial Plotter for visualization."));
  Serial.println();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200);
  delay(800);

  Wire.begin();
  Wire.setClock(100000);

  printStartupInfo();
  if (pingAddress(AS5600_ADDR)) {
    Serial.println(F("AS5600 @0x36: OK"));
  } else {
    Serial.println(F("AS5600 @0x36: NOT FOUND"));
    scanI2CBus();
  }
}

void loop() {
  const unsigned long now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleMs = now;

  EncoderSample sample;
  const bool ok = readEncoder(sample);
  const bool magnetOk = ok && sample.magnetDetected && !sample.magnetTooWeak && !sample.magnetTooStrong;

  float contDeg = NAN;
  float rawDeg = NAN;
  if (ok) {
    const int32_t contRaw = unwrapRaw(sample.raw, unwrapState);
    contDeg = countsToDeg(contRaw);
    rawDeg = rawToDeg(sample.raw);
  } else {
    resetUnwrap(unwrapState);
  }

  // CSV for serial plotter
  if (ok) {
    Serial.print(contDeg, 3);
  } else {
    Serial.print(F("nan"));
  }
  Serial.print(',');
  if (ok) {
    Serial.print(rawDeg, 3);
  } else {
    Serial.print(F("nan"));
  }
  Serial.print(',');
  Serial.print(ok ? 1 : 0);
  Serial.print(',');
  Serial.println(magnetOk ? 1 : 0);

  if (now - lastStatusMs >= STATUS_INTERVAL_MS) {
    lastStatusMs = now;
    if (ok) {
      Serial.print(F("# raw="));
      Serial.print(sample.raw);
      Serial.print(F(" deg="));
      Serial.print(rawDeg, 2);
      Serial.print(F(" md/ml/mh="));
      Serial.print(sample.magnetDetected ? 1 : 0);
      Serial.print('/');
      Serial.print(sample.magnetTooWeak ? 1 : 0);
      Serial.print('/');
      Serial.print(sample.magnetTooStrong ? 1 : 0);
      Serial.println();
    } else {
      Serial.println(F("# read failed: check VCC/GND/SDA/SCL"));
    }
    digitalWrite(LED_BUILTIN, ok ? HIGH : LOW);
  }
}
