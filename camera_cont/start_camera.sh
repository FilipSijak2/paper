#!/usr/bin/env bash
set -euo pipefail

# Zajednički parametri
COMMON_ARGS=( --ros-args
  -p camera_name:="${CAMERA_NAME:-camera}"
  -p frame_id:="${CAMERA_FRAME_ID:-camera_optical_frame}"
  -p width:=${CAMERA_WIDTH:-1280}
  -p height:=${CAMERA_HEIGHT:-720}
  -p framerate:=${CAMERA_FPS:-30}
  -p camera_info_url:="${CAMERA_INFO_URL:-file:///data/camera_info.yaml}"
)

# 1) RGB8 stream na /camera/image_color (+ compressed transport)
echo "[camera] starting RGB node -> /camera/image_color"
ros2 run rpicam_compat rpicam_node \
  "${COMMON_ARGS[@]}" \
  -r image:=/camera/image_color \
  &
PID_RGB=$!

# 2) Pokušaj RAW (Bayer) na /camera/image_raw
# Ako paralelni RAW nije podržan, proces će se ugasiti, ali RGB ostaje.
echo "[camera] starting RAW node -> /camera/image_raw"
ros2 run rpicam_compat rpicam_node \
  "${COMMON_ARGS[@]}" \
  -p output_raw:=true \
  -r image:=/camera/image_raw \
  || echo "[camera] RAW not available in parallel on this build – continuing with RGB only."

wait $PID_RGB