// Arduino UNO R4 WiFi - Custom Protocol Motor Controller
// Role: Receive motor commands from Nano ESP32, drive BTS7960 modules, LED visualization
// Communication: Custom binary protocol (robust, deterministic, easy debugging)
// 
// Architecture change: 
//   OLD: micro-ROS client (unstable, memory issues)
//   NEW: Serial protocol bridge (Nano ESP32 ↔ UNO R4)
//
// Protocol: CommandPacket (20 bytes) with CRC validation, timeout safety
// Features: Motor control + LED matrix animation + error handling
#include <Arduino.h>

// LED Matrix for visualization
#include <ArduinoGraphics.h>
#include <Arduino_LED_Matrix.h>
ArduinoLEDMatrix matrix;

// ===== PROTOCOL DEFINITIONS =====
// Custom protocol definitions (shared with Nano ESP32)
// Simplified structures for UNO R4 (only what's needed)

static const uint8_t PROTOCOL_VERSION = 1;
static const uint32_t COMMAND_PACKET_HEADER = 0xFEEDFACE;  
static const uint32_t COMMAND_PACKET_TAIL   = 0xDEADC0DE;
static const uint8_t COMMAND_PACKET_SIZE = 20;

// Command data from Host PC → Nano ESP32 → UNO R4 (20 bytes total)
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

// Validate command packet
static inline bool validate_command_packet(const CommandPacket* pkt) {
    if (pkt->header != COMMAND_PACKET_HEADER || pkt->tail != COMMAND_PACKET_TAIL) return false;
    if (pkt->version != PROTOCOL_VERSION) return false;
    uint16_t expected = crc16_ccitt((const uint8_t*)pkt, sizeof(CommandPacket) - 6, 0xFFFF);
    return expected == pkt->crc16;
}

// ===== END PROTOCOL DEFINITIONS =====

// Hardware configuration
const int RPWM_R = 9;   // Right motor PWM
const int LPWM_R = 10;  // Right motor DIR
const int RPWM_L = 5;   // Left motor PWM  
const int LPWM_L = 6;   // Left motor DIR

// Robot parameters
const float WHEEL_BASE = 0.20f;
// Wheel radius not needed now

// Serial communication buffer for commands from Nano ESP32
uint8_t cmd_buffer[COMMAND_PACKET_SIZE];
uint8_t cmd_buffer_pos = 0;
CommandPacket current_command;
bool command_valid = false;

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
void processSerialCommands();
void updateMotorControl();
void updateRobotState();
void blinkStatus();
void updateLEDDisplay();
void displayPattern(const uint32_t p[3]);

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("Arduino R4 WiFi Custom Protocol Motor Controller");
  Serial.println("Waiting for commands from Nano ESP32...");
  
  // LED matrix + status LED
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
  
  Serial.println("Motor controller ready - protocol v1.0");
  current_state = IDLE;
  last_cmd_time = millis();
}

void loop() {
  unsigned long now = millis();
  
  // Process incoming commands from Nano ESP32
  processSerialCommands();
  
  // Update robot state based on commands
  updateRobotState();
  
  // Control motors
  updateMotorControl();
  
  // Visual feedback
  blinkStatus();
  if (now - last_display_update >= DISPLAY_UPDATE_INTERVAL) {
    updateLEDDisplay();
    last_display_update = now;
  }
}

void processSerialCommands() {
  // Read available bytes from Serial (from Nano ESP32)
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
        command_valid = true;
        current_command = *cmd; // Store for potential debugging
        
        // Optional debug output (comment out for production)
        Serial.print("CMD: L=");
        Serial.print(cmd_linear, 3);
        Serial.print(" A=");
        Serial.println(cmd_angular, 3);
      } else {
        // Invalid packet - could be noise or sync issue
        command_valid = false;
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

// Custom protocol implementation complete
// Motor control + LED visualization driven by serial commands from Nano ESP32
// Much more stable and debuggable than micro-ROS approach
