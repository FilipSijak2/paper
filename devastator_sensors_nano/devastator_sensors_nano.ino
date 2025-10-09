/*
  Devastator Nano ESP32 (Arduino IDE version)
  Central micro-ROS client: /cmd_vel SUB, /imu/data PUB, /wheel_odom PUB, /system_status PUB
  Sends motor commands to UNO R4 via Serial1 using 16-byte CommandPacket.

  Hardware:
    - Arduino Nano ESP32
    - IMU: LSM6DSO32 (I2C, Adafruit library)
    - Encoders: 2x AS5600 (same address 0x36 -> need solution: I2C multiplexer OR one encoder in analog mode)
    - Motor driver BTS7960 handled by UNO R4
    - Link to UNO R4: Serial1 (GPIO16 RX, GPIO17 TX) 115200

  Arduino IDE Setup:
    1. Install "Arduino ESP32 Boards" in Boards Manager.
    2. Libraries (Library Manager): Adafruit LSM6DS, Adafruit BusIO.
    3. micro_ros_arduino: clone https://github.com/micro-ROS/micro_ros_arduino to Arduino/libraries, run provided scripts (choose esp32 + humble) OR install if available.
    4. Select Board: Arduino Nano ESP32. Upload.
    5. On host run agent:
         ros2 run micro_ros_agent micro_ros_agent serial --dev <PORT>

  CommandPacket (little endian, 16 bytes):
    uint32_t header (0xA55AA55A)
    float    linear
    float    angular
    uint16_t crc16 (CCITT over first 12 bytes)
    uint16_t tail (0x55AA)

  NOTE: Both encoder reads still target 0x36 (placeholder). Adapt once hardware addressing solved.
*/

#include <Arduino.h>
#include <Wire.h>

#include <micro_ros_arduino.h>
#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

#include <geometry_msgs/msg/twist.h>
#include <sensor_msgs/msg/imu.h>
#include <nav_msgs/msg/odometry.h>
#include <std_msgs/msg/string.h>

#include <Adafruit_LSM6DSO32.h>

// ---------------- UART to UNO R4 ----------------
HardwareSerial MotorSerial(1); // Serial1
static const int UNO_RX_PIN = 16; // Nano ESP32 RX (from UNO TX) (optional currently unused)
static const int UNO_TX_PIN = 17; // Nano ESP32 TX (to UNO RX)

// ---------------- micro-ROS objects ----------------
rcl_subscription_t cmd_sub;
rcl_publisher_t imu_pub;
rcl_publisher_t odom_pub;
rcl_publisher_t status_pub;
rcl_node_t node;
rclc_support_t support;
rcl_allocator_t allocator;
rclc_executor_t executor;

geometry_msgs__msg__Twist cmd_msg;
sensor_msgs__msg__Imu imu_msg;
nav_msgs__msg__Odometry odom_msg;
std_msgs__msg__String status_msg;

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

// ---------------- Packet Protocol ----------------
static const uint32_t CMD_HEADER = 0xA55AA55A;
static const uint16_t CMD_TAIL   = 0x55AA;
struct __attribute__((packed)) CommandPacket {
  uint32_t header;
  float linear;
  float angular;
  uint16_t crc;
  uint16_t tail;
};

uint16_t crc16_ccitt(const uint8_t* data, uint16_t len, uint16_t crc = 0xFFFF) {
  for (uint16_t i = 0; i < len; ++i) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t b = 0; b < 8; ++b) {
      if (crc & 0x8000) crc = (crc << 1) ^ 0x1021; else crc <<= 1;
    }
  }
  return crc;
}

void buildCommand(CommandPacket &pkt, float lin, float ang) {
  pkt.header = CMD_HEADER;
  pkt.linear = lin;
  pkt.angular = ang;
  pkt.tail = CMD_TAIL;
  pkt.crc = crc16_ccitt(reinterpret_cast<const uint8_t*>(&pkt), 12);
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
  Serial.println("Nano ESP32 micro-ROS (Arduino IDE) start");

  Wire.begin();
  MotorSerial.begin(115200, SERIAL_8N1, UNO_RX_PIN, UNO_TX_PIN);

  if (!imu.begin_I2C()) {
    Serial.println("IMU init FAIL");
  } else {
    imu.setAccelRange(LSM6DS_ACCEL_RANGE_4_G);
    imu.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
    imu.setAccelDataRate(LSM6DS_RATE_52_HZ);
    imu.setGyroDataRate(LSM6DS_RATE_52_HZ);
    Serial.println("IMU OK");
  }

  if (!micro_ros_init()) {
    Serial.println("micro-ROS init FAILED");
    while (true) { delay(1000); }
  }
  Serial.println("micro-ROS ready");
  last_cmd_time = millis();
}

void loop() {
  unsigned long now = millis();
  rclc_executor_spin_some(&executor, RCL_MS_TO_NS(5));

  if (now - last_cmd_time > CMD_TIMEOUT_MS) { cmd_linear = 0.0f; cmd_angular = 0.0f; }
  if (now - last_imu_time >= IMU_PERIOD_MS) { publish_imu(); last_imu_time = now; }
  if (now - last_odom_time >= ODOM_PERIOD_MS) { read_encoders(); publish_odom(); last_odom_time = now; }
  if (now - last_status_time >= STATUS_PERIOD_MS) { publish_status("ok"); last_status_time = now; }

  send_motor_command();
}

bool micro_ros_init() {
  set_microros_transports();
  allocator = rcl_get_default_allocator();
  if (rclc_support_init(&support, 0, NULL, &allocator) != RCL_RET_OK) return false;
  if (rclc_node_init_default(&node, "devastator_nano", "", &support) != RCL_RET_OK) return false;
  if (rclc_subscription_init_default(&cmd_sub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist), "cmd_vel") != RCL_RET_OK) return false;
  if (rclc_publisher_init_default(&imu_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu), "imu/data") != RCL_RET_OK) return false;
  if (rclc_publisher_init_default(&odom_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry), "wheel_odom") != RCL_RET_OK) return false;
  if (rclc_publisher_init_default(&status_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String), "system_status") != RCL_RET_OK) return false;
  if (rclc_executor_init(&executor, &support.context, 1, &allocator) != RCL_RET_OK) return false;
  if (rclc_executor_add_subscription(&executor, &cmd_sub, &cmd_msg, &cmd_callback, ON_NEW_DATA) != RCL_RET_OK) return false;
  return true;
}

void cmd_callback(const void* msg_in) {
  const geometry_msgs__msg__Twist* m = (const geometry_msgs__msg__Twist*)msg_in;
  cmd_linear = m->linear.x;
  cmd_angular = m->angular.z;
  last_cmd_time = millis();
}

void publish_imu() {
  sensors_event_t accel, gyro, temp;
  if (!imu.getEvent(&accel, &gyro, &temp)) return;
  imu_msg.header.stamp.sec = millis() / 1000;
  imu_msg.header.stamp.nanosec = (millis() % 1000) * 1000000;
  imu_msg.header.frame_id.data = (char*)"imu_link";
  imu_msg.header.frame_id.size = strlen("imu_link");
  imu_msg.linear_acceleration.x = accel.acceleration.x;
  imu_msg.linear_acceleration.y = accel.acceleration.y;
  imu_msg.linear_acceleration.z = accel.acceleration.z;
  imu_msg.angular_velocity.x = gyro.gyro.x;
  imu_msg.angular_velocity.y = gyro.gyro.y;
  imu_msg.angular_velocity.z = gyro.gyro.z;
  rcl_publish(&imu_pub, &imu_msg, NULL);
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
    }
  }

  // RIGHT encoder
  if (selectMuxChannel(MUX_CH_RIGHT)) {
    uint16_t raw_r = as5600_read_raw(0x36);
    if (raw_r != 0) {
      right_angle = angle_from_raw(raw_r);
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

void publish_odom() {
  float d_left = (left_angle - prev_left_angle) * WHEEL_RADIUS;
  float d_right = (right_angle - prev_right_angle) * WHEEL_RADIUS;
  float d_center = 0.5f * (d_left + d_right);
  float d_theta = (d_right - d_left) / WHEEL_BASE;
  yaw += d_theta;
  x_pose += d_center * cos(yaw);
  y_pose += d_center * sin(yaw);
  odom_msg.header.stamp.sec = millis() / 1000;
  odom_msg.header.stamp.nanosec = (millis() % 1000) * 1000000;
  odom_msg.header.frame_id.data = (char*)"odom";
  odom_msg.header.frame_id.size = strlen("odom");
  odom_msg.child_frame_id.data = (char*)"base_link";
  odom_msg.child_frame_id.size = strlen("base_link");
  odom_msg.pose.pose.position.x = x_pose;
  odom_msg.pose.pose.position.y = y_pose;
  odom_msg.pose.pose.position.z = 0.0f;
  float vx = d_center / (ODOM_PERIOD_MS / 1000.0f);
  float wz = d_theta / (ODOM_PERIOD_MS / 1000.0f);
  odom_msg.twist.twist.linear.x = vx;
  odom_msg.twist.twist.angular.z = wz;
  rcl_publish(&odom_pub, &odom_msg, NULL);
}

void publish_status(const char* text) {
  status_msg.data.data = (char*)text;
  status_msg.data.size = strlen(text);
  rcl_publish(&status_pub, &status_msg, NULL);
}

void send_motor_command() {
  static unsigned long last_send = 0;
  unsigned long now = millis();
  if (now - last_send < 50) return; // 20 Hz
  last_send = now;
  CommandPacket pkt; buildCommand(pkt, cmd_linear, cmd_angular);
  MotorSerial.write(reinterpret_cast<uint8_t*>(&pkt), sizeof(pkt));
}
