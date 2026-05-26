#!/usr/bin/env python3
"""Launch Nav2 collision_monitor with lifecycle management."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    params_file = LaunchConfiguration("params_file")
    cmd_vel_in = LaunchConfiguration("cmd_vel_in")
    cmd_vel_out = LaunchConfiguration("cmd_vel_out")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value="/app/collision_monitor_params.yaml",
            ),
            DeclareLaunchArgument("cmd_vel_in", default_value="/cmd_vel_collision_in"),
            DeclareLaunchArgument("cmd_vel_out", default_value="/cmd_vel"),
            Node(
                package="nav2_collision_monitor",
                executable="collision_monitor",
                name="collision_monitor",
                output="screen",
                parameters=[
                    params_file,
                    {
                        "cmd_vel_in_topic": cmd_vel_in,
                        "cmd_vel_out_topic": cmd_vel_out,
                    },
                ],
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_collision_monitor",
                output="screen",
                parameters=[
                    {
                        "use_sim_time": False,
                        "autostart": True,
                        "node_names": ["collision_monitor"],
                    }
                ],
            ),
        ]
    )
