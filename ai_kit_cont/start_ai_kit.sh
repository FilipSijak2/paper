#!/usr/bin/env bash
set -euo pipefail

set +u
source /opt/ros/humble/setup.bash
set -u

: "${RS_IMAGE_TOPIC:=/realsense/color/image_raw}"
: "${RS_CAMERA_INFO_TOPIC:=/realsense/color/camera_info}"
: "${RS_WAIT_TIMEOUT:=30}"
: "${AI_KIT_RUN_NODE:=1}"
: "${AI_KIT_NODE:=/app/realsense_hailo_node.py}"
: "${AI_KIT_REQUIRE_HAILO:=1}"
: "${HAILO_GST_PIPELINE:=}"

if [ "${AI_KIT_REQUIRE_HAILO}" = "1" ] && [ -z "${HAILO_GST_PIPELINE}" ]; then
  echo "[ai-kit] ERROR: AI_KIT_REQUIRE_HAILO=1 but HAILO_GST_PIPELINE is empty." >&2
  echo "[ai-kit]        Set HAILO_GST_PIPELINE to a valid hailonet pipeline." >&2
  exit 1
fi

if [ -n "${HAILO_GST_PIPELINE}" ]; then
  echo "[ai-kit] HAILO_GST_PIPELINE is set, validating Hailo GStreamer runtime..."
  if ! gst-inspect-1.0 hailonet >/dev/null 2>&1; then
    echo "[ai-kit] ERROR: GStreamer plugin 'hailonet' is not available." >&2
    echo "[ai-kit]        Image is not Hailo-ready. Check Docker build/install logs." >&2
    exit 1
  fi
fi

echo "[ai-kit] Waiting up to ${RS_WAIT_TIMEOUT}s for ROS image topic: ${RS_IMAGE_TOPIC}"
if ! timeout "${RS_WAIT_TIMEOUT}" bash -c "until ros2 topic list | grep -Fxq '${RS_IMAGE_TOPIC}'; do sleep 1; done"; then
  echo "[ai-kit] WARN: Topic ${RS_IMAGE_TOPIC} not detected yet." >&2
  echo "[ai-kit]       Start realsense_cont first or update RS_IMAGE_TOPIC." >&2
else
  echo "[ai-kit] Image topic detected: ${RS_IMAGE_TOPIC}"
fi

if ros2 topic list | grep -Fxq "${RS_CAMERA_INFO_TOPIC}"; then
  echo "[ai-kit] Camera info topic detected: ${RS_CAMERA_INFO_TOPIC}"
fi

if [ "${AI_KIT_RUN_NODE}" = "1" ]; then
  echo "[ai-kit] Starting ROS AI node: ${AI_KIT_NODE}"
  exec python3 "${AI_KIT_NODE}"
fi

echo "[ai-kit] AI_KIT_RUN_NODE!=1, opening shell."
exec bash
