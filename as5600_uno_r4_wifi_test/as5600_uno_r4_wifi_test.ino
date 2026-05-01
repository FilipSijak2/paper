#include <Arduino.h>
#include <Wire.h>

const uint8_t AS5600_ADDRESS = 0x36;

const uint8_t REG_STATUS = 0x0B;
const uint8_t REG_RAW_ANGLE = 0x0C;
const uint8_t REG_ANGLE = 0x0E;
const uint8_t REG_AGC = 0x1A;
const uint8_t REG_MAGNITUDE = 0x1B;

const unsigned long SAMPLE_INTERVAL_MS = 100;
const unsigned long ERROR_PRINT_INTERVAL_MS = 1000;

unsigned long lastSampleTime = 0;
unsigned long lastErrorPrintTime = 0;
unsigned long lastLedToggleTime = 0;
bool ledState = false;
bool sensorSeenOnce = false;
bool havePreviousRawAngle = false;
uint16_t previousRawAngle = 0;
int32_t completedTurns = 0;

struct AS5600Data {
  uint8_t status = 0;
  uint8_t agc = 0;
  uint16_t rawAngle = 0;
  uint16_t scaledAngle = 0;
  uint16_t magnitude = 0;
  bool magnetDetected = false;
  bool magnetTooWeak = false;
  bool magnetTooStrong = false;
};

bool pingDevice(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

bool readRegister8(uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(AS5600_ADDRESS);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(AS5600_ADDRESS, (uint8_t)1) != 1) {
    return false;
  }

  value = Wire.read();
  return true;
}

bool readRegister12(uint8_t reg, uint16_t &value) {
  Wire.beginTransmission(AS5600_ADDRESS);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(AS5600_ADDRESS, (uint8_t)2) != 2) {
    return false;
  }

  const uint8_t highByte = Wire.read();
  const uint8_t lowByte = Wire.read();
  value = ((uint16_t)highByte << 8) | lowByte;
  value &= 0x0FFF;
  return true;
}

bool readSensor(AS5600Data &data) {
  if (!readRegister8(REG_STATUS, data.status)) {
    return false;
  }
  if (!readRegister12(REG_RAW_ANGLE, data.rawAngle)) {
    return false;
  }
  if (!readRegister12(REG_ANGLE, data.scaledAngle)) {
    return false;
  }
  if (!readRegister8(REG_AGC, data.agc)) {
    return false;
  }
  if (!readRegister12(REG_MAGNITUDE, data.magnitude)) {
    return false;
  }

  data.magnetDetected = (data.status & 0b00100000) != 0;
  data.magnetTooWeak = (data.status & 0b00010000) != 0;
  data.magnetTooStrong = (data.status & 0b00001000) != 0;
  return true;
}

void printHexByte(uint8_t value) {
  if (value < 0x10) {
    Serial.print('0');
  }
  Serial.print(value, HEX);
}

void scanI2CBus() {
  Serial.println(F("I2C scan:"));
  bool foundAny = false;

  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      foundAny = true;
      Serial.print(F("  pronaden uredjaj na 0x"));
      printHexByte(address);
      Serial.println();
    }
  }

  if (!foundAny) {
    Serial.println(F("  nema I2C uredjaja na sabirnici"));
  }
}

float countsToDegrees(int32_t counts) {
  return (counts * 360.0f) / 4096.0f;
}

int32_t unwrapAngle(uint16_t rawAngle) {
  if (!havePreviousRawAngle) {
    previousRawAngle = rawAngle;
    havePreviousRawAngle = true;
    return rawAngle;
  }

  const int32_t delta = (int32_t)rawAngle - (int32_t)previousRawAngle;
  if (delta > 2048) {
    completedTurns--;
  } else if (delta < -2048) {
    completedTurns++;
  }

  previousRawAngle = rawAngle;
  return (completedTurns * 4096L) + rawAngle;
}

void updateLed(bool sensorConnected, bool magneticFieldOk) {
  const unsigned long now = millis();

  if (!sensorConnected) {
    if (now - lastLedToggleTime >= 150) {
      ledState = !ledState;
      digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
      lastLedToggleTime = now;
    }
    return;
  }

  if (!magneticFieldOk) {
    if (now - lastLedToggleTime >= 500) {
      ledState = !ledState;
      digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
      lastLedToggleTime = now;
    }
    return;
  }

  ledState = true;
  digitalWrite(LED_BUILTIN, HIGH);
}

void printReading(const AS5600Data &data, int32_t continuousCounts) {
  Serial.print(F("raw="));
  Serial.print(data.rawAngle);
  Serial.print(F("  kut_deg="));
  Serial.print(countsToDegrees(data.rawAngle), 2);
  Serial.print(F("  kontinuirani_deg="));
  Serial.print(countsToDegrees(continuousCounts), 2);
  Serial.print(F("  agc="));
  Serial.print(data.agc);
  Serial.print(F("  magnitude="));
  Serial.print(data.magnitude);
  Serial.print(F("  status_reg=0x"));
  printHexByte(data.status);
  Serial.print(F("  md="));
  Serial.print(data.magnetDetected ? 1 : 0);
  Serial.print(F("  ml="));
  Serial.print(data.magnetTooWeak ? 1 : 0);
  Serial.print(F("  mh="));
  Serial.print(data.magnetTooStrong ? 1 : 0);
  Serial.print(F("  status="));

  if (!data.magnetDetected) {
    Serial.print(F("MAGNET_NIJE_DETEKTIRAN"));
  } else if (data.magnetTooWeak) {
    Serial.print(F("MAGNET_PREDALEKO"));
  } else if (data.magnetTooStrong) {
    Serial.print(F("MAGNET_PREBLIZU"));
  } else {
    Serial.print(F("OK"));
  }

  Serial.println();
}

void printStartupHelp() {
  Serial.println(F("AS5600 test za Arduino UNO R4 WiFi"));
  Serial.println(F("Spojevi:"));
  Serial.println(F("  AS5600 SDA -> UNO R4 SDA"));
  Serial.println(F("  AS5600 SCL -> UNO R4 SCL"));
  Serial.println(F("  AS5600 GND -> UNO R4 GND"));
  Serial.println(F("  AS5600 VCC -> 5V ili 3.3V, ovisno o modulu"));
  Serial.println(F("Napomena: koristi magnet centriran iznad senzora."));
  Serial.println(F("Ako se raw i kut_deg mijenjaju dok okreces magnet, enkoder radi."));
  Serial.println();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200);
  delay(1500);

  Wire.begin();
  Wire.setClock(100000);

  printStartupHelp();

  if (pingDevice(AS5600_ADDRESS)) {
    Serial.println(F("AS5600 je pronaden na adresi 0x36."));
  } else {
    Serial.println(F("AS5600 nije pronaden na adresi 0x36."));
    scanI2CBus();
  }
}

void loop() {
  const unsigned long now = millis();
  const bool sensorConnected = pingDevice(AS5600_ADDRESS);

  if (!sensorConnected) {
    updateLed(false, false);
    havePreviousRawAngle = false;
    completedTurns = 0;
    sensorSeenOnce = false;

    if (now - lastErrorPrintTime >= ERROR_PRINT_INTERVAL_MS) {
      Serial.println(F("Greska: nema odgovora s AS5600 na 0x36. Provjeri VCC, GND, SDA, SCL i magnet."));
      scanI2CBus();
      lastErrorPrintTime = now;
    }
    return;
  }

  AS5600Data data;
  if (!readSensor(data)) {
    updateLed(false, false);
    sensorSeenOnce = false;

    if (now - lastErrorPrintTime >= ERROR_PRINT_INTERVAL_MS) {
      Serial.println(F("Greska: AS5600 je nadjen, ali citanje registara nije uspjelo."));
      lastErrorPrintTime = now;
    }
    return;
  }

  if (!sensorSeenOnce) {
    Serial.println(F("Citanje senzora je aktivno. Okreci magnet i prati promjenu kuta."));
    sensorSeenOnce = true;
  }

  updateLed(true, data.magnetDetected && !data.magnetTooWeak && !data.magnetTooStrong);

  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    const int32_t continuousCounts = unwrapAngle(data.rawAngle);
    printReading(data, continuousCounts);
    lastSampleTime = now;
  }
}
