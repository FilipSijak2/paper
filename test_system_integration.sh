#!/bin/bash
# Complete system test script for three-device robot architecture

set -e

echo "=== Three-Device Robot System Integration Test ==="
echo "Testing: Raspberry Pi ↔ Arduino R4 WiFi ↔ Arduino Nano ESP32"
echo

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
MICROROS_DEVICE=${MICROROS_DEVICE:-/dev/ttyACM0}
ENCODER_NANO_DEVICE=${ENCODER_NANO_DEVICE:-/dev/ttyUSB0}
TEST_TIMEOUT=30

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_device() {
    local device=$1
    local description=$2
    
    if [[ -e "$device" ]]; then
        print_success "$description found at $device"
        return 0
    else
        print_error "$description not found at $device"
        return 1
    fi
}

test_arduino_nano_encoder() {
    print_status "Testing Arduino Nano ESP32 encoder processor..."
    
    if ! check_device "$ENCODER_NANO_DEVICE" "Arduino Nano ESP32"; then
        print_warning "Skipping encoder processor test"
        return 1
    fi
    
    # Test serial communication with encoder processor
    timeout $TEST_TIMEOUT bash -c "
        stty -F $ENCODER_NANO_DEVICE 115200 cs8 -cstopb -parenb
        echo 'Testing encoder processor communication...'
        cat $ENCODER_NANO_DEVICE | head -n 5
    " 2>/dev/null || {
        print_error "Failed to communicate with encoder processor"
        return 1
    }
    
    print_success "Encoder processor communication OK"
    return 0
}

test_arduino_r4_microros() {
    print_status "Testing Arduino R4 WiFi micro-ROS communication..."
    
    if ! check_device "$MICROROS_DEVICE" "Arduino R4 WiFi"; then
        print_error "Arduino R4 WiFi not found"
        return 1
    fi
    
    # Start micro-ROS agent in background
    print_status "Starting micro-ROS agent..."
    timeout $TEST_TIMEOUT ros2 run micro_ros_agent micro_ros_agent serial --dev $MICROROS_DEVICE --baudrate 115200 &
    AGENT_PID=$!
    
    sleep 5  # Give agent time to connect
    
    # Test ROS2 topics
    print_status "Checking ROS2 topics..."
    TOPICS=$(timeout 10 ros2 topic list 2>/dev/null || echo "")
    
    if echo "$TOPICS" | grep -q "/cmd_vel"; then
        print_success "Found /cmd_vel topic"
    else
        print_error "Missing /cmd_vel topic"
        kill $AGENT_PID 2>/dev/null || true
        return 1
    fi
    
    if echo "$TOPICS" | grep -q "/imu"; then
        print_success "Found IMU topic"
    else
        print_warning "IMU topic not found (may be normal if IMU not connected)"
    fi
    
    if echo "$TOPICS" | grep -q "/odom"; then
        print_success "Found odometry topic"
    else
        print_warning "Odometry topic not found (may be normal if encoders not connected)"
    fi
    
    # Test basic motor control
    print_status "Testing basic motor control..."
    timeout 5 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}" || {
        print_error "Failed to send cmd_vel command"
        kill $AGENT_PID 2>/dev/null || true
        return 1
    }
    
    sleep 2
    
    # Stop motors
    timeout 5 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}" || true
    
    print_success "Motor control test completed"
    
    # Clean up
    kill $AGENT_PID 2>/dev/null || true
    return 0
}

test_docker_containers() {
    print_status "Testing Docker container system..."
    
    if ! command -v docker >/dev/null 2>&1; then
        print_error "Docker not installed"
        return 1
    fi
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        print_error "Docker Compose not installed"
        return 1
    fi
    
    # Check if docker-compose.yaml exists
    if [[ ! -f "docker-compose.yaml" ]]; then
        print_error "docker-compose.yaml not found"
        return 1
    fi
    
    # Test container build (don't start services that need hardware)
    print_status "Testing container builds..."
    docker-compose config >/dev/null || {
        print_error "Docker Compose configuration invalid"
        return 1
    }
    
    print_success "Docker Compose configuration valid"
    
    # Test building core containers (without hardware dependencies)
    docker-compose build db rosbridge || {
        print_error "Failed to build core containers"
        return 1
    }
    
    print_success "Core containers built successfully"
    return 0
}

test_i2c_communication() {
    print_status "Testing I2C bus availability..."
    
    if command -v i2cdetect >/dev/null 2>&1; then
        # Check if I2C devices are available
        I2C_DEVICES=$(i2cdetect -l 2>/dev/null | wc -l)
        if [[ $I2C_DEVICES -gt 0 ]]; then
            print_success "I2C bus available ($I2C_DEVICES buses found)"
            
            # Try to detect AS5600 encoders (address 0x36)
            if i2cdetect -y 1 2>/dev/null | grep -q "36"; then
                print_success "AS5600 encoder detected on I2C bus"
            else
                print_warning "No AS5600 encoders detected (may be normal if not connected)"
            fi
        else
            print_warning "No I2C buses found"
        fi
    else
        print_warning "i2c-tools not installed, skipping I2C test"
    fi
    
    return 0
}

run_integration_test() {
    print_status "Running full integration test..."
    
    # Create .env file if it doesn't exist
    if [[ ! -f ".env" ]]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
    fi
    
    local test_results=()
    
    # Test each component
    echo
    echo "=== Hardware Tests ==="
    test_arduino_nano_encoder && test_results+=("✓ Encoder Processor") || test_results+=("✗ Encoder Processor")
    test_arduino_r4_microros && test_results+=("✓ R4 WiFi micro-ROS") || test_results+=("✗ R4 WiFi micro-ROS")
    test_i2c_communication && test_results+=("✓ I2C Communication") || test_results+=("✗ I2C Communication")
    
    echo
    echo "=== Software Tests ==="
    test_docker_containers && test_results+=("✓ Docker Containers") || test_results+=("✗ Docker Containers")
    
    # Summary
    echo
    echo "=== Test Summary ==="
    for result in "${test_results[@]}"; do
        echo "  $result"
    done
    
    # Count successful tests
    success_count=$(printf '%s\n' "${test_results[@]}" | grep -c "✓" || echo "0")
    total_count=${#test_results[@]}
    
    echo
    if [[ $success_count -eq $total_count ]]; then
        print_success "All tests passed! ($success_count/$total_count)"
        echo
        echo "🎉 Your three-device robot system is ready!"
        echo "   Next steps:"
        echo "   1. docker-compose up -d"
        echo "   2. ros2 topic pub /cmd_vel geometry_msgs/msg/Twist ..."
        return 0
    else
        print_warning "Some tests failed ($success_count/$total_count passed)"
        echo
        echo "🔧 Fix the failing components before proceeding"
        return 1
    fi
}

# Main execution
case "${1:-test}" in
    "nano")
        test_arduino_nano_encoder
        ;;
    "r4")
        test_arduino_r4_microros
        ;;
    "docker")
        test_docker_containers
        ;;
    "i2c")
        test_i2c_communication
        ;;
    "test"|"")
        run_integration_test
        ;;
    *)
        echo "Usage: $0 [nano|r4|docker|i2c|test]"
        echo "  nano   - Test Arduino Nano ESP32 encoder processor"
        echo "  r4     - Test Arduino R4 WiFi micro-ROS"
        echo "  docker - Test Docker container system"
        echo "  i2c    - Test I2C communication"
        echo "  test   - Run full integration test (default)"
        exit 1
        ;;
esac