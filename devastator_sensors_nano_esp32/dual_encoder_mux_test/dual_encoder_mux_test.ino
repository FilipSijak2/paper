#include <Arduino.h>
#include <Wire.h>
#include <math.h>

// Hardware setup
static const uint8_t MUX_ADDR = 0x70;        // TCA9548A
static const uint8_t AS5600_ADDR = 0x36;     // AS5600 on each mux channel
static const uint8_t MUX_CH_LEFT = 0;        // left encoder channel
static const uint8_t MUX_CH_RIGHT = 4;       // right encoder channel

// AS5600 registers
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
static UnwrapState leftUnwrap;
static UnwrapState rightUnwrap;

bool pingAddress(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool selectMuxChannel(uint8_t channel) {
  if (channel > 7) return false;
  Wire.beginTransmission(MUX_ADDR);
  Wire.write((uint8_t)(1u << channel));
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

bool readEncoderOnMuxChannel(uint8_t channel, EncoderSample &sample) {
  sample = EncoderSample{};

  if (!selectMuxChannel(channel)) {
    return false;
  }

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

void printStartupInfo() {
  Serial.println(F("Dual AS5600 test (Nano ESP32 + TCA9548A)"));
  Serial.println(F("Baud: 115200"));
  Serial.println(F("CSV format: left_cont_deg,right_cont_deg,left_ok,right_ok"));
  Serial.println(F("Open Arduino Serial Plotter for quick visualization."));
  Serial.println();
}

void printI2CSummary() {
  Serial.print(F("MUX @0x70: "));
  Serial.println(pingAddress(MUX_ADDR) ? F("OK") : F("NOT FOUND"));

  EncoderSample left;
  EncoderSample right;
  const bool leftOk = readEncoderOnMuxChannel(MUX_CH_LEFT, left);
  const bool rightOk = readEncoderOnMuxChannel(MUX_CH_RIGHT, right);

  Serial.print(F("Left encoder (ch0): "));
  Serial.println(leftOk ? F("OK") : F("NO RESPONSE"));
  Serial.print(F("Right encoder (ch4): "));
  Serial.println(rightOk ? F("OK") : F("NO RESPONSE"));
  Serial.println();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200);
  delay(800);

  // Force Nano ESP32 I2C to the expected Nano pins (A4=SDA, A5=SCL).
  Wire.begin(A4, A5);
  Wire.setClock(100000);

  printStartupInfo();
  printI2CSummary();
}

void loop() {
  const unsigned long now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleMs = now;

  EncoderSample left;
  EncoderSample right;
  const bool leftOk = readEncoderOnMuxChannel(MUX_CH_LEFT, left);
  const bool rightOk = readEncoderOnMuxChannel(MUX_CH_RIGHT, right);

  float leftContDeg = NAN;
  float rightContDeg = NAN;

  if (leftOk && left.ok) {
    const int32_t leftContRaw = unwrapRaw(left.raw, leftUnwrap);
    leftContDeg = countsToDeg(leftContRaw);
  } else {
    resetUnwrap(leftUnwrap);
  }

  if (rightOk && right.ok) {
    const int32_t rightContRaw = unwrapRaw(right.raw, rightUnwrap);
    rightContDeg = countsToDeg(rightContRaw);
  } else {
    resetUnwrap(rightUnwrap);
  }

  // CSV for Serial Plotter
  if (leftOk) {
    Serial.print(leftContDeg, 3);
  } else {
    Serial.print(F("nan"));
  }
  Serial.print(',');
  if (rightOk) {
    Serial.print(rightContDeg, 3);
  } else {
    Serial.print(F("nan"));
  }
  Serial.print(',');
  Serial.print(leftOk ? 1 : 0);
  Serial.print(',');
  Serial.println(rightOk ? 1 : 0);

  // Human-readable status once per second
  if (now - lastStatusMs >= STATUS_INTERVAL_MS) {
    lastStatusMs = now;

    Serial.print(F("# L raw="));
    Serial.print(left.raw);
    Serial.print(F(" deg="));
    Serial.print(rawToDeg(left.raw), 2);
    Serial.print(F(" md/ml/mh="));
    Serial.print(left.magnetDetected ? 1 : 0);
    Serial.print('/');
    Serial.print(left.magnetTooWeak ? 1 : 0);
    Serial.print('/');
    Serial.print(left.magnetTooStrong ? 1 : 0);

    Serial.print(F(" | R raw="));
    Serial.print(right.raw);
    Serial.print(F(" deg="));
    Serial.print(rawToDeg(right.raw), 2);
    Serial.print(F(" md/ml/mh="));
    Serial.print(right.magnetDetected ? 1 : 0);
    Serial.print('/');
    Serial.print(right.magnetTooWeak ? 1 : 0);
    Serial.print('/');
    Serial.print(right.magnetTooStrong ? 1 : 0);
    Serial.println();

    digitalWrite(LED_BUILTIN, (leftOk && rightOk) ? HIGH : LOW);
  }
}
