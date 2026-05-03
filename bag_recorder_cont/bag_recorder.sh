#!/usr/bin/env bash
set -euo pipefail

ROS_DISTRO=${ROS_DISTRO:-humble}
TOPICS_FILE=${TOPICS_FILE:-/config/recorded_topics.yaml}
BAG_OUTPUT_DIR=${BAG_OUTPUT_DIR:-/bags}
MAX_BAG_MB=${MAX_BAG_MB:-150}
MAX_BAG_DURATION_S=${MAX_BAG_DURATION_S:-0}
RESTART_DELAY_S=${RESTART_DELAY_S:-3}
TOPIC_WAIT_TIMEOUT_S=${TOPIC_WAIT_TIMEOUT_S:-30}
TOPIC_RECHECK_INTERVAL_S=${TOPIC_RECHECK_INTERVAL_S:-2}
MIN_ACTIVE_TOPICS=${MIN_ACTIVE_TOPICS:-1}
RESOLVE_TOPIC_ALIASES=${RESOLVE_TOPIC_ALIASES:-1}

TOPICS=()
RESOLVED_TOPICS=()
ACTIVE_TOPICS=()
stop_requested=false

source_ros_environment() {
	export AMENT_TRACE_SETUP_FILES=${AMENT_TRACE_SETUP_FILES:-}
	set +u
	# shellcheck source=/opt/ros/humble/setup.bash
	source "/opt/ros/${ROS_DISTRO}/setup.bash"
	set -u
}

verify_ros_cli() {
	if ! command -v ros2 >/dev/null 2>&1; then
		echo "[bag_recorder][ERROR] ros2 CLI is not available after sourcing /opt/ros/${ROS_DISTRO}/setup.bash" >&2
		echo "[bag_recorder][ERROR] PATH=${PATH}" >&2
		return 1
	fi
}

log_runtime_configuration() {
	echo "[bag_recorder] ROS_DISTRO=${ROS_DISTRO}"
	echo "[bag_recorder] RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-unset}"
	echo "[bag_recorder] ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-unset}"
	echo "[bag_recorder] CYCLONEDDS_URI=${CYCLONEDDS_URI:-unset}"
}

normalize_rmw() {
	local want="${RMW_IMPLEMENTATION:-}"
	if [[ "$want" =~ cyclonedx ]]; then
		echo "[bag_recorder][WARN] Typo in RMW_IMPLEMENTATION='${want}' -> using rmw_cyclonedds_cpp" >&2
		export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
		return
	fi
	if [[ -z "$want" ]]; then
		export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
		return
	fi
	if [[ ! -e "/opt/ros/${ROS_DISTRO}/lib/librmw_${RMW_IMPLEMENTATION}.so" && ! -e "/opt/ros/${ROS_DISTRO}/lib/${RMW_IMPLEMENTATION}/librmw_${RMW_IMPLEMENTATION}.so" ]]; then
		echo "[bag_recorder][WARN] RMW implementation '${RMW_IMPLEMENTATION}' not installed -> falling back to rmw_cyclonedds_cpp" >&2
		export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
	fi
}

load_topics_file() {
	if [[ ! -s "${TOPICS_FILE}" ]]; then
		echo "No topics file at ${TOPICS_FILE} or it is empty." >&2
		return 1
	fi

	mapfile -t TOPICS < <(
		sed -n 's/^[[:space:]]*-[[:space:]]*//p' "${TOPICS_FILE}" \
		| sed 's/[[:space:]]*#.*$//' \
		| sed 's/\r$//' \
		| sed 's/[[:space:]]*$//' \
		| sed '/^$/d'
	)
	if [[ ${#TOPICS[@]} -eq 0 ]]; then
		echo "No topics found in ${TOPICS_FILE}." >&2
		return 1
	fi
}

topic_exists() {
	local topic="$1"
	ros2 topic list 2>/dev/null | grep -Fxq -- "${topic}"
}

topic_publisher_count() {
	local topic="$1"
	local out
	out="$(ros2 topic info "${topic}" 2>/dev/null || true)"
	echo "${out}" | awk -F: '/Publisher count/ {gsub(/ /, "", $2); print $2; found=1} END {if (!found) print 0}'
}

topic_has_publishers() {
	local topic="$1"
	local count
	count="$(topic_publisher_count "${topic}")"
	[[ "${count}" =~ ^[0-9]+$ ]] || count=0
	(( count > 0 ))
}

topic_candidates() {
	local requested="$1"
	printf '%s\n' "${requested}"

	case "${requested}" in
		/camera/realsense/*)
			printf '%s\n' "${requested#/camera}"
			;;
		/realsense/*)
			printf '%s\n' "/camera${requested}"
			;;
	esac

	case "${requested}" in
		/odom)
			printf '%s\n' "/wheel_odom"
			;;
		/wheel_odom)
			printf '%s\n' "/odom"
			;;
	esac

	case "${requested}" in
		*/image_compressed)
			printf '%s\n' "${requested%/image_compressed}/image_raw/compressed"
			;;
		*/image_raw/compressed)
			printf '%s\n' "${requested%/image_raw/compressed}/image_compressed"
			;;
	esac
}

dedupe_lines() {
	awk '!seen[$0]++'
}

dedupe_array() {
	if (( $# == 0 )); then
		return 0
	fi
	printf '%s\n' "$@" | dedupe_lines
}

refresh_topic_resolution() {
	local requested
	local resolved
	local candidate
	local best_existing
	RESOLVED_TOPICS=()
	ACTIVE_TOPICS=()

	for requested in "${TOPICS[@]}"; do
		resolved=""
		best_existing=""

		if [[ "${RESOLVE_TOPIC_ALIASES}" == "1" ]]; then
			while IFS= read -r candidate; do
				[[ -z "${candidate}" ]] && continue
				if topic_has_publishers "${candidate}"; then
					resolved="${candidate}"
					break
				fi
				if [[ -z "${best_existing}" ]] && topic_exists "${candidate}"; then
					best_existing="${candidate}"
				fi
			done < <(topic_candidates "${requested}" | dedupe_lines)
		else
			if topic_has_publishers "${requested}"; then
				resolved="${requested}"
			elif topic_exists "${requested}"; then
				best_existing="${requested}"
			fi
		fi

		if [[ -z "${resolved}" && -n "${best_existing}" ]]; then
			resolved="${best_existing}"
		fi
		if [[ -z "${resolved}" ]]; then
			resolved="${requested}"
		fi

		RESOLVED_TOPICS+=("${resolved}")
		if topic_has_publishers "${resolved}"; then
			ACTIVE_TOPICS+=("${resolved}")
		fi
	done

	if (( ${#RESOLVED_TOPICS[@]} > 0 )); then
		mapfile -t RESOLVED_TOPICS < <(dedupe_array "${RESOLVED_TOPICS[@]}")
	else
		RESOLVED_TOPICS=()
	fi

	if (( ${#ACTIVE_TOPICS[@]} > 0 )); then
		mapfile -t ACTIVE_TOPICS < <(dedupe_array "${ACTIVE_TOPICS[@]}")
	else
		ACTIVE_TOPICS=()
	fi
}

wait_for_active_topics() {
	local deadline
	local active_count
	deadline=$((SECONDS + TOPIC_WAIT_TIMEOUT_S))

	while true; do
		refresh_topic_resolution
		active_count=${#ACTIVE_TOPICS[@]}
		if (( active_count >= MIN_ACTIVE_TOPICS )); then
			echo "[bag_recorder] Active topics detected (${active_count}):"
			printf '  - %s\n' "${ACTIVE_TOPICS[@]}"
			echo "[bag_recorder] Recording topic set:"
			printf '  - %s\n' "${RESOLVED_TOPICS[@]}"
			return 0
		fi

		echo "[bag_recorder] Waiting for active ROS topics (${active_count}/${MIN_ACTIVE_TOPICS})..."
		echo "[bag_recorder] Configured topics:"
		printf '  - %s\n' "${TOPICS[@]}"

		if (( SECONDS >= deadline )); then
			echo "[bag_recorder][WARN] No active publishers found after ${TOPIC_WAIT_TIMEOUT_S}s." >&2
			echo "[bag_recorder][WARN] ros2 topic list output at timeout:" >&2
			ros2 topic list 2>/dev/null | sed 's/^/  - /' >&2 || true
			return 1
		fi

		sleep "${TOPIC_RECHECK_INTERVAL_S}"
	done
}

terminate() {
	stop_requested=true
	if [[ -n ${record_pid:-} ]]; then
		kill -INT "${record_pid}" 2>/dev/null || true
	fi
}

run_recorder_loop() {
	local timestamp
	local prefix
	local max_bag_bytes
	local exit_code
	local -a args

	while [[ "${stop_requested}" == false ]]; do
		timestamp=$(date -u +%Y%m%d-%H%M%S)
		prefix="${BAG_OUTPUT_DIR}/recording_${timestamp}"

		max_bag_bytes=$((MAX_BAG_MB * 1024 * 1024))
		if [[ ${max_bag_bytes} -lt 86016 ]]; then
			echo "MAX_BAG_MB too small (${MAX_BAG_MB}); must be >= 1 MB" >&2
			return 1
		fi

		if ! wait_for_active_topics; then
			echo "[bag_recorder] Skipping recorder start and retrying in ${RESTART_DELAY_S}s"
			sleep "${RESTART_DELAY_S}"
			continue
		fi

		args=(ros2 bag record --output "${prefix}" --max-bag-size "${max_bag_bytes}" --compression-mode file --compression-format zstd)
		if [[ "${MAX_BAG_DURATION_S}" != "0" ]]; then
			args+=(--max-bag-duration "${MAX_BAG_DURATION_S}")
		fi
		args+=("${RESOLVED_TOPICS[@]}")

		echo "Starting ros2 bag record -> ${prefix} (max ${MAX_BAG_MB} MB per bag)"
		"${args[@]}" &
		record_pid=$!
		set +e
		wait "${record_pid}"
		exit_code=$?
		set -e

		if [[ "${stop_requested}" == true ]]; then
			break
		fi

		echo "Recorder exited with code ${exit_code}; restarting in ${RESTART_DELAY_S}s"
		sleep "${RESTART_DELAY_S}"
	done

	echo "Recorder stopped."
}

main() {
	source_ros_environment
	normalize_rmw
	verify_ros_cli
	log_runtime_configuration
	load_topics_file
	mkdir -p "${BAG_OUTPUT_DIR}"
	trap terminate SIGINT SIGTERM
	run_recorder_loop
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi
