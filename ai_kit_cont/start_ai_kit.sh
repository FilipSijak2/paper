#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "[ai_kit_cont] CONTAINER START  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
set -u

# ---------------------------------------------------------------------------
# Hailo runtime is NOT installed inside the image.
# The host Raspberry Pi has 'hailo-all' installed via apt, which provides:
#   - /usr/lib/libhailort.so            (HailoRT userspace library)
#   - /usr/lib/aarch64-linux-gnu/       (GStreamer hailonet plugin .so)
#   - /usr/lib/hailo/                   (TAPPAS post-process .so files)
#   - /usr/lib/python3/dist-packages/   (hailort + tappas Python bindings)
# These are bind-mounted into the container via docker-compose.yaml.
# No downloading or installing is needed at runtime.
# ---------------------------------------------------------------------------

# Verify that the host mounts are in place before proceeding.
if [ ! -f /usr/lib/libhailort.so ] && [ ! -f /usr/lib/aarch64-linux-gnu/libhailort.so.4 ]; then
	if [ "$(dpkg --print-architecture)" != "arm64" ]; then
		echo "[ai-kit] WARN: Not running on arm64 — Hailo libs not expected (passthrough mode)."
	else
		echo "[ai-kit][ERROR] libhailort.so not found inside container." >&2
		echo "[ai-kit]        Make sure the host has 'hailo-all' installed:" >&2
		echo "[ai-kit]          sudo apt install hailo-all" >&2
		echo "[ai-kit]        And that docker-compose mounts /usr/lib/hailo and" >&2
		echo "[ai-kit]        /usr/lib/aarch64-linux-gnu into the container." >&2
		exit 1
	fi
else
	echo "[ai-kit] Hailo host libraries detected — no installation needed."
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

: "${RS_IMAGE_TOPIC:=/camera/realsense/color/image_raw}"
: "${RS_DEPTH_TOPIC:=/camera/realsense/aligned_depth_to_color/image_raw}"
: "${RS_CAMERA_INFO_TOPIC:=/camera/realsense/color/camera_info}"
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
if ! timeout "${RS_WAIT_TIMEOUT}" bash -c "until ros2 topic list 2>/dev/null | grep -Fxq '${RS_IMAGE_TOPIC}'; do sleep 1; done"; then
	echo "[ai-kit] WARN: Topic ${RS_IMAGE_TOPIC} not detected yet." >&2
	echo "[ai-kit]       Start realsense_cont first or update RS_IMAGE_TOPIC." >&2
else
	echo "[ai-kit] Image topic detected: ${RS_IMAGE_TOPIC}"
fi

if ros2 topic list 2>/dev/null | grep -Fxq "${RS_CAMERA_INFO_TOPIC}"; then
	echo "[ai-kit] Camera info topic detected: ${RS_CAMERA_INFO_TOPIC}"
fi

if [ "${AI_KIT_RUN_NODE}" = "1" ]; then
	echo "[ai-kit] Starting ROS AI node: ${AI_KIT_NODE}"
	# Filter rcutils raw-stderr noise caused by the Humble/Jazzy DDS type-hash
	# mismatch. These messages bypass the ROS2 logger and cannot be suppressed
	# via --log-level; they are benign and do not affect topic communication.
	exec python3 "${AI_KIT_NODE}" --ros-args --log-level rmw_cyclonedds_cpp:=ERROR \
		2> >(grep -Ev "rcutils_set_error_state|serdata\.cpp|error state is being overwritten|rcutils_reset_error|<<<|>>>" >&2)
fi

echo "[ai-kit] AI_KIT_RUN_NODE!=1, opening shell."
exec bash
