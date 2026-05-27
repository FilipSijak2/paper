#!/usr/bin/env python3
"""Small Nav2 wrapper for this robot.

The stock Nav2 launch files hard-code the final smoothed velocity topic as
``cmd_vel``. This wrapper scopes a remap so the Nav2 output can feed the local
auto/manual mux on ``/cmd_vel_auto`` while still using the upstream Nav2 bringup.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import SetRemap
from launch_ros.substitutions import FindPackageShare


def _nav2_launch(name: str) -> PathJoinSubstitution:
    return PathJoinSubstitution([FindPackageShare("nav2_bringup"), "launch", name])


def generate_launch_description() -> LaunchDescription:
    map_file = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")
    cmd_vel_out = LaunchConfiguration("cmd_vel_out")
    use_amcl = LaunchConfiguration("use_amcl")
    use_sim_time = LaunchConfiguration("use_sim_time")
    autostart = LaunchConfiguration("autostart")
    use_composition = LaunchConfiguration("use_composition")
    use_respawn = LaunchConfiguration("use_respawn")
    log_level = LaunchConfiguration("log_level")

    return LaunchDescription(
        [
            DeclareLaunchArgument("map", description="Saved occupancy map YAML"),
            DeclareLaunchArgument("params_file", default_value="/app/nav2_params.yaml"),
            DeclareLaunchArgument("cmd_vel_out", default_value="/cmd_vel_auto"),
            DeclareLaunchArgument("use_amcl", default_value="true"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("autostart", default_value="true"),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("use_respawn", default_value="False"),
            DeclareLaunchArgument("log_level", default_value="info"),
            GroupAction(
                [
                    SetRemap(src="cmd_vel", dst=cmd_vel_out),
                    SetRemap(src="/cmd_vel", dst=cmd_vel_out),
                    # Nav2 bringup may internally route velocity_smoother output
                    # through cmd_vel_smoothed -> cmd_vel. Keep both names inside
                    # the auto/mux chain so nothing publishes directly to /cmd_vel.
                    SetRemap(src="cmd_vel_smoothed", dst=cmd_vel_out),
                    SetRemap(src="/cmd_vel_smoothed", dst=cmd_vel_out),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(_nav2_launch("bringup_launch.py")),
                        condition=IfCondition(use_amcl),
                        launch_arguments={
                            "slam": "False",
                            "map": map_file,
                            "params_file": params_file,
                            "use_sim_time": use_sim_time,
                            "autostart": autostart,
                            "use_composition": use_composition,
                            "use_respawn": use_respawn,
                            "log_level": log_level,
                        }.items(),
                    ),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(_nav2_launch("navigation_launch.py")),
                        condition=UnlessCondition(use_amcl),
                        launch_arguments={
                            "params_file": params_file,
                            "use_sim_time": use_sim_time,
                            "autostart": autostart,
                            "use_composition": use_composition,
                            "use_respawn": use_respawn,
                            "log_level": log_level,
                        }.items(),
                    ),
                ]
            ),
        ]
    )
