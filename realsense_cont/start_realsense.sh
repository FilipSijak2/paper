#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "[realsense_cont] CONTAINER START  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

export AMENT_TRACE_SETUP_FILES=${AMENT_TRACE_SETUP_FILES:-}

# Source ROS
set +u
# shellcheck disable=SC1091
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
: "${RS_BASE_FRAME_ID:=}"
: "${RS_DEPTH_PROFILE:=640x480x15}"
: "${RS_COLOR_PROFILE:=640x480x15}"
: "${RS_GYRO_FPS:=200}"
: "${RS_ACCEL_FPS:=100}"
: "${RS_ALIGN_DEPTH:=true}"
: "${RS_ENABLE_POINTCLOUD:=false}"
: "${RS_COMPRESSED_JPEG_QUALITY:=40}"
: "${RS_DISABLE_USB_AUTOSUSPEND:=true}"
: "${RS_WATCHDOG_ENABLED:=true}"
: "${RS_WATCHDOG_TOPIC:=}"
: "${RS_WATCHDOG_STARTUP_TIMEOUT_S:=60}"
: "${RS_WATCHDOG_STALE_TIMEOUT_S:=15}"

if [ -z "${RS_BASE_FRAME_ID}" ]; then
	RS_BASE_FRAME_ID="${RS_CAMERA_NAME}_link"
fi

normalize_unite_imu_method() {
	case "${RS_UNITE_IMU_METHOD}" in
	0 | none | off | disabled)
		RS_UNITE_IMU_METHOD=0
		;;
	1 | copy)
		RS_UNITE_IMU_METHOD=1
		;;
	2 | linear_interpolation)
		RS_UNITE_IMU_METHOD=2
		;;
	*)
		echo "[realsense] WARN: Unsupported RS_UNITE_IMU_METHOD='${RS_UNITE_IMU_METHOD}', falling back to 2 (linear_interpolation)." >&2
		RS_UNITE_IMU_METHOD=2
		;;
	esac
}

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

extract_device_serials() {
	# Match only top-level "Serial Number" fields and ignore "Asic Serial Number".
	rs-enumerate-devices 2>/dev/null |
		awk -F': ' '/^[[:space:]]*Serial Number[[:space:]]*:/ {print $2}' |
		tr -d '\r' ||
		true
}

extract_physical_ports() {
	rs-enumerate-devices 2>/dev/null |
		awk -F': ' '/^[[:space:]]*Physical Port[[:space:]]*:/ {print $2}' |
		tr -d '\r' ||
		true
}

detected_usb_device_id() {
	extract_physical_ports |
		sed -nE 's#.*\/usb[0-9]+\/([0-9]+-[0-9]+(\.[0-9]+)*)\/.*#\1#p' |
		head -n1
}

disable_usb_autosuspend() {
	case "${RS_DISABLE_USB_AUTOSUSPEND,,}" in
	1 | true | yes | on) ;;
	*) return 0 ;;
	esac

	local usb_device_id=""
	local power_dir=""
	if [ -n "${RS_USB_PORT_ID}" ] && [ -d "/sys/bus/usb/devices/${RS_USB_PORT_ID}/power" ]; then
		usb_device_id="${RS_USB_PORT_ID}"
	elif have_cmd rs-enumerate-devices; then
		usb_device_id="$(detected_usb_device_id)"
	fi

	if [ -z "${usb_device_id}" ]; then
		echo "[realsense] WARN: Could not identify USB device path; autosuspend setting unchanged." >&2
		return 0
	fi

	power_dir="/sys/bus/usb/devices/${usb_device_id}/power"
	local changed=false
	if [ -w "${power_dir}/control" ]; then
		if printf 'on\n' >"${power_dir}/control"; then
			changed=true
		fi
	fi
	if [ -w "${power_dir}/autosuspend" ]; then
		if printf '%s\n' '-1' >"${power_dir}/autosuspend"; then
			changed=true
		fi
	fi
	if [[ "${changed}" == true ]]; then
		echo "[realsense] USB autosuspend disabled for ${usb_device_id}"
	else
		echo "[realsense] WARN: USB power settings are not writable for ${usb_device_id}; autosuspend setting unchanged." >&2
	fi
}

realsense_detected() {
	local out
	out="$(rs-enumerate-devices 2>/dev/null || true)"

	# Primary signal: at least one real device serial reported.
	if printf "%s\n" "${out}" |
		awk -F': ' '/^[[:space:]]*Serial Number[[:space:]]*:/ {found=1} END{exit !found}'; then
		return 0
	fi

	# Fallback signal: module stream profiles are present in enumerate output.
	if printf "%s\n" "${out}" | grep -q "Stream Profiles supported by"; then
		return 0
	fi

	return 1
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
		serials="$(extract_device_serials)"

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
normalize_unite_imu_method
echo "[realsense] Using unite_imu_method=${RS_UNITE_IMU_METHOD}"
echo "[realsense] Using base_frame_id=${RS_BASE_FRAME_ID}"

SELECTED_SERIAL="$(pick_serial_or_fail)"

if have_cmd rs-enumerate-devices; then
	# If we can enumerate but no device -> hard fail
	if ! realsense_detected; then
		echo "[realsense] ERROR: No RealSense devices detected inside container." >&2
		echo "[realsense]        Check USB mapping (/dev/bus/usb), privileges, cable, and power." >&2
		exit 3
	fi
fi

disable_usb_autosuspend

if [ -n "${RS_USB_PORT_ID}" ] && have_cmd rs-enumerate-devices; then
	PHYSICAL_PORTS="$(extract_physical_ports | sed '/^$/d' || true)"
	if [ -n "${PHYSICAL_PORTS}" ] && ! printf "%s\n" "${PHYSICAL_PORTS}" | grep -Fq "${RS_USB_PORT_ID}"; then
		echo "[realsense] WARN: RS_USB_PORT_ID='${RS_USB_PORT_ID}' not found in detected Physical Port values." >&2
		echo "[realsense]       Detected Physical Port values:" >&2
		printf "%s\n" "${PHYSICAL_PORTS}" | sed 's/^/  - /' >&2
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
	"base_frame_id:=${RS_BASE_FRAME_ID}"
	"depth_module.depth_profile:=${RS_DEPTH_PROFILE}"
	"rgb_camera.color_profile:=${RS_COLOR_PROFILE}"
	"gyro_fps:=${RS_GYRO_FPS}"
	"accel_fps:=${RS_ACCEL_FPS}"
	"align_depth.enable:=${RS_ALIGN_DEPTH}"
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

if [ -z "${RS_WATCHDOG_TOPIC}" ]; then
	RS_WATCHDOG_TOPIC="/camera/${RS_CAMERA_NAME}/color/camera_info"
fi

apply_runtime_compression_tuning() {
	local node="/camera/${RS_CAMERA_NAME}"
	local attempts=60
	local attempt

	if [[ -z "${RS_COMPRESSED_JPEG_QUALITY}" ]]; then
		echo "[realsense] Compressed JPEG quality tuning disabled."
		return 0
	fi

	if [[ ! "${RS_COMPRESSED_JPEG_QUALITY}" =~ ^[0-9]+$ ]] || ((RS_COMPRESSED_JPEG_QUALITY < 1 || RS_COMPRESSED_JPEG_QUALITY > 100)); then
		echo "[realsense] WARN: RS_COMPRESSED_JPEG_QUALITY='${RS_COMPRESSED_JPEG_QUALITY}' is invalid; expected 1..100. Leaving default compressed transport quality." >&2
		return 0
	fi

	for ((attempt = 1; attempt <= attempts; attempt++)); do
		if ! kill -0 "${RS_PID}" 2>/dev/null; then
			return 0
		fi

		if ros2 node list 2>/dev/null | grep -Fxq -- "${node}"; then
			# Check jpeg_quality is declared before setting it to avoid a WARN from
			# the realsense node's rclcpp when image_transport hasn't loaded yet.
			if ros2 param list "${node}" 2>/dev/null | grep -qF "jpeg_quality" &&
				ros2 param set "${node}" jpeg_quality "${RS_COMPRESSED_JPEG_QUALITY}" >/dev/null 2>&1; then
				echo "[realsense] Set ${node} jpeg_quality=${RS_COMPRESSED_JPEG_QUALITY} for compressed image transport"
				return 0
			fi
		fi

		sleep 1
	done

	echo "[realsense] WARN: Could not set jpeg_quality on ${node}; leaving default compressed transport quality." >&2
	return 0
}

stop_process() {
	local pid="${1:-}"
	local label="${2:-process}"
	local attempt
	[[ -z "${pid}" ]] && return 0
	if ! kill -0 "${pid}" 2>/dev/null; then
		wait "${pid}" 2>/dev/null || true
		return 0
	fi

	kill -TERM "${pid}" 2>/dev/null || true
	for ((attempt = 0; attempt < 50; attempt++)); do
		if ! kill -0 "${pid}" 2>/dev/null; then
			wait "${pid}" 2>/dev/null || true
			return 0
		fi
		sleep 0.2
	done

	echo "[realsense] WARN: ${label} did not stop after 10s; sending SIGKILL." >&2
	kill -KILL "${pid}" 2>/dev/null || true
	wait "${pid}" 2>/dev/null || true
}

# shellcheck disable=SC2329
terminate() {
	stop_process "${WATCHDOG_PID:-}" "frame watchdog"
	stop_process "${TUNER_PID:-}" "compression tuner"
	stop_process "${RS_PID:-}" "RealSense launch"
	exit 0
}

cleanup_helpers() {
	if [[ -n "${WATCHDOG_PID:-}" ]] && [[ "${FINISHED_PID:-}" != "${WATCHDOG_PID}" ]]; then
		stop_process "${WATCHDOG_PID}" "frame watchdog"
	fi
	stop_process "${TUNER_PID:-}" "compression tuner"
}

ros2 launch realsense2_camera rs_launch.py "${args[@]}" &
RS_PID=$!

trap terminate SIGINT SIGTERM
apply_runtime_compression_tuning &
TUNER_PID=$!

WATCHDOG_PID=""
case "${RS_WATCHDOG_ENABLED,,}" in
1 | true | yes | on)
	echo "[realsense] Starting frame watchdog topic=${RS_WATCHDOG_TOPIC} startup_timeout=${RS_WATCHDOG_STARTUP_TIMEOUT_S}s stale_timeout=${RS_WATCHDOG_STALE_TIMEOUT_S}s"
	python3 /app/realsense_watchdog.py \
		--topic "${RS_WATCHDOG_TOPIC}" \
		--startup-timeout "${RS_WATCHDOG_STARTUP_TIMEOUT_S}" \
		--stale-timeout "${RS_WATCHDOG_STALE_TIMEOUT_S}" &
	WATCHDOG_PID=$!
	;;
*)
	echo "[realsense] Frame watchdog disabled."
	;;
esac

set +e
if [[ -n "${WATCHDOG_PID}" ]]; then
	FINISHED_PID=""
	wait -n -p FINISHED_PID "${RS_PID}" "${WATCHDOG_PID}"
	FIRST_STATUS=$?

	if [[ "${FINISHED_PID}" == "${WATCHDOG_PID}" ]]; then
		WATCHDOG_STATUS="${FIRST_STATUS}"
		if [[ "${WATCHDOG_STATUS}" -eq 0 ]]; then
			WATCHDOG_STATUS=22
		fi
		echo "[realsense] Frame watchdog exited with status ${WATCHDOG_STATUS}; stopping camera launch for Docker restart." >&2
		stop_process "${RS_PID}" "RealSense launch"
		RS_STATUS="${WATCHDOG_STATUS}"
	else
		RS_STATUS="${FIRST_STATUS}"
	fi
else
	wait "${RS_PID}"
	RS_STATUS=$?
fi
set -e

cleanup_helpers
exit "${RS_STATUS}"
