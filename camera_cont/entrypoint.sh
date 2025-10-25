#!/usr/bin/env bash
set -euo pipefail

# Source ROS
. /opt/ros/humble/setup.bash

# Fail fast ako nema video uređaja
if [ ! -e "${CAMERA_DEVICE}" ]; then
  echo "[ERROR] Camera device ${CAMERA_DEVICE} not found."
  ls -l /dev/video* || true
  exit 1
fi

# Pokreni H.264 TCP stream (primarno)
# Note: v4l2h264enc koristi HW encode na RPi5; ako nije dostupan, GStreamer padne – u tom slučaju
# možeš promijeniti u x264enc (software), ali HW je poželjan.
GST_H264_PIPELINE="libcamerasrc camera-name=rpi_cam ! \
  video/x-raw,width=${WIDTH},height=${HEIGHT},framerate=${FPS}/1 ! \
  queue ! v4l2h264enc ! h264parse config-interval=1 ! \
  mpegtsmux ! tcpserversink host=0.0.0.0 port=${TCP_PORT} sync=false"

echo "[INFO] Starting H.264 TCP stream on port ${TCP_PORT} ..."
bash -lc "gst-launch-1.0 -v ${GST_H264_PIPELINE}" &
H264_PID=$!

# Pričekaj kratko da encoder krene
sleep 1

# Pokreni ROS2 node (RAW publish)
echo "[INFO] Starting ROS2 camera publisher ..."
exec ros2 run rclpy rclpy -- /app/camera_node.py
