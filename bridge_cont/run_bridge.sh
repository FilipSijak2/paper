#!/usr/bin/env bash
set -euo pipefail

# Source ROS environment
source /opt/ros/humble/setup.bash

PORT="${SERIAL_PORT:-/dev/ttyUSB0}"
BAUD="${SERIAL_BAUD:-115200}"

echo "[bridge_cont] Starting robot_serial_bridge on ${PORT}@${BAUD} (RMW=${RMW_IMPLEMENTATION:-unset})"
exec python3 /app/robot_serial_bridge.py --port "${PORT}" --baud "${BAUD}"