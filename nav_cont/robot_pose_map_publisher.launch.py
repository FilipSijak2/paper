#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    map_frame = LaunchConfiguration("map_frame")
    base_frame = LaunchConfiguration("base_frame")
    pose_topic = LaunchConfiguration("pose_topic")
    publish_rate_hz = LaunchConfiguration("publish_rate_hz")
    lookup_timeout_s = LaunchConfiguration("lookup_timeout_s")

    return LaunchDescription(
        [
            DeclareLaunchArgument("map_frame", default_value="map"),
            DeclareLaunchArgument("base_frame", default_value="base_link"),
            DeclareLaunchArgument("pose_topic", default_value="/robot_pose_map"),
            DeclareLaunchArgument("publish_rate_hz", default_value="1.0"),
            DeclareLaunchArgument("lookup_timeout_s", default_value="0.2"),
            ExecuteProcess(
                cmd=[
                    "python3",
                    "/app/robot_pose_map_publisher.py",
                    "--ros-args",
                    "-p",
                    ["map_frame:=", map_frame],
                    "-p",
                    ["base_frame:=", base_frame],
                    "-p",
                    ["pose_topic:=", pose_topic],
                    "-p",
                    ["publish_rate_hz:=", publish_rate_hz],
                    "-p",
                    ["lookup_timeout_s:=", lookup_timeout_s],
                ],
                output="screen",
            ),
        ]
    )

