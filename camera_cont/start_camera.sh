#!/usr/bin/env bash
set -euo pipefail

# Zajednički args
COMMON_ARGS=( --ros-args
  -p camera_name:="${CAMERA_NAME:-camera}"
  -p frame_id:="${CAMERA_FRAME_ID:-camera_optical_frame}"
  -p width:=${CAMERA_WIDTH:-1280}
  -p height:=${CAMERA_HEIGHT:-720}
  -p framerate:=${CAMERA_FPS:-30}
  -p camera_info_url:="${CAMERA_INFO_URL:-file:///data/camera_info.yaml}"
)

# 1) RGB8 stream na /camera/image_raw
echo "[camera] starting RGB node -> /camera/image_raw"
ros2 run rpicam_compat rpicam_node \
  "${COMMON_ARGS[@]}" \
  -r image:=/camera/image_raw \
  &
PID_RGB=$!

# 2) RAW Bayer stream na /camera/image_raw_bayer
# Napomena: ovi parametri ovise o rpicam-ros verziji. Ako RAW nije podržan paralelno,
# proces će završiti i RGB će nastaviti raditi. Logovi će to pokazati.
echo "[camera] starting RAW node -> /camera/image_raw_bayer"
ros2 run rpicam_compat rpicam_node \
  "${COMMON_ARGS[@]}" \
  -p output_raw:=true \
  -r image:=/camera/image_raw_bayer \
  || echo "[camera] RAW node exited (maybe not supported in parallel on this build)"

wait $PID_RGB
