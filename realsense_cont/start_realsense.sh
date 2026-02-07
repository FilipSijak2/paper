#!/usr/bin/env bash
set -euo pipefail

export AMENT_TRACE_SETUP_FILES=${AMENT_TRACE_SETUP_FILES:-}
set +u
source /opt/ros/humble/setup.bash
set -u

: "${RS_CAMERA_NAME:=realsense}"
: "${RS_SERIAL:=}"
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

if [ -n "${RS_SERIAL}" ]; then
  args+=("serial_no:=${RS_SERIAL}")
fi

echo "[realsense] Starting RealSense camera: ${RS_CAMERA_NAME}"
ros2 launch realsense2_camera rs_launch.py "${args[@]}"
