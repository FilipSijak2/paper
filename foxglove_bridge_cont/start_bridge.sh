#!/bin/bash
set -euo pipefail

source /opt/ros/${ROS_DISTRO}/setup.bash

ROS_ARGS=(
    "--ros-args"
    "-p" "port:=${FOXGLOVE_PORT}"
    "-p" "address:=${FOXGLOVE_ADDRESS}"
)

if [[ "${FOXGLOVE_TLS}" == "1" || "${FOXGLOVE_TLS}" == "true" ]]; then
    ROS_ARGS+=("-p" "tls:=true")
    if [[ -n "${FOXGLOVE_TLS_CERT:-}" ]]; then
        ROS_ARGS+=("-p" "certfile:=${FOXGLOVE_TLS_CERT}")
    fi
    if [[ -n "${FOXGLOVE_TLS_KEY:-}" ]]; then
        ROS_ARGS+=("-p" "keyfile:=${FOXGLOVE_TLS_KEY}")
    fi
else
    ROS_ARGS+=("-p" "tls:=false")
fi

exec ros2 run foxglove_bridge foxglove_bridge "${ROS_ARGS[@]}"
