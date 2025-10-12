#!/usr/bin/env bash
set -euo pipefail

# Purpose: Ensure the sensor_fusion workspace is built and the package is discoverable
# before launching the ROS 2 launch file. Provides self-healing if the install
# directory is missing or the package index can't find sensor_fusion_pkg.

ROS_SETUP=/opt/ros/humble/setup.bash
OVERLAY_SETUP=/app/ws/install/setup.bash
PKG_NAME="sensor_fusion_pkg"
LAUNCH_COMMAND=(ros2 launch ${PKG_NAME} sensor_fusion.launch.py)

red() { echo -e "\033[31m$*\033[0m"; }
green() { echo -e "\033[32m$*\033[0m"; }
yellow() { echo -e "\033[33m$*\033[0m"; }

if [ -f /etc/timezone ]; then echo "[INFO] Container timezone: $(cat /etc/timezone)"; fi

echo "SENSOR_FUSION_IMAGE_TAG=${SF_VERSION_TAG:-unset}"

source "$ROS_SETUP"

needs_rebuild=false
if [ ! -f "$OVERLAY_SETUP" ]; then
  yellow "[WARN] Overlay setup file missing: $OVERLAY_SETUP"
  needs_rebuild=true
else
  source "$OVERLAY_SETUP" || { yellow "[WARN] Failed sourcing overlay, will rebuild"; needs_rebuild=true; }
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
  colcon build --symlink-install --merge-install || { red "[ERROR] colcon build failed"; exit 1; }
  popd >/dev/null
  source "$OVERLAY_SETUP"
  if ros2 pkg list | grep -q "^${PKG_NAME}$"; then
    green "[OK] Package ${PKG_NAME} now discoverable after rebuild."
  else
    red "[FATAL] Package ${PKG_NAME} still not discoverable after rebuild."; exit 2
  fi
else
  green "[OK] Workspace already built and package present."
fi

# Show path debugging
which python3 || true
python3 -c "import sys; print('[DEBUG] sys.path entries:'); [print('  ', p) for p in sys.path]"

set -x
"${LAUNCH_COMMAND[@]}"
