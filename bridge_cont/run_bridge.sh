#!/usr/bin/env bash
set -eo pipefail

# Source ROS environment (temporarily disable unbound variable check)
set +u
source /opt/ros/humble/setup.bash
set -u

PORT="${SERIAL_PORT:-/dev/ttyUSB0}"
BAUD="${SERIAL_BAUD:-115200}"

normalize_rmw(){
	local want="${RMW_IMPLEMENTATION:-}";
	# If user fat-fingered 'cyclonedx' instead of 'cyclonedds', fix it.
	if [[ "$want" =~ cyclonedx ]]; then
		echo "[bridge_cont][WARN] Detected typo in RMW_IMPLEMENTATION='$want' -> correcting to rmw_cyclonedds_cpp" >&2
		export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
		return
	fi
	# If empty, default to cyclonedds
	if [[ -z "$want" ]]; then
		export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
		return
	fi
	# Validate library exists; if not, fallback
	if [[ ! -e "/opt/ros/humble/lib/librmw_${RMW_IMPLEMENTATION}.so" && ! -e "/opt/ros/humble/lib/${RMW_IMPLEMENTATION}/librmw_${RMW_IMPLEMENTATION}.so" ]]; then
		echo "[bridge_cont][WARN] RMW implementation '$RMW_IMPLEMENTATION' not installed; falling back to rmw_cyclonedds_cpp" >&2
		export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
	fi
}

normalize_rmw

echo "[bridge_cont] Starting robot_serial_bridge on ${PORT}@${BAUD} (RMW=${RMW_IMPLEMENTATION:-unset})"
exec python3 /app/robot_serial_bridge.py --port "${PORT}" --baud "${BAUD}"