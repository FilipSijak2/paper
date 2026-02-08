#!/usr/bin/env bash
set -euo pipefail

export AMENT_TRACE_SETUP_FILES=${AMENT_TRACE_SETUP_FILES:-}

# Source ROS
set +u
source /opt/ros/humble/setup.bash
set -u

: "${RS_CAMERA_NAME:=realsense}"
: "${RS_SERIAL:=}"
: "${RS_USB_PORT_ID:=}"
: "${RS_PORT_ID:=}"
: "${RS_ENABLE_DEPTH:=true}"
: "${RS_ENABLE_COLOR:=true}"
: "${RS_ENABLE_INFRA1:=false}"
: "${RS_ENABLE_INFRA2:=false}"
: "${RS_ENABLE_GYRO:=true}"
: "${RS_ENABLE_ACCEL:=true}"
: "${RS_UNITE_IMU_METHOD:=linear_interpolation}"
: "${RS_DEPTH_PROFILE:=640x480x15}"
: "${RS_COLOR_PROFILE:=640x480x15}"
: "${RS_ALIGN_DEPTH:=true}"
: "${RS_ENABLE_POINTCLOUD:=false}"

# Backward compatibility for older env naming.
if [ -z "${RS_USB_PORT_ID}" ] && [ -n "${RS_PORT_ID}" ]; then
  RS_USB_PORT_ID="${RS_PORT_ID}"
fi

# --- Helpers ---
have_cmd() { command -v "$1" >/dev/null 2>&1; }

enumerate_realsense() {
  # Prefer rs-enumerate-devices if available (best signal)
  if have_cmd rs-enumerate-devices; then
    rs-enumerate-devices 2>/dev/null || true
    return 0
  fi

  # Fallback: check USB IDs (D455 is 8086:0b5c in your output)
  if have_cmd lsusb; then
    lsusb | grep -iE '8086:' || true
  else
    echo "[realsense] WARN: neither rs-enumerate-devices nor lsusb is available in this container."
  fi
}

pick_serial_or_fail() {
  # If serial provided -> trust it (but still show what we see)
  if [ -n "${RS_SERIAL}" ]; then
    echo "${RS_SERIAL}"
    return 0
  fi

  # If USB port is explicitly selected, no serial is needed.
  if [ -n "${RS_USB_PORT_ID}" ]; then
    echo ""
    return 0
  fi

  # Try to auto-pick if exactly one device exists
  if have_cmd rs-enumerate-devices; then
    local serials
    serials="$(rs-enumerate-devices 2>/dev/null | awk -F': ' '/^[[:space:]]*Serial Number[[:space:]]*:/ {print $2}' | tr -d '\r' || true)"

    local count
    count="$(printf "%s\n" "${serials}" | sed '/^$/d' | wc -l | tr -d ' ')"

    if [ "${count}" -eq 0 ]; then
      echo ""
      return 0
    elif [ "${count}" -eq 1 ]; then
      printf "%s\n" "${serials}" | sed '/^$/d' | head -n1
      return 0
    else
      echo "[realsense] ERROR: Multiple RealSense devices detected, but neither RS_SERIAL nor RS_USB_PORT_ID is set." >&2
      echo "[realsense]        Set REALSENSE_SERIAL or REALSENSE_USB_PORT_ID in .env to choose one explicitly." >&2
      echo "[realsense]        Detected serials:" >&2
      printf "%s\n" "${serials}" | sed '/^$/d' | sed 's/^/  - /' >&2
      exit 2
    fi
  fi

  # If we can't enumerate, don't auto-pick blindly
  echo ""
}

# --- Preflight ---
echo "[realsense] Preflight: enumerating devices..."
enumerate_realsense | sed 's/^/[realsense]   /' || true

SELECTED_SERIAL="$(pick_serial_or_fail)"

if have_cmd rs-enumerate-devices; then
  # If we can enumerate but no device -> hard fail
  if ! rs-enumerate-devices 2>/dev/null | grep -q "Intel RealSense"; then
    echo "[realsense] ERROR: No RealSense devices detected inside container." >&2
    echo "[realsense]        Check USB mapping (/dev/bus/usb), privileges, cable, and power." >&2
    exit 3
  fi
fi

args=(
  "camera_name:=${RS_CAMERA_NAME}"
  "enable_depth:=${RS_ENABLE_DEPTH}"
  "enable_color:=${RS_ENABLE_COLOR}"
  "enable_infra1:=${RS_ENABLE_INFRA1}"
  "enable_infra2:=${RS_ENABLE_INFRA2}"
  "enable_gyro:=${RS_ENABLE_GYRO}"
  "enable_accel:=${RS_ENABLE_ACCEL}"
  "unite_imu_method:=${RS_UNITE_IMU_METHOD}"
  "depth_module.profile:=${RS_DEPTH_PROFILE}"
  "rgb_camera.profile:=${RS_COLOR_PROFILE}"
  "align_depth:=${RS_ALIGN_DEPTH}"
  "pointcloud.enable:=${RS_ENABLE_POINTCLOUD}"
)

if [ -n "${RS_USB_PORT_ID}" ]; then
  args+=("usb_port_id:=${RS_USB_PORT_ID}")
  echo "[realsense] Using USB port id: ${RS_USB_PORT_ID}"
fi

if [ -n "${SELECTED_SERIAL}" ]; then
  args+=("serial_no:=${SELECTED_SERIAL}")
  echo "[realsense] Using serial: ${SELECTED_SERIAL}"
elif [ -z "${RS_USB_PORT_ID}" ]; then
  echo "[realsense] Neither RS_SERIAL nor RS_USB_PORT_ID set; launching without device selector (may select any device)."
fi

echo "[realsense] Starting RealSense camera: ${RS_CAMERA_NAME}"
exec ros2 launch realsense2_camera rs_launch.py "${args[@]}"
