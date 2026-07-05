import os

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    rf2o_log_level = os.environ.get("RF2O_LOG_LEVEL", "error")
    rf2o_scan_topic = os.environ.get(
        "RF2O_SCAN_TOPIC", "/scan_filtered"
    )

    return LaunchDescription(
        [
            Node(
                package="rf2o_laser_odometry",
                executable="rf2o_laser_odometry_node",
                name="rf2o_laser_odometry",
                output="screen",
                arguments=[
                    "--ros-args",
                    "--log-level",
                    f"rf2o_laser_odometry:={rf2o_log_level}",
                ],
                parameters=[
                    {
                        "laser_scan_topic": rf2o_scan_topic,
                        "odom_topic": "/odom_rf2o",
                        "publish_tf": False,
                        "base_frame_id": "base_link",
                        "odom_frame_id": "odom",
                        "init_pose_from_topic": "",
                        "freq": 20.0,
                    }
                ],
            )
        ]
    )
