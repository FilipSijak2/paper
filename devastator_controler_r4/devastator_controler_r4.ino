// Arduino UNO R4 WiFi + micro-ROS Humble (ULTRA MINIMAL)
// Goal: Achieve successful micro-ROS handshake with minimal RAM usage.
// Features kept: cmd_vel subscription + motor actuation.
// Features removed temporarily: IMU publish, encoder I2C, LED matrix graphics (only simple blink), patterns array.
// After confirming this builds & runs, re-enable features incrementally.
#include <Arduino.h>
// Removed Wire (I2C) include to save a little flash/RAM since encoder & IMU are disabled

// micro-ROS core
// NOTE: Removed manual profile/limit macros because micro_ros_arduino is precompiled.
// Defining them here prevented the proper inclusion of the serial platform struct
// leading to: 'field platform has incomplete type uxrSerialPlatform'.
// Any real memory reduction at middleware level requires rebuilding the library
// with a custom Micro XRCE-DDS config, not redefining macros in the sketch.
#include <micro_ros_arduino.h>
#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

// ROS message types
// Keep only essential message types (reduce RAM usage)
#include <geometry_msgs/msg/twist.h>
// IMU removed for now

// Hardware libraries
// Hardware libraries
// IMU library removed to save memory

// LED Matrix for visualization (re-added minimal version)
#include <ArduinoGraphics.h>
#include <Arduino_LED_Matrix.h>
ArduinoLEDMatrix matrix;

// Hardware configuration
const int RPWM_R = 9;   // Right motor PWM
const int LPWM_R = 10;  // Right motor DIR
const int RPWM_L = 5;   // Left motor PWM  
const int LPWM_L = 6;   // Left motor DIR

// Robot parameters
const float WHEEL_BASE = 0.20f;
// Wheel radius not needed now

// I2C communication with Nano ESP32 encoder processor
// Encoder disabled

// Hardware instances
// Removed hardware heavy objects

// micro-ROS objects (minimal)
rcl_subscription_t cmd_sub;
rcl_node_t node;
rclc_executor_t executor;
rclc_support_t support;
rcl_allocator_t allocator;

// ROS messages (minimal)
geometry_msgs__msg__Twist cmd_msg;
// No IMU message now

// Control variables
volatile float cmd_linear = 0.0f;
volatile float cmd_angular = 0.0f;
unsigned long last_cmd_time = 0;
const unsigned long CMD_TIMEOUT = 1200; // command timeout

// Robot state for LED display
enum RobotState {
  IDLE,
  MOVING_FORWARD,
  MOVING_BACKWARD,
  TURNING_LEFT,
  TURNING_RIGHT,
  ERROR_STATE,
  CONNECTING
};

RobotState current_state = CONNECTING;
unsigned long last_led_toggle = 0;
bool led_state = false;
unsigned long last_display_update = 0;
const unsigned long DISPLAY_UPDATE_INTERVAL = 300; // ms

// Minimal 12x8 patterns (3 x uint32_t) kept very small to save RAM (const -> flash)
// Neutral / idle face
const uint32_t pattern_idle[3] = {
  0x18180018, // simple dots
  0x00000000,
  0x18000018
};
// Moving (forward/turn) animation frame A
const uint32_t pattern_move_a[3] = {
  0x00001800,
  0x00181800,
  0x00001800
};
// Moving animation frame B
const uint32_t pattern_move_b[3] = {
  0x00180000,
  0x00181800,
  0x00180000
};
// Error / timeout (cross)
const uint32_t pattern_error[3] = {
  0x81001881,
  0x00181800,
  0x81001881
};
// Connecting (blink)
const uint32_t pattern_connect[3] = {
  0x00000000,
  0x00180000,
  0x00000000
};

void updateLEDDisplay();
void displayPattern(const uint32_t p[3]);

// Patterns removed to save flash/RAM; single LED used instead.

// Function prototypes
void cmd_callback(const void * msg_in);
bool setupMicroROS();
void updateMotorControl();
void updateRobotState();
void blinkStatus();
uint32_t freeMemory();

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Arduino R4 WiFi Robot Controller with micro-ROS Humble");
  Serial.println("Init status LED (pin 13)...");
  pinMode(LED_BUILTIN, OUTPUT);
  matrix.begin();
  displayPattern(pattern_connect);
  
  // Motor pins
  pinMode(RPWM_R, OUTPUT);
  pinMode(LPWM_R, OUTPUT);
  pinMode(RPWM_L, OUTPUT);
  pinMode(LPWM_L, OUTPUT);
  
  // Stop motors initially
  analogWrite(RPWM_R, 0);
  analogWrite(LPWM_R, 0);
  analogWrite(RPWM_L, 0);
  analogWrite(LPWM_L, 0);
  
  // I2C skipped for now
  
  Serial.println("IMU disabled in ultra-minimal build");
  
  Serial.println("Setting up micro-ROS...");
  // Setup micro-ROS
  if (!setupMicroROS()) {
    Serial.println("micro-ROS setup failed!");
    current_state = ERROR_STATE;
    // Turn LED solid ON to indicate error (matrix disabled)
    digitalWrite(LED_BUILTIN, HIGH);
    return; // stay minimal; could loop forever if preferred
  }
  
  Serial.println("Arduino R4 WiFi Robot Controller ready!");
  Serial.print("Approx free RAM (bytes): ");
  Serial.println(freeMemory());
  // Status publisher removed to save RAM
  current_state = IDLE;
  last_cmd_time = millis();
}

void loop() {
  unsigned long now = millis();
  
  // Execute micro-ROS callbacks
  rclc_executor_spin_some(&executor, RCL_MS_TO_NS(10));
  
  // Update robot state based on commands
  updateRobotState();
  
  // Control motors
  updateMotorControl();
  
  blinkStatus();

  // LED matrix pattern update (independent of built-in LED blink)
  if (now - last_display_update >= DISPLAY_UPDATE_INTERVAL) {
    updateLEDDisplay();
    last_display_update = now;
  }

  static unsigned long last_mem = 0;
  if (now - last_mem > 5000) {
    Serial.print("[RAM] Free: ");
    Serial.println(freeMemory());
    last_mem = now;
  }
}

bool setupMicroROS() {
  Serial.println("Setting micro-ROS transport (generic)...");
  set_microros_transports();
  allocator = rcl_get_default_allocator();
  if (rclc_support_init(&support, 0, NULL, &allocator) != RCL_RET_OK) {
    Serial.println("support init FAIL");
    return false;
  }
  if (rclc_node_init_default(&node, "devastator_r4", "", &support) != RCL_RET_OK) {
    Serial.println("node init FAIL");
    return false;
  }
  if (rclc_subscription_init_default(
        &cmd_sub, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
        "cmd_vel") != RCL_RET_OK) {
    Serial.println("cmd_vel sub FAIL");
    return false;
  }
  // IMU publisher removed in minimal variant
  if (rclc_executor_init(&executor, &support.context, 1, &allocator) != RCL_RET_OK) {
    Serial.println("executor init FAIL");
    return false;
  }
  if (rclc_executor_add_subscription(&executor, &cmd_sub, &cmd_msg, &cmd_callback, ON_NEW_DATA) != RCL_RET_OK) {
    Serial.println("exec add sub FAIL");
    return false;
  }
  Serial.println("micro-ROS minimal OK");
  return true;
}

void cmd_callback(const void * msg_in) {
  const geometry_msgs__msg__Twist * msg = (const geometry_msgs__msg__Twist *)msg_in;
  cmd_linear = msg->linear.x;
  cmd_angular = msg->angular.z;
  last_cmd_time = millis();
  
  Serial.print("Received cmd_vel: linear=");
  Serial.print(cmd_linear);
  Serial.print(", angular=");
  Serial.println(cmd_angular);
}

void updateRobotState() {
  unsigned long now = millis();
  
  // Check for command timeout
  if (now - last_cmd_time > CMD_TIMEOUT) {
    if (current_state != IDLE && current_state != ERROR_STATE) {
      current_state = IDLE;
      cmd_linear = 0.0f;
      cmd_angular = 0.0f;
    }
  }
  
  // Determine state based on commands
  if (current_state != ERROR_STATE) {
    if (abs(cmd_linear) < 0.01 && abs(cmd_angular) < 0.01) {
      current_state = IDLE;
    } else if (abs(cmd_angular) > 0.1) {
      current_state = (cmd_angular > 0) ? TURNING_LEFT : TURNING_RIGHT;
    } else if (cmd_linear > 0.01) {
      current_state = MOVING_FORWARD;
    } else if (cmd_linear < -0.01) {
      current_state = MOVING_BACKWARD;
    }
  }
}

void blinkStatus() {
  unsigned long now = millis();
  unsigned interval = 400;
  if (current_state == ERROR_STATE) interval = 150;
  else if (current_state == CONNECTING) interval = 250;
  if (now - last_led_toggle >= interval) {
    led_state = !led_state;
    digitalWrite(LED_BUILTIN, led_state ? HIGH : LOW);
    last_led_toggle = now;
  }
}

void updateLEDDisplay() {
  static bool anim_toggle = false;
  const uint32_t *pat = pattern_idle;
  switch (current_state) {
    case IDLE: pat = pattern_idle; break;
    case MOVING_FORWARD:
    case MOVING_BACKWARD:
    case TURNING_LEFT:
    case TURNING_RIGHT:
      pat = anim_toggle ? pattern_move_a : pattern_move_b;
      anim_toggle = !anim_toggle;
      break;
    case ERROR_STATE: pat = pattern_error; break;
    case CONNECTING: pat = pattern_connect; break;
  }
  displayPattern(pat);
}

void displayPattern(const uint32_t p[3]) {
  // The library expects a pointer to 3 uint32_t values representing the 12x8 frame
  matrix.loadFrame(p);
}

void updateMotorControl() {
  // Simple differential drive kinematics
  float left_speed = cmd_linear - (cmd_angular * WHEEL_BASE / 2.0f);
  float right_speed = cmd_linear + (cmd_angular * WHEEL_BASE / 2.0f);
  
  // Constrain speeds to [-1.0, 1.0]
  left_speed = constrain(left_speed, -1.0f, 1.0f);
  right_speed = constrain(right_speed, -1.0f, 1.0f);
  
  // Convert to PWM (0-255)
  int left_pwm = abs(left_speed * 255);
  int right_pwm = abs(right_speed * 255);
  
  // Left motor control
  if (left_speed >= 0) {
    analogWrite(RPWM_L, left_pwm);
    analogWrite(LPWM_L, 0);
  } else {
    analogWrite(RPWM_L, 0);
    analogWrite(LPWM_L, left_pwm);
  }
  
  // Right motor control
  if (right_speed >= 0) {
    analogWrite(RPWM_R, right_pwm);
    analogWrite(LPWM_R, 0);
  } else {
    analogWrite(RPWM_R, 0);
    analogWrite(LPWM_R, right_pwm);
  }
}

// IMU, encoder and status removed in ultra-minimal variant

// Simple free memory approximation (stack pointer vs heap end).
// Works for bare-metal style Arduino cores; may be approximate on this board.
extern unsigned int _sbrk_r(struct _reent*, ptrdiff_t); // forward declare to avoid pulling in large malloc metadata
uint32_t freeMemory() {
  // Use linker symbols if available (common names for ARM GCC newlib). If not, fallback to stack-heap diff.
  char stack_var; // on stack
  // These externs may not exist; if they don't, the compiler will optimize them out unless referenced.
  extern char _end;      // end of bss
  extern char _estack;   // top of stack (origin + size)
  // Heuristic: current stack address minus current heap end.
  // micro_ros_arduino uses malloc; we can query __malloc_free_list indirectly but keep it minimal.
  char* heap_end = (char*)malloc(0); // calling malloc(0) returns current heap end pointer in many newlib implementations
  if (!heap_end) {
    return 0; // allocation failure indicates severe memory pressure
  }
  uint32_t free_bytes = (&stack_var > heap_end) ? (&stack_var - heap_end) : 0;
  return free_bytes;
}
