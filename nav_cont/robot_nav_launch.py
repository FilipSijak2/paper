#!/usr/bin/env python3
"""Small Nav2 wrapper for this robot.

The stock Nav2 navigation launch routes controller output through
``cmd_vel_nav`` and then through ``velocity_smoother`` to ``cmd_vel``. A broad
global remap of both ``cmd_vel`` and ``cmd_vel_smoothed`` can collapse those
internal topics into the same external topic and create multiple publishers on
``/cmd_vel_auto``.

This wrapper keeps the internal Nav2 velocity chain explicit:
    controller_server -> /cmd_vel_nav -> velocity_smoother -> cmd_vel_out

Recovery behaviors also publish to ``cmd_vel_out`` so they still pass through
the local auto/manual mux and safety filter.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from launch_ros.substitutions import FindPackageShare
from nav2_common.launch import RewrittenYaml


def _nav2_launch(name: str) -> PathJoinSubstitution:
    return PathJoinSubstitution([FindPackageShare("nav2_bringup"), "launch", name])


def generate_launch_description() -> LaunchDescription:
    namespace = LaunchConfiguration("namespace")
    map_file = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")
    cmd_vel_out = LaunchConfiguration("cmd_vel_out")
    use_amcl = LaunchConfiguration("use_amcl")
    use_sim_time = LaunchConfiguration("use_sim_time")
    autostart = LaunchConfiguration("autostart")
    use_composition = LaunchConfiguration("use_composition")
    use_respawn = LaunchConfiguration("use_respawn")
    log_level = LaunchConfiguration("log_level")

    lifecycle_nodes = [
        "controller_server",
        "smoother_server",
        "planner_server",
        "behavior_server",
        "bt_navigator",
        "waypoint_follower",
        "velocity_smoother",
    ]

    remappings = [("/tf", "tf"), ("/tf_static", "tf_static")]
    configured_params = ParameterFile(
        RewrittenYaml(
            source_file=params_file,
            root_key=namespace,
            param_rewrites={"use_sim_time": use_sim_time, "autostart": autostart},
            convert_types=True,
        ),
        allow_substs=True,
    )

    return LaunchDescription(
        [
            SetEnvironmentVariable("RCUTILS_LOGGING_BUFFERED_STREAM", "1"),
            DeclareLaunchArgument("namespace", default_value=""),
            DeclareLaunchArgument("map", description="Saved occupancy map YAML"),
            DeclareLaunchArgument("params_file", default_value="/app/nav2_params.yaml"),
            DeclareLaunchArgument("cmd_vel_out", default_value="/cmd_vel_auto"),
            DeclareLaunchArgument("use_amcl", default_value="true"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("autostart", default_value="true"),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("use_respawn", default_value="False"),
            DeclareLaunchArgument("log_level", default_value="info"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(_nav2_launch("localization_launch.py")),
                condition=IfCondition(use_amcl),
                launch_arguments={
                    "namespace": namespace,
                    "map": map_file,
                    "params_file": params_file,
                    "use_sim_time": use_sim_time,
                    "autostart": autostart,
                    "use_composition": use_composition,
                    "use_respawn": use_respawn,
                    "log_level": log_level,
                }.items(),
            ),
            Node(
                package="nav2_controller",
                executable="controller_server",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings + [("cmd_vel", "cmd_vel_nav")],
            ),
            Node(
                package="nav2_smoother",
                executable="smoother_server",
                name="smoother_server",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings,
            ),
            Node(
                package="nav2_planner",
                executable="planner_server",
                name="planner_server",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings,
            ),
            Node(
                package="nav2_behaviors",
                executable="behavior_server",
                name="behavior_server",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings + [("cmd_vel", cmd_vel_out)],
            ),
            Node(
                package="nav2_bt_navigator",
                executable="bt_navigator",
                name="bt_navigator",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings,
            ),
            Node(
                package="nav2_waypoint_follower",
                executable="waypoint_follower",
                name="waypoint_follower",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings,
            ),
            Node(
                package="nav2_velocity_smoother",
                executable="velocity_smoother",
                name="velocity_smoother",
                output="screen",
                respawn=use_respawn,
                respawn_delay=2.0,
                parameters=[configured_params],
                arguments=["--ros-args", "--log-level", log_level],
                remappings=remappings + [("cmd_vel", "cmd_vel_nav"), ("cmd_vel_smoothed", cmd_vel_out)],
            ),
            Node(
                package="nav2_lifecycle_manager",
                executable="lifecycle_manager",
                name="lifecycle_manager_navigation",
                output="screen",
                arguments=["--ros-args", "--log-level", log_level],
                parameters=[
                    {"use_sim_time": use_sim_time},
                    {"autostart": autostart},
                    {"node_names": lifecycle_nodes},
                ],
            ),
        ]
    )
