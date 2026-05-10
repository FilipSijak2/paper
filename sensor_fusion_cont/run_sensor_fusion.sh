#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "[sensor_fusion_cont] CONTAINER START  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# Purpose: Ensure the sensor_fusion workspace is built and the package is discoverable
# before launching the ROS 2 launch file. Provides self-healing if the install
# directory is missing or the package index can't find sensor_fusion_pkg.

ROS_SETUP=/opt/ros/humble/setup.bash
OVERLAY_SETUP=/app/ws/install/setup.bash
PKG_NAME="sensor_fusion_pkg"
LAUNCH_COMMAND=(ros2 launch "${PKG_NAME}" sensor_fusion.launch.py)
LIBEXEC_DIR=/app/ws/install/lib/${PKG_NAME}
MAX_LAUNCH_RETRIES=${MAX_LAUNCH_RETRIES:-3}
SF_IMU_SOURCE=${SF_IMU_SOURCE:-realsense}
SF_IMU_MODE=""

red() { echo -e "\033[31m$*\033[0m"; }
green() { echo -e "\033[32m$*\033[0m"; }
yellow() { echo -e "\033[33m$*\033[0m"; }

normalize_imu_source() {
	local raw_source="${SF_IMU_SOURCE,,}"
	case "${raw_source}" in
	realsense | camera | d455)
		echo "realsense"
		;;
	*)
		echo "arduino"
		;;
	esac
}

if [ -f /etc/timezone ]; then echo "[INFO] Container timezone: $(cat /etc/timezone)"; fi

echo "SENSOR_FUSION_IMAGE_TAG=${SF_VERSION_TAG:-unset}"
echo "SENSOR_FUSION_IMU_SOURCE=${SF_IMU_SOURCE}"
SF_IMU_MODE="$(normalize_imu_source)"
echo "SENSOR_FUSION_IMU_MODE=${SF_IMU_MODE}"

# Prevent 'unbound variable' issues for traced setup scripts under set -u
: "${AMENT_TRACE_SETUP_FILES:=}"
: "${COLCON_TRACE:=}"
set +u
# shellcheck disable=SC1090,SC1091
source "$ROS_SETUP"
set -u

needs_rebuild=false
if [ ! -f "$OVERLAY_SETUP" ]; then
	yellow "[WARN] Overlay setup file missing: $OVERLAY_SETUP"
	needs_rebuild=true
else
	# Guard COLCON_TRACE for colcon-generated setup scripts
	: "${COLCON_TRACE:=}"
	set +u
	# shellcheck source=/dev/null
	source "$OVERLAY_SETUP" || {
		yellow "[WARN] Failed sourcing overlay, will rebuild"
		needs_rebuild=true
	}
	set -u
fi

# Check if package is visible
if ! ros2 pkg list | grep -q "^${PKG_NAME}$"; then
	yellow "[WARN] Package ${PKG_NAME} not found in ament index; triggering rebuild."
	needs_rebuild=true
fi

if $needs_rebuild; then
	yellow "[INFO] Rebuilding workspace..."
	pushd /app/ws >/dev/null
	rm -rf build install log 2>/dev/null || true
	colcon build --symlink-install --merge-install || {
		red "[ERROR] colcon build failed"
		exit 1
	}
	popd >/dev/null
	: "${COLCON_TRACE:=}"
	set +u
	# shellcheck source=/dev/null
	source "$OVERLAY_SETUP"
	set -u
	if ros2 pkg list | grep -q "^${PKG_NAME}$"; then
		green "[OK] Package ${PKG_NAME} now discoverable after rebuild."
	else
		red "[FATAL] Package ${PKG_NAME} still not discoverable after rebuild."
		exit 2
	fi
else
	green "[OK] Workspace already built and package present."
fi

# Additional integrity check: Arduino mode launches a package executable, so it
# requires the standard ROS libexec install location. RealSense mode only uses
# the launch file plus imu_filter_madgwick and can run without it.
if [[ "${SF_IMU_MODE}" == "arduino" && ! -d "$LIBEXEC_DIR" ]]; then
	yellow "[WARN] Expected libexec directory missing: $LIBEXEC_DIR (will attempt one clean rebuild)"
	pushd /app/ws >/dev/null
	rm -rf build install log 2>/dev/null || true
	colcon build --symlink-install --merge-install || {
		red "[ERROR] Rebuild (libexec fix) failed"
		exit 1
	}
	popd >/dev/null
	set +u
	# shellcheck source=/dev/null
	source "$OVERLAY_SETUP"
	set -u
	if [ ! -d "$LIBEXEC_DIR" ]; then
		yellow "[WARN] libexec directory still absent after rebuild; Arduino mode will fallback to direct python execution"
	else
		green "[OK] libexec directory created after rebuild."
	fi
fi

# Show path debugging
which python3 || true
python3 -c "import sys; print('[DEBUG] sys.path entries:'); [print('  ', p) for p in sys.path]"

attempt=1
set +e
while :; do
	set -x
	"${LAUNCH_COMMAND[@]}"
	rc=$?
	set +x
	if [ $rc -eq 0 ]; then
		break
	fi
	red "[ERROR] ros2 launch exited with code $rc (attempt ${attempt}/${MAX_LAUNCH_RETRIES})"
	if [ "$attempt" -ge "$MAX_LAUNCH_RETRIES" ]; then
		if [[ "${SF_IMU_MODE}" == "arduino" ]]; then
			yellow "[WARN] Reached max launch retries; invoking direct Arduino fallback."
			# Direct fallback: run module entry point without launch system
			python3 - <<'PYEOF'
import os, rclpy
from sensor_fusion_pkg.arduino_listener_impl import main
print('[FALLBACK] Starting direct ArduinoImuNode (no launch)')
try:
    main()
except KeyboardInterrupt:
    pass
PYEOF
			exit $?
		fi

		red "[FATAL] Reached max launch retries in RealSense IMU mode; no safe fallback is available."
		exit $rc
	fi
	attempt=$((attempt + 1))
	sleep 2
done
set -e
