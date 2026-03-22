#!/usr/bin/env bash
set -euo pipefail

set +u
source /opt/ros/jazzy/setup.bash
set -u

# ---------------------------------------------------------------------------
# First-run: install hailo-tappas-core via pip.
#
# Why deferred and not baked into the image:
#   TAPPAS 5.x pip wheels for arm64 link against hailort, which requires the
#   HailoRT kernel module (hailort.ko) provided by the host Pi OS. The module
#   is not present in the QEMU-based CI build environment, so pip install
#   would succeed but the GStreamer hailonet plugin would not load without it.
#   On the real Pi (Ubuntu 24.04 Noble + HailoRT from host), it works natively.
#
# Also installs hailort Python bindings which TAPPAS depends on.
# The stamp file prevents re-installation on every container restart.
# ---------------------------------------------------------------------------
HAILO_STAMP=/etc/hailo-tappas-core-installed
: "${HAILO_TAPPAS_CORE_VERSION:=5.2.0}"

if [ ! -f "${HAILO_STAMP}" ]; then
  echo "[ai-kit] Installing hailo-tappas-core==${HAILO_TAPPAS_CORE_VERSION} via pip (first run)..."
  if [ "$(dpkg --print-architecture)" != "arm64" ]; then
    echo "[ai-kit] WARN: Not running on arm64 — skipping hailo install (passthrough mode)."
  else
    pip3 install --no-cache-dir --break-system-packages \
      --extra-index-url https://hailo-hailort.s3.eu-west-2.amazonaws.com \
      "hailort" \
      "hailo-tappas-core==${HAILO_TAPPAS_CORE_VERSION}" \
    || {
      echo "[ai-kit][ERROR] pip install hailo-tappas-core==${HAILO_TAPPAS_CORE_VERSION} failed." >&2
      echo "[ai-kit]        Check that the version exists on PyPI or Hailo's package index." >&2
      echo "[ai-kit]        Available: pip index versions hailo-tappas-core" >&2
      exit 1
    }
    touch "${HAILO_STAMP}"
    echo "[ai-kit] hailo-tappas-core installed successfully."
  fi
fi

# ---------------------------------------------------------------------------
# First-run: download Hailo example model resources.
# Models are not baked into the image to keep CI builds fast.
# Mount /root/hailo-rpi5-examples as a volume to persist across restarts.
# ---------------------------------------------------------------------------
HAILO_EXAMPLES_DIR=/root/hailo-rpi5-examples
RESOURCES_STAMP="${HAILO_EXAMPLES_DIR}/.resources_downloaded"
if [ ! -f "${RESOURCES_STAMP}" ]; then
  echo "[ai-kit] Downloading Hailo example model resources (first run)..."
  cd "${HAILO_EXAMPLES_DIR}"
  ./download_resources.sh
  touch "${RESOURCES_STAMP}"
  cd -
  echo "[ai-kit] Resources downloaded."
fi

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
