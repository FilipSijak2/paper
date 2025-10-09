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
#include "crc16.h"
#include "command_protocol.h"

// ---------------- Hardware Config ----------------
// I2C: IMU + Encoders (adapt if using multiplexer)
// If two AS5600 with same address: need TCA9548A or alternative wiring strategy.
// For simplicity: code assumes one on Wire (AS5600 A) and second read by powering alternative channel (placeholder).

// UART to UNO R4
static const int UNO_TX_PIN = 17; // Nano ESP32 -> UNO R4 RX
static const int UNO_RX_PIN = 16; // Nano ESP32 <- UNO R4 TX (optional)
HardwareSerial MotorSerial(1);

// micro-ROS objects
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

// IMU
aAdafruit_LSM6DSO32 imu;  // object name intentionally unique to avoid collision

// Timing
static unsigned long last_cmd_time = 0;
static unsigned long last_imu_time = 0;
static unsigned long last_odom_time = 0;
static unsigned long last_status_time = 0;

// Rates
const uint32_t IMU_PERIOD_MS = 50;   // 20 Hz
const uint32_t ODOM_PERIOD_MS = 50;  // 20 Hz (encoder based)
const uint32_t STATUS_PERIOD_MS = 2000;
const uint32_t CMD_TIMEOUT_MS = 1200;

// Kinematics (example values, adjust)
const float WHEEL_RADIUS = 0.033f;
const float WHEEL_BASE = 0.20f;

// Encoder state (angles in radians from AS5600; using placeholders until reading implemented)
volatile float left_angle = 0.0f;
volatile float right_angle = 0.0f;
volatile float prev_left_angle = 0.0f;
volatile float prev_right_angle = 0.0f;

// Command
volatile float cmd_linear = 0.0f;
volatile float cmd_angular = 0.0f;

// Odometry
float x_pose = 0.0f;
float y_pose = 0.0f;
float yaw = 0.0f;

// Utility forward declarations
void cmd_callback(const void * msg_in);
bool micro_ros_init();
void publish_imu();
void publish_odom();
void publish_status(const char* text);
void send_motor_command();
void read_encoders();

// -------------- Setup --------------
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("Nano ESP32 micro-ROS sensor/controller starting...");

  Wire.begin();

  // UART to UNO R4
  MotorSerial.begin(115200, SERIAL_8N1, UNO_RX_PIN, UNO_TX_PIN);

  // IMU init
  if (!imu.begin_I2C()) {
    Serial.println("IMU (LSM6DSO32) init FAIL");
  } else {
    Serial.println("IMU OK");
    imu.setAccelRange(LSM6DS_ACCEL_RANGE_4_G);
    imu.setGyroRange(LSM6DS_GYRO_RANGE_500_DPS);
    imu.setAccelDataRate(LSM6DS_RATE_52_HZ);
    imu.setGyroDataRate(LSM6DS_RATE_52_HZ);
  }

  if (!micro_ros_init()) {
    Serial.println("micro-ROS init FAILED");
    while (true) { delay(1000); }
  }
  Serial.println("micro-ROS init OK");
  last_cmd_time = millis();
}

// -------------- Loop --------------
void loop() {
  unsigned long now = millis();
  rclc_executor_spin_some(&executor, RCL_MS_TO_NS(5));

  // Timeout safety
  if (now - last_cmd_time > CMD_TIMEOUT_MS) {
    cmd_linear = 0.0f;
    cmd_angular = 0.0f;
  }

  // Periodic tasks
  if (now - last_imu_time >= IMU_PERIOD_MS) { publish_imu(); last_imu_time = now; }
  if (now - last_odom_time >= ODOM_PERIOD_MS) { read_encoders(); publish_odom(); last_odom_time = now; }
  if (now - last_status_time >= STATUS_PERIOD_MS) { publish_status("ok"); last_status_time = now; }

  // Send motor command every loop (could rate-limit to 20 Hz)
  send_motor_command();
}

// -------------- micro-ROS init --------------
bool micro_ros_init() {
  set_microros_transports();
  allocator = rcl_get_default_allocator();
  if (rclc_support_init(&support, 0, NULL, &allocator) != RCL_RET_OK) return false;
  if (rclc_node_init_default(&node, "devastator_nano", "", &support) != RCL_RET_OK) return false;
  if (rclc_subscription_init_default(
        &cmd_sub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
        "cmd_vel") != RCL_RET_OK) return false;
  if (rclc_publisher_init_default(
        &imu_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu),
        "imu/data") != RCL_RET_OK) return false;
  if (rclc_publisher_init_default(
        &odom_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry),
        "wheel_odom") != RCL_RET_OK) return false;
  if (rclc_publisher_init_default(
        &status_pub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, String),
        "system_status") != RCL_RET_OK) return false;
  if (rclc_executor_init(&executor, &support.context, 1, &allocator) != RCL_RET_OK) return false;
  if (rclc_executor_add_subscription(&executor, &cmd_sub, &cmd_msg, &cmd_callback, ON_NEW_DATA) != RCL_RET_OK) return false;
  return true;
}

// -------------- Callbacks --------------
void cmd_callback(const void * msg_in) {
  const geometry_msgs__msg__Twist * msg = (const geometry_msgs__msg__Twist *)msg_in;
  cmd_linear = msg->linear.x;
  cmd_angular = msg->angular.z;
  last_cmd_time = millis();
}

// -------------- IMU Publishing --------------
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
  // Orientation not provided (leave zero)

  rcl_publish(&imu_pub, &imu_msg, NULL);
}

// -------------- Encoder Reading (AS5600 placeholder) --------------
uint16_t read_as5600_raw(uint8_t i2c_addr) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(0x0E); // ANGLE high byte register
  Wire.endTransmission(false);
  Wire.requestFrom(i2c_addr, (uint8_t)2);
  if (Wire.available() < 2) return 0;
  uint16_t high = Wire.read();
  uint16_t low  = Wire.read();
  return ((high & 0x0F) << 8) | low; // 12-bit angle
}

float angle_from_raw(uint16_t raw) {
  return (float)raw * (2.0f * PI / 4096.0f);
}

void read_encoders() {
  // Assuming two encoders accessible somehow; for now same address 0x36 problematic unless hardware solution.
  uint16_t raw_left = read_as5600_raw(0x36);
  delayMicroseconds(150); // small gap
  uint16_t raw_right = read_as5600_raw(0x36); // placeholder: adapt with multiplexer or second bus

  prev_left_angle = left_angle;
  prev_right_angle = right_angle;
  left_angle = angle_from_raw(raw_left);
  right_angle = angle_from_raw(raw_right);

  // Simple unwrap (handle angle discontinuity at 2π)
  auto unwrap = [](float prev, float current) {
    float diff = current - prev;
    if (diff > PI) diff -= 2*PI;
    else if (diff < -PI) diff += 2*PI;
    return prev + diff;
  };
  left_angle = unwrap(prev_left_angle, left_angle);
  right_angle = unwrap(prev_right_angle, right_angle);
}

// -------------- Odometry Publishing --------------
void publish_odom() {
  float d_left = (left_angle - prev_left_angle) * WHEEL_RADIUS;
  float d_right = (right_angle - prev_right_angle) * WHEEL_RADIUS;
  float d_center = (d_left + d_right) * 0.5f;
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
  // Orientation yaw only (simple approximation -> leave quaternion zero or fill minimal later)

  float vx = d_center / (ODOM_PERIOD_MS / 1000.0f);
  float wz = d_theta / (ODOM_PERIOD_MS / 1000.0f);
  odom_msg.twist.twist.linear.x = vx;
  odom_msg.twist.twist.angular.z = wz;

  rcl_publish(&odom_pub, &odom_msg, NULL);
}

// -------------- Status Publishing --------------
void publish_status(const char* text) {
  status_msg.data.data = (char*)text;
  status_msg.data.size = strlen(text);
  rcl_publish(&status_pub, &status_msg, NULL);
}

// -------------- Send motor command to UNO --------------
void send_motor_command() {
  static unsigned long last_send = 0;
  unsigned long now = millis();
  if (now - last_send < 50) return; // 20 Hz
  last_send = now;

  CommandPacket pkt;
  fill_command_packet(pkt, cmd_linear, cmd_angular, crc16_ccitt);
  MotorSerial.write(reinterpret_cast<uint8_t*>(&pkt), sizeof(pkt));
}
