#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "[nav_cont] CONTAINER START  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# Simplified Nav2 start script (reverted from strict map gating version).
# Goals:
#  - Allow Nav2 to start even if no map file is currently chosen.
#  - Still honor MAP_FILE (or MAP_SESSION) if provided so autonomous navigation can work.
#  - Keep goal forwarder for /move_base_simple/goal (or overridden GOAL_TOPIC).
#  - Preserve environment-driven map selection used by mapping + DB pipeline.
#
# Environment variables:
#   MAP_ROOT         (default /srv/maps)
#   MAP_SESSION      (optional session directory under MAP_ROOT)
#   MAP_FILE         (explicit map YAML path; overrides MAP_SESSION)
#   NAV2_PARAMS_FILE (default /app/nav2_params.yaml)
#   GOAL_TOPIC       (default /move_base_simple/goal)
#   FORCE_MAP_WAIT   (0/1) if 1 and MAP_FILE resolved, wait until it exists (default 0 now)

: "${MAP_ROOT:=/srv/maps}"
: "${MAP_SESSION:=}"
: "${MAP_FILE:=}"
: "${NAV2_PARAMS_FILE:=/app/nav2_params.yaml}"
: "${GOAL_TOPIC:=/move_base_simple/goal}"
: "${FORCE_MAP_WAIT:=0}"
: "${NAV2_LAUNCH_FILE:=/app/robot_nav_launch.py}"
: "${NAV2_USE_AMCL:=true}"
: "${MAPPING_MODE:=0}"          # Set to 1 during mapping: skips Nav2/goal_forwarder, keeps cmd_vel_mux+joystick
: "${ENABLE_CMD_VEL_MUX:=1}"
: "${ENABLE_JOYSTICK:=1}"
: "${JOYSTICK_DEV:=/dev/input/js0}"
: "${TELEOP_CONFIG:=/app/teleop_f710.yaml}"
: "${CMD_VEL_AUTO:=/cmd_vel_auto}"
: "${CMD_VEL_JOY:=/cmd_vel_joy}"
: "${CMD_VEL_OUT:=/cmd_vel}"
: "${ENABLE_COLLISION_MONITOR:=0}"
: "${COLLISION_MONITOR_PARAMS:=/app/collision_monitor_params.yaml}"
: "${CMD_VEL_COLLISION_IN:=/cmd_vel_collision_in}"
: "${ENABLE_CMD_VEL_SAFETY_FILTER:=0}"
: "${CMD_VEL_SAFETY_INPUT:=/cmd_vel_safety_in}"
: "${CMD_VEL_SAFETY_STATUS:=/cmd_vel_safety_status}"
: "${CMD_VEL_FORWARD_MAX_SPEED:=0.22}"
: "${CMD_VEL_REVERSE_MAX_SPEED:=0.22}"
: "${CMD_VEL_ANGULAR_MAX_SPEED:=0.40}"
: "${CMD_VEL_FORBID_REVERSE_TURNING:=false}"
: "${CMD_VEL_SCAN_STOP_ENABLED:=false}"
: "${CMD_VEL_SCAN_TOPIC:=/scan_filtered}"
: "${CMD_VEL_FRONT_STOP_DISTANCE:=0.28}"
: "${CMD_VEL_REAR_STOP_DISTANCE:=0.22}"
: "${CMD_VEL_SCAN_HALF_ANGLE_DEG:=28.0}"
: "${CMD_VEL_SCAN_MIN_POINTS:=2}"
: "${CMD_VEL_MAP_STOP_ENABLED:=false}"
: "${CMD_VEL_MAP_TOPIC:=/map}"
: "${CMD_VEL_POSE_TOPIC:=/amcl_pose}"
: "${CMD_VEL_MAP_LOOKAHEAD_M:=0.30}"
: "${CMD_VEL_MAP_HALF_WIDTH_M:=0.18}"
: "${ENABLE_ROBOT_POSE_MAP_PUBLISHER:=0}"
: "${ROBOT_POSE_MAP_TOPIC:=/robot_pose_map}"
: "${ROBOT_POSE_MAP_FRAME:=map}"
: "${ROBOT_POSE_BASE_FRAME:=base_link}"
: "${ROBOT_POSE_PUBLISH_RATE_HZ:=1.0}"
: "${ROBOT_POSE_LOOKUP_TIMEOUT_S:=0.2}"
: "${MANUAL_DEFAULT:=false}"
: "${MANUAL_TIMEOUT_S:=0.5}"
: "${AUTO_TIMEOUT_S:=0.7}"
: "${MUX_PUBLISH_RATE_HZ:=20.0}"
: "${MANUAL_SPEED_SCALE:=1.0}"
: "${MANUAL_ANGULAR_SCALE:=1.0}"

# If MAP_FILE is set but missing, fall back to auto-resolution.
if [ -n "${MAP_FILE}" ] && [ ! -f "${MAP_FILE}" ]; then
	echo "[nav_start][WARN] MAP_FILE set but not found: ${MAP_FILE}. Falling back to auto-resolve."
	MAP_FILE=""
fi
if [ -n "${MAP_FILE}" ] && [ -f "${MAP_FILE}" ] && [ ! -s "${MAP_FILE}" ]; then
	echo "[nav_start][WARN] MAP_FILE is empty: ${MAP_FILE}. Falling back to auto-resolve."
	MAP_FILE=""
fi

# Lightweight resolution (kept, but non-blocking):
if [ -z "${MAP_FILE}" ]; then
	if [ -n "${MAP_SESSION}" ]; then
		for cand in "${MAP_ROOT}/${MAP_SESSION}/final/map.yaml" "${MAP_ROOT}/${MAP_SESSION}/map.yaml"; do
			if [ -f "$cand" ]; then
				MAP_FILE="$cand"
				break
			fi
		done
	fi
	# /app/map.yaml written by select_map.sh on the host (mounted from config/containers/map.yaml)
	if [ -z "${MAP_FILE}" ]; then
		if [ -f "/app/map.yaml" ] && [ -s "/app/map.yaml" ] && ! grep -q "placeholder: true" "/app/map.yaml"; then
			MAP_FILE="/app/map.yaml"
			echo "[nav_start] Using map from /app/map.yaml (set by select_map.sh)"
		fi
	fi
	# Active / latest symlinks as fallbacks
	if [ -z "${MAP_FILE}" ]; then
		for cand in \
			"${MAP_ROOT}/active/final/map.yaml" "${MAP_ROOT}/active/map.yaml" \
			"${MAP_ROOT}/latest/final/map.yaml" "${MAP_ROOT}/latest/map.yaml"; do
			if [ -f "$cand" ]; then
				MAP_FILE="$cand"
				break
			fi
		done
	fi
fi

if [ -n "${MAP_FILE}" ]; then
	echo "[nav_start] Using map file: ${MAP_FILE}"
	if [ "${FORCE_MAP_WAIT}" = "1" ]; then
		echo "[nav_start] Waiting for map file to exist (FORCE_MAP_WAIT=1)"
		while [ ! -f "${MAP_FILE}" ]; do
			sleep 2
			echo "[nav_start][WAIT] ${MAP_FILE}"
		done
	fi
else
	echo "[nav_start][INFO] No existing map resolved -> generating temporary placeholder so GUI prikazuje nešto."
	PLACEHOLDER_DIR="${MAP_ROOT}/__auto_placeholder"
	mkdir -p "${PLACEHOLDER_DIR}"
	PLACE_YAML="${PLACEHOLDER_DIR}/map.yaml"
	PLACE_PGM="${PLACEHOLDER_DIR}/map.pgm"
	if [ ! -f "${PLACE_PGM}" ]; then
		# Create a small 40x40 fully free space map (P5 binary PGM, maxval 255)
		{
			echo "P5"
			echo "40 40"
			echo "255"
			perl -e 'print chr(255) x (40*40)'
		} >"${PLACE_PGM}" 2>/dev/null || {
			{
				echo "P2"
				echo "40 40"
				echo "255"
			} >"${PLACE_PGM}"
			yes 255 | head -n $((40 * 40)) >>"${PLACE_PGM}"
		}
	fi
	cat >"${PLACE_YAML}" <<EOF
image: map.pgm
mode: trinary
resolution: 0.05
origin: [0.0, 0.0, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
placeholder: true
note: "Automatski generirana privremena mapa - zamijeni postavljanjem MAP_FILE / MAP_SESSION i restartom nav kontenjera"
EOF
	MAP_FILE="${PLACE_YAML}"
	echo "[nav_start] Placeholder map generated at ${MAP_FILE}"
fi

if [ ! -f "${NAV2_PARAMS_FILE}" ]; then
	echo "[nav_start][WARN] Nav2 params file missing: ${NAV2_PARAMS_FILE}" >&2
fi
if [ "${ENABLE_COLLISION_MONITOR}" = "1" ] && [ ! -f "${COLLISION_MONITOR_PARAMS}" ]; then
	echo "[nav_start][WARN] Collision monitor enabled but params missing: ${COLLISION_MONITOR_PARAMS}; publishing directly to ${CMD_VEL_OUT}" >&2
	ENABLE_COLLISION_MONITOR=0
fi

export AMENT_TRACE_SETUP_FILES=${AMENT_TRACE_SETUP_FILES:-}
set +u
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
set -u

MAP_ARG=()
if [ -n "${MAP_FILE}" ] && [ -f "${MAP_FILE}" ]; then
	MAP_ARG+=("map:=${MAP_FILE}")
fi

FINAL_CMD_VEL_OUT="${CMD_VEL_OUT}"
POST_COLLISION_CMD_VEL_OUT="${FINAL_CMD_VEL_OUT}"
if [ "${ENABLE_CMD_VEL_SAFETY_FILTER}" = "1" ]; then
	POST_COLLISION_CMD_VEL_OUT="${CMD_VEL_SAFETY_INPUT}"
fi

MUX_CMD_VEL_OUT="${POST_COLLISION_CMD_VEL_OUT}"
if [ "${ENABLE_COLLISION_MONITOR}" = "1" ]; then
	MUX_CMD_VEL_OUT="${CMD_VEL_COLLISION_IN}"
fi

NAV_CMD_VEL_OUT="${MUX_CMD_VEL_OUT}"
if [ "${ENABLE_CMD_VEL_MUX}" = "1" ]; then
	NAV_CMD_VEL_OUT="${CMD_VEL_AUTO}"
fi

NAV2_PID=""
GOAL_FORWARDER_PID=""
EXTRA_PIDS=()

if [ "${MAPPING_MODE}" = "1" ]; then
	echo "[nav_start] MAPPING_MODE=1 — skipping Nav2 and goal_forwarder (cmd_vel_mux + optional collision monitor + joystick)"
else
	echo "[nav_start] Launching Nav2 params=${NAV2_PARAMS_FILE} ${MAP_ARG:+with map arg} use_amcl=${NAV2_USE_AMCL} cmd_vel_out=${NAV_CMD_VEL_OUT}"
	if [ -f "${NAV2_LAUNCH_FILE}" ]; then
		ros2 launch "${NAV2_LAUNCH_FILE}" \
			"${MAP_ARG[@]}" \
			params_file:="${NAV2_PARAMS_FILE}" \
			cmd_vel_out:="${NAV_CMD_VEL_OUT}" \
			use_amcl:="${NAV2_USE_AMCL}" \
			use_composition:=False \
			autostart:=true &
	else
		echo "[nav_start][WARN] Custom launch file missing (${NAV2_LAUNCH_FILE}); falling back to nav2_bringup/navigation_launch.py"
		ros2 launch nav2_bringup navigation_launch.py params_file:="${NAV2_PARAMS_FILE}" &
	fi
	NAV2_PID=$!

	sleep 5 || true

	python3 /app/goal_forwarder.py --ros-args -p goal_topic:="${GOAL_TOPIC}" &
	GOAL_FORWARDER_PID=$!
fi

if [ "${ENABLE_CMD_VEL_MUX}" = "1" ]; then
	echo "[nav_start] Starting cmd_vel mux (manual_default=${MANUAL_DEFAULT})"
	python3 /app/cmd_vel_mux.py --ros-args \
		-p auto_topic:="${CMD_VEL_AUTO}" \
		-p joy_topic:="${CMD_VEL_JOY}" \
		-p out_topic:="${MUX_CMD_VEL_OUT}" \
		-p manual_default:="${MANUAL_DEFAULT}" \
		-p manual_timeout_s:="${MANUAL_TIMEOUT_S}" \
		-p auto_timeout_s:="${AUTO_TIMEOUT_S}" \
		-p publish_rate_hz:="${MUX_PUBLISH_RATE_HZ}" \
		-p manual_speed_scale:="${MANUAL_SPEED_SCALE}" \
		-p manual_angular_scale:="${MANUAL_ANGULAR_SCALE}" &
	EXTRA_PIDS+=("$!")
fi

if [ "${ENABLE_COLLISION_MONITOR}" = "1" ]; then
	echo "[nav_start] Starting collision monitor params=${COLLISION_MONITOR_PARAMS} in=${MUX_CMD_VEL_OUT} out=${POST_COLLISION_CMD_VEL_OUT}"
	ros2 launch /app/collision_monitor_launch.py \
		params_file:="${COLLISION_MONITOR_PARAMS}" \
		cmd_vel_in:="${MUX_CMD_VEL_OUT}" \
		cmd_vel_out:="${POST_COLLISION_CMD_VEL_OUT}" &
	EXTRA_PIDS+=("$!")
fi

if [ "${ENABLE_CMD_VEL_SAFETY_FILTER}" = "1" ]; then
	echo "[nav_start] Starting cmd_vel safety filter in=${POST_COLLISION_CMD_VEL_OUT} out=${FINAL_CMD_VEL_OUT}"
	python3 /app/cmd_vel_safety_filter.py --ros-args \
		-p input_topic:="${POST_COLLISION_CMD_VEL_OUT}" \
		-p output_topic:="${FINAL_CMD_VEL_OUT}" \
		-p status_topic:="${CMD_VEL_SAFETY_STATUS}" \
		-p forward_max_speed:="${CMD_VEL_FORWARD_MAX_SPEED}" \
		-p reverse_max_speed:="${CMD_VEL_REVERSE_MAX_SPEED}" \
		-p angular_max_speed:="${CMD_VEL_ANGULAR_MAX_SPEED}" \
		-p forbid_reverse_turning:="${CMD_VEL_FORBID_REVERSE_TURNING}" \
		-p scan_stop_enabled:="${CMD_VEL_SCAN_STOP_ENABLED}" \
		-p scan_topic:="${CMD_VEL_SCAN_TOPIC}" \
		-p front_stop_distance:="${CMD_VEL_FRONT_STOP_DISTANCE}" \
		-p rear_stop_distance:="${CMD_VEL_REAR_STOP_DISTANCE}" \
		-p scan_half_angle_deg:="${CMD_VEL_SCAN_HALF_ANGLE_DEG}" \
		-p scan_min_points:="${CMD_VEL_SCAN_MIN_POINTS}" \
		-p map_stop_enabled:="${CMD_VEL_MAP_STOP_ENABLED}" \
		-p map_topic:="${CMD_VEL_MAP_TOPIC}" \
		-p pose_topic:="${CMD_VEL_POSE_TOPIC}" \
		-p map_lookahead_m:="${CMD_VEL_MAP_LOOKAHEAD_M}" \
		-p map_half_width_m:="${CMD_VEL_MAP_HALF_WIDTH_M}" &
	EXTRA_PIDS+=("$!")
fi

if [ "${ENABLE_ROBOT_POSE_MAP_PUBLISHER}" = "1" ]; then
	echo "[nav_start] Starting robot_pose_map publisher topic=${ROBOT_POSE_MAP_TOPIC}"
	python3 /app/robot_pose_map_publisher.py --ros-args \
		-p map_frame:="${ROBOT_POSE_MAP_FRAME}" \
		-p base_frame:="${ROBOT_POSE_BASE_FRAME}" \
		-p pose_topic:="${ROBOT_POSE_MAP_TOPIC}" \
		-p publish_rate_hz:="${ROBOT_POSE_PUBLISH_RATE_HZ}" \
		-p lookup_timeout_s:="${ROBOT_POSE_LOOKUP_TIMEOUT_S}" &
	EXTRA_PIDS+=("$!")
fi

if [ "${ENABLE_JOYSTICK}" = "1" ]; then
	if [ -e "${JOYSTICK_DEV}" ]; then
		echo "[nav_start] Starting joystick input: dev=${JOYSTICK_DEV}"
		ros2 run joy joy_node --ros-args -p dev:="${JOYSTICK_DEV}" &
		EXTRA_PIDS+=("$!")

		if [ -f "${TELEOP_CONFIG}" ]; then
			echo "[nav_start] Starting teleop_twist_joy with config ${TELEOP_CONFIG}"
			ros2 run teleop_twist_joy teleop_node --ros-args --params-file "${TELEOP_CONFIG}" -r cmd_vel:="${CMD_VEL_JOY}" &
			EXTRA_PIDS+=("$!")
		else
			echo "[nav_start][WARN] Teleop config not found: ${TELEOP_CONFIG}"
		fi
	else
		echo "[nav_start][INFO] Joystick device not found (${JOYSTICK_DEV}); skipping joystick"
	fi
fi

if [ "${MAPPING_MODE}" = "1" ]; then
	echo "[nav_start] Mapping mode ready — /set_manual_mode service available, Nav2 not running."
else
	echo "[nav_start] Nav2 PID=${NAV2_PID}; GoalForwarder PID=${GOAL_FORWARDER_PID}"
	echo "[nav_start] Ready. If you later define a map, restart this container to apply it (or use select_map.sh if present)."
	echo "[nav_start] AMCL localization active: postavite početnu pozu preko Foxglove 2D Pose Estimate (publisha na /initialpose) ili:"
	echo "[nav_start]   python3 /app/set_initial_pose.py <x> <y> <yaw_deg> [map_frame]"
	echo "[nav_start] Primjer: python3 /app/set_initial_pose.py 0.0 0.0 90"
fi

trap 'echo "[nav_start] Stopping..."; kill ${GOAL_FORWARDER_PID:-} ${NAV2_PID:-} ${EXTRA_PIDS[@]:-} 2>/dev/null || true; wait ${GOAL_FORWARDER_PID:-} ${NAV2_PID:-} ${EXTRA_PIDS[@]:-} 2>/dev/null || true; exit 0' INT TERM
while true; do
	sleep 60
	echo "[nav_start] heartbeat $(date)"
done
