/*
  Devastator Nano ESP32 - Custom Serial Protocol Version
  Robust communication: Host PC ↔ Nano ESP32 ↔ UNO R4
  
  Replaces micro-ROS with custom binary protocol for better stability and debugging.
  
  Architecture:
    - Host PC: Python ROS 2 node bridges custom protocol ↔ standard ROS topics
    - Nano ESP32: Sensor fusion + command distribution (this file)  
    - UNO R4: Motor control + LED visualization

  Hardware:
    - Arduino Nano ESP32
    - IMU: LSM6DSO32 (I2C, Adafruit library)
    - Encoders: 2x AS5600 via TCA9548A I2C multiplexer (addresses resolved)
    - Motor driver BTS7960 handled by UNO R4
    - Link to Host: USB Serial (115200 baud)
    - Link to UNO R4: Serial1 (GPIO16 RX, GPIO17 TX) 115200

  Arduino IDE Setup:
    1. Install "Arduino ESP32 Boards" in Boards Manager.
    2. Libraries: Adafruit LSM6DS, Adafruit BusIO.
    3. Select Board: Arduino Nano ESP32. Upload.
    4. On host run Python bridge:
         python3 robot_serial_bridge.py

  Protocol: 
    Host → ESP32: CommandPacket (22 bytes, includes cmd_vel)
    ESP32 → Host: SensorPacket (66 bytes, includes IMU + encoders + odometry)
    ESP32 → UNO: CommandPacket (22 bytes, motor commands)
    
  Robust features: CRC validation, sequence numbers, timeout handling, error flags.
*/

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LSM6DSO32.h>

// ===== PROTOCOL DEFINITIONS =====
// Custom serial protocol for robust communication
// Host (Python ROS node) ↔ Nano ESP32 ↔ UNO R4

// Protocol version for compatibility checking
static const uint8_t PROTOCOL_VERSION = 1;

// Packet headers for sync and type identification
static const uint32_t SENSOR_PACKET_HEADER = 0xDEADBEEF;
static const uint32_t SENSOR_PACKET_TAIL   = 0xCAFEBABE;

static const uint32_t COMMAND_PACKET_HEADER = 0xFEEDFACE;  
static const uint32_t COMMAND_PACKET_TAIL   = 0xDEADC0DE;

static const uint32_t STATUS_PACKET_HEADER  = 0xABCDEF01;
static const uint32_t STATUS_PACKET_TAIL    = 0x12345678;

// Packet sizes for parsing
static const uint8_t SENSOR_PACKET_SIZE  = 66;  // sizeof(SensorPacket) with __attribute__((packed))
static const uint8_t COMMAND_PACKET_SIZE = 22;  // sizeof(CommandPacket) with __attribute__((packed))
static const uint8_t STATUS_PACKET_SIZE  = 32;

// Sensor data from Nano ESP32 → Host PC (64 bytes total)
struct __attribute__((packed)) SensorPacket {
    uint32_t header;        // 0xDEADBEEF
    uint8_t version;        // Protocol version
    uint8_t sequence;       // Rolling counter (0-255)
    uint16_t flags;         // Status flags (sensor health, etc.)
    
    uint32_t timestamp_ms;  // millis() from ESP32
    
    // IMU data (24 bytes)
    float accel_x;          // m/s²
    float accel_y;
    float accel_z;
    float gyro_x;           // rad/s
    float gyro_y;
    float gyro_z;
    
    // Encoder data (8 bytes)
    float left_angle;       // radians (absolute, unwrapped)
    float right_angle;      // radians (absolute, unwrapped)
    
    // Odometry (computed on ESP32) (12 bytes)
    float odom_x;           // meters
    float odom_y;           // meters  
    float odom_yaw;         // radians
    
    // System health (4 bytes)
    uint16_t battery_mv;    // Battery voltage in millivolts (optional)
    uint8_t temperature;    // Temperature in °C + 50 (so 0-255 maps to -50 to +205°C)
    uint8_t error_flags;    // Error status bits
    
    uint16_t crc16;         // CRC-16/CCITT over bytes 0 to (size-4)
    uint32_t tail;          // 0xCAFEBABE
};

// Command data from Host PC → Nano ESP32 (20 bytes total)
struct __attribute__((packed)) CommandPacket {
    uint32_t header;        // 0xFEEDFACE  
    uint8_t version;        // Protocol version
    uint8_t sequence;       // Rolling counter
    uint16_t timeout_ms;    // Command timeout (default 1200ms)
    
    float linear_x;         // m/s
    float angular_z;        // rad/s
    
    uint16_t crc16;         // CRC-16/CCITT  
    uint32_t tail;          // 0xDEADC0DE
};

// Status/heartbeat from Nano ESP32 → Host PC (32 bytes total)
struct __attribute__((packed)) StatusPacket {
    uint32_t header;        // 0xABCDEF01
    uint8_t version;        // Protocol version  
    uint8_t sequence;       // Rolling counter
    uint16_t flags;         // Status flags
    
    uint32_t uptime_ms;     // System uptime
    uint32_t loop_count;    // Main loop iterations
    uint16_t loop_rate_hz;  // Measured loop rate
    uint16_t free_heap_kb;  // Free heap in KB
    
    char status_msg[12];    // Short status string (null terminated)
    
    uint16_t crc16;         // CRC-16/CCITT
    uint32_t tail;          // 0x12345678
};

// Status flags definitions
#define SENSOR_FLAG_IMU_OK       (1 << 0)
#define SENSOR_FLAG_ENC_LEFT_OK  (1 << 1)  
#define SENSOR_FLAG_ENC_RIGHT_OK (1 << 2)
#define SENSOR_FLAG_MUX_OK       (1 << 3)
#define SENSOR_FLAG_UNO_COMM_OK  (1 << 4)

#define ERROR_FLAG_IMU_FAIL      (1 << 0)
#define ERROR_FLAG_ENC_FAIL      (1 << 1)
#define ERROR_FLAG_COMM_TIMEOUT  (1 << 2)
#define ERROR_FLAG_OVERHEAT      (1 << 3)

// CRC-16/CCITT implementation
static inline uint16_t crc16_ccitt(const uint8_t* data, uint16_t len, uint16_t crc = 0xFFFF) {
    for (uint16_t i = 0; i < len; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t b = 0; b < 8; ++b) {
            if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
            else crc <<= 1;
        }
    }
    return crc;
}

// Packet validation helpers
static inline bool validate_sensor_packet(const SensorPacket* pkt) {
    if (pkt->header != SENSOR_PACKET_HEADER || pkt->tail != SENSOR_PACKET_TAIL) return false;
    if (pkt->version != PROTOCOL_VERSION) return false;
    uint16_t expected = crc16_ccitt((const uint8_t*)pkt, sizeof(SensorPacket) - 6); // -6 for crc+tail
    return expected == pkt->crc16;
}

static inline bool validate_command_packet(const CommandPacket* pkt) {
    if (pkt->header != COMMAND_PACKET_HEADER || pkt->tail != COMMAND_PACKET_TAIL) return false;
    if (pkt->version != PROTOCOL_VERSION) return false;
    uint16_t expected = crc16_ccitt((const uint8_t*)pkt, sizeof(CommandPacket) - 6);
    return expected == pkt->crc16;
}

static inline void build_command_packet(CommandPacket* pkt, float linear, float angular, uint8_t seq = 0) {
    pkt->header = COMMAND_PACKET_HEADER;
    pkt->version = PROTOCOL_VERSION;
    pkt->sequence = seq;
    pkt->timeout_ms = 1200;
    pkt->linear_x = linear;
    pkt->angular_z = angular;
    pkt->tail = COMMAND_PACKET_TAIL;
    pkt->crc16 = crc16_ccitt((const uint8_t*)pkt, sizeof(CommandPacket) - 6);
}

static inline void build_sensor_packet(SensorPacket* pkt, uint8_t seq = 0) {
    pkt->header = SENSOR_PACKET_HEADER;
    pkt->version = PROTOCOL_VERSION;
    pkt->sequence = seq;
    pkt->tail = SENSOR_PACKET_TAIL;
    // CRC filled after data population
}

static inline void finalize_sensor_packet(SensorPacket* pkt) {
    pkt->crc16 = crc16_ccitt((const uint8_t*)pkt, sizeof(SensorPacket) - 6);
}

// ===== END PROTOCOL DEFINITIONS =====

// ---------------- UART to UNO R4 ----------------
HardwareSerial MotorSerial(1); // Serial1
static const int UNO_RX_PIN = 16; // Nano ESP32 RX (from UNO TX) (optional currently unused)
static const int UNO_TX_PIN = 17; // Nano ESP32 TX (to UNO RX)

// ---------------- Protocol Objects ----------------
SensorPacket sensor_packet;
CommandPacket command_packet; 
StatusPacket status_packet;

uint8_t sensor_seq = 0;
uint8_t command_seq = 0;
uint8_t status_seq = 0;

// Command parsing buffer
uint8_t cmd_buffer[COMMAND_PACKET_SIZE];
uint8_t cmd_buffer_pos = 0;

// ---------------- IMU ----------------
Adafruit_LSM6DSO32 imu;

// ---------------- Timing ----------------
static unsigned long last_cmd_time = 0;
static unsigned long last_imu_time = 0;
static unsigned long last_odom_time = 0;
static unsigned long last_status_time = 0;

// Periods
const uint32_t IMU_PERIOD_MS = 50;   // 20 Hz
const uint32_t ODOM_PERIOD_MS = 50;  // 20 Hz
const uint32_t STATUS_PERIOD_MS = 2000;
const uint32_t CMD_TIMEOUT_MS = 1200;

// Kinematics
const float WHEEL_RADIUS = 0.033f;
const float WHEEL_BASE = 0.20f;

// ------------- Encoders (AS5600 via TCA9548A) -------------
// Using I2C multiplexer (e.g. TCA9548A) because both AS5600 share fixed address 0x36.
// Define which multiplexer channels are wired to LEFT and RIGHT encoder modules.
// Channels valid range: 0..7
static const uint8_t MUX_ADDR = 0x70;       // Default TCA9548A address (A0..A2 = GND)
static const uint8_t MUX_CH_LEFT  = 0;      // TCA channel for left encoder
static const uint8_t MUX_CH_RIGHT = 1;      // TCA channel for right encoder
// If you wired differently, just change these two values.

// Encoder state
volatile float left_angle = 0.0f;
volatile float right_angle = 0.0f;
volatile float prev_left_angle = 0.0f;
volatile float prev_right_angle = 0.0f;

// Command
volatile float cmd_linear = 0.0f;
volatile float cmd_angular = 0.0f;

// Odometry pose
float x_pose = 0.0f;
float y_pose = 0.0f;
float yaw = 0.0f;

// Helper function to build command packets (using the protocol-defined structure)
void buildCommand(CommandPacket &pkt, float lin, float ang) {
  pkt.header = COMMAND_PACKET_HEADER;
  pkt.version = PROTOCOL_VERSION;
  pkt.sequence = 0; // Will be set by caller
  pkt.timeout_ms = 1200;
  pkt.linear_x = lin;
  pkt.angular_z = ang;
  pkt.tail = COMMAND_PACKET_TAIL;
  pkt.crc16 = crc16_ccitt(reinterpret_cast<const uint8_t*>(&pkt), sizeof(CommandPacket) - 6);
}

// Forward declarations
bool micro_ros_init();
void cmd_callback(const void* msg_in);
void publish_imu();
void read_encoders();
void publish_odom();
void publish_status(const char* text);
void send_motor_command();

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("Nano ESP32 Custom Protocol v1.0");

  Wire.begin();
  MotorSerial.begin(115200, SERIAL_8N1, UNO_RX_PIN, UNO_TX_PIN);

  // Initialize sensor packet structure
  build_sensor_packet(&sensor_packet, sensor_seq++);
  sensor_packet.flags = 0;
  sensor_packet.error_flags = 0;

  if (!imu.begin_I2C()) {
    Serial.println("IMU init FAIL");
    sensor_packet.error_flags |= ERROR_FLAG_IMU_FAIL;
  } else {
    imu.setAccelRange(LSM6DSO32_ACCEL_RANGE_4_G);
    imu.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
    imu.setAccelDataRate(LSM6DS_RATE_52_HZ);
    imu.setGyroDataRate(LSM6DS_RATE_52_HZ);
    sensor_packet.flags |= SENSOR_FLAG_IMU_OK;
    Serial.println("IMU OK");
  }

  // Test I2C multiplexer
  if (selectMuxChannel(0)) {
    sensor_packet.flags |= SENSOR_FLAG_MUX_OK;
    Serial.println("I2C MUX OK");
  } else {
    Serial.println("I2C MUX FAIL");
  }

  Serial.println("Custom protocol ready - waiting for commands");
  last_cmd_time = millis();
}

void loop() {
  unsigned long now = millis();
  
  // Process incoming commands from host
  process_host_commands();

  // Safety timeout
  if (now - last_cmd_time > CMD_TIMEOUT_MS) { 
    cmd_linear = 0.0f; 
    cmd_angular = 0.0f; 
    sensor_packet.error_flags |= ERROR_FLAG_COMM_TIMEOUT;
  } else {
    sensor_packet.error_flags &= ~ERROR_FLAG_COMM_TIMEOUT;
  }

  // Periodic sensor tasks
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

  // Send commands to UNO R4
  send_motor_command();
}

void process_host_commands() {
  // Read available bytes from USB Serial
  while (Serial.available() > 0) {
    uint8_t byte = Serial.read();
    cmd_buffer[cmd_buffer_pos++] = byte;
    
    // Check if we have a complete packet
    if (cmd_buffer_pos >= COMMAND_PACKET_SIZE) {
      CommandPacket* cmd = (CommandPacket*)cmd_buffer;
      
      if (validate_command_packet(cmd)) {
        // Valid command received
        cmd_linear = cmd->linear_x;
        cmd_angular = cmd->angular_z;
        last_cmd_time = millis();
        sensor_packet.flags |= SENSOR_FLAG_UNO_COMM_OK;
      }
      
      // Reset buffer for next packet
      cmd_buffer_pos = 0;
    }
    
    // Buffer overflow protection
    if (cmd_buffer_pos >= COMMAND_PACKET_SIZE) {
      cmd_buffer_pos = 0;
    }
  }
}

void send_sensor_packet() {
  sensor_packet.timestamp_ms = millis();
  sensor_packet.sequence = sensor_seq++;
  sensor_packet.battery_mv = 12000; // Placeholder - add ADC reading if needed
  sensor_packet.temperature = 75;   // 25°C (temp + 50)
  
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
  status_packet.loop_rate_hz = 1000 / ODOM_PERIOD_MS; // Approximate
  status_packet.free_heap_kb = ESP.getFreeHeap() / 1024;
  strncpy(status_packet.status_msg, "running", 11);
  status_packet.tail = STATUS_PACKET_TAIL;
  status_packet.crc16 = crc16_ccitt((const uint8_t*)&status_packet, sizeof(StatusPacket) - 6);
  
  Serial.write((uint8_t*)&status_packet, sizeof(StatusPacket));
}

void update_imu_data() {
  sensors_event_t accel, gyro, temp;
  if (imu.getEvent(&accel, &gyro, &temp)) {
    sensor_packet.accel_x = accel.acceleration.x;
    sensor_packet.accel_y = accel.acceleration.y;
    sensor_packet.accel_z = accel.acceleration.z;
    sensor_packet.gyro_x = gyro.gyro.x;
    sensor_packet.gyro_y = gyro.gyro.y;
    sensor_packet.gyro_z = gyro.gyro.z;
    sensor_packet.flags |= SENSOR_FLAG_IMU_OK;
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

uint16_t as5600_read_raw(uint8_t addr) {
  Wire.beginTransmission(addr);
  Wire.write(0x0E); // angle high reg
  if (Wire.endTransmission(false) != 0) return 0;
  if (Wire.requestFrom(addr, (uint8_t)2) != 2) return 0;
  uint16_t high = Wire.read();
  uint16_t low  = Wire.read();
  return ((high & 0x0F) << 8) | low; // 12-bit
}

float angle_from_raw(uint16_t raw) { return (float)raw * (2.0f * PI / 4096.0f); }

void read_encoders() {
  // Save previous for delta
  prev_left_angle = left_angle;
  prev_right_angle = right_angle;

  // LEFT encoder
  if (selectMuxChannel(MUX_CH_LEFT)) {
    uint16_t raw_l = as5600_read_raw(0x36);
    if (raw_l != 0) {
      left_angle = angle_from_raw(raw_l);
      sensor_packet.flags |= SENSOR_FLAG_ENC_LEFT_OK;
    } else {
      sensor_packet.flags &= ~SENSOR_FLAG_ENC_LEFT_OK;
    }
  }

  // RIGHT encoder
  if (selectMuxChannel(MUX_CH_RIGHT)) {
    uint16_t raw_r = as5600_read_raw(0x36);
    if (raw_r != 0) {
      right_angle = angle_from_raw(raw_r);
      sensor_packet.flags |= SENSOR_FLAG_ENC_RIGHT_OK;
    } else {
      sensor_packet.flags &= ~SENSOR_FLAG_ENC_RIGHT_OK;
    }
  }

  // Unwrap to avoid discontinuity crossing 2π boundaries
  auto unwrap = [](float prev, float current){
    float diff = current - prev;
    if (diff > PI) diff -= 2*PI; else if (diff < -PI) diff += 2*PI;
    return prev + diff;
  };
  left_angle = unwrap(prev_left_angle, left_angle);
  right_angle = unwrap(prev_right_angle, right_angle);
}

void update_odometry() {
  float d_left = (left_angle - prev_left_angle) * WHEEL_RADIUS;
  float d_right = (right_angle - prev_right_angle) * WHEEL_RADIUS;
  float d_center = 0.5f * (d_left + d_right);
  float d_theta = (d_right - d_left) / WHEEL_BASE;
  
  yaw += d_theta;
  x_pose += d_center * cos(yaw);
  y_pose += d_center * sin(yaw);
  
  // Update sensor packet with odometry
  sensor_packet.odom_x = x_pose;
  sensor_packet.odom_y = y_pose;
  sensor_packet.odom_yaw = yaw;
  
  // Store encoder angles
  sensor_packet.left_angle = left_angle;
  sensor_packet.right_angle = right_angle;
}

void send_motor_command() {
  static unsigned long last_send = 0;
  unsigned long now = millis();
  if (now - last_send < 50) return; // 20 Hz
  last_send = now;
  
  CommandPacket uno_cmd;
  build_command_packet(&uno_cmd, cmd_linear, cmd_angular, command_seq++);
  MotorSerial.write((uint8_t*)&uno_cmd, sizeof(CommandPacket));
}

