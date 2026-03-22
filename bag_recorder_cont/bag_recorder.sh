#!/usr/bin/env bash
set -euo pipefail

ROS_DISTRO=${ROS_DISTRO:-jazzy}
TOPICS_FILE=${TOPICS_FILE:-/config/recorded_topics.yaml}
BAG_OUTPUT_DIR=${BAG_OUTPUT_DIR:-/bags}
MAX_BAG_MB=${MAX_BAG_MB:-150}
MAX_BAG_DURATION_S=${MAX_BAG_DURATION_S:-0}
RESTART_DELAY_S=${RESTART_DELAY_S:-3}

export AMENT_TRACE_SETUP_FILES=${AMENT_TRACE_SETUP_FILES:-}
set +u
source /opt/ros/${ROS_DISTRO}/setup.bash
set -u

if [[ ! -s "${TOPICS_FILE}" ]]; then
	echo "No topics file at ${TOPICS_FILE} or it is empty." >&2
	exit 1
fi

mapfile -t TOPICS < <(sed -n 's/^[[:space:]]*-[[:space:]]*//p' "${TOPICS_FILE}" | sed '/^$/d')
if [[ ${#TOPICS[@]} -eq 0 ]]; then
	echo "No topics found in ${TOPICS_FILE}." >&2
	exit 1
fi

mkdir -p "${BAG_OUTPUT_DIR}"

stop_requested=false
terminate() {
	stop_requested=true
	if [[ -n ${record_pid:-} ]]; then
		kill -INT "${record_pid}" 2>/dev/null || true
	fi
}
trap terminate SIGINT SIGTERM

while [[ "${stop_requested}" == false ]]; do
	timestamp=$(date -u +%Y%m%d-%H%M%S)
	prefix="${BAG_OUTPUT_DIR}/recording_${timestamp}"

	max_bag_bytes=$((MAX_BAG_MB * 1024 * 1024))
	if [[ ${max_bag_bytes} -lt 86016 ]]; then
		echo "MAX_BAG_MB too small (${MAX_BAG_MB}); must be >= 1 MB" >&2
		exit 1
	fi

	args=(ros2 bag record --output "${prefix}" --max-bag-size "${max_bag_bytes}" --compression-mode file --compression-format zstd)
	if [[ "${MAX_BAG_DURATION_S}" != "0" ]]; then
		args+=(--max-bag-duration "${MAX_BAG_DURATION_S}")
	fi
	args+=("${TOPICS[@]}")

	echo "Starting ros2 bag record -> ${prefix} (max ${MAX_BAG_MB} MB per bag)"
	"${args[@]}" &
	record_pid=$!
	wait "${record_pid}"
	exit_code=$?

	if [[ "${stop_requested}" == true ]]; then
		break
	fi

	echo "Recorder exited with code ${exit_code}; restarting in ${RESTART_DELAY_S}s"
	sleep "${RESTART_DELAY_S}"
done

echo "Recorder stopped."
