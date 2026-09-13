#!/bin/bash
set -euo pipefail

echo "============================================================"
echo "[foxglove_bridge_cont] CONTAINER START  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# Avoid nounset failures inside ROS setup scripts.
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"
export AMENT_PYTHON_EXECUTABLE="${AMENT_PYTHON_EXECUTABLE:-}"

set +u
# shellcheck disable=SC1090,SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u

ROS_ARGS=(
	"--ros-args"
	"-p" "port:=${FOXGLOVE_PORT}"
	"-p" "address:=${FOXGLOVE_ADDRESS}"
)

# YAML string arrays are passed as single arguments (never evaluated by bash).
# Heavy camera streams can still be enabled explicitly for short diagnostics.
: "${FOXGLOVE_TOPIC_WHITELIST:=[\"^/(?!camera/).*\",\"^/camera/[^/]+/color/(image_raw/compressed|image_compressed)$\",\"^/camera/[^/]+/(imu|gyro/sample|accel/sample|[^/]+/camera_info)$\"]}"
: "${FOXGLOVE_SERVICE_WHITELIST:=[\"^/(?!.*get_type_description$).*\"]}"
: "${FOXGLOVE_CAPABILITIES:=[\"clientPublish\",\"parameters\",\"parametersSubscribe\",\"services\",\"assets\"]}"
ROS_ARGS+=(
	"-p" "topic_whitelist:=${FOXGLOVE_TOPIC_WHITELIST}"
	"-p" "service_whitelist:=${FOXGLOVE_SERVICE_WHITELIST}"
	"-p" "capabilities:=${FOXGLOVE_CAPABILITIES}"
	"-p" "use_compression:=false"
)

if [[ "${FOXGLOVE_TLS}" == "1" || "${FOXGLOVE_TLS}" == "true" ]]; then
	ROS_ARGS+=("-p" "tls:=true")
	if [[ -n "${FOXGLOVE_TLS_CERT:-}" ]]; then
		ROS_ARGS+=("-p" "certfile:=${FOXGLOVE_TLS_CERT}")
	fi
	if [[ -n "${FOXGLOVE_TLS_KEY:-}" ]]; then
		ROS_ARGS+=("-p" "keyfile:=${FOXGLOVE_TLS_KEY}")
	fi
else
	ROS_ARGS+=("-p" "tls:=false")
fi

exec ros2 run foxglove_bridge foxglove_bridge "${ROS_ARGS[@]}"
