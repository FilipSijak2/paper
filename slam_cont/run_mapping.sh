#!/usr/bin/env bash
set -euo pipefail

# Automated live SLAM + rosbag recording + offline map extraction after Ctrl+C
# Usage (inside container with ROS 2 Humble):
#   bash run_mapping.sh [--bag-prefix mysession] [--duration 0] [--topics-file topics.txt]
# If --duration > 0, recording stops after that many seconds automatically.
# On Ctrl+C: gracefully stop recording & slam_toolbox, replay bag to save final map, insert into DB.

# Legacy bag prefix (still used for bag file base). Naming overhaul below.
BAG_PREFIX="session"
DURATION=0
TOPICS_FILE=""

# Incremental naming configuration
# Default behavior now: directories named mapa1, mapa2, ... (NAME_PREFIX + index)
# Disable by exporting INCREMENTAL_NAMES=0 (then timestamp legacy name is used)
# Force a specific name with --name <value> (will append _N if already exists)
INCREMENTAL_NAMES=${INCREMENTAL_NAMES:-1}
NAME_PREFIX="${NAME_PREFIX:-mapa}"
CUSTOM_NAME=""

# Base directory for all mapping outputs (can override with env MAP_ROOT)
MAP_ROOT_DEFAULT="/app/maps"
MAP_ROOT="${MAP_ROOT:-$MAP_ROOT_DEFAULT}"
MAP_OUTPUT_BASE="" # will be set after session id
# DB connection defaults (ALLOW override from container environment). NOTE: earlier hard-coded values blocked compose env.
# For host networking, service/container names (db_cont, db, database) usually will NOT resolve -> prefer localhost / 127.0.0.1.
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-robot_data}"
DB_USER="${DB_USER:-robot_user}"
DB_PASS="${DB_PASS:-robot_pass}"
SAVE_SERVICE="/slam_toolbox/save_map"             # slam_toolbox exposes a SaveMap service compatible with nav2_msgs/srv/SaveMap in Humble
SAVE_SERVICE_TYPE_DEFAULT="nav2_msgs/srv/SaveMap" # We'll verify at runtime
SLAM_LAUNCH=(slam_toolbox online_async_launch.py)
RESTART_LOCALIZATION=${RESTART_LOCALIZATION:-0}
MAX_SAVEMAP_SECONDS=${MAX_SAVEMAP_SECONDS:-10} # Max wall time for a single SaveMap call
USE_NAV2_EXPORT=${USE_NAV2_EXPORT:-auto}       # auto|always|never
OCCUPANCY_MODE=${OCCUPANCY_MODE:-trinary}
OCC_FREE_THRESH=${OCC_FREE_THRESH:-0.25}
OCC_OCC_THRESH=${OCC_OCC_THRESH:-0.65}
NAV2_SAVE_TIMEOUT=${NAV2_SAVE_TIMEOUT:-20}
WAIT_MAP_TOPIC=${WAIT_MAP_TOPIC:-/map}
WAIT_MAP_TIMEOUT=${WAIT_MAP_TIMEOUT:-8}
BAG_REPLAY_RATE=${BAG_REPLAY_RATE:-1.0}
USE_REPLAY=${USE_REPLAY:-0}                                 # 0 = no replay (default), 1 = perform replay refinement
STORAGE_BACKEND=${STORAGE_BACKEND:-sqlite3}                 # sqlite3|mcap
FALLBACK_MAP_TIMEOUT=${FALLBACK_MAP_TIMEOUT:-8}             # seconds to wait for /map in fallback exporter
MAP_AVAILABLE_TIMEOUT=${MAP_AVAILABLE_TIMEOUT:-10}          # total seconds to wait after CTRL+C for /map to appear
FORCE_NEW_SLAM=${FORCE_NEW_SLAM:-0}                         # 1 = kill any existing slam_toolbox and start fresh with params
SLAM_PARAMS_FILE=${SLAM_PARAMS_FILE:-/app/slam_params.yaml} # path to param file (mounted from compose)
PUBLISH_MAP_PARAM_KEY=${PUBLISH_MAP_PARAM_KEY:-publish_map}
FORCE_MAPPING=${FORCE_MAPPING:-1} # 1 => enforce mode=mapping after launch
DB_HOST_CANDIDATES=${DB_HOST_CANDIDATES:-"localhost 127.0.0.1 $DB_HOST db_cont db database postgres"}
DB_MAX_RETRIES=${DB_MAX_RETRIES:-3}
DB_RETRY_DELAY=${DB_RETRY_DELAY:-3}
SAVE_SERVICE_TYPE=""                  # will be detected on first successful SaveMap call; keep empty safely under set -u with :- expansion
USE_DIRECT_SLAM=${USE_DIRECT_SLAM:-1} # 1 => use ros2 run async_slam_toolbox_node with params file, bypass generic launch
MAP_TOPIC_CANDIDATES=${MAP_TOPIC_CANDIDATES:-"/map /slam_toolbox/map /localized_map"}

# Reentrancy lock for cleanup
CLEANUP_LOCK=0

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
NC="\033[0m"

log() { echo -e "${BLUE}[run_mapping]${NC} $*"; }
info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err() { echo -e "${RED}[ERROR]${NC} $*"; }

while [[ $# -gt 0 ]]; do
	case "$1" in
	--bag-prefix)
		BAG_PREFIX="$2"
		shift 2
		;;
	--duration)
		DURATION="$2"
		shift 2
		;;
	--topics-file)
		TOPICS_FILE="$2"
		shift 2
		;;
	--map-base)
		MAP_OUTPUT_BASE="$2"
		shift 2
		;;
	--db-host)
		DB_HOST="$2"
		shift 2
		;;
	--db-name)
		DB_NAME="$2"
		shift 2
		;;
	--db-user)
		DB_USER="$2"
		shift 2
		;;
	--db-pass)
		DB_PASS="$2"
		shift 2
		;;
	--root-dir)
		MAP_ROOT="$2"
		shift 2
		;;
	--with-replay)
		USE_REPLAY=1
		shift
		;;
	--storage)
		STORAGE_BACKEND="$2"
		shift 2
		;;
	--name)
		CUSTOM_NAME="$2"
		shift 2
		;;
	--prefix)
		NAME_PREFIX="$2"
		shift 2
		;;
	--no-incremental)
		INCREMENTAL_NAMES=0
		shift
		;;
	*)
		warn "Unknown arg $1"
		shift
		;;
	esac
done

# Ensure ROS is sourced (handle unbound AMENT_TRACE_SETUP_FILES under set -u)
if [[ -f /opt/ros/humble/setup.bash ]]; then
	# Provide default to avoid 'unbound variable' in setup files when tracing disabled
	: "${AMENT_TRACE_SETUP_FILES:=}"
	set +u
	# shellcheck disable=SC1091
	source /opt/ros/humble/setup.bash
	set -u
else
	err "ROS 2 environment not found"
	exit 1
fi

SESSION_TS=$(date +%Y%m%d-%H%M%S)
SESSION_TS_UTC=$(date -u +%Y%m%d-%H%M%S)

# Interactive map name prompt (only when no --name given and stdin is a TTY)
if [[ -z "$CUSTOM_NAME" ]] && [[ -t 0 ]]; then
	echo -n "[run_mapping] Enter map name (press Enter for automatic name '${NAME_PREFIX}N'): " >&2
	read -r _user_map_name </dev/tty || true
	if [[ -n "$_user_map_name" ]]; then
		CUSTOM_NAME="$_user_map_name"
		info "Map name: $CUSTOM_NAME"
	else
		info "Using automatic incremental name (${NAME_PREFIX}N)"
	fi
fi

# Determine human-friendly SESSION_ID
SESSION_INDEX=""
if [[ -n "$CUSTOM_NAME" ]]; then
	SESSION_ID="$CUSTOM_NAME"
	# ensure uniqueness
	if [[ -e "$MAP_ROOT/$SESSION_ID" ]]; then
		suffix=1
		while [[ -e "$MAP_ROOT/${SESSION_ID}_$suffix" ]]; do suffix=$((suffix + 1)); done
		warn "Session name $SESSION_ID exists; using ${SESSION_ID}_$suffix"
		SESSION_ID="${SESSION_ID}_$suffix"
	fi
else
	if [[ "$INCREMENTAL_NAMES" == "1" ]]; then
		mkdir -p "$MAP_ROOT" || true
		max_index=0
		while IFS= read -r entry; do
			base=$(basename "$entry")
			if [[ $base =~ ^${NAME_PREFIX}([0-9]+)$ ]]; then
				num=${BASH_REMATCH[1]}
				if ((num > max_index)); then max_index=$num; fi
			fi
		done < <(find "$MAP_ROOT" -maxdepth 1 -mindepth 1 -type d -name "${NAME_PREFIX}*" 2>/dev/null || true)
		SESSION_INDEX=$((max_index + 1))
		SESSION_ID="${NAME_PREFIX}${SESSION_INDEX}"
	else
		SESSION_ID="${BAG_PREFIX}_${SESSION_TS}"
	fi
fi

SESSION_DIR="$MAP_ROOT/$SESSION_ID"
BAG_DIR="$SESSION_DIR/bag"
REPLAY_DIR="$SESSION_DIR/replay"
FINAL_DIR="$SESSION_DIR/final"
LIVE_DIR="$SESSION_DIR/live"
mkdir -p "$BAG_DIR" "$REPLAY_DIR" "$FINAL_DIR" "$LIVE_DIR"
MAP_OUTPUT_BASE="$LIVE_DIR/map"

# Ensure bag directory uniqueness (if user re-runs within same second or leftover from aborted run)
if [[ -e "$BAG_DIR" ]]; then
	if [[ -n "$(find "$BAG_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
		suffix=1
		while [[ -e "${BAG_DIR}_$suffix" ]]; do suffix=$((suffix + 1)); done
		warn "Bag directory $BAG_DIR already exists and not empty -> using ${BAG_DIR}_$suffix"
		BAG_DIR="${BAG_DIR}_$suffix"
		mkdir -p "$BAG_DIR"
	else
		# Empty leftover
		warn "Reusing empty existing bag dir $BAG_DIR"
	fi
fi

# Resolve topics list
if [[ -n "$TOPICS_FILE" ]]; then
	if [[ ! -f "$TOPICS_FILE" ]]; then
		err "Topics file $TOPICS_FILE not found"
		exit 1
	fi
	TOPICS=$(grep -Ev '^#|^$' "$TOPICS_FILE" | xargs || true)
else
	# Default essential topics for slam_toolbox map reproduction.
	# Keep wheel_odom for legacy/debug, plus rf2o and EKF odometry used when encoders are disabled.
	TOPICS="/tf /tf_static /wheel_odom /odom_rf2o /odometry/filtered /scan /imu/data /robot_description /clock"
fi
info "Topics: $TOPICS"
log "Root: $MAP_ROOT | session=$SESSION_ID (incremental=$INCREMENTAL_NAMES prefix=$NAME_PREFIX index=${SESSION_INDEX:-N/A})"

# Detect existing slam_toolbox instance (avoid parallel)
EXISTING_SLAM_PID=""
start_slam() {
	local reason="$1"
	shift || true
	info "Starting slam_toolbox ($reason)..."
	if [[ -f "$SLAM_PARAMS_FILE" ]]; then
		# Ensure publish_map true is present (non-destructive append if missing)
		if ! grep -q "^\s*${PUBLISH_MAP_PARAM_KEY}:" "$SLAM_PARAMS_FILE"; then
			warn "Param ${PUBLISH_MAP_PARAM_KEY} not found in $SLAM_PARAMS_FILE; appending publish_map: true under slam_toolbox: block"
			# naive append; assumes file has slam_toolbox: root. Could be improved with yq.
			printf '\n# Injected to ensure /map publication\n  %s: true\n' "${PUBLISH_MAP_PARAM_KEY}" >>"$SLAM_PARAMS_FILE" || true
		fi
		if [[ "$USE_DIRECT_SLAM" == "1" ]]; then
			# Direct execution avoids extra layers & makes parameter application explicit.
			# In ROS2 Humble, --params-file takes precedence over -p when both are given.
			# Use a second --params-file override to reliably force mode=mapping regardless
			# of what slam_params.yaml says (it may be set to localization for normal nav).
			_MAPPING_OVERRIDE=$(mktemp /tmp/slam_mapping_override_XXXXXX.yaml)
			printf 'slam_toolbox:\n  ros__parameters:\n    mode: mapping\n    map_file_name: ""\n' > "$_MAPPING_OVERRIDE"
			ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
				--params-file "$SLAM_PARAMS_FILE" \
				--params-file "$_MAPPING_OVERRIDE" &
			_MAPPING_OVERRIDE_PID=$!
			sleep 0.5
			rm -f "$_MAPPING_OVERRIDE"
		else
			ros2 launch slam_toolbox online_async_launch.py params_file:="$SLAM_PARAMS_FILE" &
		fi
	else
		warn "Params file $SLAM_PARAMS_FILE not found; launching without explicit params (may not publish /map)."
		ros2 launch "${SLAM_LAUNCH[@]}" &
	fi
	SLAM_PID=$!
	sleep 5
	# Post-launch param enforcement (best-effort)
	for n in slam_toolbox async_slam_toolbox_node async_slam_toolbox; do
		ros2 param set "$n" "${PUBLISH_MAP_PARAM_KEY}" true >/dev/null 2>&1 || true
	done
	if [[ "$FORCE_MAPPING" == "1" ]]; then
		for n in slam_toolbox async_slam_toolbox_node async_slam_toolbox; do
			ros2 param set "$n" mode mapping >/dev/null 2>&1 || true
		done
		info "FORCE_MAPPING=1 -> attempted to enforce mode=mapping"
	fi
}

EXISTING_SLAM_PID=""
# Match all slam_toolbox variants: async (mapping), localization, and launch-based.
# localization_slam_toolbox_node cannot switch to mapping mode (different binary),
# so it must always be killed before starting a mapping session.
SLAM_PGREP_PATTERN="async_slam_toolbox_node|localization_slam_toolbox_node|slam_toolbox.*online_async_launch|slam_toolbox.*localization_launch"
if pgrep -f "$SLAM_PGREP_PATTERN" >/dev/null 2>&1; then
	EXISTING_SLAM_PID=$(pgrep -f "$SLAM_PGREP_PATTERN" | head -n1)
	EXISTING_SLAM_TYPE=$(ps -p "$EXISTING_SLAM_PID" -o args= 2>/dev/null || echo "unknown")
	if echo "$EXISTING_SLAM_TYPE" | grep -q "localization_slam_toolbox_node"; then
		# Localization node cannot do mapping - must be replaced.
		warn "Detected localization_slam_toolbox_node (pid ${EXISTING_SLAM_PID}); killing to start mapping instance."
		kill "$EXISTING_SLAM_PID" || true
		sleep 2
		start_slam "replacing localization with mapping node"
	elif [[ "$FORCE_NEW_SLAM" == "1" ]]; then
		warn "FORCE_NEW_SLAM=1 -> killing existing slam_toolbox (pid ${EXISTING_SLAM_PID}) to relaunch with params"
		kill "$EXISTING_SLAM_PID" || true
		sleep 2
		start_slam "forced restart"
	else
		info "Detected existing slam_toolbox process (pid ${EXISTING_SLAM_PID}); will reuse (set FORCE_NEW_SLAM=1 to restart)."
	fi
else
	start_slam "fresh start"
fi

# Early check: wait briefly for /map; if absent and FORCE_NEW_SLAM=2 (aggressive), restart once automatically
if [[ "$FORCE_NEW_SLAM" == "2" ]]; then
	if ! ros2 topic list | grep -q "^${WAIT_MAP_TOPIC}$"; then
		warn "/map not present after initial launch; restarting slam_toolbox once (FORCE_NEW_SLAM=2 aggressive mode)"
		if [[ -n "${SLAM_PID:-}" ]] && kill -0 "${SLAM_PID}" 2>/dev/null; then
			kill "${SLAM_PID}"
			wait "${SLAM_PID}" 2>/dev/null || true
		fi
		start_slam "aggressive restart"
	fi
fi

# Dynamic map topic detection (best-effort)
detect_map_topic() {
	local chosen=""
	local list
	list=$(ros2 topic list 2>/dev/null || true)
	for cand in $MAP_TOPIC_CANDIDATES; do
		if echo "$list" | grep -q "^${cand}$"; then
			chosen="$cand"
			break
		fi
	done
	if [[ -n "$chosen" ]]; then
		info "Detected map topic candidate: $chosen"
		WAIT_MAP_TOPIC="$chosen"
	else
		warn "No map topic candidates present yet (${MAP_TOPIC_CANDIDATES}); will continue waiting."
	fi
}

detect_map_topic || true

# Start rosbag record
info "Starting rosbag record into $BAG_DIR (session $SESSION_ID | storage=${STORAGE_BACKEND} | replay=$([[ $USE_REPLAY -eq 1 ]] && echo on || echo off))"
ROS2_BAG_BASE="$BAG_DIR/record"
if compgen -G "${ROS2_BAG_BASE}*" >/dev/null; then
	warn "Existing record base $ROS2_BAG_BASE* found; choosing new base name"
	n=1
	while ls "${ROS2_BAG_BASE}_${n}"*.db3 >/dev/null 2>&1; do n=$((n + 1)); done
	ROS2_BAG_BASE="${ROS2_BAG_BASE}_${n}"
fi
read -r -a TOPIC_ARGS <<<"$TOPICS"
REC_CMD=(ros2 bag record -o "$ROS2_BAG_BASE" "${TOPIC_ARGS[@]}")
if [[ "$STORAGE_BACKEND" != "sqlite3" ]]; then REC_CMD+=(--storage "$STORAGE_BACKEND"); fi
if [[ $DURATION -gt 0 ]]; then REC_CMD+=(--max-bag-duration "$DURATION"); fi
"${REC_CMD[@]}" &
BAG_PID=$!
sleep 2
if ! kill -0 $BAG_PID 2>/dev/null; then
	err "ros2 bag record process exited early (PID $BAG_PID). Check topics / permissions. Continuing but replay & final map will be skipped."
	BAG_PID=0
else
	info "ros2 bag record running (pid=$BAG_PID)"
fi

# Function to save live map immediately (optional intermediate)
# Helper: wait for a service to appear (since 'ros2 service wait' subcommand does not exist in Humble base install)
wait_for_service() {
	local svc="$1"
	local timeout="${2:-5}"
	local start
	start=$(date +%s)
	while true; do
		if ros2 service list 2>/dev/null | grep -q "^${svc}$"; then
			return 0
		fi
		if (($(date +%s) - start >= timeout)); then
			return 1
		fi
		sleep 0.5
	done
}

# Wait until a topic appears and (optionally) a first message is received
wait_for_topic() {
	local topic="$1"
	local timeout="${2:-5}"
	local start
	start=$(date +%s)
	while true; do
		if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
			# Try to receive a single message quickly (best-effort)
			if command -v timeout >/dev/null 2>&1; then
				timeout 2s ros2 topic echo -n1 "$topic" >/dev/null 2>&1 && return 0 || return 0
			else
				return 0
			fi
		fi
		if (($(date +%s) - start >= timeout)); then
			return 1
		fi
		sleep 0.5
	done
}

# Function to save live map immediately (optional intermediate)
save_live_map() {
	local base="$1"
	info "Invoking SaveMap (target base: ${base})"
	if ! wait_for_service "$SAVE_SERVICE" 8; then
		warn "SaveMap service not available (timeout)"
		return 1
	fi

	# Detect actual service type (once) to avoid hard-coding wrong interface
	if [[ -z "${SAVE_SERVICE_TYPE:-}" ]]; then
		SAVE_SERVICE_TYPE=$(ros2 service type "$SAVE_SERVICE" 2>/dev/null || echo "$SAVE_SERVICE_TYPE_DEFAULT")
		log "SaveMap type: $SAVE_SERVICE_TYPE"
	fi

	case "$SAVE_SERVICE_TYPE" in
	nav2_msgs/srv/SaveMap)
		log "nav2 SaveMap -> occupancy expected"
		local req="{map_url: '${base}', image_format: 'pgm', map_mode: '${OCCUPANCY_MODE}', free_thresh: ${OCC_FREE_THRESH}, occupied_thresh: ${OCC_OCC_THRESH}}"
		if command -v timeout >/dev/null 2>&1; then
			if ! timeout "${MAX_SAVEMAP_SECONDS}s" ros2 service call "$SAVE_SERVICE" "$SAVE_SERVICE_TYPE" "$req"; then
				warn "SaveMap (nav2_msgs) call timed out/failed"
				return 1
			fi
		else
			if ! ros2 service call "$SAVE_SERVICE" "$SAVE_SERVICE_TYPE" "$req"; then
				warn "SaveMap (nav2_msgs) call failed"
				return 1
			fi
		fi
		;;
	slam_toolbox/srv/SaveMap)
		log "slam_toolbox SaveMap -> internal only"
		local req="{name: {data: '${base}'}}"
		if command -v timeout >/dev/null 2>&1; then
			if ! timeout "${MAX_SAVEMAP_SECONDS}s" ros2 service call "$SAVE_SERVICE" "$SAVE_SERVICE_TYPE" "$req"; then
				warn "SaveMap (slam_toolbox) call timed out/failed"
				return 1
			fi
		else
			if ! ros2 service call "$SAVE_SERVICE" "$SAVE_SERVICE_TYPE" "$req"; then
				warn "SaveMap (slam_toolbox) call failed"
				return 1
			fi
		fi
		log "slam_toolbox SaveMap success"
		;;
	*)
		warn "Unknown SaveMap service type '$SAVE_SERVICE_TYPE' – cannot construct request"
		return 1
		;;
	esac
}

# Fallback exporter: subscribes once to /map and writes PGM + YAML if map_saver_cli fails
fallback_export_map() {
	local base="${1:-${FALLBACK_BASE:-/tmp/fallback_map}}"
	local timeout="${2:-${FALLBACK_MAP_TIMEOUT}}"
	local topic="${3:-${WAIT_MAP_TOPIC}}"
	info "Fallback map export from ${topic} (timeout ${timeout}s)"
	python3 - <<'PYEOF'
import os, sys, time, math
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid

base=os.environ['FALLBACK_BASE']
topic=os.environ.get('FALLBACK_TOPIC','/map')
deadline=time.time()+float(os.environ.get('FALLBACK_TIMEOUT','6'))

class Once(Node):
  def __init__(self):
    super().__init__('fallback_map_exporter')
    self.sub=self.create_subscription(OccupancyGrid, topic, self.cb, 10)
    self.msg=None
  def cb(self,msg):
    if self.msg is None:
      self.msg=msg

rclpy.init()
node=Once()
while rclpy.ok() and node.msg is None and time.time()<deadline:
  rclpy.spin_once(node, timeout_sec=0.2)
if node.msg is None:
  print('[FALLBACK] No map message received', file=sys.stderr)
  rclpy.shutdown(); sys.exit(2)
m=node.msg
width=m.info.width; height=m.info.height; res=m.info.resolution
data=m.data
if len(data)!=width*height:
  print('[FALLBACK] Data length mismatch', file=sys.stderr)
  rclpy.shutdown(); sys.exit(3)
# PGM: invert occupancy (unknown=205, free=254, occ=0 typical) – replicate nav2 style
out_pgm=base+'.pgm'
out_yaml=base+'.yaml'
with open(out_pgm,'wb') as f:
  f.write(b'P5\n# fallback exporter\n%d %d\n255\n'%(width,height))
  # nav2 map_saver writes from top to bottom; OccupancyGrid data is row-major from (0,0) lower-left
  # We'll flip vertically for same orientation as nav2 output
  for row in range(height-1,-1,-1):
    start=row*width; end=start+width
    line=data[start:end]
    buf=bytearray(width)
    for i,val in enumerate(line):
      if val<0: gv=205
      elif val>=100: gv=0
      elif val<=0: gv=254
      else:
        # linear interpolate between free(254) and occ(0)
        gv=int((100-val)/100*254)
      buf[i]=gv
    f.write(buf)
yaml_content=f"""image: {os.path.basename(out_pgm)}
resolution: {res}
origin: [0.0, 0.0, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.25
mode: trinary
"""
with open(out_yaml,'w') as f: f.write(yaml_content)
print('[FALLBACK] Map written', out_pgm, out_yaml)
rclpy.shutdown()
PYEOF
	local rc=$?
	if [[ $rc -ne 0 ]]; then
		warn "Fallback exporter failed (rc=$rc)"
	fi
}

# Graceful shutdown handler
cleanup() {
	if ((CLEANUP_LOCK == 1)); then
		warn "Cleanup already in progress – ignoring extra signal. Please wait..."
		return
	fi
	CLEANUP_LOCK=1
	echo
	warn "CTRL+C detected: stopping recording & SLAM; will extract final map from bag replay."
	# Ignore further INT/TERM so da ne prekinemo replay / map saver
	trap '' INT TERM
	set +e
	if kill -0 "${BAG_PID}" 2>/dev/null; then
		kill "${BAG_PID}"
		wait "${BAG_PID}" 2>/dev/null
	fi
	# Save map and serialize pose graph BEFORE killing slam_toolbox so the services are reachable.
	save_live_map "$MAP_OUTPUT_BASE" || warn "Live SaveMap skipped/failed (non-fatal)"
	# Serialize pose graph for localization mode (requires mapping node still running).
	# Serialize to BOTH live/ and final/ so select_map.sh can find it regardless of which path it checks.
	mkdir -p "$FINAL_DIR"
	info "Serializing pose graph for localization (targets: ${MAP_OUTPUT_BASE}, ${FINAL_DIR}/map)"
	if wait_for_service "/slam_toolbox/serialize_pose_graph" 8; then
		_serialize_ok=0
		timeout 15s ros2 service call /slam_toolbox/serialize_pose_graph \
			slam_toolbox/srv/SerializePoseGraph "{filename: {data: '${MAP_OUTPUT_BASE}'}}" \
			&& _serialize_ok=1 || warn "serialize_pose_graph (live) call failed"
		if [[ $_serialize_ok -eq 1 ]]; then
			# Copy to final/ so select_map.sh finds it there
			cp -f "${MAP_OUTPUT_BASE}.posegraph" "${FINAL_DIR}/map.posegraph" 2>/dev/null || true
			cp -f "${MAP_OUTPUT_BASE}.data"      "${FINAL_DIR}/map.data"      2>/dev/null || true
			info "Pose graph copied to final: ${FINAL_DIR}/map.posegraph"
		fi
	else
		warn "serialize_pose_graph service not available – localization mode will not have a pose graph"
	fi
	if [[ -n "${SLAM_PID:-}" ]] && kill -0 "${SLAM_PID}" 2>/dev/null; then
		kill "${SLAM_PID}"
		wait "${SLAM_PID}" 2>/dev/null
	else
		info "Leaving existing slam_toolbox (pid ${EXISTING_SLAM_PID}) to be stopped externally if desired."
	fi

	# Optional replay bag to regenerate consistent final map (if enabled)
	# Detect bag presence using metadata.yaml to avoid glob race
	HAVE_BAG_FILES=""
	if [[ -d "${ROS2_BAG_BASE}" && -f "${ROS2_BAG_BASE}/metadata.yaml" ]]; then
		HAVE_BAG_FILES=1
	else
		# Fallback: any db3 anywhere under bag dir
		first_db3=$(find "$BAG_DIR" -maxdepth 2 -name '*.db3' -print -quit 2>/dev/null || true)
		[[ -n "$first_db3" ]] && HAVE_BAG_FILES=1
	fi
	if [[ $USE_REPLAY -eq 1 ]]; then
		if [[ -z "$HAVE_BAG_FILES" ]]; then
			warn "No bag data (metadata.yaml) found under $BAG_DIR – skipping replay and final SaveMap."
			PLAY_PID=0
			REPLAY_SLAM_PID=0
		else
			info "Replay mapping (base ${ROS2_BAG_BASE})"
			ros2 launch "${SLAM_LAUNCH[@]}" &
			REPLAY_SLAM_PID=$!
			sleep 4
			ros2 bag play "${ROS2_BAG_BASE}" --clock --rate "${BAG_REPLAY_RATE}" 2>/dev/null &
			PLAY_PID=$!
		fi
	else
		info "Replay disabled (USE_REPLAY=0); using live map snapshot only."
		PLAY_PID=0
		REPLAY_SLAM_PID=0
	fi

	FINAL_BASE="$FINAL_DIR/map"
	if [[ $USE_REPLAY -eq 1 && -n "$HAVE_BAG_FILES" ]]; then
		log "Replay wait"
		TIME_WAIT=25
		while [[ $TIME_WAIT -gt 0 ]]; do
			sleep 5
			TIME_WAIT=$((TIME_WAIT - 5))
			echo -n '.'
		done
		echo
		save_live_map "$FINAL_BASE" || warn "Final SaveMap failed"
	else
		log "No replay final SaveMap path"
	fi

	# Wait explicitly for /map to appear if we expect occupancy export or fallback
	if [[ "${USE_NAV2_EXPORT}" != "never" ]]; then
		info "Waiting up to ${MAP_AVAILABLE_TIMEOUT}s for ${WAIT_MAP_TOPIC} before export"
		wait_for_topic "${WAIT_MAP_TOPIC}" "${MAP_AVAILABLE_TIMEOUT}" || warn "${WAIT_MAP_TOPIC} not ready before export attempts"
	fi
	# Optional: occupancy grid export via nav2 map_saver if available / requested
	if [[ "${USE_NAV2_EXPORT}" != "never" ]]; then
		local have_nav2="false"
		if [[ -d /opt/ros/humble/share/nav2_map_server ]]; then have_nav2="true"; fi
		if [[ "${USE_NAV2_EXPORT}" == "always" ]] || [[ "${USE_NAV2_EXPORT}" == "auto" && "${SAVE_SERVICE_TYPE:-}" != "nav2_msgs/srv/SaveMap" ]]; then
			if [[ "$have_nav2" == "true" ]]; then
				info "Export occupancy (mode=${OCCUPANCY_MODE})"
				# Use float for save_map_timeout parameter to satisfy rcl parameter type expectations
				# Ensure /map topic is actually present (slam_toolbox may publish it; if not, map_saver will fail)
				if wait_for_topic "${WAIT_MAP_TOPIC}" "${WAIT_MAP_TIMEOUT}"; then
					# Use CLI flags --occ/--free; provide topic explicitly in case default differs
					local saver_cmd=(ros2 run nav2_map_server map_saver_cli -f "${FINAL_BASE}" -t "${WAIT_MAP_TOPIC}" --occ "${OCC_OCC_THRESH}" --free "${OCC_FREE_THRESH}")
					if command -v setsid >/dev/null 2>&1; then saver_cmd=(setsid "${saver_cmd[@]}"); fi
					local SAVER_OK=0
					if command -v timeout >/dev/null 2>&1; then
						timeout "${NAV2_SAVE_TIMEOUT}s" "${saver_cmd[@]}" || SAVER_OK=$?
					else
						"${saver_cmd[@]}" || SAVER_OK=$?
					fi
					if [[ $SAVER_OK -ne 0 || ! -f "${FINAL_BASE}.yaml" ]]; then
						warn "map_saver_cli failed or produced no files; attempting fallback exporter"
						FALLBACK_BASE="${FINAL_BASE}" FALLBACK_TOPIC="${WAIT_MAP_TOPIC}" FALLBACK_TIMEOUT="${FALLBACK_MAP_TIMEOUT}" fallback_export_map "${FINAL_BASE}" "${FALLBACK_MAP_TIMEOUT}" "${WAIT_MAP_TOPIC}" || true
					fi
				else
					warn "/map topic not detected within ${WAIT_MAP_TIMEOUT}s; skipping nav2 occupancy export"
				fi
			else
				info "nav2_map_server not present; skipping occupancy export (set USE_NAV2_EXPORT=never to silence)."
			fi
		fi
	fi
	if kill -0 $PLAY_PID 2>/dev/null; then kill $PLAY_PID; fi
	if kill -0 $REPLAY_SLAM_PID 2>/dev/null; then kill $REPLAY_SLAM_PID; fi

	# Insert YAML to DB
	YAML_FILE="${FINAL_BASE}.yaml"
	PGM_FILE="${FINAL_BASE}.pgm"
	# Create PNG if possible
	if [[ -f "$PGM_FILE" ]]; then
		if command -v convert >/dev/null 2>&1; then
			if convert "$PGM_FILE" "${FINAL_DIR}/map.png"; then
				info "Generated PNG: ${FINAL_DIR}/map.png"
			else
				warn "PNG conversion failed"
			fi
		else
			# Fallback python conversion (grayscale)
			python3 - "$PGM_FILE" "${FINAL_DIR}/map.png" <<'PYEOF'
from PIL import Image
import sys, os
pgm=sys.argv[1]
png=sys.argv[2]
try:
    im=Image.open(pgm)
    im.save(png)
    print('[INFO] Fallback PNG created', png)
except Exception as e:
    print('[WARN] PNG fallback failed', e)
PYEOF
		fi
	fi
	if [[ -f "$YAML_FILE" ]]; then
		info "Computing YAML sha256 hash and inserting map into database (robot_data.maps) with fallback hosts: ${DB_HOST_CANDIDATES} (primary=${DB_HOST})"
		export YAML_FILE="$YAML_FILE" MAP_NAME="${SESSION_ID}" DB_HOST_PRIMARY="$DB_HOST" DB_FULL_NAME="$DB_NAME" DB_USER="$DB_USER" DB_PASS="$DB_PASS" DB_HOST_CANDIDATES="$DB_HOST_CANDIDATES" DB_MAX_RETRIES="$DB_MAX_RETRIES" DB_RETRY_DELAY="$DB_RETRY_DELAY"
		python3 - <<'PYEOF'
import psycopg2, yaml, json, hashlib, os, re, sys, time

yaml_file=os.environ['YAML_FILE']
name=os.environ['MAP_NAME']
primary=os.environ['DB_HOST_PRIMARY']
candidates=os.environ['DB_HOST_CANDIDATES'].split()
if primary not in candidates:
  candidates.insert(0, primary)
db_name=os.environ['DB_FULL_NAME']
db_user=os.environ['DB_USER']
db_pass=os.environ['DB_PASS']
max_retries=int(os.environ.get('DB_MAX_RETRIES','3'))
retry_delay=int(os.environ.get('DB_RETRY_DELAY','3'))

def load_map_meta(path):
  with open(path,'rb') as f: content=f.read()
  sha=hashlib.sha256(content).hexdigest()
  data=yaml.safe_load(content)
  if not isinstance(data, dict):
    raise ValueError('YAML root not a dict')
  res=float(data.get('resolution',0.05))
  origin=list(data.get('origin',[0.0,0.0,0.0]))
  if len(origin)<2: origin=[0.0,0.0,0.0]
  # Determine image file path: prefer YAML 'image' key if present
  image_rel=data.get('image', None)
  if image_rel:
    # image path is relative to YAML dir
    base_dir=os.path.dirname(path)
    pgm_path=os.path.join(base_dir, image_rel)
  else:
    pgm_path=re.sub(r"\\.yaml$",".pgm", path)
  width=0;height=0
  try:
    with open(pgm_path,'rb') as pf:
      magic=pf.readline().strip()
      if magic not in (b'P5', b'P2'):
        raise ValueError('Unsupported PGM format magic '+magic.decode(errors='ignore'))
      # Skip comments
      line=pf.readline()
      while line.startswith(b'#'):
        line=pf.readline()
      dims=line.strip().split()
      if len(dims)==2:
        width=int(dims[0]);height=int(dims[1])
      # Read maxval (but ignore content)
      _=pf.readline().strip()
  except Exception as e:
    print('[DB] Warning: PGM parse failed:', e)
  return content, sha, data, res, origin, pgm_path, width, height

content, sha, data, res, origin, pgm_path, width, height = load_map_meta(yaml_file)
metadata={'yaml_sha256': sha, 'map_yaml_raw': data}

def attempt(host):
  try:
    conn=psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=host, port=5432, connect_timeout=3)
  except Exception as e:
    return False, f'connect fail: {e}'
  try:
    cur=conn.cursor()
    cur.execute("""
      SELECT id FROM robot_data.maps
      WHERE metadata ->> 'yaml_sha256' = %s
      LIMIT 1
    """, (sha,))
    existing=cur.fetchone()
    if existing:
      print(f"[DB] Duplicate map (hash={sha}) exists id={existing[0]} host={host}; skipping insert")
      conn.close(); return True, 'duplicate'
    # choose data
    try:
      with open(pgm_path,'rb') as pf: map_binary=pf.read()
    except Exception:
      map_binary=content
    cur.execute("""
      INSERT INTO robot_data.maps (name, description, map_data, resolution, origin_x, origin_y, width, height, metadata)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (name, None, psycopg2.Binary(map_binary), res, float(origin[0]), float(origin[1]), width, height, json.dumps(metadata)))
    conn.commit(); cur.close(); conn.close()
    print(f"[DB] Map inserted (hash={sha}) via host={host}")
    return True, 'inserted'
  except Exception as e:
    try: conn.close()
    except Exception: pass
    return False, f'query fail: {e}'

success=False
for host in candidates:
  attempts=0
  while attempts < max_retries and not success:
    ok, msg = attempt(host)
    if ok:
      success=True
      break
    print(f"[DB] Host {host} attempt {attempts+1}/{max_retries} failed: {msg}")
    attempts+=1
    if attempts < max_retries: time.sleep(retry_delay)
  if success:
    break

if not success:
  print(f"[DB] All hosts failed ({' '.join(candidates)}); map not inserted")
PYEOF
	else
		warn "Final YAML map not found: $YAML_FILE"
	fi

	# Metadata file (created once)
	if [[ ! -f "$SESSION_DIR/meta.json" ]]; then
		CREATED_LOCAL=$(date +%Y-%m-%dT%H:%M:%S%z)
		CREATED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
		EPOCH=$(date +%s)
		cat >"$SESSION_DIR/meta.json" <<METAJSON
{
  "id": "${SESSION_ID}",
  "index": ${SESSION_INDEX:-null},
  "incremental": ${INCREMENTAL_NAMES},
  "prefix": "${NAME_PREFIX}",
  "created_local": "${CREATED_LOCAL}",
  "created_utc": "${CREATED_UTC}",
  "epoch": ${EPOCH},
  "legacy_bag_prefix": "${BAG_PREFIX}",
  "legacy_timestamp_local": "${SESSION_TS}",
  "legacy_timestamp_utc": "${SESSION_TS_UTC}"
}
METAJSON
	fi

	info "Artifacts:"
	echo "Session directory structure:"
	find "$SESSION_DIR" -maxdepth 3 -type f -print 2>/dev/null | sed 's#^#  - #' || true
	info "Primary final outputs: $FINAL_BASE.pgm / $FINAL_BASE.yaml"
	if [[ -f "${FINAL_DIR}/map.png" ]]; then info "PNG preview: ${FINAL_DIR}/map.png"; fi

	# Optional restart of localization slam_toolbox (fresh instance) after mapping completes
	if [[ "$RESTART_LOCALIZATION" == "1" ]]; then
		info "RESTART_LOCALIZATION=1 -> starting new localization slam_toolbox instance"
		ros2 launch "${SLAM_LAUNCH[@]}" >/dev/null 2>&1 &
		info "Localization slam_toolbox restarted in background (pid $!)."
	fi
	info "Done."
	# Update latest symlink (best-effort)
	if command -v ln >/dev/null 2>&1; then
		(cd "${MAP_ROOT}" 2>/dev/null && {
			rm -f latest
			ln -s "${SESSION_ID}" latest
		}) || true
		info "Symlink updated: ${MAP_ROOT}/latest -> ${SESSION_ID}"
	fi
	exit 0
}

trap cleanup INT TERM

info "Mapping in progress. Press CTRL+C to finish and generate final map from bag replay."
# Simple heartbeat
while true; do
	sleep 30
	echo "[heartbeat] $(date)"
done
