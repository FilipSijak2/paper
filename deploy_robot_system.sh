#!/bin/bash
# Deploy robot system with health checks and rollback capability

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
	print_status "Checking prerequisites..."

	# Check if running on Raspberry Pi
	if [[ ! -f "/etc/os-release" ]] || ! grep -q "Raspberry\|Ubuntu" /etc/os-release; then
		print_warning "Not running on Raspberry Pi/Ubuntu - some features may not work"
	fi

	# Check Docker
	if ! command -v docker >/dev/null 2>&1; then
		print_error "Docker not installed"
		exit 1
	fi

	if ! command -v docker-compose >/dev/null 2>&1; then
		print_error "Docker Compose not installed"
		exit 1
	fi

	# Check ROS2 (for testing)
	if ! command -v ros2 >/dev/null 2>&1; then
		print_warning "ROS2 not installed locally - container testing will be limited"
	fi

	# Check .env file
	if [[ ! -f ".env" ]]; then
		print_status "Creating .env from template..."
		cp .env.example .env
		print_warning "Please edit .env file with your settings before continuing"
		exit 1
	fi

	print_success "Prerequisites check passed"
}

# Check hardware connections
check_hardware() {
	print_status "Checking hardware connections..."

	# Check Arduino R4 WiFi connection
	if [[ -e "/dev/ttyACM0" ]]; then
		print_success "Arduino R4 WiFi found at /dev/ttyACM0"
	else
		print_error "Arduino R4 WiFi not found at /dev/ttyACM0"
		print_status "Available devices:"
		found_device=false
		for dev in /dev/ttyACM* /dev/ttyUSB*; do
			if [[ -e "$dev" ]]; then
				found_device=true
				ls -la "$dev"
			fi
		done
		if [[ "$found_device" == false ]]; then
			echo "  No Arduino devices found"
		fi
		exit 1
	fi

	# Check permissions
	if [[ ! -r "/dev/ttyACM0" ]]; then
		print_warning "No read permission on /dev/ttyACM0"
		print_status "Adding user to dialout group..."
		sudo usermod -a -G dialout "$USER"
		print_warning "Please log out and back in for group changes to take effect"
	fi

	# Optional: Check for encoder processor
	if [[ -e "/dev/ttyUSB0" ]]; then
		print_success "Arduino Nano ESP32 found at /dev/ttyUSB0"
	else
		print_warning "Arduino Nano ESP32 not found - encoder processor may not be connected"
	fi
}

# Create required directories
setup_directories() {
	print_status "Setting up directories..."

	mkdir -p srv/{maps,db,db_backups,slam_config,nav_config,sensor_config,robot_config}

	# Create robot description if it doesn't exist
	if [[ ! -f "srv/robot_config/robot_description.yaml" ]]; then
		cat >srv/robot_config/robot_description.yaml <<'EOF'
robot_state_publisher:
  ros__parameters:
    robot_description: |
      <?xml version="1.0"?>
      <robot name="devastator_robot">
        <link name="base_link"/>
        <link name="imu_link"/>
        <joint name="base_to_imu" type="fixed">
          <parent link="base_link"/>
          <child link="imu_link"/>
          <origin xyz="0 0 0.05" rpy="0 0 0"/>
        </joint>
      </robot>
EOF
	fi

	# Set proper permissions
	sudo chown -R "$USER":"$USER" srv/

	print_success "Directories created"
}

# Deploy containers
deploy_containers() {
	print_status "Deploying containers..."

	# Pull/build images
	docker-compose build

	# Start core services first (database)
	print_status "Starting database..."
	docker-compose up -d db

	# Wait for database to be ready
	print_status "Waiting for database to be ready..."
	timeout 60 bash -c 'until docker-compose exec db pg_isready -U postgres; do sleep 2; done' || {
		print_error "Database failed to start"
		docker-compose logs db
		exit 1
	}

	# Start micro-ROS agent (critical for robot communication)
	print_status "Starting micro-ROS agent..."
	docker-compose up -d micro_ros_agent

	sleep 5

	# Check micro-ROS agent health
	if ! docker-compose ps micro_ros_agent | grep -q "Up"; then
		print_error "micro-ROS agent failed to start"
		docker-compose logs micro_ros_agent
		exit 1
	fi

	# Start remaining services
	print_status "Starting robot services..."
	docker-compose up -d slam navigation sensor_fusion rosbridge diagnostics

	print_success "All containers deployed"
}

# Health check
health_check() {
	print_status "Performing health checks..."

	# Check container status
	FAILED_SERVICES=()

	for service in db micro_ros_agent slam navigation sensor_fusion rosbridge diagnostics; do
		if docker-compose ps "$service" | grep -q "Up"; then
			print_success "$service is running"
		else
			print_error "$service is not running"
			FAILED_SERVICES+=("$service")
		fi
	done

	if [[ ${#FAILED_SERVICES[@]} -gt 0 ]]; then
		print_error "Failed services: ${FAILED_SERVICES[*]}"
		return 1
	fi

	# Test ROS2 communication
	print_status "Testing ROS2 communication..."
	sleep 10 # Give services time to initialize

	# Check if topics are available
	EXPECTED_TOPICS=("/cmd_vel" "/diagnostics")

	for topic in "${EXPECTED_TOPICS[@]}"; do
		if timeout 10 docker-compose exec micro_ros_agent ros2 topic list 2>/dev/null | grep -q "$topic"; then
			print_success "Topic $topic is available"
		else
			print_warning "Topic $topic is not available (may be normal during startup)"
		fi
	done

	return 0
}

# Test robot movement
test_movement() {
	print_status "Testing robot movement..."

	# Send forward command
	print_status "Moving forward..."
	timeout 5 docker-compose exec micro_ros_agent ros2 topic pub --once /cmd_vel geometry_msgs/Twist "linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}" || {
		print_error "Failed to send movement command"
		return 1
	}

	sleep 2

	# Stop robot
	print_status "Stopping robot..."
	timeout 5 docker-compose exec micro_ros_agent ros2 topic pub --once /cmd_vel geometry_msgs/Twist "linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}" || {
		print_warning "Failed to send stop command"
	}

	print_success "Movement test completed"
	return 0
}

# Main deployment
deploy_robot_system() {
	echo "=== Robot System Deployment ==="
	echo "Deploying three-device robot architecture:"
	echo "  • Raspberry Pi (ROS2 containers)"
	echo "  • Arduino R4 WiFi (motor control + micro-ROS)"
	echo "  • Arduino Nano ESP32 (encoder processor)"
	echo

	check_prerequisites
	check_hardware
	setup_directories
	deploy_containers

	if health_check; then
		print_success "System deployment successful!"
		echo
		echo "🤖 Robot system is ready!"
		echo
		echo "Web interface: http://localhost:9090"
		echo "Database: localhost:5432"
		echo
		echo "Test commands:"
		echo "  # List ROS topics"
		echo "  docker-compose exec micro_ros_agent ros2 topic list"
		echo
		echo "  # Move robot forward"
		echo "  docker-compose exec micro_ros_agent ros2 topic pub --once /cmd_vel geometry_msgs/Twist \"linear: {x: 0.1}\""
		echo
		echo "  # View logs"
		echo "  docker-compose logs -f [service_name]"
		echo

		if [[ "${1}" == "--test-movement" ]]; then
			echo
			test_movement
		fi

	else
		print_error "System deployment failed - check logs and retry"
		echo
		echo "Troubleshooting commands:"
		echo "  docker-compose logs [service_name]"
		echo "  docker-compose ps"
		echo "  docker-compose restart [service_name]"
		exit 1
	fi
}

# Handle script arguments
case "${1}" in
"--test-movement" | "-t")
	deploy_robot_system --test-movement
	;;
"--help" | "-h")
	echo "Usage: $0 [OPTIONS]"
	echo "Deploy the three-device robot system"
	echo
	echo "Options:"
	echo "  -t, --test-movement    Test robot movement after deployment"
	echo "  -h, --help            Show this help message"
	echo
	echo "Environment:"
	echo "  Edit .env file to configure settings"
	exit 0
	;;
"")
	deploy_robot_system
	;;
*)
	print_error "Unknown option: $1"
	echo "Use --help for usage information"
	exit 1
	;;
esac
