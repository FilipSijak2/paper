#!/usr/bin/env bash
set -euo pipefail

set +u
source /opt/ros/humble/setup.bash
set -u

# ---------------------------------------------------------------------------
# First-run: install hailo-tappas-core from RPi apt repo.
#
# Why deferred and not baked into the image:
#   hailo-tappas-core requires Debian Bookworm libraries (libopencv-core406,
#   libpython3.11, gstreamer1.0-libcamera) that are not available in the
#   Ubuntu Jammy base image used for building. On the real Raspberry Pi running
#   Raspberry Pi OS (Bookworm), all those libraries are present natively and
#   apt-get install works without any conflicts.
#
# The stamp file prevents re-installation on every container restart.
# Mount /var/cache/apt as a volume to speed up repeated installations.
# ---------------------------------------------------------------------------
HAILO_STAMP=/etc/hailo-tappas-core-installed
: "${HAILO_TAPPAS_CORE_VERSION:=3.31.0+1-1}"

if [ ! -f "${HAILO_STAMP}" ]; then
  echo "[ai-kit] Installing hailo-tappas-core=${HAILO_TAPPAS_CORE_VERSION} (first run)..."
  if [ "$(dpkg --print-architecture)" != "arm64" ]; then
    echo "[ai-kit] WARN: Not running on arm64 — skipping hailo install (passthrough mode)."
  else
    mkdir -p /etc/apt/keyrings
    wget --tries=5 --waitretry=15 --timeout=60 -qO- \
      https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
      | gpg --dearmor > /etc/apt/keyrings/raspberrypi-archive-keyring.gpg
    echo "deb [signed-by=/etc/apt/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian/ bookworm main" \
      > /etc/apt/sources.list.d/raspi.list
    apt-get update -o Acquire::Retries=3
    apt-get install -y --no-install-recommends \
      "hailo-tappas-core=${HAILO_TAPPAS_CORE_VERSION}" \
    || {
      echo "[ai-kit][ERROR] Could not install hailo-tappas-core=${HAILO_TAPPAS_CORE_VERSION}" >&2
      echo "[ai-kit]        Versions in RPi archive:" >&2
      apt-cache policy hailo-tappas-core 2>/dev/null >&2 || true
      rm -f /etc/apt/sources.list.d/raspi.list
      exit 1
    }
    rm -f /etc/apt/sources.list.d/raspi.list
    rm -rf /var/lib/apt/lists/*
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
