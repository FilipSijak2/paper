#!/usr/bin/env bash
set -euo pipefail

# Automated live SLAM + rosbag recording + offline map extraction after Ctrl+C
# Usage (inside container with ROS 2 Humble):
#   bash run_mapping.sh [--bag-prefix mysession] [--duration 0] [--topics-file topics.txt]
# If --duration > 0, recording stops after that many seconds automatically.
# On Ctrl+C: gracefully stop recording & slam_toolbox, replay bag to save final map, insert into DB.

BAG_PREFIX="session"
DURATION=0
TOPICS_FILE=""
# Base directory for all mapping outputs (can override with env MAP_ROOT)
MAP_ROOT_DEFAULT="/app/maps"
MAP_ROOT="${MAP_ROOT:-$MAP_ROOT_DEFAULT}"
MAP_OUTPUT_BASE=""  # will be set after session id
# DB connection defaults aligned with robot_db schema (init-db.sql)
DB_HOST="db_cont"
DB_NAME="robot_data"
DB_USER="app_user"
DB_PASS="app_pass"
SAVE_SERVICE="/slam_toolbox/save_map"
SLAM_LAUNCH="slam_toolbox online_async_launch.py"
RESTART_LOCALIZATION=${RESTART_LOCALIZATION:-0}

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; BLUE="\033[0;34m"; NC="\033[0m"

log(){ echo -e "${BLUE}[run_mapping]${NC} $*"; }
info(){ echo -e "${GREEN}[INFO]${NC} $*"; }
warn(){ echo -e "${YELLOW}[WARN]${NC} $*"; }
err(){ echo -e "${RED}[ERROR]${NC} $*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bag-prefix) BAG_PREFIX="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --topics-file) TOPICS_FILE="$2"; shift 2;;
    --map-base) MAP_OUTPUT_BASE="$2"; shift 2;;
    --db-host) DB_HOST="$2"; shift 2;;
    --db-name) DB_NAME="$2"; shift 2;;
    --db-user) DB_USER="$2"; shift 2;;
  --db-pass) DB_PASS="$2"; shift 2;;
  --root-dir) MAP_ROOT="$2"; shift 2;;
    *) warn "Unknown arg $1"; shift;;
  esac
done

# Ensure ROS is sourced
if [[ -f /opt/ros/humble/setup.bash ]]; then
  source /opt/ros/humble/setup.bash
else
  err "ROS 2 environment not found"; exit 1
fi

SESSION_TS=$(date +%Y%m%d-%H%M%S)
SESSION_ID="${BAG_PREFIX}_${SESSION_TS}"
SESSION_DIR="$MAP_ROOT/$SESSION_ID"
BAG_DIR="$SESSION_DIR/bag"
REPLAY_DIR="$SESSION_DIR/replay"
FINAL_DIR="$SESSION_DIR/final"
LIVE_DIR="$SESSION_DIR/live"
MAP_BAG_REPLAY_BASE="$REPLAY_DIR/map"
mkdir -p "$BAG_DIR" "$REPLAY_DIR" "$FINAL_DIR" "$LIVE_DIR"
MAP_OUTPUT_BASE="$LIVE_DIR/map"

# Resolve topics list
if [[ -n "$TOPICS_FILE" ]]; then
  if [[ ! -f "$TOPICS_FILE" ]]; then err "Topics file $TOPICS_FILE not found"; exit 1; fi
  TOPICS=$(grep -Ev '^#|^$' "$TOPICS_FILE" | xargs || true)
else
  # Default essential topics for slam_toolbox map reproduction (adjust as needed)
  TOPICS="/tf /tf_static /odom /scan /imu /robot_description /clock"
fi
info "Recording topics: $TOPICS"
info "Map root directory: $MAP_ROOT"

# Detect existing slam_toolbox instance (avoid parallel)
EXISTING_SLAM_PID=""
if pgrep -f "slam_toolbox.*online_async_launch.py" >/dev/null 2>&1; then
  EXISTING_SLAM_PID=$(pgrep -f "slam_toolbox.*online_async_launch.py" | head -n1)
  info "Detected existing slam_toolbox process (pid ${EXISTING_SLAM_PID}); will reuse for live mapping (no new instance)."
else
  info "Starting new slam_toolbox instance..."
  ros2 launch $SLAM_LAUNCH &
  SLAM_PID=$!
  sleep 4
fi

# Start rosbag record
info "Starting rosbag record into $BAG_DIR (session $SESSION_ID)"
if [[ $DURATION -gt 0 ]]; then
  ros2 bag record -o "$BAG_DIR" $TOPICS --max-bag-duration $DURATION &
else
  ros2 bag record -o "$BAG_DIR" $TOPICS &
fi
BAG_PID=$!

# Function to save live map immediately (optional intermediate)
save_live_map(){
  local base="$1"
  info "Invoking SaveMap service to write ${base}.pgm/yaml"
  if ros2 service wait "$SAVE_SERVICE" --timeout 5; then
    ros2 service call "$SAVE_SERVICE" nav2_msgs/srv/SaveMap "{map_url: '${base}', map_format: 'pgm'}" || warn "SaveMap call failed"
  else
    warn "SaveMap service not available"
  fi
}

# Graceful shutdown handler
cleanup(){
  echo
  warn "CTRL+C detected: stopping recording & SLAM; will extract final map from bag replay."
  set +e
  if kill -0 $BAG_PID 2>/dev/null; then kill $BAG_PID; wait $BAG_PID 2>/dev/null; fi
  if [[ -n "${SLAM_PID:-}" ]] && kill -0 ${SLAM_PID} 2>/dev/null; then
    kill ${SLAM_PID}; wait ${SLAM_PID} 2>/dev/null
  else
    info "Leaving existing slam_toolbox (pid ${EXISTING_SLAM_PID}) to be stopped externally if desired."
  fi
  # First attempt to save current live map
  save_live_map "$MAP_OUTPUT_BASE"

  # Replay bag to regenerate consistent final map
  info "Replaying bag for clean map (fresh slam_toolbox instance)"
  ros2 launch $SLAM_LAUNCH &
  REPLAY_SLAM_PID=$!
  sleep 4
  # Play bag (no loop) - no need to record again
  ros2 bag play "$BAG_DIR"/*.db3 --clock 2> /dev/null &
  PLAY_PID=$!

  # Wait some seconds for map to build incrementally
  info "Allowing replay to build map (timed wait)"
  TIME_WAIT=25
  while [[ $TIME_WAIT -gt 0 ]]; do
    sleep 5; TIME_WAIT=$((TIME_WAIT-5)); echo -n '.'
  done
  echo
  # Save final map
  FINAL_BASE="$FINAL_DIR/map"
  save_live_map "$FINAL_BASE"
  if kill -0 $PLAY_PID 2>/dev/null; then kill $PLAY_PID; fi
  if kill -0 $REPLAY_SLAM_PID 2>/dev/null; then kill $REPLAY_SLAM_PID; fi

  # Insert YAML to DB
  YAML_FILE="${FINAL_BASE}.yaml"
  PGM_FILE="${FINAL_BASE}.pgm"
  # Create PNG if possible
  if [[ -f "$PGM_FILE" ]]; then
    if command -v convert >/dev/null 2>&1; then
      convert "$PGM_FILE" "${FINAL_DIR}/map.png" && info "Generated PNG: ${FINAL_DIR}/map.png" || warn "PNG conversion failed"
    else
      # Fallback python conversion (grayscale)
      python3 - <<'PYEOF'
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
  info "Computing YAML sha256 hash and inserting map into database schema robot_data.maps"
    export YAML_FILE="$YAML_FILE" MAP_NAME="${BAG_PREFIX}_${SESSION_TS}" DB_HOST="$DB_HOST" DB_FULL_NAME="$DB_NAME" DB_USER="$DB_USER" DB_PASS="$DB_PASS"
  python3 - <<'PYEOF'
import psycopg2, yaml, json, hashlib, os, re, sys
yaml_file=os.environ['YAML_FILE']
name=os.environ['MAP_NAME']
db_host=os.environ['DB_HOST']
db_name=os.environ['DB_FULL_NAME']
db_user=os.environ['DB_USER']
db_pass=os.environ['DB_PASS']
try:
  with open(yaml_file,'rb') as f:
    content=f.read()
  sha=hashlib.sha256(content).hexdigest()
  data=yaml.safe_load(content)
  # Extract minimal fields from YAML for required columns
  res=float(data.get('resolution',0.05))
  origin=list(data.get('origin', [0.0,0.0,0.0]))
  if len(origin)<2: origin=[0.0,0.0,0.0]
  # width/height are not in YAML; derive by loading associated PGM
  pgm_path=re.sub(r"\.yaml$",".pgm", yaml_file)
  width=0;height=0
  try:
    with open(pgm_path,'rb') as pf:
      # Parse PGM header (P5) minimal
      magic=pf.readline().strip()
      if magic!=b'P5':
        raise ValueError('Unsupported PGM format '+magic.decode())
      line=pf.readline()
      while line.startswith(b'#'):
        line=pf.readline()
      dims=line.strip().split()
      if len(dims)==2:
        width=int(dims[0]);height=int(dims[1])
      maxval=int(pf.readline().strip())
  except Exception as e:
    print('[DB] Warning: could not parse PGM dimensions:', e)
  metadata={'yaml_sha256': sha, 'map_yaml_raw': data}
  # Connect and check for duplicate by hash in metadata
  conn=psycopg2.connect(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=5432)
  cur=conn.cursor()
  # Look for existing map with same hash (search in metadata JSONB if available)
  cur.execute("""
    SELECT id FROM robot_data.maps
    WHERE metadata ->> 'yaml_sha256' = %s
    LIMIT 1
  """, (sha,))
  existing=cur.fetchone()
  if existing:
    print(f"[DB] Duplicate map detected (hash={sha}); skipping insert. Existing id={existing[0]}")
  else:
    # Insert minimal binary map_data: store PGM bytes (could be large) or YAML? We'll store PGM if exists else YAML
    map_binary=b''
    try:
      with open(pgm_path,'rb') as pf: map_binary=pf.read()
    except Exception:
      map_binary=content  # fallback to YAML bytes
    cur.execute("""
      INSERT INTO robot_data.maps (name, description, map_data, resolution, origin_x, origin_y, width, height, metadata)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (name, None, psycopg2.Binary(map_binary), res, float(origin[0]), float(origin[1]), width, height, json.dumps(metadata)))
    print(f"[DB] Map inserted (hash={sha})")
  conn.commit(); cur.close(); conn.close()
except Exception as e:
  print(f"[DB] Failed to insert map: {e}")
PYEOF
  else
  warn "Final YAML map not found: $YAML_FILE"
  fi

  info "Artifacts:"
  echo "Session directory structure:"
  find "$SESSION_DIR" -maxdepth 3 -type f -print 2>/dev/null | sed 's#^#  - #' || true
  info "Primary final outputs: $FINAL_BASE.pgm / $FINAL_BASE.yaml"
  if [[ -f "${FINAL_DIR}/map.png" ]]; then info "PNG preview: ${FINAL_DIR}/map.png"; fi

  # Optional restart of localization slam_toolbox (fresh instance) after mapping completes
  if [[ "$RESTART_LOCALIZATION" == "1" ]]; then
    info "RESTART_LOCALIZATION=1 -> starting new localization slam_toolbox instance"
    ros2 launch $SLAM_LAUNCH >/dev/null 2>&1 &
    info "Localization slam_toolbox restarted in background (pid $!)."
  fi
  info "Done."
  exit 0
}

trap cleanup INT TERM

info "Mapping in progress. Press CTRL+C to finish and generate final map from bag replay."
# Simple heartbeat
while true; do sleep 30; echo "[heartbeat] $(date)"; done
