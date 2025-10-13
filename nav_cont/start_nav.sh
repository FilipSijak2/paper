#!/usr/bin/env bash
set -euo pipefail

# Entry script to start Nav2 bringup and auxiliary nodes.
# Environment variables:
#   MAP_SESSION (optional session directory name under MAP_ROOT to auto-pick map)
#   MAP_FILE (explicit full path to map yaml overrides MAP_SESSION) (default /srv/maps/active/final/map.yaml)
#   NAV2_PARAMS_FILE (/app/nav2_params.yaml)
#   GOAL_TOPIC (/simple_goal)
#   FORCE_MAP_WAIT=1 (wait until MAP_FILE exists)

: "${MAP_ROOT:=/srv/maps}"
: "${MAP_SESSION:=}"
: "${MAP_FILE:=}"
: "${NAV2_PARAMS_FILE:=/app/nav2_params.yaml}"
: "${GOAL_TOPIC:=/simple_goal}"
: "${FORCE_MAP_WAIT:=1}"

# Resolve MAP_FILE if not explicitly provided. Resolution order:
# 1) If MAP_FILE already set and exists -> use it.
# 2) If MAP_SESSION set:
#      try <MAP_ROOT>/<MAP_SESSION>/final/map.yaml then map.yaml
# 3) Symlink /srv/maps/active/final/map.yaml then /srv/maps/active/map.yaml
# 4) Symlink /srv/maps/latest/final/map.yaml then /srv/maps/latest/map.yaml
# 5) Fallback: leave empty (nav2 will rely on params yaml_filename)
if [ -z "${MAP_FILE}" ]; then
  try_candidates=()
  if [ -n "${MAP_SESSION}" ]; then
    try_candidates+=("${MAP_ROOT}/${MAP_SESSION}/final/map.yaml" "${MAP_ROOT}/${MAP_SESSION}/map.yaml")
  fi
  try_candidates+=("${MAP_ROOT}/active/final/map.yaml" "${MAP_ROOT}/active/map.yaml" \
                   "${MAP_ROOT}/latest/final/map.yaml" "${MAP_ROOT}/latest/map.yaml")
  for cand in "${try_candidates[@]}"; do
    if [ -f "$cand" ]; then MAP_FILE="$cand"; break; fi
  done
fi

if [ -n "${MAP_FILE}" ]; then
  echo "[nav_start] Resolved MAP_FILE=${MAP_FILE}"
fi

# Enforce: map must be defined via .env (MAP_FILE or MAP_SESSION -> resolved). If not, block robot movement.
if [ -z "${MAP_FILE}" ]; then
  echo "[nav_start][ERROR] Nije definirana mapa (MAP_FILE ili MAP_SESSION). Navigacija i kretanje su blokirani dok se ne definira mapa." >&2
  echo "[nav_start][INFO] Postavi u .env: MAP_SESSION=<session_dir> ili MAP_FILE=/srv/maps/<session>/final/map.yaml pa restartaj container." >&2
  # Pasivna petlja: ne pokreći Nav2; samo heartbeat log da operator vidi status
  while true; do sleep 30; echo "[nav_start][WAITING_FOR_MAP] $(date) still no MAP_FILE defined"; done
fi

if [ "${FORCE_MAP_WAIT}" = "1" ]; then
  echo "[nav_start] Waiting for map file to exist: ${MAP_FILE}"
  while [ ! -f "${MAP_FILE}" ]; do
    echo "[nav_start][WAIT] Map file not found yet: ${MAP_FILE}"; sleep 3;
  done
fi

if [ ! -f "${NAV2_PARAMS_FILE}" ]; then
  echo "[nav_start][WARN] Nav2 params file missing: ${NAV2_PARAMS_FILE}." >&2
fi

source /opt/ros/humble/setup.bash

echo "[nav_start] Starting Nav2 with REQUIRED map=${MAP_FILE} params=${NAV2_PARAMS_FILE}"
ros2 launch nav2_bringup navigation_launch.py map:=${MAP_FILE} params_file:=${NAV2_PARAMS_FILE} &
NAV2_PID=$!

sleep 5

python3 /app/goal_forwarder.py --ros-args -p goal_topic:=${GOAL_TOPIC} &
GOAL_FORWARDER_PID=$!

echo "[nav_start] Nav2 PID=${NAV2_PID}; GoalForwarder PID=${GOAL_FORWARDER_PID}"
echo "[nav_start] Ready. Goals disabled without valid map; map enforced from .env."
trap 'echo "[nav_start] Stopping..."; kill ${GOAL_FORWARDER_PID} ${NAV2_PID} 2>/dev/null || true; wait ${GOAL_FORWARDER_PID} ${NAV2_PID} 2>/dev/null || true; exit 0' INT TERM
while true; do sleep 60; echo "[nav_start] heartbeat $(date)"; done
