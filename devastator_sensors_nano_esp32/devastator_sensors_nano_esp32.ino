/*
  Devastator Nano ESP32 - single-controller firmware

  Architecture:
    - Host PC / Raspberry Pi <-> USB serial <-> Nano ESP32
    - Nano ESP32 handles:
      - IMU readout
      - AS5600 encoder readout via TCA9548A
      - odometry computation
      - direct DRV8833 motor control

  Recommended motor wiring:
    - D5  -> DRV8833 AIN1 (left forward)
    - D6  -> DRV8833 AIN2 (left reverse)
    - D9  -> DRV8833 BIN1 (right forward)
    - D10 -> DRV8833 BIN2 (right reverse)
    - DRV8833 nSLEEP/SLP tied HIGH in hardware

  Protocol:
    - Host -> ESP32: CommandPacket (cmd_vel)
    - ESP32 -> Host: SensorPacket + StatusPacket
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LSM6DSO32.h>
#include <string.h>

static const uint8_t PROTOCOL_VERSION = 1;

static const uint32_t SENSOR_PACKET_HEADER = 0xDEADBEEF;
static const uint32_t SENSOR_PACKET_TAIL   = 0xCAFEBABE;
static const uint32_t COMMAND_PACKET_HEADER = 0xFEEDFACE;
static const uint32_t COMMAND_PACKET_TAIL   = 0xDEADC0DE;
static const uint32_t STATUS_PACKET_HEADER  = 0xABCDEF01;
static const uint32_t STATUS_PACKET_TAIL    = 0x12345678;

struct __attribute__((packed)) SensorPacket {
    uint32_t header;
    uint8_t version;
    uint8_t sequence;
    uint16_t flags;
    uint32_t timestamp_ms;
    float accel_x;
    float accel_y;
    float accel_z;
    float gyro_x;
    float gyro_y;
    float gyro_z;
    float left_angle;
    float right_angle;
    float odom_x;
    float odom_y;
    float odom_yaw;
    uint16_t battery_mv;
    uint8_t temperature;
    uint8_t error_flags;
    uint16_t crc16;
    uint32_t tail;
};

struct __attribute__((packed)) CommandPacket {
    uint32_t header;
    uint8_t version;
    uint8_t sequence;
    uint16_t timeout_ms;
    float linear_x;
    float angular_z;
    uint16_t crc16;
    uint32_t tail;
};

struct __attribute__((packed)) StatusPacket {
    uint32_t header;
    uint8_t version;
    uint8_t sequence;
    uint16_t flags;
    uint32_t uptime_ms;
    uint32_t loop_count;
    uint16_t loop_rate_hz;
    uint16_t free_heap_kb;
    char status_msg[12];
    uint16_t crc16;
    uint32_t tail;
};

static const uint8_t SENSOR_PACKET_SIZE  = sizeof(SensorPacket);
static const uint8_t COMMAND_PACKET_SIZE = sizeof(CommandPacket);
static const uint8_t STATUS_PACKET_SIZE  = sizeof(StatusPacket);

static_assert(sizeof(SensorPacket) == 66, "SensorPacket layout changed unexpectedly");
static_assert(sizeof(CommandPacket) == 22, "CommandPacket layout changed unexpectedly");
static_assert(sizeof(StatusPacket) == 38, "StatusPacket layout changed unexpectedly");

#define SENSOR_FLAG_IMU_OK       (1 << 0)
#define SENSOR_FLAG_ENC_LEFT_OK  (1 << 1)
#define SENSOR_FLAG_ENC_RIGHT_OK (1 << 2)
#define SENSOR_FLAG_MUX_OK       (1 << 3)
#define SENSOR_FLAG_CMD_RX_OK    (1 << 4)

#define ERROR_FLAG_IMU_FAIL      (1 << 0)
#define ERROR_FLAG_ENC_FAIL      (1 << 1)
#define ERROR_FLAG_COMM_TIMEOUT  (1 << 2)
#define ERROR_FLAG_OVERHEAT      (1 << 3)

#define LOG_PRINTLN(msg) do { if (ENABLE_SERIAL_DIAGNOSTICS) { Serial.println(msg); } } while (0)

static inline uint16_t crc16_ccitt(const uint8_t* data, uint16_t len, uint16_t crc = 0xFFFF) {
    for (uint16_t i = 0; i < len; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t b = 0; b < 8; ++b) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

static inline bool validate_command_packet(const CommandPacket* pkt) {
    if (pkt->header != COMMAND_PACKET_HEADER || pkt->tail != COMMAND_PACKET_TAIL) return false;
    if (pkt->version != PROTOCOL_VERSION) return false;
    const uint16_t expected = crc16_ccitt((const uint8_t*)pkt, sizeof(CommandPacket) - 6);
    return expected == pkt->crc16;
}

static inline void build_sensor_packet(SensorPacket* pkt, uint8_t seq = 0) {
    pkt->header = SENSOR_PACKET_HEADER;
    pkt->version = PROTOCOL_VERSION;
    pkt->sequence = seq;
    pkt->tail = SENSOR_PACKET_TAIL;
}

static inline void finalize_sensor_packet(SensorPacket* pkt) {
    pkt->crc16 = crc16_ccitt((const uint8_t*)pkt, sizeof(SensorPacket) - 6);
}

SensorPacket sensor_packet;
StatusPacket status_packet;

uint8_t sensor_seq = 0;
uint8_t status_seq = 0;

static const bool ENABLE_SERIAL_DIAGNOSTICS = false;
static const bool LEFT_MOTOR_INVERTED = false;
static const bool RIGHT_MOTOR_INVERTED = false;
static const bool LEFT_ENCODER_INVERTED = false;
static const bool RIGHT_ENCODER_INVERTED = false;

static const uint16_t DEFAULT_COMMAND_TIMEOUT_MS = 1200;
static const uint16_t MIN_COMMAND_TIMEOUT_MS = 100;
static const uint16_t MAX_COMMAND_TIMEOUT_MS = 5000;

static const uint8_t AS5600_ADDR = 0x36;
static const size_t COMMAND_RX_BUFFER_SIZE = COMMAND_PACKET_SIZE * 4;
static const uint8_t COMMAND_HEADER_BYTES[4] = {
    (uint8_t)(COMMAND_PACKET_HEADER & 0xFF),
    (uint8_t)((COMMAND_PACKET_HEADER >> 8) & 0xFF),
    (uint8_t)((COMMAND_PACKET_HEADER >> 16) & 0xFF),
    (uint8_t)((COMMAND_PACKET_HEADER >> 24) & 0xFF),
};

uint8_t cmd_buffer[COMMAND_RX_BUFFER_SIZE];
size_t cmd_buffer_len = 0;

Adafruit_LSM6DSO32 imu;

static unsigned long last_cmd_time = 0;
static unsigned long last_imu_time = 0;
static unsigned long last_odom_time = 0;
static unsigned long last_status_time = 0;

const uint32_t IMU_PERIOD_MS = 50;
const uint32_t ODOM_PERIOD_MS = 50;
const uint32_t STATUS_PERIOD_MS = 2000;

const float WHEEL_RADIUS = 0.033f;
const float WHEEL_BASE = 0.20f;

static const int DRV_AIN1_PIN = 5;
static const int DRV_AIN2_PIN = 6;
static const int DRV_BIN1_PIN = 9;
static const int DRV_BIN2_PIN = 10;

static const uint8_t MUX_ADDR = 0x70;
static const uint8_t MUX_CH_LEFT = 0;
static const uint8_t MUX_CH_RIGHT = 4;

volatile float left_angle = 0.0f;
volatile float right_angle = 0.0f;
volatile float prev_left_angle = 0.0f;
volatile float prev_right_angle = 0.0f;
volatile float cmd_linear = 0.0f;
volatile float cmd_angular = 0.0f;

bool left_encoder_initialized = false;
bool right_encoder_initialized = false;
bool left_encoder_sample_ok = false;
bool right_encoder_sample_ok = false;
uint16_t command_timeout_ms = DEFAULT_COMMAND_TIMEOUT_MS;

float x_pose = 0.0f;
float y_pose = 0.0f;
float yaw = 0.0f;

void process_host_commands();
void send_sensor_packet();
void send_status_packet();
void update_imu_data();
bool selectMuxChannel(uint8_t ch);
bool as5600_read_raw(uint8_t addr, uint16_t* raw_out);
float angle_from_raw(uint16_t raw, bool inverted);
void read_encoders();
void update_odometry();
void stop_motors();
void update_motor_control();
int find_command_header(const uint8_t* data, size_t len);
float unwrap_angle(float previous_unwrapped, float current_wrapped);

void setup() {
  Serial.begin(115200);
  delay(400);
  LOG_PRINTLN(F("Nano ESP32 single-controller firmware"));

  Wire.begin();

  pinMode(DRV_AIN1_PIN, OUTPUT);
  pinMode(DRV_AIN2_PIN, OUTPUT);
  pinMode(DRV_BIN1_PIN, OUTPUT);
  pinMode(DRV_BIN2_PIN, OUTPUT);
  stop_motors();

  build_sensor_packet(&sensor_packet, sensor_seq++);
  sensor_packet.flags = 0;
  sensor_packet.error_flags = 0;

  if (!imu.begin_I2C()) {
    LOG_PRINTLN(F("IMU init FAIL"));
    sensor_packet.error_flags |= ERROR_FLAG_IMU_FAIL;
  } else {
    imu.setAccelRange(LSM6DSO32_ACCEL_RANGE_4_G);
    imu.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
    imu.setAccelDataRate(LSM6DS_RATE_52_HZ);
    imu.setGyroDataRate(LSM6DS_RATE_52_HZ);
    sensor_packet.flags |= SENSOR_FLAG_IMU_OK;
    LOG_PRINTLN(F("IMU OK"));
  }

  if (selectMuxChannel(MUX_CH_LEFT)) {
    sensor_packet.flags |= SENSOR_FLAG_MUX_OK;
    LOG_PRINTLN(F("I2C MUX OK"));
  } else {
    LOG_PRINTLN(F("I2C MUX FAIL"));
  }

  LOG_PRINTLN(F("Custom protocol ready - waiting for commands"));
  last_cmd_time = millis();
}

void loop() {
  const unsigned long now = millis();

  process_host_commands();

  if (now - last_cmd_time > command_timeout_ms) {
    cmd_linear = 0.0f;
    cmd_angular = 0.0f;
    sensor_packet.flags &= ~SENSOR_FLAG_CMD_RX_OK;
    sensor_packet.error_flags |= ERROR_FLAG_COMM_TIMEOUT;
  } else {
    sensor_packet.error_flags &= ~ERROR_FLAG_COMM_TIMEOUT;
  }

  if (now - last_imu_time >= IMU_PERIOD_MS) {
    update_imu_data();
    last_imu_time = now;
  }

  if (now - last_odom_time >= ODOM_PERIOD_MS) {
    read_encoders();
    update_odometry();
    send_sensor_packet();
    last_odom_time = now;
  }

  if (now - last_status_time >= STATUS_PERIOD_MS) {
    send_status_packet();
    last_status_time = now;
  }

  update_motor_control();
}

void process_host_commands() {
  while (Serial.available() > 0) {
    const int incoming = Serial.read();
    if (incoming < 0) {
      break;
    }

    if (cmd_buffer_len < COMMAND_RX_BUFFER_SIZE) {
      cmd_buffer[cmd_buffer_len++] = (uint8_t)incoming;
    } else {
      memmove(cmd_buffer, cmd_buffer + 1, COMMAND_RX_BUFFER_SIZE - 1);
      cmd_buffer[COMMAND_RX_BUFFER_SIZE - 1] = (uint8_t)incoming;
    }
  }

  while (cmd_buffer_len >= sizeof(COMMAND_HEADER_BYTES)) {
    const int header_pos = find_command_header(cmd_buffer, cmd_buffer_len);
    if (header_pos < 0) {
      if (cmd_buffer_len > sizeof(COMMAND_HEADER_BYTES) - 1) {
        const size_t tail_len = sizeof(COMMAND_HEADER_BYTES) - 1;
        memmove(cmd_buffer, cmd_buffer + cmd_buffer_len - tail_len, tail_len);
        cmd_buffer_len = tail_len;
      }
      return;
    }

    if (header_pos > 0) {
      memmove(cmd_buffer, cmd_buffer + header_pos, cmd_buffer_len - (size_t)header_pos);
      cmd_buffer_len -= (size_t)header_pos;
    }

    if (cmd_buffer_len < COMMAND_PACKET_SIZE) {
      return;
    }

    const CommandPacket* cmd = (const CommandPacket*)cmd_buffer;
    if (!validate_command_packet(cmd)) {
      memmove(cmd_buffer, cmd_buffer + 1, cmd_buffer_len - 1);
      cmd_buffer_len -= 1;
      continue;
    }

    cmd_linear = cmd->linear_x;
    cmd_angular = cmd->angular_z;
    command_timeout_ms = constrain(cmd->timeout_ms, MIN_COMMAND_TIMEOUT_MS, MAX_COMMAND_TIMEOUT_MS);
    last_cmd_time = millis();
    sensor_packet.flags |= SENSOR_FLAG_CMD_RX_OK;

    if (cmd_buffer_len > COMMAND_PACKET_SIZE) {
      memmove(cmd_buffer, cmd_buffer + COMMAND_PACKET_SIZE, cmd_buffer_len - COMMAND_PACKET_SIZE);
    }
    cmd_buffer_len -= COMMAND_PACKET_SIZE;
  }
}

void send_sensor_packet() {
  sensor_packet.timestamp_ms = millis();
  sensor_packet.sequence = sensor_seq++;
  sensor_packet.battery_mv = 12000;
  sensor_packet.temperature = 75;

  finalize_sensor_packet(&sensor_packet);
  Serial.write((uint8_t*)&sensor_packet, sizeof(SensorPacket));
}

void send_status_packet() {
  static uint32_t loop_count = 0;
  loop_count++;

  status_packet.header = STATUS_PACKET_HEADER;
  status_packet.version = PROTOCOL_VERSION;
  status_packet.sequence = status_seq++;
  status_packet.flags = sensor_packet.flags;
  status_packet.uptime_ms = millis();
  status_packet.loop_count = loop_count;
  status_packet.loop_rate_hz = 1000 / ODOM_PERIOD_MS;
  status_packet.free_heap_kb = ESP.getFreeHeap() / 1024;
  strncpy(status_packet.status_msg, "running", sizeof(status_packet.status_msg) - 1);
  status_packet.status_msg[sizeof(status_packet.status_msg) - 1] = '\0';
  status_packet.tail = STATUS_PACKET_TAIL;
  status_packet.crc16 = crc16_ccitt((const uint8_t*)&status_packet, sizeof(StatusPacket) - 6);

  Serial.write((uint8_t*)&status_packet, sizeof(StatusPacket));
}

void update_imu_data() {
  sensors_event_t accel;
  sensors_event_t gyro;
  sensors_event_t temp;

  if (imu.getEvent(&accel, &gyro, &temp)) {
    sensor_packet.accel_x = accel.acceleration.x;
    sensor_packet.accel_y = accel.acceleration.y;
    sensor_packet.accel_z = accel.acceleration.z;
    sensor_packet.gyro_x = gyro.gyro.x;
    sensor_packet.gyro_y = gyro.gyro.y;
    sensor_packet.gyro_z = gyro.gyro.z;
    sensor_packet.flags |= SENSOR_FLAG_IMU_OK;
    sensor_packet.error_flags &= ~ERROR_FLAG_IMU_FAIL;
  } else {
    sensor_packet.flags &= ~SENSOR_FLAG_IMU_OK;
    sensor_packet.error_flags |= ERROR_FLAG_IMU_FAIL;
  }
}

bool selectMuxChannel(uint8_t ch) {
  if (ch > 7) return false;
  Wire.beginTransmission(MUX_ADDR);
  Wire.write(1 << ch);
  return Wire.endTransmission() == 0;
}

bool as5600_read_raw(uint8_t addr, uint16_t* raw_out) {
  if (raw_out == nullptr) return false;
  Wire.beginTransmission(addr);
  Wire.write(0x0E);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)2) != 2) return false;
  const uint16_t high = Wire.read();
  const uint16_t low = Wire.read();
  *raw_out = ((high & 0x0F) << 8) | low;
  return true;
}

float angle_from_raw(uint16_t raw, bool inverted) {
  float angle = (float)raw * (2.0f * PI / 4096.0f);
  if (inverted) {
    angle = (2.0f * PI) - angle;
    if (angle >= 2.0f * PI) {
      angle -= 2.0f * PI;
    }
  }
  return angle;
}

int find_command_header(const uint8_t* data, size_t len) {
  if (len < sizeof(COMMAND_HEADER_BYTES)) return -1;
  for (size_t i = 0; i <= len - sizeof(COMMAND_HEADER_BYTES); ++i) {
    if (memcmp(data + i, COMMAND_HEADER_BYTES, sizeof(COMMAND_HEADER_BYTES)) == 0) {
      return (int)i;
    }
  }
  return -1;
}

float unwrap_angle(float previous_unwrapped, float current_wrapped) {
  float previous_wrapped = fmodf(previous_unwrapped, 2.0f * PI);
  if (previous_wrapped < 0.0f) {
    previous_wrapped += 2.0f * PI;
  }

  float diff = current_wrapped - previous_wrapped;
  if (diff > PI) {
    diff -= 2.0f * PI;
  } else if (diff < -PI) {
    diff += 2.0f * PI;
  }

  return previous_unwrapped + diff;
}

void read_encoders() {
  prev_left_angle = left_angle;
  prev_right_angle = right_angle;

  left_encoder_sample_ok = false;
  right_encoder_sample_ok = false;

  if (selectMuxChannel(MUX_CH_LEFT)) {
    uint16_t raw_l = 0;
    if (as5600_read_raw(AS5600_ADDR, &raw_l)) {
      const float wrapped_left = angle_from_raw(raw_l, LEFT_ENCODER_INVERTED);
      if (!left_encoder_initialized) {
        left_angle = wrapped_left;
        prev_left_angle = wrapped_left;
        left_encoder_initialized = true;
      } else {
        left_angle = unwrap_angle(left_angle, wrapped_left);
      }
      left_encoder_sample_ok = true;
    }
  }

  if (selectMuxChannel(MUX_CH_RIGHT)) {
    uint16_t raw_r = 0;
    if (as5600_read_raw(AS5600_ADDR, &raw_r)) {
      const float wrapped_right = angle_from_raw(raw_r, RIGHT_ENCODER_INVERTED);
      if (!right_encoder_initialized) {
        right_angle = wrapped_right;
        prev_right_angle = wrapped_right;
        right_encoder_initialized = true;
      } else {
        right_angle = unwrap_angle(right_angle, wrapped_right);
      }
      right_encoder_sample_ok = true;
    }
  }

  if (left_encoder_sample_ok) {
    sensor_packet.flags |= SENSOR_FLAG_ENC_LEFT_OK;
  } else {
    sensor_packet.flags &= ~SENSOR_FLAG_ENC_LEFT_OK;
    prev_left_angle = left_angle;
  }

  if (right_encoder_sample_ok) {
    sensor_packet.flags |= SENSOR_FLAG_ENC_RIGHT_OK;
  } else {
    sensor_packet.flags &= ~SENSOR_FLAG_ENC_RIGHT_OK;
    prev_right_angle = right_angle;
  }

  if (left_encoder_sample_ok && right_encoder_sample_ok) {
    sensor_packet.error_flags &= ~ERROR_FLAG_ENC_FAIL;
  } else {
    sensor_packet.error_flags |= ERROR_FLAG_ENC_FAIL;
  }
}

void update_odometry() {
  if (!(left_encoder_initialized && right_encoder_initialized &&
        left_encoder_sample_ok && right_encoder_sample_ok)) {
    sensor_packet.left_angle = left_angle;
    sensor_packet.right_angle = right_angle;
    sensor_packet.odom_x = x_pose;
    sensor_packet.odom_y = y_pose;
    sensor_packet.odom_yaw = yaw;
    return;
  }

  const float d_left = (left_angle - prev_left_angle) * WHEEL_RADIUS;
  const float d_right = (right_angle - prev_right_angle) * WHEEL_RADIUS;
  const float d_center = 0.5f * (d_left + d_right);
  const float d_theta = (d_right - d_left) / WHEEL_BASE;

  yaw += d_theta;
  x_pose += d_center * cos(yaw);
  y_pose += d_center * sin(yaw);

  sensor_packet.odom_x = x_pose;
  sensor_packet.odom_y = y_pose;
  sensor_packet.odom_yaw = yaw;
  sensor_packet.left_angle = left_angle;
  sensor_packet.right_angle = right_angle;
}

void stop_motors() {
  analogWrite(DRV_AIN1_PIN, 0);
  analogWrite(DRV_AIN2_PIN, 0);
  analogWrite(DRV_BIN1_PIN, 0);
  analogWrite(DRV_BIN2_PIN, 0);
}

void update_motor_control() {
  float left_speed = cmd_linear - (cmd_angular * WHEEL_BASE / 2.0f);
  float right_speed = cmd_linear + (cmd_angular * WHEEL_BASE / 2.0f);

  if (LEFT_MOTOR_INVERTED) {
    left_speed = -left_speed;
  }
  if (RIGHT_MOTOR_INVERTED) {
    right_speed = -right_speed;
  }

  left_speed = constrain(left_speed, -1.0f, 1.0f);
  right_speed = constrain(right_speed, -1.0f, 1.0f);

  const int left_pwm = (int)(fabsf(left_speed) * 255.0f);
  const int right_pwm = (int)(fabsf(right_speed) * 255.0f);

  if (left_speed >= 0.0f) {
    analogWrite(DRV_AIN1_PIN, left_pwm);
    analogWrite(DRV_AIN2_PIN, 0);
  } else {
    analogWrite(DRV_AIN1_PIN, 0);
    analogWrite(DRV_AIN2_PIN, left_pwm);
  }

  if (right_speed >= 0.0f) {
    analogWrite(DRV_BIN1_PIN, right_pwm);
    analogWrite(DRV_BIN2_PIN, 0);
  } else {
    analogWrite(DRV_BIN1_PIN, 0);
    analogWrite(DRV_BIN2_PIN, right_pwm);
  }
}
