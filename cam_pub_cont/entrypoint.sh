#!/usr/bin/env bash
set -e

# ROS env
source /opt/ros/humble/setup.bash
source /opt/ros_ws/install/setup.bash

# Proslijedi CMD/args
exec "$@"
