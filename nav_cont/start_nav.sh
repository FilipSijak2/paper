#!/usr/bin/env bash
set -euo pipefail

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
#   GOAL_TOPIC       (default /simple_goal)
#   FORCE_MAP_WAIT   (0/1) if 1 and MAP_FILE resolved, wait until it exists (default 0 now)

: "${MAP_ROOT:=/srv/maps}"
: "${MAP_SESSION:=}"
: "${MAP_FILE:=}"
: "${NAV2_PARAMS_FILE:=/app/nav2_params.yaml}"
: "${GOAL_TOPIC:=/simple_goal}"
: "${FORCE_MAP_WAIT:=0}"

# Lightweight resolution (kept, but non-blocking):
if [ -z "${MAP_FILE}" ]; then
  if [ -n "${MAP_SESSION}" ]; then
    for cand in "${MAP_ROOT}/${MAP_SESSION}/final/map.yaml" "${MAP_ROOT}/${MAP_SESSION}/map.yaml"; do
      if [ -f "$cand" ]; then MAP_FILE="$cand"; break; fi
    done
  fi
  # Active / latest symlinks as fallbacks
  if [ -z "${MAP_FILE}" ]; then
    for cand in \
      "${MAP_ROOT}/active/final/map.yaml" "${MAP_ROOT}/active/map.yaml" \
      "${MAP_ROOT}/latest/final/map.yaml" "${MAP_ROOT}/latest/map.yaml"; do
      if [ -f "$cand" ]; then MAP_FILE="$cand"; break; fi
    done
  fi
fi

if [ -n "${MAP_FILE}" ]; then
  echo "[nav_start] Using map file: ${MAP_FILE}"
  if [ "${FORCE_MAP_WAIT}" = "1" ]; then
    echo "[nav_start] Waiting for map file to exist (FORCE_MAP_WAIT=1)"
    while [ ! -f "${MAP_FILE}" ]; do sleep 2; echo "[nav_start][WAIT] ${MAP_FILE}"; done
  fi
else
  echo "[nav_start][INFO] No existing map resolved -> generating temporary placeholder so GUI prikazuje nešto."
  PLACEHOLDER_DIR="${MAP_ROOT}/__auto_placeholder"
  mkdir -p "${PLACEHOLDER_DIR}"
  PLACE_YAML="${PLACEHOLDER_DIR}/map.yaml"
  PLACE_PGM="${PLACEHOLDER_DIR}/map.pgm"
  if [ ! -f "${PLACE_PGM}" ]; then
    # Create a small 40x40 fully free space map (P5 binary PGM, maxval 255)
    { echo "P5"; echo "40 40"; echo "255"; perl -e 'print chr(255) x (40*40)'; } > "${PLACE_PGM}" 2>/dev/null || {
      echo "P2" > "${PLACE_PGM}"; echo "40 40" >> "${PLACE_PGM}"; echo "255" >> "${PLACE_PGM}"; yes 255 | head -n $((40*40)) >> "${PLACE_PGM}"; }
  fi
  cat > "${PLACE_YAML}" <<EOF
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

source /opt/ros/humble/setup.bash

MAP_ARG=()
if [ -n "${MAP_FILE}" ] && [ -f "${MAP_FILE}" ]; then
  MAP_ARG+=("map:=${MAP_FILE}")
fi

echo "[nav_start] Launching Nav2 params=${NAV2_PARAMS_FILE} ${MAP_ARG:+with map arg}" 
ros2 launch nav2_bringup navigation_launch.py "${MAP_ARG[@]}" params_file:=${NAV2_PARAMS_FILE} &
NAV2_PID=$!

sleep 5 || true

python3 /app/goal_forwarder.py --ros-args -p goal_topic:=${GOAL_TOPIC} &
GOAL_FORWARDER_PID=$!

echo "[nav_start] Nav2 PID=${NAV2_PID}; GoalForwarder PID=${GOAL_FORWARDER_PID}"
echo "[nav_start] Ready. If you later define a map, restart this container to apply it (or use select_map.sh if present)."

trap 'echo "[nav_start] Stopping..."; kill ${GOAL_FORWARDER_PID} ${NAV2_PID} 2>/dev/null || true; wait ${GOAL_FORWARDER_PID} ${NAV2_PID} 2>/dev/null || true; exit 0' INT TERM
while true; do sleep 60; echo "[nav_start] heartbeat $(date)"; done
